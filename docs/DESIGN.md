# 설계

## 목적과 범위

AI · 반도체 · 자동차(전기차·자율주행·내연기관·국제 규제) · 배터리 · 로봇 분야의 RSS를 **GitHub Actions가 주기적으로 수집**해 **GitHub Pages**가 정적 페이지로
보여 주는 **무료 · 서버리스** 개인용 대시보드(https://berry3536.github.io/news-radar/). 백엔드/DB가 없으며, 운영은
`feeds.json` 한 파일만 고치면 된다(RULE3).

범위 밖: RSS/Atom이 없는 소스(RULE13), 정시 수집 보장(RULE14), 서버·DB·과거 수집 이력(RULE15).

## 구조

평면 구조(`.claude/kit.json` `layout: "script"`): 수집기는 모듈 하나(`aggregate.py`), 대시보드는 파일 하나(`index.html`)라
레이어·import-linter 계약이 없다.

| 파일 | 맡는 것 |
|---|---|
| `feeds.json` | 카테고리·피드·키워드 필터·한도 설정. 정상 운영에서 고치는 유일한 파일(RULE3) |
| `aggregate.py` | 수집기(Python 3.13, `feedparser`, RULE9). 피드 단위 실패 격리, `[OK]`/`[FAIL]` 로그(RULE4) |
| `index.html` | 단일 파일 대시보드, 외부 JS 없음(RULE10). 카테고리 칩·검색·상대 시각 표시 |
| `data.json` | 수집 결과. 로컬에서 생성되고 git이 추적하지 않는다. 배포본은 `gh-pages` 브랜치에만(RULE1) |
| `pyproject.toml` / `uv.lock` / `.python-version` | 의존성(`feedparser`, 개발용 pytest·ruff), uv로 잠금, Python 3.13 |
| `tests/test_aggregate.py` | `aggregate.py` 단위 테스트(외부 네트워크 없음. 피드 타임아웃은 127.0.0.1의 응답 없는 가짜 서버로) |
| `.github/workflows/update.yml` | 예약 수집 → `gh-pages` 배포(RULE2) |
| `.github/workflows/ci.yml` | ruff · `py_compile` · pytest · `feeds.json` 파싱 검사. 공개 레포라 단독 CI(RULE12) |
| `.github/workflows/dependabot-merge.yml` | Dependabot patch/minor PR 자동 머지(stark-kit 생성물) |
| `README.md` | 사람용 소개와 빠른 시작 |

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
2. `aggregate.py`가 `feeds.json`의 카테고리마다 피드를 읽고, 항목마다 기간(RULE6) → 키워드(RULE5) → 중복(RULE7) 순으로
   거른 뒤 최신순 정렬, 피드별 상한, 카테고리 상한(RULE8)을 적용해 `data.json`을 쓴다.
3. 워크플로가 `index.html` + `data.json` + `.nojekyll`을 새 저장소의 커밋 1개로 만들어 `gh-pages`에 force push한다(RULE2).
   이 배포 단계는 `master`에서 돈 실행만 하고(`if: github.ref == 'refs/heads/master'`), 앞 단계가 실패하면 돌지 않는다(RULE16).
   다른 ref로 수동 실행하면 수집만 하고 배포하지 않는다. `master`/`develop`에는 봇 커밋이 남지 않는다(RULE1).
4. GitHub Pages가 `gh-pages` `/`(root)를 서빙하고, 브라우저의 `index.html`이 `data.json`을 캐시 없이 fetch해 그린다.

`feeds.json` 형식:

| 키 | 뜻 | 없을 때 |
|---|---|---|
| `max_age_days` | 이보다 오래된 항목 제외, 날짜 미상은 유지(RULE6) | 14 |
| `max_items_per_category` | 카테고리당 최대 노출 수(RULE8) | 40 |
| `max_items_per_feed` | 한 카테고리 안에서 피드(출처 이름) 하나가 차지할 수 있는 최대 건수. 카테고리 상한보다 먼저 건다(RULE8) | 8 |
| `feed_timeout_seconds` | 피드 요청 타임아웃(초). 연결, TLS 핸드셰이크, 소켓 읽기 한 번마다 걸리고(응답 전체 시간·DNS 조회는 아님), 넘으면 그 피드만 실패(RULE4). 0보다 커야 한다(0 이하면 `[ERROR]`, 종료 코드 1, 배포하지 않음) | 30 |
| `categories[].key` / `label` | 내부 식별자(고유) / 화면 표시명 | — |
| `categories[].include_keywords` / `exclude_keywords` | 키워드 필터(RULE5) | 빈 목록 |
| `categories[].feeds[]` | `{ "name", "url", "tz" }`(`tz`는 선택). 카테고리마다 주제 피드를 넣고, 주제가 섞인 피드는 키워드로 거른다. `name`은 화면의 출처 이름이자 피드별 상한을 세는 단위(RULE8) | — |
| `categories[].feeds[].tz` | 원문에 시간대가 없는 발행 시각을 읽을 고정 UTC 오프셋 `±HH:MM`(예: `"+09:00"`). 시간대가 적힌 시각에는 쓰지 않는다(RULE6). 같은 피드를 여러 카테고리에 넣으면 항목마다 적는다 | UTC |

`data.json` 형식(수집기 → 대시보드 경계): `generated_at`(UTC ISO 8601), `categories[]` = `{ key, label, count, items[] }`,
`items[]` = `{ title, link, source, published }`(`link`는 `http`/`https` 절대 URL 또는 빈 문자열(RULE11), `published`는 UTC ISO 8601
또는 `null`). 요약은 필터에만 쓰고 내보내지 않는다. 대시보드는 `link`가 `http://`·`https://`로 시작할 때만 제목을 링크로 그린다.

외부 경계: 피드 사이트(HTTP, 실패는 피드 단위로 격리), GitHub Actions(예약 실행, `GITHUB_TOKEN`으로 `gh-pages` push),
GitHub Pages(정적 서빙), Google Fonts(대시보드 글꼴 스타일시트).

## 오류 모델

| 오류 | 처리 | 보이는 곳 |
|---|---|---|
| `feeds.json` 읽기·파싱 실패 | `[ERROR]` 후 종료 코드 1 → 워크플로 실패, 배포 단계를 건너뛰어 직전 배포본이 남는다. CI가 파싱을 미리 검사한다 | Actions run 실패 |
| `feeds.json` 키 누락·형식 오류(카테고리에 `key`·`label`이 없음, 숫자로 읽히지 않는 한도 값(`max_age_days: "two weeks"`, `null`), `categories`·`feeds`가 목록이 아님, 키워드 목록에 문자열이 아닌 값) | 검사하지 않는다. `[ERROR]` 없이 traceback(`KeyError`·`ValueError`·`TypeError`·`AttributeError`)으로 끝나 종료 코드 1 → 배포 단계를 건너뛰어 직전 배포본이 남는다. 카테고리 하나의 오류도 실행 전체를 멈춘다(피드 `tz`와 달리 격리되지 않는다). 숫자로 읽히는 문자열(`"14"`)은 받아들인다. CI의 `feeds.json` 검사는 JSON 파싱만 본다 | Actions run 실패, run 로그 traceback |
| `feeds.json` 값이 틀렸지만 실행은 됨(`include_keywords`·`exclude_keywords`를 목록 대신 문자열로 씀, 한도 값 0 이하. `feed_timeout_seconds` 0 이하는 예외로 `[ERROR]` 후 종료 코드 1, RULE4) | 검사하지 않고 그대로 쓴다. 문자열 키워드 목록은 글자 하나하나가 키워드가 되어(`"robot"` → `r`·`o`·`b`·`t`) include는 거의 전부 통과시키고 exclude는 거의 전부 뺀다. `max_items_per_category` 음수는 카테고리마다 정렬 맨 뒤 항목을 그 수만큼 빼고, `max_age_days` 0 이하는 발행 시각이 수집 시각보다 이른 항목을 모두 뺀다(날짜 미상은 남는다). `max_items_per_category` 0이나 `max_items_per_feed` 0 이하는 모든 카테고리를 비운다(전체 0건, RULE16) | 경고 없음. 대시보드에서 카테고리 내용·건수가 달라진 것으로만 보인다(전체 0건이면 아래 "수집 결과가 전체 0건" 줄) |
| 피드 하나 실패(예외, 또는 `bozo`이면서 entry 0개) | 그 피드만 건너뛰고 계속(RULE4) | run 로그 `[FAIL] <카테고리> / <피드>: <원인>` |
| 피드가 응답하지 않음(연결·핸드셰이크·읽기 대기가 `feed_timeout_seconds`를 넘음) | 그 요청을 끊고 그 피드만 건너뛰고 계속(RULE4) | run 로그 `[FAIL] <카테고리> / <피드>: ... timed out`(응답 대기: http 피드는 `timed out`, https 피드는 `The read operation timed out`. 연결·TLS 단계에서 끊기면 `bozo: <urlopen error ... timed out>`) |
| 수집 job이 `timeout-minutes`(15분)를 넘음(피드 타임아웃이 끊지 못하는 멈춤) | GitHub가 job을 취소한다. 배포 단계가 돌지 않아 직전 배포본이 남는다 | Actions run 취소 |
| 피드 항목의 `tz` 형식이 틀림(`"KST"`, `"+9"` 등) | 그 피드만 요청 없이 건너뛰고 계속(RULE4). CI의 `feeds.json` 검사는 JSON 파싱만 본다 | run 로그 `[FAIL] <카테고리> / <피드>: 잘못된 tz 값 ...` |
| 수집 결과가 전체 0건(피드가 모두 실패, 필터가 전부 걸러냄, 카테고리 없음) | `[ERROR]` 후 `data.json`을 쓰지 않고 종료 코드 1 → 배포 단계를 건너뛰어 직전 배포본이 남는다(RULE16). 카테고리 하나만 0건이면 그대로 게시 | Actions run 실패, run 로그 `[ERROR] 수집된 항목이 0건...`. 대시보드는 직전 배포본("last sync"가 멈춤) |
| 항목의 날짜를 해석할 수 없음 | 날짜 미상으로 유지, 정렬 맨 뒤(RULE6) | 대시보드 "날짜 미상" |
| 항목 링크가 `http`/`https` 절대 URL이 아님(`javascript:` 같은 다른 스킴, 기준 URL 없이 남은 상대 링크, URL로 나눌 수 없음) | 항목은 남기고 링크만 빈 문자열로 내보낸다. 중복 키는 제목(RULE7). 대시보드도 `http(s)://`로 시작하지 않는 링크는 `href`에 넣지 않는다(RULE11) | 대시보드에서 그 항목 제목이 링크 없는 글자로 보인다. 로그에는 남지 않는다 |
| 대시보드가 `data.json`을 못 받음 | 오류 안내(HTTP 상태 포함) | 대시보드 붉은 안내 문구 |

수집은 피드 단위로 fail-open(RULE4), 설정 오류(읽기·파싱 실패, 키 누락·형식 오류)와 전체 0건은 배포 쪽으로 fail-closed(직전
배포본 유지, RULE16)다. 다만 `feeds.json` 값의 형식·범위는 검사하지 않아, 실행을 멈추지 않는 잘못된 값(문자열 키워드 목록,
0 이하 한도)은 경고 없이 그대로 쓰인다(ROADMAP GATE0 관찰).

## 알려진 한계

- 원문 시각에 시간대가 있는지는 ISO 8601과 RFC 2822 형식으로만 판정한다(`aggregate.lacks_tz`). 그 밖의 형식(예: 연도가
  맨 뒤인 asctime, 시간대 이름이 가운데 있는 문자열)은 피드의 `tz`가 잘못 적용되거나 적용되지 않을 수 있다. 지금 `tz`를 쓰는
  세 피드의 형식(`2026-11-21 11:51:51`)은 정확히 처리된다.
- 피드 타임아웃은 연결·TLS 핸드셰이크·소켓 읽기 한 번마다 걸린다. 조금씩 계속 보내는 서버나 DNS 조회 지연은 job 한도
  15분까지 수집을 붙잡을 수 있고, 그 실행은 배포하지 않는다(RULE4).
- 예약 실행은 정시에 돌지 않는다. 실측으로 수 시간 늦게 시작하고 하루 2~4회 실행된다(RULE14, ROADMAP GATE0 관찰).
- 공개 레포에서 60일간 저장소 활동이 없으면 GitHub가 예약 워크플로를 끈다. 확인·재활성은 [RUNBOOK.md](RUNBOOK.md) 운영.
- 예약 실행은 기본 브랜치 `master`의 파일을 쓴다. `feeds.json` 변경은 릴리스로 `master`에 들어간 뒤부터 반영된다.
- 피드 URL은 바뀌거나 죽을 수 있다. 실패는 `[FAIL]`로 보이지만, 정상 응답에 entry가 0개인 피드는 `[OK] 0 entries`로
  남아 구별되지 않는다(ROADMAP GATE0 관찰).
- 전체 0건이면 직전 배포본이 그대로 남아(RULE16), 대시보드만 봐서는 수집이 멈춘 것을 알기 어렵다. "last sync" 시각과
  Actions run 실패로 본다.
- 대시보드 검색은 제목과 출처만 본다(요약은 `data.json`에 없다).
- RSS/Atom만 수집한다(RULE13). 과거 수집 결과는 남지 않는다(RULE15).
