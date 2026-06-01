# 기술뉴스 레이더 (Tech News Radar)

전기차 · 배터리 · 모터 · 로봇 · AI 분야의 RSS를 **GitHub Actions가 주기적으로 수집**해
**GitHub Pages**가 정적 페이지로 보여주는 **무료 · 서버리스** 개인용 대시보드.
백엔드/DB가 없으며, 운영은 `feeds.json` 한 파일만 고치면 된다.

## 아키텍처

```
┌─────────────────────┐   cron (00/06/12/18 UTC)   ┌──────────────────┐
│  GitHub Actions      │ ─────────────────────────▶ │  aggregate.py     │
│  (.github/workflows) │                            │  feedparser로 수집 │
└─────────────────────┘                            └────────┬─────────┘
            ▲                                                │ 생성
            │ commit & push (변경 시에만)                      ▼
            │                                          ┌──────────────┐
            └──────────────────────────────────────── │  data.json    │
                                                       └──────┬───────┘
                                                              │ fetch
                  ┌────────────────────────────┐              ▼
   브라우저 ◀───── │  GitHub Pages (index.html)   │ ◀───── data.json 서빙
                  └────────────────────────────┘
```

`GitHub Actions(cron)` → `aggregate.py` 실행 → `data.json` 생성/커밋 → `GitHub Pages`가
`index.html` + `data.json` 서빙.

## 파일 구조

```
.
├── feeds.json                  # 소스/카테고리/필터 설정 (운영 시 이 파일만 수정)
├── aggregate.py                # 수집기 (Python 3.12, feedparser)
├── requirements.txt            # feedparser
├── data.json                   # 수집 결과(자동 생성·커밋). 초기엔 (샘플) 데이터
├── index.html                  # 단일 파일 대시보드 (외부 JS 의존성 없음)
└── .github/workflows/update.yml# 스케줄 수집 워크플로
```

## 배포 절차

1. **레포 push** — 이 디렉터리를 GitHub 저장소에 올린다.
2. **Pages 켜기** — `Settings → Pages → Build and deployment`
   - Source: **Deploy from a branch**
   - Branch: 기본 브랜치(`main`/`master`) `/ (root)` 선택 후 저장
3. **Actions write 권한** — `Settings → Actions → General → Workflow permissions`
   에서 **Read and write permissions** 선택(워크플로의 `permissions: contents: write`로도
   커버되지만, 조직/레포 기본값이 read-only면 여기서 풀어줘야 함).
4. **수동 1회 실행** — `Actions → Aggregate tech news → Run workflow`로 첫 수집 실행.
   완료되면 `data.json`이 실제 데이터로 갱신되고, Pages URL에서 대시보드가 보인다.

> Pages URL: `https://<사용자명>.github.io/<레포명>/`

## feeds.json 커스터마이징

```jsonc
{
  "max_age_days": 14,            // 이보다 오래된 항목 제외(날짜 미상은 유지)
  "max_items_per_category": 40,  // 카테고리당 최대 노출 수
  "categories": [
    {
      "key": "battery",          // 내부 식별자(고유)
      "label": "배터리",          // 화면 표시명
      "include_keywords": ["battery", "배터리", "리튬"],  // 비면 전부 통과
      "exclude_keywords": [],    // 걸리면 제외
      "feeds": [
        { "name": "Electrek", "url": "https://electrek.co/feed/" }
      ]
    }
  ]
}
```

**필터 규칙**

- `include_keywords`가 **비어 있으면 전부 통과**. 값이 있으면 **제목+요약에 하나라도 포함**돼야 통과.
- `exclude_keywords`에 **하나라도 걸리면 제외**.
- 대소문자는 무시한다.
- **같은 피드 URL을 여러 카테고리에 넣고**, 각 카테고리의 키워드로 분리하는 패턴을 권장한다.
  (예: Electrek 피드를 `전기차`·`배터리`·`모터`에 모두 넣고 각 카테고리 키워드로 갈라내기 —
  실제 `feeds.json`이 이 방식으로 구성돼 있다.)

## 동작/한계 · 주의사항

- **scheduled cron은 정시를 보장하지 않는다.** GitHub의 부하에 따라 **수 분~수십 분 지연되거나
  스킵**될 수 있다. 정확한 타이밍이 필요한 용도에는 부적합하다.
- **60일간 저장소 활동이 없으면 scheduled 워크플로가 자동 비활성화**된다. 가끔 커밋이 일어나면
  유지되지만, 비활성화되면 Actions 탭에서 다시 켜야 한다.
- **피드 URL은 바뀌거나 죽을 수 있다.** 수집기는 피드 단위로 예외를 격리해, 죽은 피드 하나가
  전체 수집을 막지 않는다. 실패는 로그에 `[FAIL]`, 성공은 `[OK]`로 남는다.
- **RSS/Atom이 없는 소스는 수집 불가.** 본 도구는 피드만 처리하며, 스크래핑은 하지 않는다.
- 의존성은 Python의 `feedparser` 하나, 프런트는 외부 JS 라이브러리 없이 단일 HTML이다.

## 로컬 실행/검증

```bash
pip install -r requirements.txt
python aggregate.py            # data.json 생성 (네트워크 필요)
python -m http.server          # http://localhost:8000 에서 index.html 확인
```

네트워크가 막힌 환경이라면 `data.json`(샘플)만으로도 `index.html` 렌더링을 확인할 수 있다.
