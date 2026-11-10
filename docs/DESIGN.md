# 설계

## 목적과 범위

전기차 · 배터리 · 모터 · 로봇 · AI 분야의 RSS를 **GitHub Actions가 주기적으로 수집**해 **GitHub Pages**가 정적 페이지로
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
| `tests/test_aggregate.py` | `aggregate.py`의 순수 함수 단위 테스트(네트워크 없음) |
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

1. `update.yml`이 예약(또는 수동)으로 기본 브랜치 `master`를 체크아웃하고 `uv sync --locked` 후 `aggregate.py`를 실행한다.
2. `aggregate.py`가 `feeds.json`의 카테고리마다 피드를 읽고, 항목마다 기간(RULE6) → 키워드(RULE5) → 중복(RULE7) 순으로
   거른 뒤 최신순 정렬·상한(RULE8)을 적용해 `data.json`을 쓴다.
3. 워크플로가 `index.html` + `data.json` + `.nojekyll`을 새 저장소의 커밋 1개로 만들어 `gh-pages`에 force push한다(RULE2).
   `master`/`develop`에는 봇 커밋이 남지 않는다(RULE1).
4. GitHub Pages가 `gh-pages` `/`(root)를 서빙하고, 브라우저의 `index.html`이 `data.json`을 캐시 없이 fetch해 그린다.

`feeds.json` 형식:

| 키 | 뜻 | 없을 때 |
|---|---|---|
| `max_age_days` | 이보다 오래된 항목 제외, 날짜 미상은 유지(RULE6) | 14 |
| `max_items_per_category` | 카테고리당 최대 노출 수(RULE8) | 40 |
| `categories[].key` / `label` | 내부 식별자(고유) / 화면 표시명 | — |
| `categories[].include_keywords` / `exclude_keywords` | 키워드 필터(RULE5) | 빈 목록 |
| `categories[].feeds[]` | `{ "name", "url" }`. 같은 피드 URL을 여러 카테고리에 넣고 키워드로 가르는 방식을 쓴다 | — |

`data.json` 형식(수집기 → 대시보드 경계): `generated_at`(UTC ISO 8601), `categories[]` = `{ key, label, count, items[] }`,
`items[]` = `{ title, link, source, published }`(`published`는 UTC ISO 8601 또는 `null`). 요약은 필터에만 쓰고 내보내지 않는다.

외부 경계: 피드 사이트(HTTP, 실패는 피드 단위로 격리), GitHub Actions(예약 실행, `GITHUB_TOKEN`으로 `gh-pages` push),
GitHub Pages(정적 서빙), Google Fonts(대시보드 글꼴 스타일시트).

## 오류 모델

| 오류 | 처리 | 보이는 곳 |
|---|---|---|
| `feeds.json` 읽기·파싱 실패 | `[ERROR]` 후 종료 코드 1 → 워크플로 실패, 배포 단계를 건너뛰어 직전 배포본이 남는다. CI가 파싱을 미리 검사한다 | Actions run 실패 |
| 피드 하나 실패(예외, 또는 `bozo`이면서 entry 0개) | 그 피드만 건너뛰고 계속(RULE4) | run 로그 `[FAIL] <카테고리> / <피드>: <원인>` |
| 수집 결과 0건 | `[WARN]` 로그 후 0건 `data.json`을 그대로 게시 | 대시보드 "수집된 항목이 없습니다" 안내 |
| 항목의 날짜를 해석할 수 없음 | 날짜 미상으로 유지, 정렬 맨 뒤(RULE6) | 대시보드 "날짜 미상" |
| 대시보드가 `data.json`을 못 받음 | 오류 안내(HTTP 상태 포함) | 대시보드 붉은 안내 문구 |

수집은 피드 단위로 fail-open(RULE4), 설정 오류는 배포 쪽으로 fail-closed(직전 배포본 유지)다.

## 알려진 한계

- 대시보드의 "last sync" 시각이 지역 시간인데 "UTC"로 표기된다: DEFECT1.
- 쿼리스트링으로 기사를 구별하는 링크(`.../articleView.html?idxno=NNN`)는 중복 키가 같아져 그 피드에서 카테고리마다
  1건만 남는다: DEFECT2.
- 국내 피드 3곳의 발행 시각이 9시간 미래로 기록된다(KST 시각을 UTC로 읽는 것으로 보인다): DEFECT3.
- 피드 요청에 타임아웃이 없어, 연결만 받고 응답하지 않는 피드 하나가 수집 전체를 멈출 수 있다: DEFECT4.
- 항목 링크의 스킴을 검사하지 않아 `javascript:` 같은 링크도 그대로 `href`가 된다: DEFECT5.
- 예약 실행은 정시에 돌지 않는다. 실측으로 수 시간 늦게 시작하고 하루 2~4회 실행된다(RULE14, ROADMAP GATE0 관찰).
- 공개 레포에서 60일간 저장소 활동이 없으면 GitHub가 예약 워크플로를 끈다. 확인·재활성은 [RUNBOOK.md](RUNBOOK.md) 운영.
- 예약 실행은 기본 브랜치 `master`의 파일을 쓴다. `feeds.json` 변경은 릴리스로 `master`에 들어간 뒤부터 반영된다.
- 피드 URL은 바뀌거나 죽을 수 있다. 실패는 `[FAIL]`로 보이지만, 정상 응답에 entry가 0개인 피드는 `[OK] 0 entries`로
  남아 구별되지 않는다(ROADMAP GATE0 관찰).
- 모든 피드가 실패하면 빈 배포본이 직전 배포본을 덮고, 다음 실행까지 남는다(ROADMAP GATE1-T6).
- 대시보드 검색은 제목과 출처만 본다(요약은 `data.json`에 없다).
- RSS/Atom만 수집한다(RULE13). 과거 수집 결과는 남지 않는다(RULE15).
