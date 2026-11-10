# 로드맵

News Radar는 지금 GATE0에 있고 최종 목표 GATE2를 향한다. 게이트는 제품의 **검증 가능한 상태**이지 티켓 묶음이 아니다.
진행 상태는 이 파일에만 쓴다. 설계는 [DESIGN.md](DESIGN.md), 규칙은 [RULES.md](RULES.md), 절차는 [RUNBOOK.md](RUNBOOK.md).

## 읽는 법

- ID: `GATEn` 게이트 · `GATEn-Tk` 티켓(게이트 n의 브랜치 하나 분량 작업) · `GRn` 게이트 리뷰 ·
  `DEFECTn` 결함(레포 전역, 발견 순) · `RULEn` 규칙(불변식·한도·범위·안 하기로 한 것).
  어디서나 같은 모양: 브랜치 `feature/GATE1-T1-<slug>`, 커밋 `fix: ... (GATE1-T1)`, 릴리스 노트 `(GATE1-T1, DEFECT3)`.
- 게이트는 번호 순서로 지난다. 이전 GR이 pass하기 전에는 다음 게이트의 티켓을 시작하지 않는다.
  예외는 *parallel* 표시가 있는 게이트·티켓이며, 어느 GR 전에 pass해야 하는지 진입 조건 줄에 적는다.
- 티켓 상태: `open` → `in progress`(브랜치 생성) → `done <머지 sha>`. 행은 지우지 않는다.
- 결함은 발견 즉시 `## 결함`에 다음 번호로 등록한다(현재 게이트와 무관). 티켓의 "닫는 결함" 열이 결함을
  가리키고, 티켓이 머지되면 결함 상태를 `fixed by GATEn-Tk`로 바꾼다.
- 게이트 리뷰는 종료 기준을 증거(테스트 결과와 커밋, 검증자 보고, 워크플로 run id, 운영 로그, RUNBOOK QA 번호)로
  확인한다. 세션이 증거를 모아 판정안(`pass` / `pass with notes` / `fail`)을 적고, **사용자만 GR을 닫는다.**
  `fail`이면 같은 게이트에 티켓을 추가하고 같은 `GRn`으로 다시 심사한다.
- GATE0는 현황 진단이다. GR0 증거에는 **결함 리뷰 보고**가 반드시 들어간다. 마지막 리뷰 이후 바뀐 코드는 전부
  다시 보고, 제품 전체를 RULE 표와 대조한다. 확인된 지적은 GR0 판정안을 적기 전에 DEFECT로 등록한다.
- 릴리스는 증거이지 게이트가 아니다. 한 게이트가 여러 릴리스에 걸쳐도 된다.
- 퇴역한 옛 ID는 맨 끝 대응표에 한 번만 적는다.

## 현황

| | |
|---|---|
| 현재 게이트 | **GATE0** |
| 현재 티켓 | 없음 |
| 마지막 GR | 없음 (GR0 판정안 `proposed: pass with notes`, 사용자 미결) |
| 최신 릴리스 | v1.0.1 (2026-11-03) |
| 열린 결함 | 6 (DEFECT1~DEFECT6) |
| 다음 할 일 | 사용자가 GR0를 닫는다. 그 뒤 GATE1-T2(DEFECT2, 브랜치 `feature/GATE1-T2-<slug>`)부터 GATE1 작업 순서대로 |

## 현재 작업

GATE0 결함 리뷰 (브랜치 `feature/gate0-defect-review`, `docs/`만 바꾼다).

- Goal: GR0 근거가 될 결함 리뷰. 이전 리뷰가 없으므로 첫 커밋부터 develop 끝까지 코드 전체를 RULE1~RULE15와 대조한다.
- Acceptance: RULE별 대조 결과, 확인된 결함을 DEFECT2부터 등록, GATE0 절에 결함 리뷰 보고와 GR0 `proposed` 판정안,
  GR 기록 GR0 행 갱신. 코드는 고치지 않는다.

## 결함

| 결함 | 발견 | 차이 | 영향 | 상태 |
|---|---|---|---|---|
| DEFECT1 | 2026-11-04, 코드 읽기(`index.html` `applyData`·`fmtDateTime`) | 상단 "last sync" 시각을 브라우저 지역 시간으로 계산하고 뒤에 "UTC"를 붙인다 | KST 브라우저에서 2026-11-04 04:47 UTC 수집이 "2026-11-04 13:47 UTC"로 보인다. 수집 시각을 9시간 늦게(미래로) 읽게 된다. 수집·배포 자체는 정상 | open |
| DEFECT2 | 2026-11-10, GATE0 결함 리뷰: 배포본 `data.json`(gh-pages `df9ed5e`)과 run 42733691513 로그, 실험 E4, `aggregate.py` `dedup_key`(77행) | 쿼리스트링이 기사 식별자인 링크(`.../news/articleView.html?idxno=NNN`)는 기사가 달라도 중복 키가 같아져, 그 피드에서는 카테고리마다 첫 기사 1건만 남는다 | 모터그래프·로봇신문·AI타임스(피드 15개 중 4자리)가 매 실행 50 entries를 받고도 1건씩만 보인다. master에 남은 2026-06-01~10-12 스냅샷 516개도 모두 1건. arXiv 두 피드가 0건인 실행(2026-10-27~11-10, 43회 중 19회)에는 AI 카테고리 전체가 1건이다 | open |
| DEFECT3 | 2026-11-10, GATE0 결함 리뷰: 배포본 `data.json`, master 스냅샷 516개, 실험 E3 | 국내 피드 3곳(모터그래프·로봇신문·AI타임스) 항목의 발행 시각이 실제보다 9시간 늦게(미래로) 기록된다. 수집 시각보다 0~9시간 앞선 항목이 스냅샷에서 942번 나왔고 모두 이 세 피드다. KST 시각이 UTC로 해석된 것으로 보인다(원문 피드의 시각 표기는 오프라인 원칙으로 확인하지 않았다) | 해당 항목이 실제보다 위로 정렬되고 대시보드에 최대 9시간 "방금"(강조색)으로 보인다. 기간 필터(RULE6) 경계도 9시간 어긋난다. 예: 배포본 `df9ed5e`(수집 01:09 UTC)의 AI타임스 항목 `published` `2026-11-10T09:05:00+00:00` | open |
| DEFECT4 | 2026-11-10, GATE0 결함 리뷰: 실험 E7, `aggregate.py` `collect_feed`(97행), feedparser 6.0.14 `http.py` 171행 `opener.open(request)`, `update.yml` job 설정 | 피드 요청에 타임아웃이 없다. 연결만 받고 응답하지 않는 피드 하나에서 `collect_feed`가 돌아오지 않아 수집 전체가 멈춘다(RULE4 "수집 전체를 멈추지 않는다"와 다름). job에 `timeout-minutes`가 없어 GitHub 기본 한도(360분)까지 기다린 뒤 취소되고 배포 단계는 돌지 않는다 | 그 실행은 배포본을 갱신하지 못하고, 같은 `concurrency` 그룹의 다음 예약 실행은 그동안 줄을 선다. 2026-06-01 이후 613회 실행에서는 일어나지 않았다 | open |
| DEFECT5 | 2026-11-10, GATE0 결함 리뷰: 실험 E6(Node `vm`), feedparser 오프라인 파싱, `index.html` `renderGrid`(352~354행) | 항목 링크의 스킴을 검사하지 않는다. 피드가 `javascript:`·`vbscript:`·`data:` 링크를 주면 feedparser가 그대로 넘기고, `esc()`는 HTML 특수문자만 바꾸므로 그 값이 그대로 `<a href>`가 된다. RULE11의 근거(외부 피드 내용으로 공개 페이지에 스크립트 주입)를 막지 못한다 | 악성·탈취된 피드, 또는 `http://` 피드 3개의 전송 구간 변조로 대시보드 링크에 스크립트 URL이 들어갈 수 있다. 클릭해야 하고, `target="_blank"` 링크에서 실제로 실행되는지는 브라우저마다 다르며 이번에 확인하지 않았다. 지금 배포본의 링크는 모두 `http(s)://`다 | open |
| DEFECT6 | 2026-11-10, GATE0 결함 리뷰: RULE12 대조(`git grep`), `.claude/CONVENTIONS.md` 43행 | stark-kit이 생성한 `.claude/CONVENTIONS.md`가 예시로 다른 비공개 저장소의 이름과 그 안의 파일 경로를 담고 있다(RULE12 "비공개 정보를 커밋하지 않는다"와 다름) | 2026-10-14(`dd59233`)부터 공개 레포의 `master`·`develop`에 있다. 토큰·자격 증명은 아니다. 고쳐도 git 이력에는 남는다(이력은 다시 쓰지 않는다) | open |

## GATE0 — 현황 진단 (2026-11-04, 결함 리뷰 2026-11-10)

**제품이 약속하는 것** ([DESIGN.md](DESIGN.md)): `feeds.json`에 적은 RSS를 매일 정해진 시각(00·06·12·18시 UTC 예약)에
수집해 기간·키워드·중복 규칙(RULE5~RULE8)으로 거르고, `gh-pages` 브랜치로 배포해 GitHub Pages 대시보드
(https://berry3536.github.io/news-radar/)에서 보여 준다. 정상 운영에서 사람이 고치는 것은 `feeds.json`뿐이다(RULE3).

**지켜지는 곳**:

- 테스트: pytest 16개(날짜 6 · 텍스트 정리 1 · 중복 키 2 · 키워드 필터 6 · 카테고리 처리 1, 네트워크 없음).
  v1.0.1 master `5731e98`의 CI run 41605796586에서 `16 passed`.
- CI: `ci.yml`이 develop·master push와 PR마다 ruff · `py_compile` · pytest · `feeds.json` 파싱을 검사한다.
- 수집·배포: `update.yml` 실행 613회(2026-06-01 ~ 2026-11-10, 예약 612 + 수동 1) 전부 성공, 실패 0.
  최근 run 42733691513(2026-11-10 01:09 UTC): 피드 15개 모두 `[OK]`, `[FAIL]` 0, 117건 →
  gh-pages `df9ed5e` → pages-build-deployment run 42733735769 성공. 2026-10-27 이후 43회 모두 `[FAIL]` 0.
  실행 성공과 `[OK]`는 DEFECT2·DEFECT3을 드러내지 않는다(50 entries를 받은 피드가 1건만 남아도 성공).
- 배포 위치: master 트리에 `data.json` 없음, gh-pages는 커밋 1개(`.nojekyll`, `data.json`, `index.html`) (RULE1, RULE2).

**지켜지지 않는 곳** (피해 순): DEFECT2(국내 피드 3곳의 기사가 카테고리마다 1건만 남는다, 매 실행),
DEFECT3(그 피드들의 발행 시각이 9시간 미래로 기록된다, 매 실행), DEFECT1(상단 "last sync" 표기),
DEFECT4(응답 없는 피드 하나가 수집 전체를 멈춘다, 일어난 적 없음), DEFECT5(링크 스킴을 검사하지 않는다, 일어난 적 없음),
DEFECT6(키트 생성 파일에 다른 저장소 이름).

**관찰 항목** (결함으로 등록하지 않음. GATE2 조건과 GR에서 다시 본다):

- 스케줄 60일 비활성: 공개 레포에서 60일간 저장소 활동이 없으면 GitHub가 예약 워크플로를 끈다.
  2026-11-10 현재 `Aggregate tech news`는 `active`. 마지막 사람 push는 2026-11-10(develop).
  워크플로의 gh-pages push(봇)나 Dependabot 자동 머지가 "활동"으로 잡히는지는 확인하지 않았다.
  확인·재활성 절차는 [RUNBOOK.md](RUNBOOK.md) 운영.
- 예약 실행 지연·누락: 예정 56회 중 2026-10-21 ~ 11-03에 48회, 2026-10-27 ~ 11-09에 42회 실행했다. 시작은 정시보다
  중앙값 4.0시간, 최대 5.7시간 늦다(2026-10-27 ~ 11-09). 배포본 갱신 간격은 최대 13시간 8분(2026-11-03 00:28 → 13:35 UTC).
  정시 보장은 하지 않기로 했다(RULE14).
- 0건 피드 (RULE 공백, 2026-11-10 관찰로 둠): 정상 응답이지만 entry가 0개인 피드도 `[OK] ... 0 entries`로 남아 죽은
  피드와 구별되지 않는다(RULE4의 실패 정의대로). 2026-10-27 ~ 11-10 실행 43회 중 30회에 arXiv 피드가 0건이었고
  (다른 피드는 없음), 19회는 cs.AI·cs.LG 모두 0건이었다. `feeds.json`의 빈 `url`도 `[OK] 0 entries`로 찍힌다(E5).
- `feeds.json` 형식 검사 없음 (RULE 공백, 관찰): `key`·`label` 누락이나 숫자가 아닌 `max_age_days`는 `[ERROR]` 없이
  traceback으로 끝난다(배포 단계는 건너뛰어 직전 배포본이 남는다). `max_items_per_category` 0은 빈 배포, 음수는 가장
  오래된 항목을 경고 없이 버리고, `include_keywords`를 문자열로 쓰면 글자 단위로 비교해 거의 전부 통과한다(E5, 검증자).
  CI는 JSON 파싱만 본다.
- 미래 날짜 (RULE 공백, 관찰): 수집 시각보다 늦은 발행 시각도 남고 맨 위에 "방금"으로 보인다(E3, E6). 지금까지 나온
  미래 시각은 모두 DEFECT3의 세 피드였다(다른 소스 0건).
- 키워드 부분 일치와 요약 태그 (RULE 공백, 관찰): 부분 문자열 일치라 `cell`이 `excellent`에, `motor`가 `motorcycle`에
  걸린다. 요약의 HTML 태그를 지우지 않아 링크·이미지 주소 속 단어에도 걸린다(검증자 재현). 실제 피드 결과가 바뀌는지는
  확인하지 않았다.
- 전체 실패 시 덮어쓰기: 모든 피드가 실패해도 0건 `data.json`이 직전 배포본을 덮는다(E1, DESIGN 오류 모델에 적힌 동작).
  master 스냅샷 516개와 최근 실행 43회에 0건은 없었다. 2026-11-10 사용자 결정으로 규칙을 바꾼다: GATE1-T6.

**결함 리뷰** (2026-11-10): 범위 전체(`c8f2902..4b92135`, 이전 리뷰 없음)와 RULE1~RULE15 대조. 방법 verifier 1
(correctness, 단서 없이 독립 확인), 오프라인 실험 7건(E1 전체 실패·설정 오류, E2 0건·bozo 피드, E3 날짜,
E4 중복 키, E5 설정 이상값, E6 Node `vm`의 대시보드 escape, E7 응답 없는 로컬 소켓; 27개 경우), 코드 읽기, 배포본과
master 스냅샷 516개·최근 run 로그 43개 분석(외부 네트워크 없음). 결과 DEFECT2~DEFECT6 등록. RULE4(DEFECT4)·
RULE6(DEFECT3)·RULE12(DEFECT6)가 지켜지지 않고, RULE7·RULE11은 문장대로 구현됐지만 근거를 지키지 못한다
(DEFECT2·DEFECT5). 나머지 RULE은 지켜진다. 검증자 VERDICT는 FAIL: 지적 9건 중 4건은 DEFECT2~DEFECT5와 같고,
2건은 RULE 공백(`feeds.json` 형식 검사, 요약 태그), 3건은 문서·테스트(GATE1-T8)로 처리했다. 기각 8건:

- 극단 날짜(연도 9999, 음수 오프셋) 항목 하나가 그 피드를 `[FAIL]`로 만든다(E2): RULE4는 피드 단위 격리만 약속하고
  수집은 계속된다. 실제 피드에서 나올 입력이 아니다.
- `count`와 전체 합계가 escape 없이 `innerHTML`에 들어간다(`index.html` 312·316행): 수집기는 int만 쓰고, `data.json`을
  바꿀 수 있으면 같은 브랜치의 `index.html`도 바꿀 수 있어 새 위협 경로가 아니다.
- 항목 툴팁과 7일 이상 지난 날짜가 지역 시각이다: "UTC"라고 표기하지 않으므로 약속과 다르지 않다(DEFECT1과 다름).
- `generated_at`의 마이크로초 6자리: Node(V8)는 정상 해석한다. 다른 브라우저에서 문제라는 증거는 없다(확인 못 함).
- 중복 키가 `#fragment`·호스트 대소문자·`http`/`https` 차이를 합치지 않는다: RULE7이 약속하지 않고, 스냅샷 517개에서
  카테고리 안 같은 제목 중복은 0건이다.
- deny 패턴 `git push*gh-pages*`가 `git -C <dir> push ... gh-pages`를 잡지 못한다: 실수 방지 장치이고 규칙의 본체는
  Forbidden이다(키트 설정이라 보고만).
- `update.yml`의 `uv sync --locked`가 dev 그룹(pytest·ruff)까지 설치한다: 수집기가 import하지 않으므로 RULE9 위반이 아니다.
- 키워드 부분 문자열 일치와 motor include의 `traction` 중복: RULE5 "포함" 문장 그대로이고 `feeds.json` 운영 문제다(관찰).

RULE 공백 질문 5건(0건 피드, 전체 실패, `feeds.json` 형식 검사, 미래 날짜, 키워드 부분 일치·요약 태그): 전체 실패만
규칙으로 정하고(GATE1-T6) 나머지는 관찰로 둔다(2026-11-10 사용자 결정).

**GR0 판정안**: pass with notes. 수집·배포 파이프라인(613회 연속 성공, gh-pages 커밋 1개, RULE1·RULE2), 피드 예외 격리,
기간·키워드 필터와 정렬·상한(테스트 16개, 실험 E1~E5)은 믿을 수 있다. 수집 결과의 내용은 믿을 수 없다: 국내 피드 3곳의
기사가 카테고리마다 1건만 남고(DEFECT2) 그 시각이 9시간 미래다(DEFECT3). 둘 다 지금 배포본에 매 실행 나타난다는 것이
note다. GATE1은 이 둘을 먼저 고치고(GATE1-T2·T3), DEFECT1·DEFECT4·DEFECT5·DEFECT6, 전체 0건 배포 금지(GATE1-T6),
문서·테스트 정리(GATE1-T8)까지 v1.1.0으로 닫는다. 0건 피드 표시, `feeds.json` 형식 검사, 미래 날짜, 키워드 부분 일치·요약
태그는 관찰로 두고 GR1에서 다시 본다.

## GATE1 — 대시보드가 피드의 기사를 빠짐없이 올바른 시각으로 보여 주고, 피드 하나가 수집과 화면을 망치지 않는다

진입: GR0 pass. 목표 릴리스: v1.1.0(중복 키·시각 해석 규칙과 배포 조건이 바뀐다). (GATE1 신설은 2026-11-04,
DEFECT2~DEFECT6과 전체 0건 규칙 추가는 2026-11-10 사용자 결정, GR 기록 GR0 행 참조.)

작업 순서는 피해 순이다: T2 → T3 → T1 → T4 → T6 → T5 → T7 → T8. T2와 T3은 같은 릴리스로 낸다(T2만 나가면 9시간 미래
항목이 그 피드마다 최대 50건으로 늘어난다).

| 티켓 | 작업 | 닫는 결함 | 선행 | 상태 |
|---|---|---|---|---|
| GATE1-T1 | `index.html`의 "last sync" 시각을 UTC로 계산해 표시한다(`fmtDateTime`이 `getUTC*`를 쓰거나 UTC 전용 포맷 함수를 둔다). 레이블 "UTC"와 값의 시간대가 같아진다. 항목별 날짜 표시는 범위 밖(별도 결함이면 새 번호로 등록) | DEFECT1 | — | open |
| GATE1-T2 | 중복 키에서 기사를 식별하는 쿼리를 지우지 않는다: 추적 파라미터(`utm_*` 등)만 떼고 나머지 쿼리는 키에 남긴다. RULE7 문장 개정, `idxno`만 다른 기사가 각각 남는 테스트 | DEFECT2 | — | open |
| GATE1-T3 | 시간대 없는 발행 시각을 피드별로 해석한다(예: `feeds.json` 피드 항목의 시간대 키, 없으면 UTC). 먼저 세 피드의 원문 시각 표기를 확인한다. RULE6 값 개정 | DEFECT3 | — | open |
| GATE1-T4 | 피드 요청에 타임아웃을 둬서 넘으면 그 피드만 `[FAIL]`로 건너뛰고, `update.yml` job에 `timeout-minutes`를 둔다. 값은 RULE4에 적는다 | DEFECT4 | — | open |
| GATE1-T5 | `http`/`https`가 아닌 항목 링크는 내보내지 않는다(수집기에서 빈 링크로, 대시보드에서도 스킴 검사). RULE11 문장 개정 | DEFECT5 | — | open |
| GATE1-T6 | 수집 결과가 전체 0건이면 `data.json`을 게시하지 않고 직전 배포본을 유지한다(`aggregate.py` 종료 코드 1 → 배포 단계를 건너뜀). 새 RULE 번호를 받고 DESIGN 오류 모델을 고친다 | — (GR0 결정) | — | open |
| GATE1-T7 | `.claude/CONVENTIONS.md`의 다른 저장소 예시를 일반 문장으로 바꾼 stark-kit 버전을 `kit sync`로 반영한다 | DEFECT6 | stark-kit 문안 수정 | open |
| GATE1-T8 | 문서·주석·테스트 정리: `aggregate.py` docstring(배포 방식), `update.yml` 예약 주석(RULE14 참조), DESIGN "데이터와 흐름" 1번의 수동 실행 ref 문장(필요하면 배포 단계를 `master` 전용으로), DESIGN 오류 모델에 `feeds.json` 키 누락·형식 오류 줄, RULES "지키는 곳"이 가리키는 테스트 보강(`collect_feed` bozo 판정, 요약에만 키워드가 있는 항목, 먼저 수집된 항목이 남는 중복) | — | — | open |

종료 기준 (GR1):

- [ ] DEFECT1~DEFECT6이 모두 `fixed by GATE1-Tk`. 증거: 각 티켓의 테스트와 머지 커밋.
- [ ] 배포본 화면의 "last sync" 값이 `data.json`의 `generated_at`(UTC)과 분 단위까지 같다. 증거: 릴리스 뒤 Pages 화면과 배포본 `data.json` 비교, KST 브라우저에서 확인.
- [ ] 릴리스 뒤 배포본 `data.json`에서 include 필터가 없는 카테고리(ev·robot·ai)에 모터그래프·로봇신문·AI타임스가 각각 2건 이상 있고, 어떤 항목의 `published`도 `generated_at`보다 늦지 않다. 증거: QA1 실행 뒤 배포본.
- [ ] 응답하지 않는 피드(테스트의 로컬 가짜 서버)는 정해진 시간 안에 `[FAIL]`로 끝나고 나머지 피드는 수집된다. `update.yml` job에 `timeout-minutes`가 있다. 증거: 테스트와 CI run.
- [ ] `http`/`https`가 아닌 링크는 `data.json`과 대시보드 `href`에 나오지 않는다. 증거: 테스트.
- [ ] 전체 0건이면 배포 단계가 돌지 않고 직전 배포본이 남는다. 증거: 테스트(`main()` 종료 코드)와 워크플로 단계 조건.
- [ ] `.claude/CONVENTIONS.md`에 다른 저장소의 이름·경로가 없다. 증거: `git grep`.
- [ ] v1.1.0 태그와 GitHub Release 공개.

GR1이 GATE2를 위해 정해야 할 것: GATE0 관찰로 남긴 RULE 공백(0건 피드 표시, `feeds.json` 형식 검사, 미래 날짜,
키워드 부분 일치·요약 태그) 가운데 GATE2 전에 규칙으로 정할 것이 있는지.

## GATE2 — 최종 목표 상태

진입: GR1 pass. 아래가 성립하면 도달:

- 무인 운영이 이어진다: 예약 수집이 사람 개입 없이 계속 성공하고, gh-pages 배포본(`data.json` `generated_at`)이
  하루 안에 갱신된다. 증거: `update.yml` run 기록과 배포본 시각.
- 예약 워크플로가 60일 비활성으로 꺼지지 않거나, 꺼지는 조건과 되살리는 절차가 확인돼 있다.
- 피드 추가·교체와 키워드 변경은 `feeds.json` 수정만으로 끝난다(코드 수정 없음, RULE3).
  반영은 릴리스로 master에 들어간 뒤 다음 예약 실행부터다([RUNBOOK.md](RUNBOOK.md)).
- 죽은 피드 하나가 수집 전체를 막지 않는다(RULE4).
- 의존성 갱신이 Dependabot 자동 머지로 유지된다.
- 열린 결함 0.

GATE2 밖(새 범위 결정이 필요한 것, 결함이 아님): 정시 수집(RULE14), RSS/Atom 없는 소스의 스크래핑(RULE13),
서버·DB·과거 수집 이력 보관(RULE15), 알림·계정 같은 새 기능.

## GR 기록

| GR | 날짜 | 판정 | 증거 | 다음 게이트를 위한 결정 |
|---|---|---|---|---|
| GR0 | 2026-11-10 | proposed: pass with notes | 결함 리뷰(2026-11-10, 범위 `c8f2902..4b92135` 전체와 RULE1~RULE15, verifier 1 correctness: VERDICT FAIL, 지적 9건 중 4건이 DEFECT2~DEFECT5와 같음; 오프라인 실험 7건; 결과 DEFECT2~DEFECT6 등록, 기각 8건, RULE 공백 5건); 이 진단; v1.0.1(2026-11-03); pytest 16 passed(CI run 41605796586, master `5731e98`); `update.yml` 613회 전부 성공(2026-06-01~11-10), 최근 run 42733691513(피드 15개 `[OK]`, 117건) → pages run 42733735769 | 결정(2026-11-04, 사용자): DEFECT1은 GATE1에서 닫는다(GATE1-T1), 최종 목표는 GATE2. 결정(2026-11-10, 사용자): DEFECT2~DEFECT6도 GATE1에 두고 목표 릴리스를 v1.1.0으로 한다(GATE1-T2~T5, T7); 전체 0건이면 배포하지 않는다(GATE1-T6, 새 RULE); 문서·테스트 정리는 GATE1 티켓 하나(GATE1-T8); 0건 피드 표시·`feeds.json` 형식 검사·미래 날짜·키워드 부분 일치와 요약 태그는 관찰로 둔다. 남은 질문: 없음(GR0를 닫는 것만 남음) |

## 옛 ID 대응표

없음
