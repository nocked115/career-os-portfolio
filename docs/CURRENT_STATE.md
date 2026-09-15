# Career OS — 현재 상태

> ## 이 문서의 역할
>
> **지금 실제로 코드로 존재하는 것만** 적는다.
> 만들고 싶은 것은 [PRODUCT.md](PRODUCT.md) 와 [FEATURES.md](FEATURES.md) 에 있다.
>
> 이 둘을 섞지 않는 것이 이 문서의 존재 이유다.
> "이거 만들었었나, 만들려고 했던 건가?" 를 없애기 위한 문서다.
>
> 코드를 바꾸면 이 문서도 같이 고친다.
> 여기 적힌 것과 코드가 다르면 **코드가 맞다.**

기준 커밋: `11d8fff` (45) · 브랜치 `main`

---

## 1. 한눈에

```
백엔드    FastAPI + SQLAlchemy + SQLite,  Alembic 으로 스키마 관리
프런트    React 19 + Vite,  해시 라우터(직접 구현),  사이드바 + 작업 화면 10개 + 홈
테스트    540개 (539 통과 · 1 건너뜀)
API       155개 오퍼레이션 / 113개 경로  (OpenAPI 기준)
모델      21개 + 연결 테이블 6개 = 27개 테이블
마이그레이션  0001 ~ 0019
```

**모든 영역에 화면이 있다.** 다만 레거시 대시보드용 엔드포인트
(`/today` · `/weekly-plan` · `/analytics/learning-priority` · `/jobs`)는
`main.py` 에 남아 있고, `App.jsx` 가 처음 뜰 때 아직 이것들을 부른다
(`api.js` 의 대시보드 로드, `OverviewPage` 가 `weeklyPlan` 을 받는다).

---

## 2. 아키텍처

```
frontend/src/
  App.jsx            324줄. 해시 경로 → 화면 선택
  router.js          해시 라우터 (react-router 없음)
  api.js             API 접근 단일 출처
  readOnly.js        읽기 전용 배포본 여부를 화면에 알린다
  format.js          분 · 영역 · 중요도 한국어 표기
  components/
    ui.jsx           공용 조각 — Button · LoadingState · ErrorState · EmptyState
                     ProgressBar · StatusBadge · NextActionCard · WhyPanel
                     ConfirmButton · Notice
    Universe.jsx  Sidebar.jsx  CareerCompanion.jsx
    TodayPage.jsx  TodayFocus.jsx  WhyPlanPage.jsx  OverviewPage.jsx
    CalendarPage.jsx  LearningPage.jsx  LearningSession.jsx
    LibraryPanel.jsx  LibraryShelf.jsx  LibraryToday.jsx
    ProjectsPage.jsx  OpportunitiesPage.jsx  OpportunityMap.jsx
    ApplicationsPage.jsx  ApplicationWorkspace.jsx  CoverLetterPanel.jsx
    ProofPage.jsx  CertificatesCard.jsx  ProfileHeader.jsx
    ReviewPage.jsx  ActivityGrid.jsx  DemoBanner.jsx
        │
        │ HTTP / JSON   (VITE_API_BASE_URL, 기본 127.0.0.1:8000)
        ▼
backend/app/
  main.py            레거시 MVP 엔드포인트 + 라우터 등록 + 화면 서빙
  auth.py            Basic Auth · 읽기 전용 · 공개 데모
  routers/           HTTP 만
    learning  library  opportunities  experiences  applications
    workspace  market  evidence  proof  target_careers  today
    profile  universe  calendar  transfer  review  certificates
    overview  _common
  services/          재사용 계산 로직 — 여기가 단일 출처다
    priority.py      학습 우선순위
    learning.py      학습 진행률 / Learning Session
    opportunity.py   기회 수집 / 매칭 점수
    opportunity_map.py  기회 한 건의 요구 스킬 지도
    posting_parser.py   붙여넣은 공고 → 칸 (규칙 기반, URL 을 열지 않음)
    market.py        시장 신호 / 스냅샷
    evidence.py      증거 집계 (홈의 별 개수)
    today.py         오늘 계획 생성 / 완료 / 이월
    why.py           판단 근거 모음
    library.py       내 자료 / Resource Selector / 서가 · HOT
    proof.py         증거화 제안 / 전환 / 이력서 문장
    jd.py            JD 분석 / 경험 자동 매칭
    application.py   상태 전이 / 자소서 구조 · 점검
    application_board.py  지원서 보드
    calendar.py      일정 · 빈 시간 · 월/주/일
    profile.py  certificates.py
    universe.py  overview.py  review.py  transfer.py
  collectors/        수집원 어댑터 (소스 독립)
    base.py  mock.py  saramin.py  __init__.py
  agents/            Career Agent + 도구
  automation.py      파이프라인
  scheduler.py       APScheduler (매일 08:00)
  demo.py            데모 데이터 시드
  models.py  schemas.py  database.py  collector.py(레거시)
        │
        ▼
  alembic/           마이그레이션 — 스키마의 소유자
        ▼
  SQLite (career_os.db)
```

### 구조 원칙 (지금 지켜지고 있는 것)

1. **계산 로직은 `services/` 에 한 번만.**
   우선순위 계산이 4곳에 복사돼 서로 다른 값을 내던 버그가 있었고,
   Mission 021 에서 통합했다. 새 계산 지점을 만들지 않는다.
2. **스키마는 Alembic 이 소유한다.** `create_all` 은 제거됐다.
3. **비즈니스 로직은 수집원을 알지 못한다.** `collectors/` 레지스트리를 통한다.
4. **레거시 엔드포인트는 `main.py` 에 두고 건드리지 않는다.**
   신규는 `routers/` 로 분리한다.

---

## 3. 데이터 모델 — 실제 테이블

### 레거시 MVP

```
skills              name(unique) · category · level(0~4) · status · aliases
projects            name(unique) · description · status · career_related
                    estimated_hours · progress_percent · daily_minutes
                    target_date(String) · github_url · demo_url · results
jobs                company · title · role · employment_type · url
                    deadline(String) · description · status
learning_resources  title · url · resource_type · duration_minutes
                    ownership · total_units · unit_label
                    importance · status · skill_id

project_skills · job_skills                        (M:N)
```

### Mission 021 — 학습 / 기회 / 경험 / 지원

```
learning_paths      title · status · progress_percent · target_date · skill_id
learning_steps      learning_path_id · title · description · position
                    status · estimated_minutes · completed_at
                    UNIQUE(learning_path_id, position)

opportunities       opportunity_type · title · organization · role
                    source · source_external_id · source_url · location
                    deadline(DateTime) · status · raw_payload
                    legacy_job_id · match_score · match_recommendation · scored_at
                    UNIQUE(source, source_external_id)

experiences         experience_type · title · organization · short_description
                    problem · role · actions · results · technologies
                    metrics · tags · start_date · end_date
                    github_url · blog_url · demo_url · project_id

portfolio_entries   title · problem · role · actions · results · technologies
                    github_url · demo_url · status · display_order
                    experience_id · project_id

applications        opportunity_id | legacy_job_id (하나는 필수)
                    status · deadline · job_analysis · notes · applied_at

application_experience_matches   match_score · match_notes
cover_letter_questions           question · character_limit · position
cover_letter_answers             draft · version · is_current

learning_step_resources · experience_skills        (M:N)
```

### Mission 023 — 기회 매칭 / 시장

```
market_snapshots    skill_id · opportunity_count · total_opportunities
                    percentage · captured_at

opportunity_skills                                 (M:N)
```

### 그 뒤에 추가된 것 (0005 ~ 0019)

```
target_careers          title · description · keywords · target_date · is_active
target_career_skills                               (M:N)
daily_plan_tasks        plan_date · position · task_type · title · minutes
                        reason · status · completed_at · carried_from
                        plan_available_minutes · plan_intensity
                        learning_step_id · project_id · learning_resource_id
                        application_id · opportunity_id
learning_resource_segments  (4.2b)
profiles                name · day_start_minute(기본 540) · day_end_minute(기본 1320)
                        daily_cap_minutes(기본 180) · github_url · blog_url
calendar_blocks         title · kind · weekday · date · start_minute · end_minute
                        all_day(0018) · note
skill_level_events      skill_id · from_level · to_level · source · note · changed_at
certificates            category(language · job) · name · score · detail · issuer
                        status(held · planned) · acquired_on · expires_on · note  (0019)
```

`certificates` 에는 **번호(자격번호 · 수험번호 · 등록번호) 칸이 없다.**
개인정보라 일부러 두지 않았다 (`models.py` 주석).

### 레거시 병행 구조

```
Job              레거시 엔드포인트(/jobs, /jobs/{id}/match)가 이걸 본다
  ▲
  │ legacy_job_id (1:1, nullable)
  │
Opportunity      수요 집계의 모수
```

`opportunity_type == "job"` 인 기회는 수집 시 레거시 `Job` 도 만들어 연결한다.
반대로 `Job` 으로 들어온 것도 `Opportunity` 에 남긴다 (`bridge_from_legacy_job`).
그 이전에 만들어진 `Job` 은 0013 마이그레이션이 옮겼다 — 수요를 두 테이블이
다르게 세던 문제 때문이다.

---

## 4. 동작하는 기능

### 4.0 Target Career

목표 직무. **모든 우선순위 계산의 기준점이다.**

- 활성은 한 번에 하나. 바꿔도 이전 목표를 지우지 않는다
- 스킬을 연결해 "이 직무가 요구하는 것" 을 정의한다
- `GET /target-careers/active` — 없으면 404 가 아니라 null.
  아직 정하지 않은 것은 오류가 아니다

### 4.1 학습 우선순위 — `services/priority.py`

**모든 우선순위 계산의 단일 출처.** API 와 Agent 가 같은 함수를 쓴다.

```
market_percentage  = round(요구 기회 수 / 모아둔 기회 수 × 100)
skill_gap          = max(0, 4 - 내 레벨)

project_strength   = 커리어 프로젝트 중 가장 멀리 간 것
                     만들기로 했다 0.10 · 만드는 중 0.25 · 만들었다 0.50
                     보여줄 수 있다 0.70 · 경험으로 남았다 0.85
learning_strength  = 0.4 × (학습 경로 진행률 / 100)
evidence_strength  = project + learning - project × learning   (상한 0.85)
evidence_weight    = max(0.15, 1 - evidence_strength)

target_weight      = 1.0 (목표 직무가 요구하는 스킬 · 목표 없음)
                   = 0.6 (목표는 있는데 무관한 스킬)

priority_score     = market_percentage × skill_gap
                     × evidence_weight × target_weight
```

목표 직무가 없으면 `target_weight` 가 전부 1.0 이라 이전과 결과가 같다.
무관한 스킬을 0 으로 만들지는 않는다 — 목표는 바뀔 수 있다.

학습은 프로젝트보다 약한 증거로 본다.
경로를 100% 끝내도 학습 쪽 세기는 0.4 라 완료한 프로젝트 하나(0.50)를 넘지 않는다.
0% 짜리 빈 프로젝트는 0.10 뿐이라, 만들기만 해서는 우선순위가 크게 내려가지 않는다.

### 4.2 학습 루프 — **닫혀 있다**

```
Learning Step 완료
  → Learning Path 진행률       스텝이 바뀔 때마다 자동
  → Skill Evidence             learning_strength 에 반영
  → Learning Priority          점수가 실제로 내려감
  → 다음 Today Plan            집중 스킬이 바뀜
```

`POST /learning-steps/{id}/complete` 는 무엇이 바뀌었는지를 같이 돌려준다 —
`progress_before` 와 `effects`, 다음 단계(`next_step`).

### 4.2b My Learning Library

**새 자료를 추천하지 않는다. 내가 이미 가진 것 중에서 고른다.**

`LearningResource` 가 곧 라이브러리 항목이다. 별도 모델을 만들지 않았다.
라이브러리 항목이 학습 단계에 연결되면 그게 곧 "오늘의 자료" 이기 때문이다.

```
url          nullable — 내가 가진 종이책에는 URL 이 없다
ownership    owned(가짐) · saved(저장함) · wishlist(사고 싶음)
total_units  전체 분량 (책이면 쪽수, 영상이면 길이)
unit_label   "쪽" · "분" 등
```

**Segment** — 오늘 실제로 소비하는 단위

```
learning_resource_segments
  label            "3장 — EC2 기초"
  start_ref/end_ref  페이지 범위 또는 타임스탬프
  estimated_minutes
  status           not_started · in_progress · completed
```

"책 한 권을 읽으세요" 가 아니라 "3장을 15분 읽으세요" 여야 한다.

조각이 전부 끝나면 자료 자체가 완료로 올라간다.

| 엔드포인트 | 설명 |
|---|---|
| `GET /library` | 요약 + 목록 + `hot` (type · ownership · skill 필터) |
| `POST /resources/{id}/shelf` | 서가 옮기기 (지금 학습 · 다음 학습 · 보류 …) |
| `POST /resources/{id}/add-to-plan` | 오늘 계획에 올리기 |
| `POST/GET /resources/{id}/segments` | 조각 추가 / 목록 |
| `PATCH/DELETE /segments/{id}` | 수정 / 삭제 |
| `POST /segments/{id}/complete` | 조각 완료 |
| `GET /library/selection` | 지금 쓸 자료 선별 |
| `GET /learning-steps/{id}/selection` | 단계별 **선별** |

### 4.2c Resource Selector

이 단계에 대해 **오늘 볼 것만** 고르고 **나머지는 치운다.**

```
정렬     중요도(primary → supplementary → deep_dive)
        같으면 소유(owned → saved → wishlist)
제외     이미 끝낸 조각
        예상 시간이 없는 자료 — 얼마나 걸릴지 모르면 계획이 거짓이 된다
        남은 시간으로 부족한 것
```

**치운 것을 함께 돌려준다.**

```
오늘 볼 것                                30분 / 예산 40분
[PRIMARY] AWS 완벽 가이드 · 3장 — EC2 기초   15분  (내가 가진 것 · 오프라인)
[PRIMARY] AWS 공식 문서 — EC2 개요          15분  (저장해둠)

나머지 자료 3개 → 지금은 볼 필요 없음
  EC2 인스턴스 실습 — 오늘 남은 시간(10분)으로는 부족합니다
```

**마지막 줄을 빼면 그냥 목록이다.** 치운 것을 보여주는 것까지가 선별이다.
(화면에서는 `PRIMARY` 대신 "핵심 · 보조 · 깊이 파기" 로 쓴다 — `format.js`)

### 4.3 Learning Session

`GET /learning-steps/{id}/session` 이 한 번에 준다.

| 구성 | 출처 |
|---|---|
| `why_now` | 저장된 공고 수 / 요구 공고 수 / 레벨 / 프로젝트 증거 / 학습 진행률 |
| `goals` | **단계 설명의 각 줄.** 설명에 없는 것은 만들지 않는다 |
| `materials` | 연결된 자료를 중요도(primary/supplementary/deep_dive)별로 |

공고가 없으면 "계산할 수 없습니다" 라고 말하고 수요를 지어내지 않는다.

### 4.4 기회 수집 — `collectors/` + `services/opportunity.py`

```
수집원 → fetch() → normalize() → Opportunity → 스킬 연결 → 레거시 Job 브릿지
```

- 수집원은 `SOURCE_NAME` / `is_available()` / `fetch()` / `normalize()` 만 노출
- `(source, source_external_id)` 로 upsert. 재수집해도 중복 없음
- 사용자가 바꾼 `status` 는 재수집이 덮어쓰지 않는다
- **등록된 수집원은 `mock` 과 `saramin` 둘이다**
  - `mock` 은 운영(`CAREER_OS_ENV=production`)에서 꺼진다
  - `saramin` 은 `SARAMIN_API_KEY` 가 있고 공개 데모가 아닐 때만 켜진다

**붙여넣기** — `POST /opportunities/parse` (`services/posting_parser.py`)

공고 사이트를 앱이 열지 않는다. 사람이 복사해 붙인 글에서 제목 · 마감 ·
요구 스킬 · 지원 자격을 규칙으로 찾아 **미리보기**로 돌려준다. 저장하지 않는다.
못 찾으면 비워 두고, 찾은 칸마다 근거가 된 줄을 같이 준다.
경력 N년 · 학위 · 어학 같은 걸림돌 표현은 따로 표시하되 충족 여부는 판단하지 않는다.

### 4.5 기회 매칭 점수

```
관련성          40   지금 우선순위가 높은 스킬을 요구하는가
                     (학습 우선순위를 읽으므로 Target Career 가 자동 반영된다)
준비도          30   요구 스킬 중 보유 비율
포트폴리오 가치  15   공모전·대외활동이거나 증거 없는 스킬인가
마감 실현 가능성 15   필요 시간을 알면 "하루 몇 시간" 으로,
                     모르면 남은 일수로 판단

70+  recommended    40~69  consider    40 미만  skip
마감 지남 → 점수와 무관하게 skip
```

**필요 시간** (`estimated_hours`) 을 알면 훨씬 정확해진다.

```
하루 1시간 이하 comfortable · 2시간 이하 workable
하루 4시간 이하 tight · 초과 unrealistic
```

**계획에 추가** — `POST /opportunities/{id}/add-to-plan`
지원서가 없으면 관심 상태로 만들고, 오늘 계획에 태스크를 올린다.
DISCOVER 가 북마크 목록으로 끝나지 않게 하는 연결이다.

`GET /opportunities/{id}/map` 은 이 공고 기준으로 스킬 → 공부 → 프로젝트 → 경험을 잇는다.

모든 판정에 근거가 붙는다. 추천할 게 없으면 빈 목록을 돌려준다.

### 4.6 시장 신호

- Opportunity 기반 집계
- 수집 때마다 `MarketSnapshot` 에 스킬별 한 줄
- 최근 두 스냅샷 비교 → `up` / `down` / `flat` / `unknown`
- **스냅샷이 하나뿐이면 `unknown`.** 비교할 과거 없이 화살표를 그리지 않는다
- 3포인트 미만 변화는 `flat`
- 순서는 id 기준 (SQLite 의 `CURRENT_TIMESTAMP` 는 초 단위)

### 4.6a Today Plan

**시스템이 오늘 할 일을 결정한다.** 사용자가 넣는 게 아니다.

```
학습 우선순위 + 학습 진행 + 프로젝트 진행
    + 마감 + 가용 시간 + 강도
        → Today Plan
```

후보 순서(중요도 순, `services/today.py` `build_candidates`):

```
1. 마감 임박   지원 준비 · 기회 마감 · 캘린더 마감 — 놓치면 되돌릴 수 없다
2. 이월        어제 못 한 것. 그냥 버리지 않는다 (수명을 넘기면 빠진다)
3. 학습        우선순위 1위 스킬의 다음 단계
4. 프로젝트    진행 중인 것. 스킬 순위와 무관하게 올라온다
```

강도:

| | 최대 개수 | 한 덩어리 | 자투리 하한 |
|---|---|---|---|
| 가볍게 | 2 | 30분 | 10분 |
| 보통 | 3 | 60분 | 15분 |
| 몰입 | 2 | 120분 | 45분 |

`min_block` 은 **남은 자투리 시간을 쓰지 않는다**는 뜻이다.
일이 짧다고 버리는 규칙이 아니다.

| 엔드포인트 | 설명 |
|---|---|
| `POST /today/plan` | 계획 생성. 이미 끝낸 일은 지우지 않는다 |
| `GET /today/plan` | 저장된 계획 (수명을 넘긴 이월은 `stale` 로 따로) |
| `GET /today/why` | 판단 근거 — 왜 이 계획인가 화면 |
| `GET /today/intensities` | 강도 목록 |
| `GET /today/deadlines` | 다가오는 마감 |
| `POST /today/tasks/{id}/complete` | 완료 — 실제 진행도까지 갱신하고 `effects` 를 돌려준다 |
| `POST /today/tasks/{id}/skip` | 넘김 — 이월되지 않는다 |
| `POST /today/tasks/{id}/revive` | 사흘 넘게 밀려 빠진 일을 "그래도 하겠다" 고 되살린다 |

**계획을 저장하는 이유**는 완료 체크와 미완료 이월 때문이다.
매번 계산해서 버리면 둘 다 할 수 없다.
계획을 만들 때 쓴 설정(시간·강도)도 함께 저장한다.
안 그러면 조회할 때 실제와 다른 "남은 시간" 이 나온다.

**모든 태스크에 이유가 붙는다.** 설명할 수 없으면 계획에 넣지 않는다.

### 4.6b 증거 집계

`GET /analytics/evidence` — 홈 화면의 별 개수.

```
완료한 학습 단계 · 완료한 프로젝트 · Experience · Portfolio · 떨어진 지원
```

총합과 구성을 함께 돌려준다. 0이면 0이다. 규칙은 DESIGN.md 4c.

### 4.6c PROVE — 활동을 증거로

프로젝트를 끝내도 아무 제안이 없으면 사용자는 그냥 잊는다.
**증거화는 자동 제안이 있어야 실제로 일어난다.**

```
Project 완료 → Experience Bank → Portfolio → Resume Bullet
```

| 엔드포인트 | 설명 |
|---|---|
| `GET /projects/{id}/evidence` | 무엇을 증명하는지 + 남은 행동 |
| `PATCH /projects/{id}` | 프로젝트 수정 |
| `POST /projects/{id}/to-experience` | Experience 로 전환 (내용 복사, 중복 안 만듦) |
| `POST /portfolio-entries/{id}/resume-bullet` | 이력서 문장 초안 |
| `GET /experiences/usage` | 경험마다 연결된 프로젝트 · 포트폴리오 · 매칭한 지원서 · 비어 있는 칸 |

**이력서 문장은 LLM 이 아니다.** 저장된 조각을 조립할 뿐이다.

```
{기술} 기반 {제목} — {행동} → {결과}
```

무엇을 했고 어떤 결과가 있었는지가 **둘 다 비어 있으면 문장을 만들지 않는다.**
"지어내지 않습니다" 라고 답하고, 무엇이 비었는지 알려준다.

### 4.6d APPLY — 보드 · JD 분석 · 상태 전이 · 자소서 지원

**LLM 이 아니다.** 등록된 스킬 이름(과 별칭)을 JD 본문에서 찾는다.
다만 기존 `collector.link_skills_from_description` 보다 정확하다.

```
기존:  "go" in description   → "Google" 에도 걸렸다
지금:  단어 경계 + 언급 횟수 + 첫 등장 위치로 강조도를 낸다
```

| 엔드포인트 | 설명 |
|---|---|
| `GET /applications/board` | 지원서 보드 — 다음에 할 한 가지부터 |
| `GET /applications/{id}/analysis` | 요구 역량 · 강조도 · 내 강약 · 추천 경험 |
| `POST /applications/{id}/auto-match` | 경험 매칭 점수를 자동 저장 (사람이 쓴 메모는 유지) |
| `GET /applications/{id}/transitions` | 지금 갈 수 있는 상태 |
| `POST /applications/{id}/move` | 상태 이동. 규칙 밖이면 409 + 한국어 사유, `force=true` 로 정정 |
| `GET /cover-letter-questions/{id}/outline` | 쓸 구조 (문장은 안 만든다) |
| `POST /cover-letter-questions/{id}/review` | 글자 수 · 근거 유무 점검 |

**상태 전이**

```
interested → preparing → ready → applied
                                    ├─ document_pass → interview → accepted
                                    └─ rejected                  └─ rejected
언제든 → withdrawn      accepted / rejected / withdrawn 은 끝
```

잘못 누른 것을 되돌릴 길로 `force=true` 를 남겼다.
409 의 사유는 "'준비 중' 에서는 … (으)로만 갈 수 있습니다" 처럼
상태 이름을 한국어로 바꿔 말한다 (`application.describe_transition`).

**할 수 없는 것을 명시한다**

```
분석    등록되지 않은 역량은 찾지 못한다 (notes 에 적는다)
추천    덮는 경험이 없으면 억지로 추천하지 않는다
구조    어떤 경험을 어떤 순서로 쓸지만 정한다. 문장은 만들지 않는다
점검    글자 수와 근거 유무만 본다. 문체·설득력은 판단하지 않는다
```

### 4.6e 캘린더 · 프로필 · 자격증

| 엔드포인트 | 설명 |
|---|---|
| `GET/POST /calendar/blocks` · `PATCH/DELETE /calendar/blocks/{id}` | 일정 (반복 요일 또는 날짜, 종일 · 마감 종류) |
| `GET /calendar/day` · `/week` · `/month` | 하루 빈 시간 / 주 / 월 한 장 |
| `PATCH /calendar/settings` | 활동 시간대 · 하루 상한 |
| `GET/PATCH /profile` | 이름 · 활동 시간대 · 하루 상한 · GitHub · 블로그 |
| `GET/POST /certificates` · `PATCH/DELETE /certificates/{id}` | 자격증 · 어학 (보유 · 준비 중, 만료일) |
| `GET /skills/{id}/level-events` | 스킬 레벨 변경 이력 |

오늘 제안 시간 = min(활동 시간대 − 일정, 하루 상한). 빈 시간을 그대로 쓰지 않는다.
마감 종류(`kind == "deadline"`) 일정은 오늘 계획의 마감 후보로 들어간다.

### 4.6f 홈 · 한눈에 보기 · 회고

| 엔드포인트 | 설명 |
|---|---|
| `GET /universe` | 홈 — 나 · 천체 6개(영어 이름 + 한국어) · `today.first_task` · 증거 |
| `GET /overview` | 한눈에 보기 — 계획 · 지원서 · 자격증 등 상태 |
| `GET /analytics/review` | 월 회고 — 계획 대비 실행(`execution`) · 미룬 것(`postponed`) · 다음 달(`next_month`) |
| `GET /analytics/review/trend` | 여러 달 추이 |
| `GET /analytics/activity` | 날짜별 한 일 (회고의 칸) |
| `GET /transfer/export` · `POST /transfer/import` | 27개 테이블 통째로 내보내기 / 불러오기 |

### 4.7 Career Agent

**LLM 이 아니다.** 키워드 부분문자열 매칭.

| intent | 트리거 | 동작 |
|---|---|---|
| `today` | 오늘, today, 할 일 | 우선순위 + 프로젝트 + 자료로 계획 |
| `learning` | 공부, 학습, 스킬 | 학습 우선순위 |
| `jobs` | 공고, 채용, 회사 | 공고 목록 |
| `projects` | 프로젝트, 진행률 | 진행 중 프로젝트 |
| `automation` | 업데이트, 동기화 | 파이프라인 실행 |
| `automation_status` | 자동화 + 상태/언제 | 스케줄러 상태 |
| `general` | 그 외 | 폴백 |

시간 추출: `"60분"` → 60, `"2시간"` → 120.

도구는 4개(`get_learning_priority` / `get_active_projects` /
`get_saved_resources` / `get_jobs`)이고 **레거시 모델만 본다** (`Job` · `Project` ·
`LearningResource` · 우선순위). Learning Path, Opportunity, Experience, Application 에는
접근하지 못한다.

화면의 캡슐(`CareerCompanion.jsx`)은 화면마다 역할 이름을 한국어로 바꾼다 —
오늘 계획 안내 · 상태 안내 · 시간 안내 · 학습 안내 · 프로젝트 안내 · 기회 안내 ·
경험 안내 · 지원서 안내 · 회고 안내. 설명하지 못하므로 "튜터" 라고 부르지 않는다.

### 4.8 자동화

```
매일 08:00 (APScheduler) 또는 POST /automation/run 또는 Agent
      ↓
수집원 실행 → Opportunity upsert → 스킬 연결 → 레거시 Job 브릿지
      ↓
기회 채점 → 시장 스냅샷 → career state 재계산
```

실행 상태(`last_run_at` / `last_status` / `last_error`)는 **메모리에만** 있다
(`scheduler.py` 의 `automation_status`). 서버를 재시작하면 초기화된다.

---

## 5. 화면

### 있는 것

경로는 해시(`#/…`)이고 사이드바가 작업 화면 10개를 잇는다. 작업 화면의 글자는 한국어다.

| 화면 | 경로 | 파일 | 내용 |
|---|---|---|---|
| Career Universe 홈 | `#/` | `Universe.jsx` | 나 · 천체(영어 + 한국어) · 들어가기 전 요약 · 오늘 첫 할 일 · 한눈에 보기 |
| 한눈에 보기 | `#/overview` | `OverviewPage.jsx` | 지금 상태 한 장 |
| 오늘 | `#/today` | `TodayPage.jsx` · `TodayFocus.jsx` | 쓸 수 있는 시간 · 핵심 초점 · 진행, 가장 먼저 할 일, 항목마다 영역 · 선택 이유 · 완료하면 |
| 왜 이 계획인가 | `#/today/why` | `WhyPlanPage.jsx` | 판단에 쓴 것(펼치면 원본 숫자) · 그래서 고른 것 · 한계 |
| 캘린더 | `#/calendar` | `CalendarPage.jsx` | 월 · 주 · 일, 종일 일정, 마감, 설정은 칸을 벗어날 때 저장 |
| 학습 | `#/learning` | `LearningPage.jsx` | 탭 넷(학습 경로 · 내 자료 · 세션 기록 · 진행과 레벨), 완료 피드백 |
| Learning Session | `#/learning/sessions/{id}` | `LearningSession.jsx` | 지금 볼 이유, 목표 체크, 선별된 자료, 시작/완료 |
| 내 자료 | `#/library` | `LibraryShelf.jsx` · `LibraryToday.jsx` · `LibraryPanel.jsx` | 서가 레일 · HOT · 지금 쓸 자료 · 안 해도 되는 자료 · 등록과 챕터 |
| 프로젝트 | `#/projects` | `ProjectsPage.jsx` | 진행 · 완료 시 증거로 이어짐 |
| 기회 | `#/opportunities` | `OpportunitiesPage.jsx` · `OpportunityMap.jsx` | 공고 붙여넣기, 지원 자격 표시, 매칭 · 마감 · 근거, 계획 추가, 시장 신호 |
| 지원서 | `#/applications` | `ApplicationsPage.jsx` | 보드 — 다음에 할 한 가지부터 |
| 워크스페이스 | `#/applications/{id}` | `ApplicationWorkspace.jsx` · `CoverLetterPanel.jsx` | 상태 흐름 · 다음 행동 · 자소서 · 추천 경험 · JD 분석 · 한계 |
| 경험 | `#/experience` | `ProofPage.jsx` · `ProfileHeader.jsx` · `CertificatesCard.jsx` | 증거의 별, 증거화 제안, Experience Bank, Portfolio, 사용처, 자격증 · 어학 |
| 회고 | `#/review` | `ReviewPage.jsx` · `ActivityGrid.jsx` | 날마다 칸, 계획 대비 실행, 미룬 것, 다음 달 |

공용 조각은 `ui.jsx` 한 곳에 있다. 읽기 전용 배포본이면 쓰기 버튼이 막힌다
(`readOnly.js` · `Button` 의 `writes`).

### 없는 것

```
외부 캘린더 · 학교 시간표 가져오기   일정은 손으로 넣는다
유튜브 재생목록 가져오기             영상 URL 은 카드에 붙일 수 있지만 목록 가져오기는 없다
```

### 프런트 이슈 — 해결됨

`src/index.css` 가 Vite 스타터 템플릿 그대로였고 세 가지 문제를 일으켰다.

1. **다크 모드에서 제목이 보이지 않았다.**
   템플릿이 `h1, h2` 색을 `#f3f4f6`(거의 흰색)으로 바꾸는데
   `App.css` 배경은 밝은 색(`#f5f6f8`)이라 제목이 배경에 묻혔다.
   OS 를 다크 모드로 쓰면 화면 제목이 전부 사라진 상태였다
2. `#root { text-align: center }` 가 새 화면의 목록을 가운데로 밀었다
3. `#root` 의 고정 폭과 `border-inline` 때문에 본문 좌우에 세로선이 그려졌다

최소 리셋으로 교체했다. 화면 디자인은 `App.css` 가 소유한다.

---

## 6. 테스트 — 540개

```
test_today_plan.py                40   계획 생성 · 강도 · 마감 · 이월 · 완료
test_opportunities.py             35   수집 upsert, 브릿지, 점수, 추천
test_workspace.py                 29   JD 분석 · 자동 매칭 · 상태 전이 · 자소서
test_library.py                   24   라이브러리 · 조각 · 선별
test_career_api.py                22   Mission 021 CRUD
test_proof.py                     21   증거화 제안 · 전환 · 이력서 문장
test_saramin_collector.py         18   사람인 어댑터
test_transfer.py                  17   내보내기 · 불러오기
test_target_career.py             17   목표 직무 · 우선순위 반영
test_read_only.py                 17   읽기 전용 · 공개 데모
test_auth.py                      17   Basic Auth
test_application_board.py         17   지원서 보드
test_learning_session.py          16   세션 구성, 자료 중요도, 완료
test_calendar.py                  16   일정 · 빈 시간 · 월/주/일
test_opportunity_effort.py        14   필요 시간 · 계획 연결 · 입력 검증
test_market_signals.py            14   집계, 스냅샷, 추세
test_priority.py                  13   우선순위 규칙
test_evidence.py                  13   증거 집계 규칙
test_posting_parser.py            12   공고 붙여넣기
test_legacy_endpoints.py          12   레거시 회귀
test_learning_progress_chain.py   12   학습 → 우선순위 → Today 연쇄
test_universe.py                  11   홈
test_learning_api.py              11   학습 경로/단계
test_review.py                    10   회고
test_collectors.py                10   어댑터 계약, 레지스트리
test_skill_level.py                9   스킬 레벨 이력
test_overview_review.py            8   한눈에 보기 · 회고
test_library_shelf.py              8   서가 · HOT · 계획에 올리기
test_certificates.py               8   자격증 · 어학
test_why.py                        7   판단 근거
test_carry_over_lifetime.py        7   이월 수명
test_automation_pipeline.py        7   파이프라인 전환 회귀
test_profile_links.py              6   프로필 · 경험 링크
test_opportunity_map.py            6   기회 스킬 지도
test_profile.py                    5   프로필
test_plan_task_cleanup.py          5   지워진 대상을 가리키는 계획 항목
test_experience_usage.py           5   경험 사용처
test_activity.py                   5   날짜별 활동
test_today_explain.py              4   오늘 설명
test_mock_collector_gate.py        4   운영에서 mock 끄기
test_migrations.py                 4   마이그레이션 왕복
test_learning_feedback.py          4   학습 완료 피드백
```

---

## 7. 실행

```bash
# 백엔드
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/alembic upgrade head        # 스키마는 Alembic 이 만든다
./.venv/bin/uvicorn app.main:app --reload

# 프런트
cd frontend
npm install
npm run dev
```

```
API     http://127.0.0.1:8000
문서    http://127.0.0.1:8000/docs
화면    http://localhost:5173
```

확인 절차:

```bash
./.venv/bin/alembic check       # "No new upgrade operations detected."
./.venv/bin/alembic current     # 0019_certificates (head)
./.venv/bin/pytest -q           # 539 passed, 1 skipped
```

---

## 8. 제품 방향과 어긋나 있는 지점

재정의된 방향([PRODUCT.md](PRODUCT.md))과 현재 코드의 차이.
**이 표가 다음 작업의 근거다.**

| 방향 | 현재 코드 | 분류 |
|---|---|---|
| ~~My Learning Library~~ | ✅ url nullable · 소유 구분 · 조각(Segment) · Resource Selector · 서가 | 완료 |
| ~~Target Career~~ | ✅ 만들었다. 우선순위와 기회 매칭에 반영된다 | 완료 |
| ~~기회 매칭의 목표 관련성~~ | ✅ 우선순위를 통해 자동 반영된다 (단일 출처의 이점) | 완료 |
| ~~Career Universe 홈~~ | ✅ `Universe.jsx` + `GET /universe` | 완료 |
| ~~Today 가 제품의 중심~~ | ✅ 가용 시간 · 강도 · 마감 · 완료 체크 · 이월 모두 동작 | 완료 |
| Agent 가 전체 맥락 이해 | 도구가 레거시 모델만 본다 | **수정 필요** |
| ~~프로젝트 완료 → 증거화 제안~~ | ✅ 제안 · 전환 · 이력서 문장 · Project 필드 모두 추가 | 완료 |
| ~~경험 자동 매칭~~ | ✅ 요구 역량 커버리지로 자동 채점 | 완료 |
| ~~JD 텍스트 분석~~ | ✅ 단어 경계 · 강조도. 단 등록된 스킬만 찾는다 | 완료 |
| ~~시장 신호 추세 화면~~ | ✅ 기회 화면에 표시. 레거시 `/weekly-plan` 은 한눈에 보기가 아직 받는다 | 부분 완료 |
| 실제 외부 수집원 | 사람인 어댑터 있음 — 키가 있어야 켜진다. 그 외는 붙여넣기 | **부분** |
| 자동화 상태 영속화 | 메모리에만 | **수정 필요** |

### 살릴 것 (그대로 둔다)

```
services/priority.py        단일 출처 구조와 계산식
services/learning.py        진행률 연쇄
collectors/                 어댑터 계약
Alembic 마이그레이션 체계
Learning Session 의 WHY NOW 구성 방식
기회 매칭 점수 구조 (관련성/준비도/포트폴리오/마감)
근거 규칙 — 데이터 없으면 없다고 말하기
테스트
App.css 의 톤
```
