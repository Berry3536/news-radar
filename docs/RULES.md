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
| RULE2 | `gh-pages`에는 `update.yml` 워크플로만 push한다. 사람·Claude가 손으로 push하지 않는다 | 커밋 1개(`index.html`, `data.json`, `.nojekyll`), 성공한 실행마다 force push로 덮어씀(실패한 실행은 게시하지 않는다, RULE16) | `update.yml`(새 저장소 `git init` 후 `push --force`), `.claude/settings.json` deny `git push*gh-pages*`, `CLAUDE.md` Forbidden | 배포 브랜치는 매 실행 통째로 바뀐다. 손으로 넣은 커밋은 다음 실행에 사라지고, 그 사이에는 검증 안 된 배포본이 공개된다. 2026-10-12 |
| RULE3 | 수집 대상·필터·한도는 `feeds.json`에만 둔다. 코드에 피드 URL·키워드·한도 값을 넣지 않는다 | `max_age_days`, `max_items_per_category`, `feed_timeout_seconds`, `categories[]` | `aggregate.py` `main`(설정은 `feeds.json`에서만 읽음), CI·`kit.json` verify의 `feeds.json` 파싱 검사 | 정상 운영을 파일 하나 편집으로 끝내기 위해(README 약속). 코드 기본값 14·40·30은 `feeds.json`에 키가 없을 때만 쓴다 |
| RULE4 | 피드 하나의 실패는 그 피드만 건너뛰고 수집 전체를 멈추지 않는다. 응답하지 않는 피드는 타임아웃으로 끊어 실패로 본다. 실패는 `[FAIL]`, 성공은 `[OK]`로 로그에 남긴다 | 실패 = 예외(타임아웃 포함), 또는 `bozo`이면서 entry 0개. 피드 요청 타임아웃 = 30초(`feeds.json` `feed_timeout_seconds`): 연결, TLS 핸드셰이크, 소켓 읽기 한 번마다 걸린다. 응답 전체를 받는 시간과 DNS 조회에는 걸리지 않는다. 0 이하는 `[ERROR]`로 거부한다(종료 코드 1, 배포하지 않음). 수집 job 한도 = `timeout-minutes` 15(`update.yml`) | `aggregate.py` `main`(소켓 기본 타임아웃), `build_category`(피드 단위 `try/except`), `collect_feed`; `.github/workflows/update.yml` job `timeout-minutes`; `tests/test_aggregate.py::test_build_category_filters_dedups_sorts_and_caps`(죽은 피드 B), `test_collect_feed_times_out_on_silent_server`(http·https), `test_build_category_skips_a_feed_that_never_answers`, `test_main_applies_feed_timeout_seconds`, `test_main_defaults_feed_timeout_to_30_seconds`, `test_main_rejects_non_positive_feed_timeout` | 공개 RSS URL은 바뀌거나 죽는다. `bozo`만으로 실패 처리하지 않는 것은 멀쩡한 피드도 `bozo=1`로 오는 경우가 있어서다. 타임아웃: feedparser 6은 URL을 urllib으로 타임아웃 없이 열어, 연결만 받고 응답하지 않는 서버 하나가 수집 전체를 멈출 수 있었다(DEFECT4, GATE1-T4). feedparser에 타임아웃 인자가 없어 소켓 기본 타임아웃으로 건다(표준 라이브러리, RULE9). 30초는 정상 실행 전체보다 길다(2026-11-21~24 실행 8회, 17~27초). 조금씩 계속 보내는 서버나 DNS 조회 지연은 피드 타임아웃으로 끊기지 않아, job 한도 15분이 GitHub 기본 360분 대신 끊는다. 지금 피드 요청 15개가 각각 한 단계에서 한 번 끊기면 7.5분이다. 한 요청이 단계마다 한도 직전까지 버티거나 주소(IPv6·IPv4)마다 연결을 다시 시도하면 요청 하나가 30초를 넘을 수 있어, 실제 상한은 job 한도다. 0을 거부하는 것은 `socket.setdefaulttimeout(0)`이 "타임아웃 없음"이 아니라 non-blocking 소켓이라 모든 피드가 실패하기 때문이다. 한도에 걸린 실행은 배포 단계가 돌지 않아 직전 배포본이 남는다 |
| RULE5 | 키워드 필터는 제목+요약을 대소문자 무시로 본다. `exclude_keywords`에 하나라도 걸리면 제외(include보다 우선), `include_keywords`가 비면 전부 통과, 값이 있으면 하나 이상 포함돼야 통과 | — | `aggregate.py` `passes_filters`; `test_passes_filters`(6개 경우) | README 필터 규칙. 같은 피드를 여러 카테고리에 넣고 키워드로 가르는 운영 방식의 바탕 |
| RULE6 | 발행 시각은 UTC로 정규화하고, `max_age_days`보다 오래된 항목은 뺀다. 날짜를 알 수 없는 항목은 남기고 정렬 맨 뒤에 둔다 | `max_age_days` = 14(`feeds.json`). 시각 우선순위: `published_parsed` → `updated_parsed` → `published` → `updated` 문자열. 원문에 시간대가 없는 시각은 피드 항목의 `tz`(`feeds.json`, `±HH:MM` 고정 오프셋, 없으면 UTC)로 읽고, 시간대가 적힌 시각은 그대로 둔다. 형식이 틀린 `tz`는 그 피드만 실패(RULE4) | `aggregate.py` `parse_date`, `lacks_tz`, `parse_tz`, `collect_feed`, `build_category`; `test_parse_date_*`(14개), `test_parse_tz_*`(13개), `test_lacks_tz`(13개), `test_collect_feed_reads_naive_pubdate_in_feed_tz`, `test_build_category_skips_only_the_feed_with_invalid_tz`, `test_build_category_filters_dedups_sorts_and_caps` | 날짜 없는 피드 항목을 버리면 그런 소스가 통째로 사라진다(README "날짜 미상은 유지"). 14는 2026-06-01 첫 `feeds.json` 값. 피드별 `tz`: 국내 피드 3곳(모터그래프·로봇신문·AI타임스)이 `pubDate`를 시간대 없는 KST 시각(`2026-11-21 11:51:51`)으로 내보내, UTC로 읽으면 9시간 미래가 된다(DEFECT3, GATE1-T3). feedparser의 struct_time은 "시간대 없음"과 "명시적 UTC"를 구별하지 못해 원문 문자열을 본다. IANA 이름(`Asia/Seoul`)은 Windows에서 `tzdata` 패키지가 있어야 해 버렸다(RULE9). 한국은 일광절약시간이 없어 고정 오프셋으로 충분하다 |
| RULE7 | 중복 제거는 카테고리 안에서만 한다. 키는 링크에서 추적 파라미터와 경로 끝 `/`를 뗀 값(나머지 쿼리는 원래 순서·표기대로 남긴다), 링크가 없으면 제목 소문자. 먼저 수집된 항목이 남는다 | 추적 파라미터 = 이름이 `utm_`로 시작하거나 `fbclid`·`gclid`인 것(대소문자 무시) | `aggregate.py` `dedup_key`, `is_tracking_param`, `build_category`; `test_dedup_key_*`(4개), `test_build_category_filters_dedups_sorts_and_caps`, `test_build_category_keeps_articles_that_differ_only_in_query` | 추적 파라미터만 다른 같은 기사를 하나로. 쿼리 전체를 떼지 않는 것은 쿼리가 기사 식별자인 피드(`articleView.html?idxno=NNN`)가 있어서다(DEFECT2, GATE1-T2). 링크를 URL로 나눌 수 없으면 링크 문자열을 그대로 키로 쓴다(키 계산이 수집을 멈추지 않게, RULE4). 카테고리 사이 중복은 허용한다(같은 피드를 여러 카테고리에 넣는 방식) |
| RULE8 | 각 카테고리는 최신순으로 정렬해 상한까지만 내보낸다 | `max_items_per_category` = 40(`feeds.json`) | `aggregate.py` `build_category`; `test_build_category_filters_dedups_sorts_and_caps`(상한 1) | 40은 2026-06-01 첫 `feeds.json` 값. 값은 `feeds.json`에서 바꾼다(RULE3) |
| RULE9 | 수집기의 런타임 의존성은 `feedparser` 하나다 | — | `pyproject.toml` `dependencies` | `aggregate.py` 설계 원칙("외부 의존성은 feedparser 하나뿐")과 README, 2026-06-01. 예약 실행에서 깨질 곳을 줄인다 |
| RULE10 | 대시보드는 `index.html` 한 파일이며 외부 JS를 쓰지 않는다. 데이터는 같은 경로의 `data.json`을 fetch한다 | 외부 자원은 Google Fonts 스타일시트뿐 | `index.html`(인라인 `<script>`); 배포 단계가 이 파일 하나를 복사(`update.yml`) | 빌드 단계 없이 gh-pages에 파일 두 개만 올리면 된다. 갱신할 프런트 의존성이 없다. README, 2026-06-01 |
| RULE11 | `data.json`에서 온 문자열(제목·출처·링크·카테고리 이름)과 검색어는 HTML escape한 뒤 화면에 넣는다. 항목 링크는 `http`/`https` 링크만 게시하고 링크로 그린다: 수집기는 그 밖의 링크를 빈 문자열로 내보내고, 대시보드는 `http://`·`https://`로 시작하지 않는 링크를 `href`에 넣지 않고 제목을 글자로만 보인다 | 허용 스킴 = `http`, `https`(대소문자 무시, 앞뒤 공백은 뗀다). 링크가 글자 그대로 `http://`·`https://`로 시작해야 하고(수집기와 대시보드가 같은 판정), 수집기는 호스트가 있는 절대 URL만 남긴다. 그 밖(`javascript:`·`vbscript:`·`data:` 등 다른 스킴, 기준 URL 없이 남은 상대 링크, URL로 나눌 수 없는 링크)은 빈 링크 | `index.html` `esc()`(모든 `innerHTML` 조립 지점), `isWebLink`(`renderGrid`의 `href`); `aggregate.py` `safe_link`, `collect_feed`; `test_safe_link`(20개), `test_collect_feed_keeps_only_http_links`, `test_collect_feed_keeps_relative_links_that_feedparser_resolves`, `test_build_category_dedups_items_with_dropped_links_by_title` | 외부 피드 내용을 그대로 `innerHTML`에 넣으면 공개 페이지에 스크립트가 주입될 수 있다. escape는 HTML 특수문자만 바꾸므로 `javascript:` 같은 링크는 그대로 `href`가 됐다(DEFECT5, GATE1-T5). feedparser도 링크 스킴을 거르지 않는다. 악성·탈취된 피드뿐 아니라 `http://` 피드 3곳은 전송 구간 변조로도 링크가 바뀔 수 있다. 막을 스킴을 나열하지 않고 허용 목록으로 정해 모르는 스킴도 막는다. 수집기와 대시보드 두 곳에서 검사하는 것은 대시보드가 받은 `data.json`을 그대로 믿지 않게 하기 위해서다. 항목은 버리지 않고 링크만 비운다(제목은 보인다). 링크가 비면 중복 키는 제목이다(RULE7). 상대 링크는 feedparser가 피드 URL(리다이렉트 뒤 최종 URL)이나 `xml:base`로 절대 URL로 바꿔 주므로 정상 피드의 링크는 버려지지 않는다 |
| RULE12 | 공개 레포다. 비공개 정보(토큰, 개인 설정, 내부 문서)를 커밋하지 않는다 | 시크릿은 GitHub Secrets에만(`DEPENDABOT_MERGE_TOKEN`); `update.yml`은 `GITHUB_TOKEN`만 쓴다 | 사람 리뷰, `CLAUDE.md` 소개 문단 | 저장소와 배포본이 모두 공개된다. 공개 레포라 비공개 stark-kit의 재사용 워크플로도 부르지 않는다(`ci.yml` 단독) |
| RULE16 | 수집 결과가 전체 0건이면 아무것도 게시하지 않고 직전 배포본을 남긴다 | 0건 = 모든 카테고리의 `count` 합이 0(피드가 모두 실패했거나, 키워드 필터가 전부 걸렀거나, 카테고리가 없음). 이때 `[ERROR]`를 남기고 `data.json`을 쓰지 않으며 종료 코드 1 | `aggregate.py` `main`; `update.yml` "Publish to gh-pages" 단계(앞 단계가 성공해야 돈다); `test_main_publishes_nothing_when_zero_items`(3개 경우), `test_main_writes_data_json_when_any_item_is_collected` | 전에는 0건 `data.json`이 직전 배포본을 덮어, 피드가 한꺼번에 죽거나 설정을 잘못 바꾸면 다음 정상 실행까지 대시보드가 비었다(GATE0 실험 E1, GR0 결정 2026-11-10). 0건 배포본은 볼 것이 없어, 조금 오래된 직전 배포본이 낫다. 실행은 실패로 끝나 Actions run 기록과 "last sync" 시각으로 드러난다. 카테고리 하나만 0건인 경우는 그대로 게시한다(다른 카테고리는 볼 수 있으므로) |

## 안 하기로 한 것

| 규칙 | 하지 않는 것 | 근거 |
|---|---|---|
| RULE13 | RSS/Atom이 없는 소스는 수집하지 않는다(스크래핑 안 함) | 피드만 처리해 사이트 화면 구조가 바뀌어도 수집기가 깨지지 않게 한다. README 한계 절, 2026-06-01 |
| RULE14 | 정시 수집을 보장하지 않는다. 예약은 00·06·12·18시 UTC이지만 GitHub 예약 실행은 지연·누락될 수 있다 | GitHub Actions 예약 실행의 성질이며, 정확한 타이밍이 필요한 용도는 범위 밖(README 한계 절, 2026-06-01). 실측: 2026-10-21~11-03 예정 56회 중 48회 실행, 정시보다 수 시간 늦게 시작 |
| RULE15 | 서버·DB를 두지 않고 과거 수집 결과를 보관하지 않는다. 배포본은 성공한 실행마다 덮어쓴다 | 무료·서버리스 운영(README "백엔드/DB가 없으며", 2026-06-01). 이력 보관은 배포 브랜치를 커밋 1개로 유지하는 방식(RULE2)과 맞지 않는다 |

## 개정 이력

| 날짜 | 규칙 | 전 | 후 | 이유 | 출처 |
|---|---|---|---|---|---|
| 2026-11-04 | RULE1~RULE15 | — | 신설 | 새 문서 체계로 이행: `CLAUDE.md` Forbidden 두 줄(→ RULE1·RULE2), README 필터 규칙·한계 절과 `aggregate.py` 동작을 번호로 등록 | GR0 이전, 이행 기록 |
| 2026-11-21 | RULE7 | 키는 링크에서 쿼리스트링 전체와 끝 `/`를 뗀 값 | 키는 링크에서 추적 파라미터(`utm_*`, `fbclid`, `gclid`)와 경로 끝 `/`만 뗀 값, 나머지 쿼리는 남긴다 | 쿼리가 기사 식별자인 국내 피드 3곳이 매 실행 50건을 받고도 카테고리마다 1건만 남았다 | GATE1-T2, DEFECT2 |
| 2026-11-21 | RULE6 | 시간대 없는 문자열은 UTC | 시간대 없는 시각은 피드 항목의 `tz`(`±HH:MM` 고정 오프셋, 없으면 UTC)로 읽는다. 시간대가 적힌 시각은 그대로 | 국내 피드 3곳이 시간대 없는 KST 시각을 내보내 발행 시각이 9시간 미래로 기록됐다 | GATE1-T3, DEFECT3 |
| 2026-11-24 | RULE11 | 문자열과 검색어를 HTML escape한 뒤 화면에 넣는다(링크 스킴은 보지 않음) | 여기에 더해 항목 링크는 `http`/`https`만: 수집기는 그 밖의 링크를 빈 문자열로 내보내고, 대시보드는 `http(s)://`로 시작하는 링크만 `href`에 넣고 나머지는 제목을 글자로 보인다 | escape만으로는 피드가 준 `javascript:`·`vbscript:`·`data:` 링크가 그대로 `href`가 되어, 공개 페이지에 스크립트 URL이 들어갈 수 있었다 | GATE1-T5, DEFECT5 |
| 2026-11-24 | RULE4 | 피드 요청에 타임아웃이 없고, 수집 job 한도는 GitHub 기본 360분 | 피드 요청 타임아웃 30초(`feeds.json` `feed_timeout_seconds`, 넘으면 그 피드만 `[FAIL]`), 수집 job `timeout-minutes` 15 | 연결만 받고 응답하지 않는 피드 하나가 수집 전체를 멈추고, 그 실행은 360분 뒤 취소돼 배포하지 못한다 | GATE1-T4, DEFECT4 |
| 2026-11-24 | RULE3 | 값: `max_age_days`, `max_items_per_category`, `categories[]` | 값에 `feed_timeout_seconds`(키가 없으면 30) 추가 | 피드 요청 타임아웃(RULE4)도 한도라 `feeds.json`에 둔다 | GATE1-T4, DEFECT4 |
| 2026-11-25 | RULE16 | — | 신설: 전체 0건이면 `data.json`을 쓰지 않고 종료 코드 1, 배포 단계를 건너뛰어 직전 배포본 유지 | 0건 `data.json`이 직전 배포본을 덮어 대시보드가 비었다(GATE0 실험 E1) | GATE1-T6, GR0 결정 |
| 2026-11-25 | RULE2, RULE15 | 실행마다 덮어씀 | 성공한 실행마다 덮어씀 | RULE16으로 전체 0건인 실행도 게시하지 않아, "매 실행"이 실제 동작과 맞지 않았다(설정 오류 실행은 전부터 게시하지 않았다) | GATE1-T6 |
