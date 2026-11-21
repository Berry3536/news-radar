# 규칙

제품이 항상 지켜야 하는 것의 등록부. 번호는 제정 순이며 개정해도 바뀌지 않는다. 할 일은 [ROADMAP.md](ROADMAP.md)의 티켓,
설계 설명은 [DESIGN.md](DESIGN.md).

## 읽는 법

- `RULEn` 한 항목 = 문장 / 값(있으면) / 지키는 곳(파일·테스트) / 근거(왜 이 값인지, 버린 대안, 정한 GR 또는 날짜).
- 새 결정은 ROADMAP의 GR 기록 "다음 게이트를 위한 결정" 칸에 먼저 적고, 코드가 지켜야 할 것이 되면 여기서 다음 번호를 받는다.
- 아직 지켜지지 않는 규칙은 ROADMAP 티켓이 `⚠ GATEn-Tk`로 가리킨다. 규칙을 바꾸면 개정 이력에 전·후·이유를 남긴다.
- 안 하기로 한 것도 규칙이다(범위 밖 선언). 번호를 받고 근거를 적는다.
- 문장과 지키는 곳은 `CLAUDE.md`의 `## Rules` 표(영어)에도 같은 번호로 있다.

## 규칙

| 규칙 | 문장 | 값 | 지키는 곳 | 근거 |
|---|---|---|---|---|
| RULE1 | 수집 결과 `data.json`은 `gh-pages` 브랜치에만 게시한다. `master`/`develop`에는 커밋하지 않는다 | — | `.gitignore`(`data.json`), `.github/workflows/update.yml` "Publish to gh-pages" 단계, `CLAUDE.md` Forbidden | gitflow에서 master는 release/hotfix 머지만 받는다. 예약 실행마다 봇 커밋이 쌓이면 이력이 묻힌다. 2026-10-12 `10e3604`에서 master 커밋 방식(`chore: update data.json [skip ci]`)을 버렸다 |
| RULE2 | `gh-pages`에는 `update.yml` 워크플로만 push한다. 사람·Claude가 손으로 push하지 않는다 | 커밋 1개(`index.html`, `data.json`, `.nojekyll`), 실행마다 force push로 덮어씀 | `update.yml`(새 저장소 `git init` 후 `push --force`), `.claude/settings.json` deny `git push*gh-pages*`, `CLAUDE.md` Forbidden | 배포 브랜치는 매 실행 통째로 바뀐다. 손으로 넣은 커밋은 다음 실행에 사라지고, 그 사이에는 검증 안 된 배포본이 공개된다. 2026-10-12 |
| RULE3 | 수집 대상·필터·한도는 `feeds.json`에만 둔다. 코드에 피드 URL·키워드·한도 값을 넣지 않는다 | `max_age_days`, `max_items_per_category`, `categories[]` | `aggregate.py` `main`(설정은 `feeds.json`에서만 읽음), CI·`kit.json` verify의 `feeds.json` 파싱 검사 | 정상 운영을 파일 하나 편집으로 끝내기 위해(README 약속). 코드 기본값 14·40은 `feeds.json`에 키가 없을 때만 쓴다 |
| RULE4 | 피드 하나의 실패는 그 피드만 건너뛰고 수집 전체를 멈추지 않는다. 실패는 `[FAIL]`, 성공은 `[OK]`로 로그에 남긴다 | 실패 = 예외, 또는 `bozo`이면서 entry 0개 | `aggregate.py` `build_category`(피드 단위 `try/except`), `collect_feed`; `tests/test_aggregate.py::test_build_category_filters_dedups_sorts_and_caps`(죽은 피드 B) | 공개 RSS URL은 바뀌거나 죽는다. `bozo`만으로 실패 처리하지 않는 것은 멀쩡한 피드도 `bozo=1`로 오는 경우가 있어서다 |
| RULE5 | 키워드 필터는 제목+요약을 대소문자 무시로 본다. `exclude_keywords`에 하나라도 걸리면 제외(include보다 우선), `include_keywords`가 비면 전부 통과, 값이 있으면 하나 이상 포함돼야 통과 | — | `aggregate.py` `passes_filters`; `test_passes_filters`(6개 경우) | README 필터 규칙. 같은 피드를 여러 카테고리에 넣고 키워드로 가르는 운영 방식의 바탕 |
| RULE6 | 발행 시각은 UTC로 정규화하고, `max_age_days`보다 오래된 항목은 뺀다. 날짜를 알 수 없는 항목은 남기고 정렬 맨 뒤에 둔다 | `max_age_days` = 14(`feeds.json`). 시각 우선순위: `published_parsed` → `updated_parsed` → `published` → `updated` 문자열. 원문에 시간대가 없는 시각은 피드 항목의 `tz`(`feeds.json`, `±HH:MM` 고정 오프셋, 없으면 UTC)로 읽고, 시간대가 적힌 시각은 그대로 둔다. 형식이 틀린 `tz`는 그 피드만 실패(RULE4) | `aggregate.py` `parse_date`, `lacks_tz`, `parse_tz`, `collect_feed`, `build_category`; `test_parse_date_*`(14개), `test_parse_tz_*`(13개), `test_lacks_tz`(13개), `test_collect_feed_reads_naive_pubdate_in_feed_tz`, `test_build_category_skips_only_the_feed_with_invalid_tz`, `test_build_category_filters_dedups_sorts_and_caps` | 날짜 없는 피드 항목을 버리면 그런 소스가 통째로 사라진다(README "날짜 미상은 유지"). 14는 2026-06-01 첫 `feeds.json` 값. 피드별 `tz`: 국내 피드 3곳(모터그래프·로봇신문·AI타임스)이 `pubDate`를 시간대 없는 KST 시각(`2026-11-21 11:51:51`)으로 내보내, UTC로 읽으면 9시간 미래가 된다(DEFECT3, GATE1-T3). feedparser의 struct_time은 "시간대 없음"과 "명시적 UTC"를 구별하지 못해 원문 문자열을 본다. IANA 이름(`Asia/Seoul`)은 Windows에서 `tzdata` 패키지가 있어야 해 버렸다(RULE9). 한국은 일광절약시간이 없어 고정 오프셋으로 충분하다 |
| RULE7 | 중복 제거는 카테고리 안에서만 한다. 키는 링크에서 추적 파라미터와 경로 끝 `/`를 뗀 값(나머지 쿼리는 원래 순서·표기대로 남긴다), 링크가 없으면 제목 소문자. 먼저 수집된 항목이 남는다 | 추적 파라미터 = 이름이 `utm_`로 시작하거나 `fbclid`·`gclid`인 것(대소문자 무시) | `aggregate.py` `dedup_key`, `is_tracking_param`, `build_category`; `test_dedup_key_*`(4개), `test_build_category_filters_dedups_sorts_and_caps`, `test_build_category_keeps_articles_that_differ_only_in_query` | 추적 파라미터만 다른 같은 기사를 하나로. 쿼리 전체를 떼지 않는 것은 쿼리가 기사 식별자인 피드(`articleView.html?idxno=NNN`)가 있어서다(DEFECT2, GATE1-T2). 링크를 URL로 나눌 수 없으면 링크 문자열을 그대로 키로 쓴다(키 계산이 수집을 멈추지 않게, RULE4). 카테고리 사이 중복은 허용한다(같은 피드를 여러 카테고리에 넣는 방식) |
| RULE8 | 각 카테고리는 최신순으로 정렬해 상한까지만 내보낸다 | `max_items_per_category` = 40(`feeds.json`) | `aggregate.py` `build_category`; `test_build_category_filters_dedups_sorts_and_caps`(상한 1) | 40은 2026-06-01 첫 `feeds.json` 값. 값은 `feeds.json`에서 바꾼다(RULE3) |
| RULE9 | 수집기의 런타임 의존성은 `feedparser` 하나다 | — | `pyproject.toml` `dependencies` | `aggregate.py` 설계 원칙("외부 의존성은 feedparser 하나뿐")과 README, 2026-06-01. 예약 실행에서 깨질 곳을 줄인다 |
| RULE10 | 대시보드는 `index.html` 한 파일이며 외부 JS를 쓰지 않는다. 데이터는 같은 경로의 `data.json`을 fetch한다 | 외부 자원은 Google Fonts 스타일시트뿐 | `index.html`(인라인 `<script>`); 배포 단계가 이 파일 하나를 복사(`update.yml`) | 빌드 단계 없이 gh-pages에 파일 두 개만 올리면 된다. 갱신할 프런트 의존성이 없다. README, 2026-06-01 |
| RULE11 | `data.json`에서 온 문자열(제목·출처·링크·카테고리 이름)과 검색어는 HTML escape한 뒤 화면에 넣는다 | — | `index.html` `esc()`(모든 `innerHTML` 조립 지점) | 외부 피드 내용을 그대로 `innerHTML`에 넣으면 공개 페이지에 스크립트가 주입될 수 있다 |
| RULE12 | 공개 레포다. 비공개 정보(토큰, 개인 설정, 내부 문서)를 커밋하지 않는다 | 시크릿은 GitHub Secrets에만(`DEPENDABOT_MERGE_TOKEN`); `update.yml`은 `GITHUB_TOKEN`만 쓴다 | 사람 리뷰, `CLAUDE.md` 소개 문단 | 저장소와 배포본이 모두 공개된다. 공개 레포라 비공개 stark-kit의 재사용 워크플로도 부르지 않는다(`ci.yml` 단독) |

## 안 하기로 한 것

| 규칙 | 하지 않는 것 | 근거 |
|---|---|---|
| RULE13 | RSS/Atom이 없는 소스는 수집하지 않는다(스크래핑 안 함) | 피드만 처리해 사이트 화면 구조가 바뀌어도 수집기가 깨지지 않게 한다. README 한계 절, 2026-06-01 |
| RULE14 | 정시 수집을 보장하지 않는다. 예약은 00·06·12·18시 UTC이지만 GitHub 예약 실행은 지연·누락될 수 있다 | GitHub Actions 예약 실행의 성질이며, 정확한 타이밍이 필요한 용도는 범위 밖(README 한계 절, 2026-06-01). 실측: 2026-10-21~11-03 예정 56회 중 48회 실행, 정시보다 수 시간 늦게 시작 |
| RULE15 | 서버·DB를 두지 않고 과거 수집 결과를 보관하지 않는다. 배포본은 매 실행 덮어쓴다 | 무료·서버리스 운영(README "백엔드/DB가 없으며", 2026-06-01). 이력 보관은 배포 브랜치를 커밋 1개로 유지하는 방식(RULE2)과 맞지 않는다 |

## 개정 이력

| 날짜 | 규칙 | 전 | 후 | 이유 | 출처 |
|---|---|---|---|---|---|
| 2026-11-04 | RULE1~RULE15 | — | 신설 | 새 문서 체계로 이행: `CLAUDE.md` Forbidden 두 줄(→ RULE1·RULE2), README 필터 규칙·한계 절과 `aggregate.py` 동작을 번호로 등록 | GR0 이전, 이행 기록 |
| 2026-11-21 | RULE7 | 키는 링크에서 쿼리스트링 전체와 끝 `/`를 뗀 값 | 키는 링크에서 추적 파라미터(`utm_*`, `fbclid`, `gclid`)와 경로 끝 `/`만 뗀 값, 나머지 쿼리는 남긴다 | 쿼리가 기사 식별자인 국내 피드 3곳이 매 실행 50건을 받고도 카테고리마다 1건만 남았다 | GATE1-T2, DEFECT2 |
| 2026-11-21 | RULE6 | 시간대 없는 문자열은 UTC | 시간대 없는 시각은 피드 항목의 `tz`(`±HH:MM` 고정 오프셋, 없으면 UTC)로 읽는다. 시간대가 적힌 시각은 그대로 | 국내 피드 3곳이 시간대 없는 KST 시각을 내보내 발행 시각이 9시간 미래로 기록됐다 | GATE1-T3, DEFECT3 |
