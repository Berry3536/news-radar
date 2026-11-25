#!/usr/bin/env python3
"""개인용 기술뉴스 자동집계 수집기.

feeds.json을 읽어 카테고리별 RSS 피드를 수집/정규화/필터링한 뒤
정적 페이지(index.html)가 읽을 data.json을 생성한다.

설계 원칙:
- 외부 의존성은 feedparser 하나뿐.
- 죽은 피드 하나가 전체 수집을 막지 않도록 피드 단위로 예외를 격리한다.
- 서버/DB 없음. GitHub Actions(update.yml)가 주기적으로 실행하고, master에서 돈 실행이 성공하면 워크플로가
  index.html + data.json + .nojekyll을 커밋 1개로 gh-pages에 force push한다(RULE1, RULE2).
- 수집 결과가 전체 0건이면 data.json을 쓰지 않고 1로 끝나 아무것도 배포하지 않는다(RULE16).
"""

from __future__ import annotations

import json
import re
import socket
import sys
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import feedparser

CONFIG_PATH = "feeds.json"
OUTPUT_PATH = "data.json"

# 기사를 식별하지 않고 유입 경로만 추적하는 쿼리 파라미터 (RULE7).
TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = frozenset({"fbclid", "gclid"})

# 항목 링크로 내보내는 스킴 (RULE11). 허용 목록이라 javascript:·vbscript:·data: 등 나머지는 모두 막힌다.
LINK_SCHEMES = frozenset({"http", "https"})

# feeds.json 피드 항목의 "tz": 고정 UTC 오프셋 "+09:00" / "-05:00".
# IANA 이름(Asia/Seoul)은 Windows에서 tzdata 패키지가 있어야 해 쓰지 않는다(런타임 의존성은 feedparser 하나).
TZ_OFFSET_RE = re.compile(r"([+-])([01]\d|2[0-3]):([0-5]\d)")


def log(msg: str) -> None:
    """진행 로그는 stderr로 (stdout은 깨끗하게 유지)."""
    print(msg, file=sys.stderr, flush=True)


def parse_tz(value: object) -> tzinfo:
    """feeds.json 피드 항목의 "tz" 값을 tzinfo로 바꾼다.

    "+09:00" 같은 ±HH:MM 고정 오프셋만 받는다. 키가 없으면(None) UTC.
    형식이 틀리면 ValueError — build_category가 그 피드만 [FAIL]로 건너뛴다.
    """
    if value is None:
        return UTC
    m = TZ_OFFSET_RE.fullmatch(value) if isinstance(value, str) else None
    if m is None:
        raise ValueError(f"잘못된 tz 값 {value!r} (형식: +09:00 같은 ±HH:MM 고정 오프셋)")
    sign = -1 if m.group(1) == "-" else 1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def lacks_tz(raw: object) -> bool:
    """원문 날짜 문자열에 시간대 표기가 없으면 True.

    feedparser는 시간대 없는 문자열("2026-11-21 11:51:51")을 UTC로 읽는데, struct_time만으로는
    "시간대 없음"과 "명시적 UTC"를 구별할 수 없어 원문을 본다.
    ISO 8601 또는 RFC 2822로 해석되고 시간대가 없어야 True. 해석할 수 없으면 False(feedparser 값을 그대로 쓴다).
    """
    if not isinstance(raw, str):
        return False
    raw = raw.strip()
    try:
        return datetime.fromisoformat(raw).tzinfo is None
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return False
    if dt.tzinfo is not None:
        return False
    # parsedate_to_datetime은 "-0000"과 모르는 시간대 이름("KST")도 naive로 돌려준다.
    # 마지막 토큰이 시간대 표기(부호·괄호로 시작하거나 글자를 포함)가 아닐 때만 시간대 없음으로 본다.
    last = raw.split()[-1]
    return not (last[0] in "+-(" or any(c.isalpha() for c in last))


def parse_date(entry, tz: tzinfo = UTC) -> datetime | None:
    """entry에서 발행 시각을 UTC aware datetime으로 정규화한다.

    우선순위:
      1) feedparser가 파싱한 published_parsed / updated_parsed (이미 UTC struct_time)
      2) 원문 문자열 published / updated 를 email.utils로 파싱
    원문 문자열에 시간대가 없으면(lacks_tz) 그 시각을 tz(피드의 "tz", 기본 UTC)의 시각으로 읽는다.
    feedparser는 시간대 없는 문자열을 UTC로 읽으므로 1)의 struct_time도 tz로 다시 해석한다.
    시간대가 적힌 문자열은 그대로 둔다(두 번 옮기지 않는다).
    실패하면 None.
    """
    for key in ("published", "updated"):
        st = entry.get(f"{key}_parsed")
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=UTC)
            except (TypeError, ValueError):
                continue
            if lacks_tz(entry.get(key)):
                dt = dt.replace(tzinfo=tz).astimezone(UTC)
            return dt

    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
            except (TypeError, ValueError, IndexError, OverflowError):
                dt = None
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz if lacks_tz(val) else UTC)
                return dt.astimezone(UTC)

    return None


def clean_text(value: str) -> str:
    """HTML 엔티티 해제 + 공백 정리."""
    if not value:
        return ""
    return " ".join(unescape(value).split())


def safe_link(link: str) -> str:
    """항목 링크가 http(s) 절대 URL이면 앞뒤 공백만 떼어 그대로, 아니면 빈 문자열 (RULE11).

    esc()는 HTML 특수문자만 바꾸므로 javascript: 같은 링크가 대시보드 href로 가면 막지 못한다.
    링크가 글자 그대로 "http://"·"https://"(대소문자 무시)로 시작해야 한다. 대시보드 isWebLink와 같은 판정이라,
    urlsplit이 지워 주는 스킴 안의 탭·앞쪽 제어 문자("ht\\ttps://", "\\x00https://")도 통과하지 못한다.
    호스트가 없거나 URL로 나눌 수 없는 링크도 버린다.
    상대 링크는 feedparser가 피드 URL(리다이렉트 뒤 최종 URL)이나 xml:base로 이미 절대 URL로 바꿔 준다.
    기준 URL 없이 상대로 남은 링크(피드 문서를 문자열로 넘긴 경우)는 버린다.
    """
    link = link.strip()
    scheme, sep, _ = link.partition("://")
    if not sep or scheme.lower() not in LINK_SCHEMES:
        return ""
    try:
        parts = urlsplit(link)
    except ValueError:  # 예: 닫히지 않은 IPv6 호스트
        return ""
    return link if parts.netloc else ""


def is_tracking_param(name: str) -> bool:
    """추적 파라미터(utm_*, fbclid, gclid)인지. 대소문자 무시."""
    lowered = name.lower()
    return lowered.startswith(TRACKING_PARAM_PREFIXES) or lowered in TRACKING_PARAMS


def dedup_key(link: str, title: str) -> str:
    """중복 판정 키 (RULE7).

    링크에서 추적 파라미터와 경로 끝 '/'를 뗀 값. 나머지 쿼리는 기사 식별자일 수 있어
    (예: articleView.html?idxno=NNN) 원래 순서·표기 그대로 남긴다.
    링크를 URL로 나눌 수 없으면 링크 문자열 그대로, 링크가 없으면 제목 소문자.
    """
    link = link.strip()
    if not link:
        return title.strip().lower()
    try:
        parts = urlsplit(link)
    except ValueError:  # 예: 닫히지 않은 IPv6 호스트. 키 계산이 수집을 멈추면 안 된다(RULE4)
        return link
    kept = [p for p in parts.query.split("&") if p and not is_tracking_param(p.split("=", 1)[0])]
    return urlunsplit(parts._replace(path=parts.path.rstrip("/"), query="&".join(kept)))


def passes_filters(text: str, include: list[str], exclude: list[str]) -> bool:
    """키워드 필터. text는 제목+요약(소문자 비교).

    - exclude 중 하나라도 걸리면 제외
    - include가 비면 전부 통과, 값이 있으면 하나라도 포함돼야 통과
    """
    lowered = text.lower()
    if exclude and any(kw.lower() in lowered for kw in exclude):
        return False
    if include and not any(kw.lower() in lowered for kw in include):
        return False
    return True


def collect_feed(name: str, url: str, tz: tzinfo = UTC) -> list[dict]:
    """단일 피드를 파싱해 entry 목록을 반환. 실패 시 예외를 올린다.

    tz는 시간대 없는 발행 시각을 읽을 피드의 시간대(parse_tz, parse_date 참고).
    네트워크 대기는 main이 건 소켓 기본 타임아웃에서 끊긴다: 응답 대기는 TimeoutError가 그대로 올라오고,
    연결·TLS 핸드셰이크는 feedparser가 bozo(entry 0개)로 돌려줘 아래 RuntimeError가 된다.
    """
    parsed = feedparser.parse(url)

    # bozo: 피드가 잘못됐거나 네트워크 오류일 때 1.
    # 다만 일부 멀쩡한 피드도 bozo=1로 오는 경우가 있어, entry가 하나라도
    # 있으면 진행하고 entry가 전혀 없을 때만 실패로 본다.
    if parsed.bozo and not parsed.entries:
        exc = parsed.get("bozo_exception")
        raise RuntimeError(f"bozo: {exc}")

    items: list[dict] = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title", ""))
        link = safe_link(entry.get("link") or "")  # 빈 링크면 중복 키는 제목 (RULE7)
        summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
        dt = parse_date(entry, tz)
        items.append(
            {
                "title": title,
                "link": link,
                "source": name,
                "summary": summary,
                "dt": dt,
            }
        )
    return items


def build_category(cat: dict, max_age_days: int, max_items: int, max_per_feed: int | None = None) -> dict:
    """카테고리 하나를 수집/필터/정렬/중복제거해 출력 형태로 만든다.

    max_per_feed가 있으면 최신순으로 피드(출처 이름)마다 그 건수까지만 남긴 뒤 카테고리 상한을 건다(RULE8).
    """
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    include = cat.get("include_keywords", []) or []
    exclude = cat.get("exclude_keywords", []) or []

    seen: set[str] = set()
    collected: list[dict] = []

    for feed in cat.get("feeds", []):
        name = feed.get("name", feed.get("url", "?"))
        url = feed.get("url", "")
        try:
            tz = parse_tz(feed.get("tz"))  # 잘못된 tz는 이 피드만 실패(요청 전에 걸러진다)
            entries = collect_feed(name, url, tz)
        except Exception as exc:  # 죽은 피드·잘못된 피드 설정 격리 — 전체 중단 금지
            log(f"  [FAIL] {cat['key']} / {name}: {exc}")
            continue
        log(f"  [OK]   {cat['key']} / {name}: {len(entries)} entries")

        for item in entries:
            # 1) 기간 필터 (날짜 None이면 유지)
            if item["dt"] is not None and item["dt"] < cutoff:
                continue
            # 2) 키워드 필터 (제목 + 요약)
            if not passes_filters(item["title"] + " " + item["summary"], include, exclude):
                continue
            # 3) 중복 제거
            key = dedup_key(item["link"], item["title"])
            if key in seen:
                continue
            seen.add(key)
            collected.append(item)

    # 최신순 정렬 (날짜 None은 맨 뒤)
    far_past = datetime.min.replace(tzinfo=UTC)
    collected.sort(key=lambda it: it["dt"] or far_past, reverse=True)

    # 피드별 상한: 글이 많은 피드 하나가 카테고리를 다 차지하지 않게 한다.
    # 기간·키워드·중복 제거 뒤라 버려진 항목은 칸을 쓰지 않는다.
    if max_per_feed is not None:
        per_feed: dict[str, int] = {}
        kept: list[dict] = []
        for it in collected:
            used = per_feed.get(it["source"], 0)
            if used < max_per_feed:
                per_feed[it["source"]] = used + 1
                kept.append(it)
        collected = kept

    # 카테고리당 상한
    collected = collected[:max_items]

    items_out = [
        {
            "title": it["title"],
            "link": it["link"],
            "source": it["source"],
            "published": it["dt"].isoformat() if it["dt"] else None,
        }
        for it in collected
    ]

    return {
        "key": cat["key"],
        "label": cat["label"],
        "count": len(items_out),
        "items": items_out,
    }


def main() -> int:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log(f"[ERROR] {CONFIG_PATH} 로드 실패: {exc}")
        return 1

    max_age_days = int(config.get("max_age_days", 14))
    max_items = int(config.get("max_items_per_category", 40))
    max_per_feed = int(config.get("max_items_per_feed", 8))
    # feedparser는 URL을 urllib으로 타임아웃 없이 열어, 새 소켓이 받는 기본 타임아웃이 곧 피드 요청 타임아웃이다.
    # 응답 없는 피드도 그 피드만 [FAIL]로 끝난다(RULE4, DEFECT4).
    feed_timeout = float(config.get("feed_timeout_seconds", 30))
    if feed_timeout <= 0:
        # 0은 "타임아웃 없음"이 아니라 non-blocking 소켓이라 모든 피드가 실패한다. 배포하지 않고 끝낸다.
        log(f"[ERROR] feed_timeout_seconds는 0보다 커야 합니다: {feed_timeout}")
        return 1
    socket.setdefaulttimeout(feed_timeout)

    categories_out: list[dict] = []
    total = 0
    for cat in config.get("categories", []):
        log(f"[CATEGORY] {cat.get('label', cat.get('key', '?'))}")
        result = build_category(cat, max_age_days, max_items, max_per_feed)
        total += result["count"]
        categories_out.append(result)

    if total == 0:
        # 피드가 모두 실패했거나 필터가 전부 걸렀다. 빈 data.json으로 직전 배포본을 덮지 않는다(RULE16):
        # 파일을 쓰지 않고 1로 끝내면 워크플로의 배포 단계가 돌지 않는다.
        log("[ERROR] 수집된 항목이 0건이라 data.json을 쓰지 않습니다(직전 배포본 유지). 피드 URL/필터를 확인하세요.")
        return 1

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "categories": categories_out,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"[DONE] 총 {total}건 → {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
