#!/usr/bin/env python3
"""개인용 기술뉴스 자동집계 수집기.

feeds.json을 읽어 카테고리별 RSS 피드를 수집/정규화/필터링한 뒤
정적 페이지(index.html)가 읽을 data.json을 생성한다.

설계 원칙:
- 외부 의존성은 feedparser 하나뿐.
- 죽은 피드 하나가 전체 수집을 막지 않도록 피드 단위로 예외를 격리한다.
- 서버/DB 없음. GitHub Actions가 주기적으로 실행 → data.json 커밋.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser

CONFIG_PATH = "feeds.json"
OUTPUT_PATH = "data.json"


def log(msg: str) -> None:
    """진행 로그는 stderr로 (stdout은 깨끗하게 유지)."""
    print(msg, file=sys.stderr, flush=True)


def parse_date(entry) -> datetime | None:
    """entry에서 발행 시각을 UTC aware datetime으로 정규화한다.

    우선순위:
      1) feedparser가 파싱한 published_parsed / updated_parsed (이미 UTC struct_time)
      2) 원문 문자열 published / updated 를 email.utils로 파싱
         (tz 정보 없으면 UTC로 간주)
    실패하면 None.
    """
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass

    for key in ("published", "updated"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
            except (TypeError, ValueError, IndexError):
                dt = None
            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)

    return None


def clean_text(value: str) -> str:
    """HTML 엔티티 해제 + 공백 정리."""
    if not value:
        return ""
    return " ".join(unescape(value).split())


def dedup_key(link: str, title: str) -> str:
    """중복 판정 키: 링크에서 쿼리스트링(? 이후) 제거.

    링크가 없으면 제목 소문자.
    """
    if link:
        return link.split("?", 1)[0].strip().rstrip("/")
    return title.strip().lower()


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


def collect_feed(name: str, url: str) -> list[dict]:
    """단일 피드를 파싱해 entry 목록을 반환. 실패 시 예외를 올린다."""
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
        link = (entry.get("link") or "").strip()
        summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
        dt = parse_date(entry)
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


def build_category(cat: dict, max_age_days: int, max_items: int) -> dict:
    """카테고리 하나를 수집/필터/정렬/중복제거해 출력 형태로 만든다."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    include = cat.get("include_keywords", []) or []
    exclude = cat.get("exclude_keywords", []) or []

    seen: set[str] = set()
    collected: list[dict] = []

    for feed in cat.get("feeds", []):
        name = feed.get("name", feed.get("url", "?"))
        url = feed.get("url", "")
        try:
            entries = collect_feed(name, url)
        except Exception as exc:  # 죽은 피드 격리 — 전체 중단 금지
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
    far_past = datetime.min.replace(tzinfo=timezone.utc)
    collected.sort(key=lambda it: it["dt"] or far_past, reverse=True)

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

    categories_out: list[dict] = []
    total = 0
    for cat in config.get("categories", []):
        log(f"[CATEGORY] {cat.get('label', cat.get('key', '?'))}")
        result = build_category(cat, max_age_days, max_items)
        total += result["count"]
        categories_out.append(result)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories_out,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write("\n")

    log(f"[DONE] 총 {total}건 → {OUTPUT_PATH}")
    if total == 0:
        log("[WARN] 수집된 항목이 0건입니다. 피드 URL/필터를 확인하세요.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
