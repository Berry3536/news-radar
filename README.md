# 테크 노트 (Tech Note)

AI · 반도체 · 자동차(전기차·자율주행·내연기관·국제 규제) · 배터리 · 로봇 분야의 RSS를 **GitHub Actions가 주기적으로 수집**해
**GitHub Pages**가 정적 페이지로 보여주는 **무료 · 서버리스** 개인용 대시보드(저장소 이름은 `news-radar`).
백엔드/DB가 없으며, 운영은 `feeds.json` 한 파일만 고치면 된다.

화면은 분야 칩, 제목·출처 검색, 분야별 기사 열(최신순)과 마지막 수집 시각(UTC)으로 되어 있다. 시스템 글꼴만 쓰며
`data.json` 말고 외부 요청을 하지 않는다. 화면 구성은 [docs/DESIGN.md](docs/DESIGN.md)의 "구조".

## 아키텍처

`GitHub Actions(cron)` → `aggregate.py` 실행 → `index.html` + `data.json`을 `gh-pages` 브랜치(커밋 1개,
`master`에서 성공한 실행마다 덮어씀)로 push → `GitHub Pages`가 `gh-pages`를 서빙. `master`/`develop`에는 봇 커밋이 남지 않는다.

구성도, 파일 구조, `feeds.json`·`data.json` 형식은 [docs/DESIGN.md](docs/DESIGN.md).

## 배포 절차

처음 배포 설정(Pages 켜기, Actions 쓰기 권한, 첫 수동 실행)은 [docs/RUNBOOK.md](docs/RUNBOOK.md)의 "운영 → 처음 설정".

## feeds.json 커스터마이징

```jsonc
{
  "max_age_days": 14,            // 이보다 오래된 항목 제외(날짜 미상은 유지)
  "max_items_per_category": 40,  // 카테고리당 최대 노출 수
  "max_items_per_feed": 8,       // 카테고리 안에서 피드 하나의 최대 노출 수
  "feed_timeout_seconds": 30,    // 피드 요청 타임아웃(초, 0보다 큰 정수), 넘으면 그 피드만 건너뜀
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

필터·기간·중복 제거의 정확한 규칙은 [docs/RULES.md](docs/RULES.md)의 RULE5~RULE8.
카테고리마다 **그 주제의 피드**(전문 매체, 또는 매체의 주제별 RSS)를 넣는 것을 기본으로 하고, 여러 주제가 섞인
피드는 `include_keywords`로 거른다(예: `배터리`의 더구루·디일렉 전체 기사). 글이 많은 피드 하나가 카테고리를 덮지
않도록 피드별 상한 `max_items_per_feed`가 걸린다(RULE8).

고친 뒤에는 `uv run python aggregate.py --check`로 형식을 검사한다(네트워크 없음). 키 오타·빠진 키·잘못된 값이 하나라도
있으면 수집하지 않고 틀린 곳을 모두 `[ERROR]`로 알린다([docs/RULES.md](docs/RULES.md)의 RULE17).

## 동작/한계 · 주의사항

예약 수집은 정시를 보장하지 않고, 60일간 저장소 활동이 없으면 꺼질 수 있으며, RSS/Atom이 있는 소스만 수집한다.
죽은 피드 하나는 전체 수집을 막지 않는다. 자세한 내용은 [docs/DESIGN.md](docs/DESIGN.md)의 "알려진 한계",
확인·재활성 절차는 [docs/RUNBOOK.md](docs/RUNBOOK.md)의 "운영".

## 로컬 실행/검증

```bash
uv sync                        # .venv 생성 (Python 3.13, uv.lock 기준)
uv run python aggregate.py     # data.json 생성 (네트워크 필요)
uv run python -m http.server   # http://localhost:8000 에서 index.html 확인
```

`data.json`은 git에서 추적하지 않는다. 네트워크가 막힌 환경이라면 `gh-pages` 브랜치의 `data.json`을
받아(`git show origin/gh-pages:data.json > data.json`) 렌더링을 확인한다. 테스트·검사 명령 전체는
[docs/RUNBOOK.md](docs/RUNBOOK.md)의 "개발".

## 문서

| 문서 | 내용 |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | 제품이 무엇인가: 범위, 구성도와 파일 구조, 데이터 형식, 오류 처리, 알려진 한계 |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | 어떻게 돌리나: 개발·검증, 처음 설정·수동 실행·상태 확인, 릴리스, 릴리스 이력 |
| [docs/RULES.md](docs/RULES.md) | 제품이 항상 지키는 것(배포 위치, 필터·날짜·중복 제거 규칙, 안 하기로 한 것) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 진행 상태: 게이트, 결함, 게이트 리뷰 기록 |
