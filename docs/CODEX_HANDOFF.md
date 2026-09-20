# Career OS — 개발 인수인계

> 새 세션은 이 문서부터 읽는다.
>
> ```
> Read docs/CODEX_HANDOFF.md and follow its instructions.
> ```

---

## 1. Before touching code

```
1. Read README.md
2. Read docs/PRODUCT.md
3. Read docs/FEATURES.md
4. Read docs/USER_FLOW.md
5. Read docs/DESIGN.md
6. Read docs/DATA_MODEL.md
7. Read docs/CURRENT_STATE.md
8. Read docs/ROADMAP.md

Then inspect the actual repository.

Documentation describes product intent.
Actual code describes current implementation.

Never assume a planned feature already exists.
Never rewrite working functionality merely to match documentation.
Implement one phase at a time, then stop.
```

---

## 2. 지금 상태

```
저장소   /Users/hyun/Documents/career-os
원격     https://github.com/nocked115/career-os
브랜치   main

완료     PHASE 0 ~ 5.5 · PHASE 5.6 캘린더 (routers/calendar.py)
         배포 — 컨테이너 하나 · Basic Auth · 읽기 전용 · 공개 데모
         (Dockerfile · app/auth.py · docs/DEPLOY.md)
미정     PHASE 6 LLM 도입 — Agent 는 아직 키워드 기반 (docs/AGENT.md)
```

Phase 5.6 이후 커밋은 Phase 번호 대신 `45: ...` 처럼 일련번호를 단다.
ROADMAP.md 의 진행 표시가 이 상태를 따라오지 못했을 수 있으니,
다음 작업을 정하기 전에 `git log` 와 코드를 먼저 볼 것.

### 왜 Reset 을 했는가

세션마다 Learning, 공고, Agent, 자소서, Experience Bank, Portfolio,
자동화가 하나씩 추가되면서 각각은 좋았지만
**"이 앱을 켜면 나는 무엇을 하게 되는가"** 가 흐려졌다.

Mission 번호 체계를 Phase 로 바꾸고, 제품 정의를 다시 고정했다.
기존 코드는 버리지 않는다. **현재 구현된 기반**으로 취급한다.

---

## 3. 문서 지도

| 문서 | 답하는 질문 |
|---|---|
| [../README.md](../README.md) | 이게 뭔가 |
| [PRODUCT.md](PRODUCT.md) | 왜 만드는가 · 북극성 · 추천 철학 |
| [FEATURES.md](FEATURES.md) | 무엇을 만드는가 (기능별 6단 명세 + 상태 배지) |
| [USER_FLOW.md](USER_FLOW.md) | 기능이 어떻게 연결되는가 |
| [LEARNING.md](LEARNING.md) | My Learning Library · Path · Session · Progress |
| [OPPORTUNITIES.md](OPPORTUNITIES.md) | 수집 · 매칭 · 시장 신호 · JD 분석 |
| [APPLICATIONS.md](APPLICATIONS.md) | Experience Bank · Portfolio · 지원 · 자소서 |
| [AGENT.md](AGENT.md) | Career Agent 의 역할과 한계 |
| [DESIGN.md](DESIGN.md) | Career Universe · 화면 설계 |
| [DATA_MODEL.md](DATA_MODEL.md) | 실제 테이블 vs 개념 모델 |
| **[CURRENT_STATE.md](CURRENT_STATE.md)** | **지금 실제로 코드에 있는 것** |
| [ROADMAP.md](ROADMAP.md) | 어떤 순서로 만드는가 |
| [DEPLOY.md](DEPLOY.md) | 배포 · 환경변수 · 데이터 옮기기 |
| [DECISIONS.md](DECISIONS.md) | 왜 그렇게 정했고 무엇을 포기했는가 |
| [REVIEW.md](REVIEW.md) | 외부 검토용 안내 |

### 가장 중요한 구분

```
PRODUCT.md / FEATURES.md      최종적으로 만들고 싶은 것
CURRENT_STATE.md              지금 실제로 만들어진 것
```

이 둘을 섞지 않는 것이 이 문서 세트의 존재 이유다.
**여기 적힌 것과 코드가 다르면 코드가 맞다.**

---

## 4. 코드 지도

```
backend/app/
  models.py              실제 테이블
  schemas.py             검증 규칙
  main.py                앱 기동 · 미들웨어 · 정적 화면 서빙 + 레거시 MVP 엔드포인트 (/agent 등)
  auth.py                Basic Auth · 읽기 전용 · 공개 데모 판정
  demo.py                데모 데이터 시드 (CAREER_OS_SEED_DEMO)
  routers/               신규 엔드포인트 (today · calendar · transfer · certificates 등)
  services/              계산 로직 — 단일 출처
    priority.py            학습 우선순위
    learning.py            학습 진행률 / Learning Session
    opportunity.py         기회 수집 / 매칭 점수
    market.py              시장 신호 / 스냅샷
    evidence.py            증거 집계 (홈의 별 개수)
    transfer.py            내보내기 / 불러오기
    …                      today · calendar · review · profile 등 라우터별 모듈
  collectors/            수집원 어댑터 (mock · 사람인)
  agents/                Career Agent + 도구
  automation.py          파이프라인
  scheduler.py           APScheduler
  collector.py           레거시 Job 수집기 (아직 남아있음)

backend/
  alembic/versions/      마이그레이션 0001~0019 (head: 0019_certificates)
  tests/                 539 passed · 1 skipped

frontend/src/
  App.jsx                화면 셸 (해시 라우팅으로 화면을 고른다)
  router.js              해시 라우터 (react-router 없음)
  api.js                 API 접근 단일 출처
  components/            화면별 페이지 · CareerCompanion 등
```

---

## 5. 작업 전 확인

```bash
cd backend

./.venv/bin/alembic check      # "No new upgrade operations detected."
./.venv/bin/alembic current    # 0019_certificates (head)
./.venv/bin/pytest -q          # 539 passed, 1 skipped

cd ../frontend
npm run lint                   # oxlint
VITE_API_BASE_URL="" npm run build
```

`VITE_API_BASE_URL=""` 는 배포처럼 같은 출처로 API 를 부르게 한다
(`Dockerfile` 과 같다). 비우지 않으면 `http://127.0.0.1:8000` 을 쓴다.

모두 통과하지 않으면 작업을 시작하지 말고 원인을 먼저 찾는다.

venv 가 없으면 만든다. 저장소에 포함되지 않는다.

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
```

프로젝트 디렉터리를 옮기면 `.venv/bin/` 의 shebang 이 옛 경로를 가리켜
`bad interpreter` 오류가 난다. 이때도 venv 를 다시 만든다.

---

## 6. 실행

```bash
# 백엔드
cd backend
./.venv/bin/alembic upgrade head      # 스키마는 Alembic 이 만든다
./.venv/bin/uvicorn app.main:app --reload

# 프런트
cd frontend
npm install && npm run dev
```

```
API     http://127.0.0.1:8000
문서    http://127.0.0.1:8000/docs
화면    http://localhost:5173
```

---

## 7. 규칙

### 절대 하지 말 것

```
❌ 동작하는 기능을 문서에 맞추려고 다시 쓰기
❌ 코드를 읽지 않고 수정하기
❌ 한 번에 여러 Phase 진행하기
❌ Phase 가 끝났다고 자동으로 다음 Phase 시작하기
❌ 마이그레이션 없이 모델 바꾸기
❌ 우선순위 계산을 새로 만들기 — services/priority.py 를 쓸 것
❌ 경험이나 통계를 지어내기
❌ 비교할 과거 없이 추세 화살표 그리기
❌ 개념 모델을 그대로 테이블로 옮기기
```

### 반드시 할 것

```
✅ 수정 전에 해당 파일을 읽는다
✅ 모델을 바꾸면 마이그레이션을 만든다
✅ 변경 후 테스트를 돌린다
✅ 한 Phase 만 하고 멈춘다
✅ 기존 엔드포인트의 응답 형태를 유지한다 (프런트가 읽고 있다)
✅ 문서의 구현 상태 배지와 CURRENT_STATE.md 를 갱신한다
```

### 새 기능을 넣기 전 필터

```
이 기능은 DISCOVER / DECIDE / LEARN / BUILD / PROVE / APPLY
중 어디에 속하는가?
            ↓
Today's Action 을 더 잘 결정하게 만드는가?
            ↓
      YES → 검토      NO → Backlog
```

---

## 8. 변경 후 체크리스트

```
□ 관련 파일을 수정 전에 읽었다
□ 모델을 바꿨다면 마이그레이션을 만들었다
□ alembic check 가 통과한다
□ pytest 가 통과한다
□ 기존 API 응답 형태를 깨지 않았다
□ 프런트엔드가 읽는 키를 유지했다
   (skill · my_level · total_demand · demand_count 등 —
    바꾸기 전에 frontend/src 에서 키 이름을 grep 할 것)
□ 대시보드가 여전히 뜬다
□ 새 기능에 테스트를 추가했다
□ FEATURES.md 배지와 CURRENT_STATE.md 를 갱신했다
□ 커밋하지 않고 사용자에게 결과를 보여줬다
```

---

## 9. 자주 걸리는 함정

| 함정 | 설명 |
|---|---|
| `create_all` 을 다시 넣기 | 마이그레이션과 충돌한다. 제거된 것이 의도다 |
| 우선순위 계산을 새로 짜기 | 한 번 4개로 갈라져 버그가 났다. `services/priority.py` 를 쓸 것 |
| `Job` 을 지우고 `Opportunity` 로 갈아타기 | 대시보드와 수집기가 `Job` 을 쓴다. `legacy_job_id` 로 병행 중 |
| 응답 키 이름 바꾸기 | `components/` 의 화면들이 직접 읽는다. 레거시 엔드포인트는 `test_legacy_endpoints.py` 가 잡아준다 |
| `App.css` 갈아엎기 | 이미 목표 톤에 부합한다. 확장할 것 |
| 모델 생성 시 필드를 하나씩 나열 | 세 번 같은 버그가 났다. 반드시 `**payload.model_dump()` |
| ALTER 로 텍스트 컬럼 추가할 때 `server_default` 누락 | 기존 행이 NULL 이 되고 응답이 500 으로 죽는다 (unit_label · results) |
| 시간 입력에 `Query(ge=..., le=...)` 누락 | 음수 분짜리 태스크가 계획에 들어간다 |
| `hidden` 속성으로 화면 숨기기 | `display: grid` 가 덮는다. `[hidden]` 규칙이 CSS 에 있다 |
| 수집원을 비즈니스 로직에서 직접 부르기 | `collectors/` 레지스트리를 통할 것 |
| 스냅샷 없이 추세 그리기 | 비교할 과거가 없으면 `unknown` 이다 |
| `LearningResource.url` 이 있다고 가정하기 | 이미 nullable 이다 (종이책 등). 링크로 렌더링하는 화면은 URL 없는 자료를 처리해야 한다 |

---

## 10. 다음 작업

PHASE 2 (LEARNING) 는 끝났다 — `LearningResource.url` 은 nullable 이고,
부분 단위(`LearningResourceSegment`)도 있다.

다음 작업은 이 문서에 고정하지 않는다. [ROADMAP.md](ROADMAP.md) 와
[CURRENT_STATE.md](CURRENT_STATE.md) 를 읽되, 2장의 상태와 `git log` 로
실제로 끝난 것을 먼저 확인하고 사용자에게 무엇을 할지 묻는다.
남은 큰 결정은 PHASE 6 의 LLM 도입 여부다.

시작 전에 5장의 확인 절차를 먼저 돌릴 것.
