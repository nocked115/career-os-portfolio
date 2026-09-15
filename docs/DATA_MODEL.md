# Career OS — Data Model

> ## ⚠ 이 문서를 쓰는 법
>
> 이 문서에는 **실제 존재하는 테이블**과 **개념적 구상**이 함께 들어있다.
> 반드시 구분해서 읽을 것.
>
> **개념 모델을 그대로 SQLAlchemy 테이블로 옮기지 말 것.**
> 먼저 `backend/app/models.py` 를 읽고, 기존 구조 중 재사용 가능한 것을
> 찾은 뒤, 가장 작은 호환 확장을 설계할 것.
>
> 스키마는 **Alembic** 이 관리한다. `create_all` 은 제거되었다.
> 모델을 바꿨으면 반드시 마이그레이션을 만들 것.

---

## 1. 현재 존재하는 테이블

전부 실재한다. `backend/app/models.py` 에 정의되어 있고
마이그레이션 `0001_baseline` ~ `0019_certificates` 로 생성된다 (5장).
뒤 마이그레이션이 붙인 컬럼은 `← 00NN` 으로 표시했다.

### 1.1 레거시 MVP

```
skills
  id, name(unique), category, level(0~4), status,
  aliases(쉼표 구분 별칭)                           ← 0014

projects
  id, name(unique), description, status, career_related,
  estimated_hours, progress_percent, daily_minutes, target_date(String),
  github_url, demo_url, results                     ← 0010

jobs
  id, company, title, role, employment_type,
  url, deadline(String), description, status

learning_resources          (= 내 자료. 별도 Library 테이블 없음)
  id, title, url(nullable ← 0008), resource_type(기본 "video"),
  duration_minutes, status, skill_id(FK, NOT NULL),
  importance(primary/supplementary/deep_dive)       ← 0003
  ownership(owned/saved/wishlist), total_units, unit_label  ← 0008

project_skills   (M:N 연결)
job_skills       (M:N 연결)
```

### 1.2 Mission 021 추가

```
learning_paths
  id, title, description, status, progress_percent,
  target_date(Date), skill_id(FK, nullable),
  created_at, updated_at

learning_steps
  id, learning_path_id(FK), title, description,
  position, status, progress_percent, estimated_minutes,
  completed_at
  ⚠ UNIQUE(learning_path_id, position)

learning_step_resources   (M:N: step ↔ resource)

opportunities
  id, opportunity_type, title, organization, role, description,
  source, source_external_id, source_url, location,
  employment_type, deadline(DateTime), status, raw_payload,
  legacy_job_id(FK→jobs, unique, nullable),
  match_score(Float), match_recommendation, scored_at,  ← 0004
  estimated_hours(nullable)                            ← 0009
  collected_at, updated_at
  ⚠ UNIQUE(source, source_external_id)

experiences
  id, experience_type, title, organization, short_description,
  problem, role, actions, results,
  technologies, metrics, tags,
  start_date, end_date, github_url, demo_url,
  blog_url                                             ← 0017
  project_id(FK→projects, unique, nullable),
  created_at, updated_at

experience_skills   (M:N: experience ↔ skill)

opportunity_skills  (M:N: opportunity ↔ skill)              ← 0004

market_snapshots                                           ← 0004
  id, skill_id(FK), opportunity_count, total_opportunities,
  percentage, captured_at

portfolio_entries
  id, title, short_description, problem, role, actions, results,
  technologies, github_url, demo_url, status, display_order,
  resume_bullet                                        ← 0010
  experience_id(FK, nullable), project_id(FK, nullable),
  created_at, updated_at

applications
  id, opportunity_id(FK, nullable), legacy_job_id(FK, nullable),
  status, deadline, job_analysis(Text), notes, applied_at,
  created_at, updated_at
  ⚠ opportunity_id 와 legacy_job_id 중 하나는 필수 (스키마 검증)

application_experience_matches
  application_id(PK,FK), experience_id(PK,FK),
  match_score(Float), match_notes

cover_letter_questions
  id, application_id(FK), question, character_limit, position
  ⚠ UNIQUE(application_id, position)

cover_letter_answers
  id, question_id(FK), draft, version, is_current,
  created_at, updated_at
  ⚠ UNIQUE(question_id, version)
```

### 1.3 Phase 1 이후 추가

```
target_careers                                             ← 0005
  id, title, description, keywords(쉼표 구분), target_date(Date),
  is_active(한 번에 하나), created_at, updated_at

target_career_skills  (M:N: target_career ↔ skill)          ← 0005

daily_plan_tasks                                           ← 0006
  id, plan_date, position,
  task_type(learning_step · project · resource · application · opportunity),
  title, minutes, reason, status(planned · done · skipped), completed_at,
  carried_from(Date, 이월된 경우 원래 날짜),
  plan_available_minutes, plan_intensity                   ← 0007
  learning_step_id · project_id · learning_resource_id ·
  application_id (FK, 모두 nullable),
  opportunity_id(FK, nullable)                             ← 0015
  created_at, updated_at

learning_resource_segments  (자료 안의 조각 — "3장", "0:00–10:00")  ← 0008
  id, learning_resource_id(FK), position, label,
  start_ref, end_ref, estimated_minutes, status, completed_at
  ⚠ UNIQUE(learning_resource_id, position)

profiles  (1인용, 항상 한 줄)                               ← 0011
  id, name,
  day_start_minute(기본 540), day_end_minute(기본 1320),
  daily_cap_minutes(기본 180)                              ← 0012
  github_url, blog_url                                     ← 0017
  created_at, updated_at

calendar_blocks                                            ← 0012
  id, title, kind(class · work · personal · fixed · deadline),
  weekday(0=월~6=일) 또는 date — 정확히 하나 (스키마 검증),
  start_minute, end_minute (자정 기준 분),
  all_day                                                  ← 0018
  note, created_at, updated_at
  ⚠ 종일 일정과 deadline 은 date 에만 걸 수 있고 시각은 0–1440 으로 저장
  ⚠ kind 값은 DB 에서 자유 문자열. 허용 값은 schemas.CalendarKind 가 막는다

skill_level_events  (레벨 변화 이력)                        ← 0016
  id, skill_id(FK), from_level, to_level,
  source(기본 "manual"), note, changed_at

certificates  (자격증 · 어학)                               ← 0019
  id, category(language · job), name,
  score(문자열 — "900" · "IH"), detail, issuer,
  status(held · planned), acquired_on, expires_on, note,
  created_at, updated_at
  ⚠ 자격번호 · 수험번호 칸은 일부러 없다 (개인정보. 제출은 원본 증빙으로)
```

`0013_unify_demand` 는 스키마를 바꾸지 않는다. Opportunity 가 없던
레거시 Job 을 `source="legacy_job"` 인 Opportunity 로 옮기는 데이터 마이그레이션이다.

### 1.4 관계도 (실제)

```
                    Skill
                      │
        ┌─────────────┼──────────────┬──────────────┐
        │             │              │              │
      Job         Project      LearningResource  LearningPath
     (M:N)         (M:N)          (1:M)            (1:M)
        │             │              │              │
        │             │              └──── M:N ─────┤
        │             │                             │
        │             │                       LearningStep
        │             │
        │             └──── 1:1 (nullable) ──► Experience
        │                                          │ M:N ► Skill
        │                                          │
   Opportunity ◄── 1:1 (legacy_job_id)             │
        │                                          ▼
        │                                   PortfolioEntry
        ▼                                          ▲
   Application ──────────────────────────────────┘ (nullable FK)
        │
        ├──► ApplicationExperienceMatch ──► Experience
        │
        └──► CoverLetterQuestion ──► CoverLetterAnswer (버전)
```

위 그림에 없는 연결:

```
TargetCareer ── M:N ──► Skill
Skill ──► SkillLevelEvent (1:M)          Skill ──► MarketSnapshot (1:M)
LearningResource ──► LearningResourceSegment (1:M)
DailyPlanTask ──► LearningStep | Project | LearningResource
                  | Application | Opportunity   (모두 nullable FK)
Profile · CalendarBlock · Certificate    다른 테이블과 FK 없음
```

---

## 2. 레거시 호환 설계

Mission 021 은 기존 `Job` 을 **지우지 않고** 상위 개념을 추가했다.

```
Job              레거시. 수집기와 대시보드가 여전히 사용
  ▲
  │ legacy_job_id (1:1, nullable)
  │
Opportunity      소스 독립적 상위 개념
```

`Application` 도 두 방향 모두 연결할 수 있다.

```
Application
  ├─ opportunity_id   새 방식
  └─ legacy_job_id    기존 Job 에 직접 지원
```

**이유**: 기존 대시보드와 수집기를 깨지 않으면서
새 구조로 점진 이전하기 위해서다.

**현재 상태** (0013 이후): 수집기와 붙여넣기 저장은 `Opportunity` 에 쓴다.
`opportunity_type == "job"` 인 기회는 레거시 `Job` 으로도 만들어져
`legacy_job_id` 로 연결된다. `/jobs/{id}/match` 가 아직 `Job` 을 보기 때문이다.

반대로 `POST /jobs` 로 들어온 Job 도 `Opportunity`(`source="legacy_job"`)
로 남는다 (`services/opportunity.py` 의 `bridge_from_legacy_job`).
그래서 **수요 집계의 모수는 `Opportunity` 하나다** — 우선순위 계산은
`Opportunity` 수를 센다 (`services/priority.py`).

---

## 3. 개념 모델

> ## ⚠ 아래는 구상이다. 테이블이 아니다.
> **이것을 그대로 SQLAlchemy 테이블로 만들지 말 것.**
> 먼저 `backend/app/models.py` 를 검사해서 재사용 가능한 것을 찾고,
> 가장 작은 호환 확장을 설계할 것.

Career OS 가 그리는 개념 관계:

```
TargetCareer                             ✅ 존재 (Phase 1)
 │   목표 직무. 활성 목표와 무관한 스킬은 우선순위 가중치 0.6
 │
 └─ Skill                                 ✅ 존재
     │
     ├─ LearningPath                      ✅ 존재
     │   └─ LearningStep                  ✅ 존재
     │       └─ LearningResource          ✅ 존재 (M:N)
     │
     ├─ MyLearningLibrary                 ✅ Phase 2 — 별도 테이블 없이
     │   ├─ LibraryItem                   = learning_resources
     │   │    ownership · url(nullable) · total_units / unit_label
     │   └─ LibrarySegment                = learning_resource_segments
     │        status · estimated_minutes
     │
     ├─ Project                           ✅ 존재
     │   └─ Experience                    ✅ 존재 (1:1, nullable)
     │       └─ PortfolioEntry            ✅ 존재
     │            resume_bullet           ✅ 존재 (Phase 4)
     │
     └─ Opportunity                       ✅ 존재 (붙여넣기 · 수집기가 채운다)
         ├─ Skill (M:N)                   ✅ 존재
         ├─ MarketSnapshot                ✅ 존재 (추세 계산용)
         ├─ Job Analysis                  🟡 저장 안 함
         │    GET /applications/{id}/analysis 가 규칙 기반으로 매번 계산
         │    Application.job_analysis 는 Text 필드일 뿐이다
         └─ Application                   ✅ 존재
             ├─ Experience Match          ✅ 존재 (점수는 사람이 입력)
             └─ Cover Letter              ✅ 존재 (Question → Answer 버전)
```

`Skill` 이 모든 것의 중심이다.
스킬을 통해 시장 수요(Job/Opportunity), 학습(LearningPath),
증거(Project/Experience)가 하나로 연결된다.

### 명세가 그리는 최종 관계도

```
TargetCareer          ✅ 있음
      │
      ▼
    Skill             ✅ 있음
 ┌────┼──────────────┐
 ↓    ↓              ↓
Job  LearningPath   Project
 │       │             │
 │   LearningStep      │
 │       │             │
 │   Resource          │
 │       │             │
 │   Progress          │      ❌ 별도 Progress 테이블 없음
 │                     │         (Step 안의 status 로 대체)
 ↓                     ↓
Opportunity        Experience
      │               │
      └──────┬────────┘
             ↓
        Application
             │
             ↓
       CoverLetter
             │
             ↓
      Application Result    ❌ 없음 (status 로 대체)
```

### 3.1 아직 없는 개념

| 개념 | 상태 | 비고 |
|---|---|---|
| `TargetCareer` | ✅ | `target_careers` + `target_career_skills` (0005). 화면에서 만드는 곳은 없고 API 로만 설정 |
| `LibraryItem` / `LibrarySegment` | ✅ | 별도 모델 없이 `learning_resources` 확장 + `learning_resource_segments` (0008). `url` nullable |
| `Progress` (별도 테이블) | ❌ | 현재는 Step/Path/Segment 의 `status`, `progress_percent`, `completed_at` 으로 처리 |
| `SkillEvidence` | ❌ | 테이블 없음. `services/priority.py` 가 프로젝트 단계(진행·결과물·경험 전환)와 학습 진행률로 매번 계산 |
| 자료 중요도 | ✅ | `importance` = `primary` / `supplementary` / `deep_dive` (0003) |
| 자료 종류 열거 | 🟡 | DB 는 자유 문자열(기본값 `"video"`). 허용 값은 `schemas.ResourceType` 이 막는다 |
| Opportunity 점수 | ✅ | `match_score` / `match_recommendation` / `scored_at` |
| `TargetCareer` 기반 관련성 | ✅ | 활성 목표의 스킬이 아니면 우선순위 가중치 0.6 (`TARGET_OFF_WEIGHT`) |
| 기회 소요 시간 | ✅ | `opportunities.estimated_hours` (0009) |
| `resume_bullet` | ✅ | `portfolio_entries.resume_bullet` (0010) |
| Market 스냅샷 | ✅ | `market_snapshots` — 수집 때마다 스킬별 한 줄 |
| Learning Session | ❌ | 세션 기록 테이블 없음. 목표 체크는 브라우저(localStorage)에만 |
| 오늘 계획 | ✅ | `daily_plan_tasks` — 완료 · 넘김 · 이월(`carried_from`) · 계획 설정 저장 |
| 캘린더 · 활동 시간대 | ✅ | `calendar_blocks` + `profiles` 의 시간대·하루 상한 |
| 스킬 레벨 이력 | ✅ | `skill_level_events` (0016). 자동 상승은 없고 사람이 바꾼 것만 남는다 |
| 자격증 · 어학 | ✅ | `certificates` (0019). 번호 필드는 의도적으로 없다 |

### 3.2 명세와 구현이 다른 지점

| 명세 | 현재 구현 | 판단 |
|---|---|---|
| Experience 의 `Situation` + `Task` 분리 | `problem` 하나로 합침 | 미결. STAR 엄격히 갈 거면 분리 필요 |
| Project 의 GitHub/demo URL, results | `projects.github_url` · `demo_url` · `results` (0010) | 반영됨 |
| Job `deadline` | `String` | Opportunity 는 `DateTime`. 타입 불일치 |
| Project `target_date` | `String` | 날짜 연산하려면 `Date` 필요 |

---

## 4. 확장할 때의 규칙

1. **먼저 `models.py` 를 읽는다.** 이미 있는 걸 다시 만들지 않는다
2. **기존 컬럼을 지우거나 이름을 바꾸지 않는다.** 대시보드와 수집기가 쓰고 있다
3. **새 필드는 nullable 또는 기본값을 준다.** 기존 행이 깨지면 안 된다
4. **반드시 마이그레이션을 만든다.**
   ```bash
   alembic revision --autogenerate -m "설명"
   alembic upgrade head
   ```
5. **`alembic check` 로 모델과 마이그레이션이 일치하는지 확인한다**
6. **SQLite 호환을 유지한다.** `env.py` 가 `render_as_batch` 를 켜두어
   SQLite 에서도 ALTER 가 동작한다. PostgreSQL 전환 가능성을 닫지 않는다
7. **테스트를 돌린다.** `pytest` — 현재 540개 수집됨
8. **`LearningResource.url` 은 이미 nullable 이다 (0008).**
   종이책처럼 URL 이 없는 자료가 있다. 자료를 링크로 그리는 화면은
   `url` 이 비었을 때를 처리해야 한다 (학습 세션은 "오프라인" 으로 표시)

---

## 5. 마이그레이션 현황

```
0001_baseline      레거시 MVP 6개 테이블
                   기존 DB 에는 stamp 로 표시만 함
                   빈 DB 에서는 실제로 생성

0002_mission021    Mission 021 신규 11개 테이블
0003_mission022    learning_resources.importance
0004_mission023    market_snapshots · opportunity_skills, opportunities 매칭 점수 3칸
0005_target_career target_careers · target_career_skills
0006_today_plan    daily_plan_tasks
0007_plan_settings daily_plan_tasks.plan_available_minutes · plan_intensity
0008_library       learning_resource_segments,
                   learning_resources.ownership · total_units · unit_label, url nullable
0009_effort        opportunities.estimated_hours
0010_evidence      projects.github_url · demo_url · results,
                   portfolio_entries.resume_bullet
0011_profile       profiles
0012_calendar      calendar_blocks, profiles 시간대 · 하루 상한
0013_unify_demand  데이터만 — 레거시 Job 을 Opportunity 로 옮김
0014_aliases       skills.aliases
0015_plan_opp      daily_plan_tasks.opportunity_id
0016_skill_level   skill_level_events
0017_links         profiles.github_url · blog_url, experiences.blog_url
0018_all_day       calendar_blocks.all_day
0019_certificates  certificates
```

검증 완료:

- 빈 DB → `upgrade head` → 모델과 완전 일치 (`alembic check` 통과)
- `downgrade base` → `alembic_version` 만 남고 깨끗이 제거
- 기존 데이터 보존 확인
