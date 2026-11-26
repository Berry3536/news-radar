# 설계

## 목적과 범위

**테크 노트**(Tech Note, 저장소 `news-radar`)는 AI · 반도체 · 자동차(전기차·자율주행·내연기관·국제 규제) · 배터리 · 로봇 분야의 RSS를
**GitHub Actions가 주기적으로 수집**해 **GitHub Pages**가 정적 페이지로 보여 주는 **무료 · 서버리스** 개인용 대시보드
(https://berry3536.github.io/news-radar/). 백엔드/DB가 없으며, 운영은 `feeds.json` 한 파일만 고치면 된다(RULE3).

범위 밖: RSS/Atom이 없는 소스(RULE13), 정시 수집 보장(RULE14), 서버·DB·과거 수집 이력(RULE15).

## 구조

평면 구조(`.claude/kit.json` `layout: "script"`): 수집기는 모듈 하나(`aggregate.py`), 대시보드는 파일 하나(`index.html`)라
레이어·import-linter 계약이 없다.

| 파일 | 맡는 것 |
|---|---|
| `feeds.json` | 카테고리·피드·키워드 필터·한도 설정. 정상 운영에서 고치는 유일한 파일(RULE3) |
| `aggregate.py` | 수집기(Python 3.13, `feedparser`, RULE9). 피드 단위 실패 격리, `[OK]`/`[FAIL]` 로그(RULE4) |
| `index.html` | 단일 파일 대시보드(인라인 CSS·JS, 외부 JS·글꼴 없음, RULE10). 화면은 아래 "화면" |
| `data.json` | 수집 결과. 로컬에서 생성되고 git이 추적하지 않는다. 배포본은 `gh-pages` 브랜치에만(RULE1) |
| `pyproject.toml` / `uv.lock` / `.python-version` | 의존성(`feedparser`, 개발용 pytest·ruff), uv로 잠금, Python 3.13 |
| `tests/test_aggregate.py` | `aggregate.py` 단위 테스트(외부 네트워크 없음. 피드 타임아웃은 127.0.0.1의 응답 없는 가짜 서버로) |
| `.github/workflows/update.yml` | 예약 수집 → `gh-pages` 배포(RULE2) |
| `.github/workflows/ci.yml` | ruff · `py_compile` · pytest · `feeds.json` 형식 검사(`aggregate.py --check`, RULE17). 공개 레포라 단독 CI(RULE12) |
| `.github/workflows/dependabot-merge.yml` | Dependabot patch/minor PR 자동 머지(stark-kit 생성물) |
| `README.md` | 사람용 소개와 빠른 시작 |

**화면**(`index.html`). 위에서부터 머리표(`TECH NOTE · RSS DIGEST`), 제목 "테크 노트", 가는 회색 선, 부제, 분야 칩("전체"와
카테고리마다 건수)과 검색 칸(제목·출처). 그 오른쪽(좁은 화면에서는 부제 아래)의 짙은 칸 하나에 "LAST SYNC"(`generated_at`을
UTC로, DEFECT1)와 전체 건수. 본문은 카테고리마다 열 하나로, 머리에 `data.json` 순서의 번호(01~)·이름·보이는 건수, 항목마다
제목(`http(s)` 링크만 링크로, RULE11)·출처·상대 시각(마우스를 올리면 브라우저 시간대의 발행 시각). 칩 하나를 고르면 그 열이
화면 폭을 쓰고 항목이 여러 열로 놓인다. 불러오는 중·전체 0건·검색 결과 없음은 회색 안내 칸, 불러오기 실패는 검은 테두리 안내 칸.

디자인 언어: 흰 바탕, 글자 `#1A1A1A`·`#2B2B2B`, 보조 글자 `#6B6B6B`·`#767676`(흰 바탕 대비 4.5:1 이상), 선 `#D6D6D6`·`#EBEBEB`,
반경 4px. 색은 포인트색 `#D98A1E` 하나로, 6시간 안의 기사 표시(굵은 시각 앞 작은 네모)에만 쓴다. 짙은 바탕(`#1A1A1A`)은 수집 상태
칸과 선택된 칩뿐. 글꼴은 시스템 한글 글꼴(맑은 고딕 등), 숫자와 영문 머리표는 Arial. 넓은 화면에서 세 열, 좁아지면 두 열·한 열이 된다.

## 데이터와 흐름

```
┌─────────────────────┐   cron (00/06/12/18 UTC)   ┌──────────────────┐
│  GitHub Actions      │ ─────────────────────────▶ │  aggregate.py     │
│  (.github/workflows) │                            │  feedparser로 수집 │
└─────────────────────┘                            └────────┬─────────┘
            ▲                                                │ 생성
            │ gh-pages 브랜치로 force push                      ▼
            │                                          ┌──────────────┐
            └──────────────────────────────────────── │  data.json    │
                                                       └──────┬───────┘
                                                              │ fetch
                  ┌────────────────────────────┐              ▼
   브라우저 ◀───── │  GitHub Pages (index.html)   │ ◀───── data.json 서빙
                  └────────────────────────────┘
```

1. `update.yml`이 체크아웃하고(예약 실행은 기본 브랜치 `master`, 수동 실행은 고른 ref) `uv sync --locked` 후 `aggregate.py`를
   실행한다.
2. `aggregate.py`가 `feeds.json` 형식을 검사하고(RULE17, 틀린 곳이 있으면 수집하지 않고 종료 코드 1) 카테고리마다 피드를 읽어,
   항목마다 기간(RULE6) → 키워드(RULE5) → 중복(RULE7) 순으로 거른 뒤 최신순 정렬, 피드별 상한, 카테고리 상한(RULE8)을 적용해
   `data.json`을 쓴다.
3. 워크플로가 `index.html` + `data.json` + `.nojekyll`을 새 저장소의 커밋 1개로 만들어 `gh-pages`에 force push한다(RULE2).
   이 배포 단계는 `master`에서 돈 실행만 하고(`if: github.ref == 'refs/heads/master'`), 앞 단계가 실패하면 돌지 않는다(RULE16).
   다른 ref로 수동 실행하면 수집만 하고 배포하지 않는다. `master`/`develop`에는 봇 커밋이 남지 않는다(RULE1).
4. GitHub Pages가 `gh-pages` `/`(root)를 서빙하고, 브라우저의 `index.html`이 `data.json`을 캐시 없이 fetch해 그린다.

`feeds.json` 형식:

| 키 | 뜻 | 형식 | 없을 때 |
|---|---|---|---|
| `max_age_days` | 이보다 오래된 항목 제외, 날짜 미상은 유지(RULE6) | 0보다 큰 정수 | 14 |
| `max_items_per_category` | 카테고리당 최대 노출 수(RULE8) | 0보다 큰 정수 | 40 |
| `max_items_per_feed` | 한 카테고리 안에서 피드(출처 이름) 하나가 차지할 수 있는 최대 건수. 카테고리 상한보다 먼저 건다(RULE8) | 0보다 큰 정수 | 8 |
| `feed_timeout_seconds` | 피드 요청 타임아웃(초). 연결, TLS 핸드셰이크, 소켓 읽기 한 번마다 걸리고(응답 전체 시간·DNS 조회는 아님), 넘으면 그 피드만 실패(RULE4) | 0보다 큰 정수 | 30 |
| `categories` | 카테고리 목록. 비어 있으면 전체 0건이라 배포하지 않는다(RULE16) | 목록 | 필수 |
| `categories[].key` / `label` | 내부 식별자 / 화면 표시명 | 비어 있지 않은 문자열. `key`는 카테고리끼리 달라야 한다 | 필수 |
| `categories[].include_keywords` / `exclude_keywords` | 키워드 필터(RULE5) | 비어 있지 않은 문자열의 목록(문자열 하나는 안 된다) | 빈 목록 |
| `categories[].feeds[]` | `{ "name", "url", "tz" }`. 카테고리마다 주제 피드를 넣고, 주제가 섞인 피드는 키워드로 거른다 | 목록(비어도 된다) | 필수 |
| `categories[].feeds[].name` / `url` | 화면의 출처 이름이자 피드별 상한을 세는 단위(RULE8, 같은 이름이면 상한을 같이 센다) / 피드 주소 | 비어 있지 않은 문자열 / 앞뒤 공백 없이 `http://`·`https://`로 시작하고 호스트가 있는 URL | 필수 |
| `categories[].feeds[].tz` | 원문에 시간대가 없는 발행 시각을 읽을 고정 UTC 오프셋(예: `"+09:00"`). 시간대가 적힌 시각에는 쓰지 않는다(RULE6). 같은 피드를 여러 카테고리에 넣으면 항목마다 적는다 | `±HH:MM` | UTC |

`aggregate.py`는 수집 전에 이 표대로 검사한다(RULE17): 표에 없는 키(오타 `include_keyword` 등)는 오류, 키에 적은 `null`은
값으로 보고 검사한다(기본값을 쓰려면 키를 뺀다), `true`·소수·숫자로 읽히는 문자열(`"14"`)은 정수가 아니다. 한 객체 안에 같은 키가
두 번 있으면 읽기 실패다. 검사만 하려면 `uv run python aggregate.py --check`(네트워크 없음, CI도 같은 명령).

`data.json` 형식(수집기 → 대시보드 경계): `generated_at`(UTC ISO 8601), `categories[]` = `{ key, label, count, items[] }`,
`items[]` = `{ title, link, source, published }`(`link`는 `http`/`https` 절대 URL 또는 빈 문자열(RULE11), `published`는 UTC ISO 8601
또는 `null`). 요약은 필터에만 쓰고 내보내지 않는다. 대시보드는 `link`가 `http://`·`https://`로 시작할 때만 제목을 링크로 그린다.

외부 경계: 피드 사이트(HTTP, 실패는 피드 단위로 격리), GitHub Actions(예약 실행, `GITHUB_TOKEN`으로 `gh-pages` push),
GitHub Pages(정적 서빙). 대시보드는 `data.json` 말고 외부에 요청하지 않는다(RULE10).

## 오류 모델

| 오류 | 처리 | 보이는 곳 |
|---|---|---|
| `feeds.json` 읽기·파싱 실패(파일 없음, JSON 문법 오류, UTF-8이 아님, 한 객체 안에 같은 키가 두 번) | `[ERROR] feeds.json 로드 실패: <원인>` 후 종료 코드 1 → 워크플로 실패, 배포 단계를 건너뛰어 직전 배포본이 남는다. CI가 같은 검사(`aggregate.py --check`)를 미리 돌린다 | CI 실패, Actions run 실패 |
| `feeds.json` 형식 오류(RULE17): 필수 키 누락(`categories`, 카테고리 `key`·`label`·`feeds`, 피드 `name`·`url`), 표에 없는 키(오타 `include_keyword`), 목록이 아닌 `categories`·`feeds`, 목록 대신 문자열로 쓴 `include_keywords`·`exclude_keywords`(`"robot"`), 문자열이 아니거나 빈 키워드, 0보다 큰 정수가 아닌 한도(`max_age_days: "two weeks"`, `null`, 숫자로 읽히는 문자열 `"14"`, 소수, `true`, `max_age_days` 0 이하, `max_items_per_category` 0·음수, `max_items_per_feed` 0 이하, `feed_timeout_seconds` 0 이하), 빈 `key`·`label`·`name`, 카테고리 `key` 중복, `http`/`https`가 아니거나 호스트가 없는 피드 `url`(빈 `url` 포함), `±HH:MM`이 아닌 피드 `tz`(`"KST"`, `"+9"`) | 수집 전에 파일 전체를 검사해 문제마다 `[ERROR] <위치>: <문제>` 한 줄(위치 예 `categories[3](battery).feeds[1](디일렉).tz`, 번호는 0부터), 끝에 `[ERROR] feeds.json 형식 오류 N건: ...`을 남기고, 네트워크 요청 없이 종료 코드 1 → 배포 단계를 건너뛰어 직전 배포본이 남는다. 피드 하나의 `tz` 오류도 실행 전체를 멈춘다(RULE6). CI가 같은 검사를 네트워크 없이 돌려(`aggregate.py --check`) 릴리스 전에 잡는다 | CI 실패, Actions run 실패, run 로그 `[ERROR] <위치>: <문제>` |
| 피드 하나 실패(예외, 또는 `bozo`이면서 entry 0개) | 그 피드만 건너뛰고 계속(RULE4) | run 로그 `[FAIL] <카테고리> / <피드>: <원인>` |
| 피드가 응답하지 않음(연결·핸드셰이크·읽기 대기가 `feed_timeout_seconds`를 넘음) | 그 요청을 끊고 그 피드만 건너뛰고 계속(RULE4) | run 로그 `[FAIL] <카테고리> / <피드>: ... timed out`(응답 대기: http 피드는 `timed out`, https 피드는 `The read operation timed out`. 연결·TLS 단계에서 끊기면 `bozo: <urlopen error ... timed out>`) |
| 수집 job이 `timeout-minutes`(15분)를 넘음(피드 타임아웃이 끊지 못하는 멈춤) | GitHub가 job을 취소한다. 배포 단계가 돌지 않아 직전 배포본이 남는다 | Actions run 취소 |
| 수집 결과가 전체 0건(피드가 모두 실패, 필터가 전부 걸러냄, 카테고리 없음) | `[ERROR]` 후 `data.json`을 쓰지 않고 종료 코드 1 → 배포 단계를 건너뛰어 직전 배포본이 남는다(RULE16). 카테고리 하나만 0건이면 그대로 게시 | Actions run 실패, run 로그 `[ERROR] 수집된 항목이 0건...`. 대시보드는 직전 배포본("last sync"가 멈춤) |
| 항목의 날짜를 해석할 수 없음(피드 `tz`로 옮기면 날짜 범위를 넘는 시각 포함) | 그 항목만 날짜 미상으로 유지, 정렬 맨 뒤(RULE6). 피드는 계속(RULE4) | 대시보드 "날짜 미상" |
| 항목 링크가 `http`/`https` 절대 URL이 아님(`javascript:` 같은 다른 스킴, 기준 URL 없이 남은 상대 링크, URL로 나눌 수 없음) | 항목은 남기고 링크만 빈 문자열로 내보낸다. 중복 키는 제목(RULE7). 대시보드도 `http(s)://`로 시작하지 않는 링크는 `href`에 넣지 않는다(RULE11) | 대시보드에서 그 항목 제목이 링크 없는 글자로 보인다. 로그에는 남지 않는다 |
| 대시보드가 `data.json`을 못 받음 | 오류 안내(HTTP 상태 포함) | 대시보드 검은 테두리 안내 칸 |

수집은 피드 단위로 fail-open(RULE4), 설정 오류(읽기·파싱 실패, 형식 오류, RULE17)와 전체 0건은 배포 쪽으로 fail-closed(직전
배포본 유지, RULE16)다. 형식 검사는 형식과 값의 범위만 본다: 형식이 맞는 URL이 죽었거나 RSS가 아니면 수집 때 그 피드만
`[FAIL]`(RULE4)이고, 아무 항목도 고르지 못하는 키워드는 경고 없이 쓰인다.

## 알려진 한계

- 원문 시각에 시간대가 있는지는 ISO 8601과 RFC 2822 형식으로만 판정한다(`aggregate.lacks_tz`). 그 밖의 형식(예: 연도가
  맨 뒤인 asctime, 시간대 이름이 가운데 있는 문자열)은 피드의 `tz`가 잘못 적용되거나 적용되지 않을 수 있다. 지금 `tz`를 쓰는
  피드 8개(7개 사이트, 2026-11-25 확인)의 형식(`2026-11-21 11:51:51`)은 정확히 처리된다.
- 같은 기사가 한 카테고리의 두 피드에 있으면 먼저 나열된 피드의 사본이 남고(RULE7), 그 사본이 피드별 상한(RULE8)에
  잘리면 다른 피드의 사본도 남지 않는다(다른 피드에 칸이 있어도). 지금 `feeds.json`은 카테고리 안 피드의 사이트가 모두 달라
  일어나지 않는다(GR1 검토, 2026-11-25).
- 피드 타임아웃은 연결·TLS 핸드셰이크·소켓 읽기 한 번마다 걸린다. 조금씩 계속 보내는 서버나 DNS 조회 지연은 job 한도
  15분까지 수집을 붙잡을 수 있고, 그 실행은 배포하지 않는다(RULE4).
- 예약 실행은 정시에 돌지 않는다. 실측으로 수 시간 늦게 시작하고 하루 2~4회 실행된다(RULE14, ROADMAP GATE0 관찰).
- 공개 레포에서 60일간 저장소 활동이 없으면 GitHub가 예약 워크플로를 끈다. 확인·재활성은 [RUNBOOK.md](RUNBOOK.md) 운영.
- 예약 실행은 기본 브랜치 `master`의 파일을 쓴다. `feeds.json` 변경은 릴리스로 `master`에 들어간 뒤부터 반영된다.
- 피드 URL은 바뀌거나 죽을 수 있다. 실패는 `[FAIL]`로 보이지만, 정상 응답에 entry가 0개인 피드는 `[OK] 0 entries`로
  남아 구별되지 않는다(ROADMAP GATE0 관찰).
- 한도 값에는 상한이 없다(RULE17은 0보다 큰 정수만 본다). 날짜·소켓이 다룰 수 없을 만큼 큰 값(예: `max_age_days` 1000000)은
  형식 검사를 통과한 뒤 수집 전에 `[ERROR]` 없이 traceback(`OverflowError`)으로 끝난다(종료 코드 1, 배포하지 않음).
- 전체 0건이면 직전 배포본이 그대로 남아(RULE16), 대시보드만 봐서는 수집이 멈춘 것을 알기 어렵다. "last sync" 시각과
  Actions run 실패로 본다.
- 대시보드 검색은 제목과 출처만 본다(요약은 `data.json`에 없다).
- RSS/Atom만 수집한다(RULE13). 과거 수집 결과는 남지 않는다(RULE15).
