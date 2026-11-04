# 런북

## 개발

```powershell
uv sync                                   # .venv (Python 3.13, uv.lock 기준), pytest·ruff 포함
git config core.hooksPath .githooks       # 새 clone에서 한 번: gitflow 가드 훅
```

검증(`.claude/kit.json` `commands.verify`와 같다):

```powershell
uv run ruff check .
uv run pytest
uv run python -c "import json; json.load(open('feeds.json', encoding='utf-8'))"
git diff --check
```

CI(`ci.yml`)는 `git diff --check` 대신 `uv run python -m py_compile aggregate.py`를 더해 develop·master push와 PR마다 돈다.
테스트는 네트워크를 쓰지 않는다. 실제 수집과 화면 확인:

```powershell
uv run python aggregate.py        # data.json 생성(네트워크 필요), 피드별 [OK]/[FAIL] 로그
uv run python -m http.server      # http://localhost:8000 에서 index.html 확인
```

`data.json`은 git이 추적하지 않는다(RULE1). 네트워크가 막혔으면 배포본을 받아 화면만 확인한다:
`git show origin/gh-pages:data.json > data.json`.

피드 추가·변경은 `feeds.json`만 고친다(RULE3). 로컬 `aggregate.py` 실행으로 새 피드가 `[OK]`이고 entry가 0이 아님을 본 뒤
feature 브랜치 → develop → 릴리스.

## 운영

**처음 설정**(새 저장소에 배포할 때 한 번):

1. 저장소를 GitHub에 push한다.
2. `Settings → Pages → Build and deployment`: Source **Deploy from a branch**, Branch `gh-pages` `/ (root)`
   (브랜치는 첫 워크플로 실행 뒤 생긴다).
3. `Settings → Actions → General → Workflow permissions`: **Read and write permissions**
   (워크플로의 `permissions: contents: write`로도 되지만, 조직·레포 기본값이 read-only면 여기서 풀어야 한다).
4. `Actions → Aggregate tech news → Run workflow`로 첫 수집을 돌린다. 끝나면 Pages URL
   `https://<사용자명>.github.io/<레포명>/`에 대시보드가 보인다.

**예약 실행**: `update.yml` cron `0 0,6,12,18 * * *`(KST 09·15·21·03시). 기본 브랜치 `master`의 파일로 돈다.
실제로는 수 시간 늦게 시작하고 하루 2~4회 실행된다(RULE14). 실행이 겹치면 `concurrency: aggregate`로 줄을 선다.

**수동 실행**: `gh workflow run update.yml --repo Berry3536/news-radar --ref master`
(또는 `Actions → Aggregate tech news → Run workflow`). 다른 브랜치로 돌리면 릴리스 안 된 설정이 공개 배포본이 되므로
`master`로만 돌린다.

**상태 확인**:

```powershell
gh run list --repo Berry3536/news-radar --workflow update.yml --limit 5
gh run view <run-id> --repo Berry3536/news-radar --log | Select-String '\[(OK|FAIL|WARN|ERROR|DONE)'
git fetch origin gh-pages; git show origin/gh-pages:data.json | Select-Object -First 2    # generated_at
```

**예약 수집이 멈췄을 때 확인할 곳**:

1. 워크플로 상태: `gh workflow list --repo Berry3536/news-radar --all`에서 `Aggregate tech news`가 `active`인지.
   `disabled_inactivity`면 60일 비활성(아래), `disabled_manually`면 누군가 끈 것.
2. 마지막 run의 실패 단계: `gh run view <run-id> --repo Berry3536/news-radar --log-failed`.
   - `Install dependencies`: `uv.lock`과 `pyproject.toml` 불일치(`uv sync --locked`). develop에서 `uv lock` 후 릴리스.
   - `Aggregate feeds`: `feeds.json` 로드 실패(`[ERROR]`). 직전 배포본이 남아 있다. `feeds.json`을 고쳐 핫픽스.
   - `Publish to gh-pages`: 쓰기 권한. 처음 설정 3번을 확인.
3. run은 성공했는데 화면이 그대로: `gh run list --repo Berry3536/news-radar --workflow pages-build-deployment --limit 3`,
   `Settings → Pages` 소스가 `gh-pages` `/ (root)`인지.
4. 카테고리가 비거나 줄었음: 로그의 `[FAIL]`과 `0 entries` 피드를 찾아 `feeds.json` URL을 바꾼다.

**60일 비활성으로 꺼졌을 때**: 공개 레포에서 60일간 저장소 활동이 없으면 GitHub가 예약 워크플로를 끈다.

```powershell
gh workflow enable update.yml --repo Berry3536/news-radar
gh workflow run update.yml --repo Berry3536/news-radar --ref master
```

(또는 `Actions → Aggregate tech news → Enable workflow`.) 다시 켠 뒤 수동 실행 1회로 배포본을 갱신한다.
워크플로의 `gh-pages` push나 Dependabot 자동 머지가 "활동"으로 잡히는지는 확인되지 않았다(ROADMAP GATE0 관찰).

**정지**: `gh workflow disable update.yml --repo Berry3536/news-radar`. 배포본은 마지막 상태로 남는다.
대시보드까지 내리려면 `Settings → Pages`에서 끈다.

**복구**: 배포본을 손으로 고치지 않는다(RULE2). 원인을 `master`에 넣은 뒤(핫픽스) 수동 실행으로 덮어쓴다.
일시적인 피드 문제는 다음 예약 실행이 덮는다.

## 릴리스와 핫픽스

- 버전은 `pyproject.toml` `version` 한 곳(`kit.json` `release.version_file`). 릴리스 노트 파일은 없고(`notes_file: null`)
  GitHub Release 본문을 stark-kit 릴리스 노트 템플릿으로 쓴다.
- 빌드 산출물이 없다. 릴리스 = `master` 머지 + 태그 `vX.Y.Z` + GitHub Release.
- `master` 머지가 곧 운영 반영이다. 예약 워크플로(`update.yml`, `dependabot-merge.yml`)는 `master` 사본으로 돌므로
  `feeds.json`·`aggregate.py`·`index.html`·워크플로 변경은 릴리스 뒤 다음 실행부터 쓰인다. 머지 직후 QA1로 확인한다.
- 핫픽스(`hotfix/X.Y.Z`, `master`에서): 배포 중인 수집·화면이 깨졌을 때. 피드 하나가 죽어도 나머지는 계속 수집되므로(RULE4)
  급하지 않으면 다음 릴리스에 넣는다.
- 시크릿: `update.yml`은 `GITHUB_TOKEN`만 쓴다. `DEPENDABOT_MERGE_TOKEN`(소유자 fine-grained PAT)은 `dependabot-merge.yml` 전용.
  저장소 설정 두 가지가 운영에 필요하다: Pages 소스 `gh-pages`, Actions 쓰기 권한.

## QA

자동: CI(ruff · `py_compile` · pytest 16개 · `feeds.json` 파싱), develop·master push와 PR마다.

수동(릴리스 머지 뒤):

| QA | 확인 | 통과 기준 |
|---|---|---|
| QA1 | `master`로 수동 실행 1회(`gh workflow run update.yml --repo Berry3536/news-radar --ref master`) | run 성공, 로그 `[FAIL]` 0(있으면 원인 기록), `[DONE] 총 N건`의 N > 0 |
| QA2 | Pages 대시보드 | pages-build-deployment 성공, 카테고리 칩 5개, "last sync"가 QA1 실행 시각(DEFECT1이 열려 있는 동안은 지역 시간으로 읽는다), 검색어 입력 시 목록이 줄어든다 |
| QA3 | `feeds.json`을 바꾼 릴리스만 | 새·바뀐 피드가 QA1 로그에 `[OK]`이고 entry가 0이 아니다 |

## 릴리스 이력

| 버전 | 날짜 | 상태 | 내용 |
|---|---|---|---|
| v1.0.1 | 2026-11-03 | published | 정비 릴리스: 수집 로직 테스트 16개, Dependabot 자동 머지 워크플로, 개발 도구 갱신(setup-uv 10.3.3, ruff 0.17.3, pytest 9.2.0). 대시보드·수집 방식은 v1.0.0과 같다 |
| v1.0.0 | 2026-10-14 | 태그만(GitHub Release 없음) | 첫 릴리스: `gh-pages` 배포 전환(RULE1·RULE2), uv·단독 CI, stark-kit 도입 |
