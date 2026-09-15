# Career OS — Features

> ## 읽는 법
>
> 각 기능은 아래 6단으로 기술한다.
>
> ```
> 목적            왜 존재하는가
> 필요한 데이터    무엇이 있어야 동작하는가
> 사용자 행동      사용자가 무엇을 하는가
> 시스템 행동      Career OS 가 무엇을 하는가
> 화면            어디에 어떻게 보이는가
> 향후 기능        아직 없는 것
> ```
>
> 그리고 각 기능에 **상태 배지**가 붙는다.
>
> | 배지 | 의미 |
> |---|---|
> | `구현됨 · UI 있음` | 백엔드 + 화면 모두 있음. 지금 쓸 수 있다 |
> | `구현됨 · API만` | 백엔드는 동작하지만 **화면이 없다.** `/docs` 로만 확인 가능 |
> | `계획` | 아직 코드가 없다 |
>
> **`계획` 을 구현된 것으로 착각하지 말 것.**
> 문서는 제품 의도이고 코드가 진실이다.

---

## 상태 요약

| # | 기능 | 상태 |
|---|---|---|
| 0 | **Target Career** (목표 직무) | `구현됨 · API만` (등록 · 활성화는 API, 화면은 표시만) |
| 1 | Career Universe (홈) | `구현됨 · UI 있음` |
| 2 | Today | `구현됨 · UI 있음` |
| 3 | Learning Path | `구현됨 · UI 있음` |
| 3b | **My Learning Library** | `구현됨 · UI 있음` |
| 4 | Learning Session | `구현됨 · UI 있음` |
| 5 | Learning Progress | `구현됨 · UI 있음` |
| 6 | Resources | `구현됨 · UI 있음` |
| 7 | Projects | `구현됨 · UI 있음` (증거화 제안 포함) |
| 8 | Opportunities | `구현됨 · UI 있음` |
| 9 | Market Signals | `구현됨 · UI 있음` |
| 10 | Opportunity Matching | `구현됨 · UI 있음` |
| 11 | Job Analysis | `구현됨 · UI 있음` (지원서 Workspace 안 · 강조도 · 자동 매칭) |
| 12 | Experience Bank | `구현됨 · UI 있음` |
| 13 | Portfolio | `구현됨 · UI 있음` |
| 14 | Applications | `구현됨` (보드 · 다음 행동 · 상태 전이 규칙) |
| 15 | Cover Letter Workspace | `구현됨` (문항별 진행 · 버전 · 구조 · 점검) |
| 16 | Career Agent | `구현됨 · UI 있음` |
| 17 | Automation | `구현됨 · UI 있음` |
| 18 | Calendar | `구현됨 · UI 있음` |
| 19 | 한눈에 보기 (Overview) | `구현됨 · UI 있음` |
| 20 | 회고 (Review) | `구현됨 · UI 있음` |
| 21 | 자격증 · 어학 | `구현됨 · UI 있음` |

---

## 0. Target Career — `구현됨 · API만`

### 목적

**모든 판단의 기준점.** 목표 직무가 없으면 "무엇이 중요한가" 를 정할 수 없다.

### 필요한 데이터

```
TargetCareer   title · description · keywords(쉼표 구분) · target_date
               is_active   활성은 한 번에 하나. 바꿔도 이전 목표를 지우지 않는다
               skills      Skill 과 M:N
```

### 사용자 행동

(등록 화면 없음) API 로 목표를 만들고 스킬을 연결한 뒤 활성화한다.
화면은 활성 목표를 **보여주기만** 한다 — 상단 프로필 줄과 우주 홈 중앙.
없으면 "목표 직무를 정하면 모든 판단의 기준이 됩니다." 라고 쓴다.

### 시스템 행동

`services/priority.py` 안에서만 반영한다. **새 계산 지점을 만들지 않는다.**

```
target_weight   활성 목표의 스킬이면 1.0 · 아니면 0.6
                활성 목표가 없거나 스킬이 비어 있으면 모두 1.0 (이전과 같음)
priority_score  = market_percentage × skill_gap × (evidence_weight × target_weight)
```

0 으로 만들지 않는 이유: 목표와 무관해 보여도 수요가 아주 높으면 알아볼 가치가 있고,
목표는 바뀔 수 있다.

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /target-careers` | 생성 / 목록 |
| `GET /target-careers/active` | 활성 목표 |
| `GET/PATCH/DELETE /target-careers/{id}` | 조회 / 부분수정 / 삭제 |
| `POST /target-careers/{id}/activate` | 활성화 (나머지는 비활성) |
| `POST/DELETE /target-careers/{id}/skills/{sid}` | 스킬 연결 / 해제 |

### 향후 기능

```
목표 등록 · 전환 화면            현재는 API 로만 (프런트 api.targetCareers 는 있지만 쓰는 화면 없음)
keywords 활용                    저장만 한다. 계산은 연결된 skills 만 본다
```

---

## 1. Career Universe (홈) — `구현됨 · UI 있음`

### 목적

앱을 열었을 때 **내 커리어 전체가 하나의 시스템으로 보이게** 한다.
그리고 "오늘 무엇을 할지" 로 바로 이어준다.

### 필요한 데이터

Target Career · 오늘 계획 · 각 영역의 요약 상태 · 쌓인 증거 개수

### 사용자 행동

궤도를 드래그하거나 천체를 눌러 영역을 고른다 (궤도를 누른 뒤 `←` `→` 로도 돌린다).
고르면 바로 이동하지 않고 **요약("지금 볼 이유")을 한 번 거친 뒤** `들어가기 →` 로 들어간다.
오늘 카드를 누르면 Today, 한눈에 보기 카드를 누르면 Overview 가 열린다.

### 시스템 행동

`GET /universe` (`services/universe.py`) — **새로 계산하지 않고** 각 서비스 값을 모은다.

```
me          이름 · 활성 목표 직무 · 집중 스킬
today       가용 · 계획 분 · 할 일 수 · 끝낸 수 · first_task (아직 안 한 첫 할 일)
readiness   목표 직무 스킬의 평균 숙련도. "커리어 68% 완료" 같은 숫자는 만들지 않는다
evidence    쌓인 증거 개수 (배경의 별)
planets     영역마다 badge · why(근거 숫자 포함) · stats · route · section
```

천체는 6개. 영어 이름과 한국어 이름을 함께 준다.

```
LEARNING       학습 · 내 자료
PROJECTS       만들기 · 증거
OPPORTUNITIES  기회 · 공고 · 공모전
EXPERIENCE     경험 · 포트폴리오
APPLICATIONS   지원 · 자기소개서
MY LIBRARY     내가 가진 것
```

### 화면

```
                    ✦ OPPORTUNITIES
                ●───────  ───────●
             LEARNING       PROJECTS
                     🌎
                 이름 · 목표 직무 (없으면 "목표 미설정")
              ●                     ●
         EXPERIENCE          APPLICATIONS
                    ✦ MY LIBRARY

 [오늘  먼저 · SQL 윈도 함수 복습      ]   [한눈에 보기  지금 상태를 한 장으로 →]
        학습 · 30분 · 전체 1/3 끝냄
```

Today 는 별도 행성이 아니라 **아래 카드로 붙는다.** 개수만으로는 "오늘 뭘 하면 되지?" 에
답이 안 되므로 첫 할 일을 바로 보인다. 홈에는 사이드바와 Career Agent 동반자가 뜨지 않는다.

자세한 설계는 [DESIGN.md](DESIGN.md).

## 2. Today — `구현됨 · UI 있음`

### 목적

"오늘 정확히 무엇을 할 것인가" 를 결정하고 실행하게 한다.

### 필요한 데이터

학습 우선순위 · 학습 경로의 다음 단계 · 진행 중 프로젝트 · 학습 자료 ·
마감(지원서 · 공고) · 어제 남은 할 일 · 가용 시간 · 강도

### 사용자 행동

- 화면을 열고 맨 위 "가장 먼저 할 일" 하나를 본다
- `시간 · 강도 설정` 에서 가용 시간과 강도(가볍게 · 보통 · 몰입)를 고르고 계획을 세운다
- 할 일을 체크해 완료하거나 `오늘은 넘기기` 한다. 사흘 넘게 밀린 일은 `그래도 할래요` 또는 `치우기`
- `계산 근거 전체 보기 →` 로 판단 근거 화면(`#/today/why`)을 연다

### 시스템 행동

계획은 저장된다 (`DailyPlanTask`). 완료 체크와 이월을 하려면 기록이 있어야 한다.

```
후보 모으기 (services/today.py — 순서가 중요도 순)
  1. 마감 임박   14일 안. 3일 안이면 맨 앞
  2. 이월        어제 못 한 것. 사흘 넘게 밀린 것은 계획에 안 올리고 stale 로 물어본다
  3. 학습        우선순위 1위 스킬의 다음 단계
  4. 프로젝트    진행 중인 것. 스킬 순위와 무관하게 온다
        ↓
강도에 맞게 배분
  light       최대 2개 · 한 덩어리 30분
  normal      최대 3개 · 한 덩어리 60분
  deep_focus  최대 2개 · 한 덩어리 120분
        ↓
저장. 다시 세우면 planned 만 새로 짠다 — 끝낸 일과 넘긴 일은 기록으로 남는다
```

| 엔드포인트 | 설명 |
|---|---|
| `GET/POST /today/plan?available_minutes&intensity` | 저장된 계획 조회 / 계획 세우기 |
| `GET /today/why` | 계획의 판단 근거. 데이터가 없는 입력도 `available=false` 로 남긴다 |
| `GET /today/intensities` | 강도와 그 의미 |
| `GET /today/deadlines` | 다가오는 마감 |
| `POST /today/tasks/{id}/complete` · `skip` · `revive` | 완료 / 넘김 / 밀린 일 다시 올리기 |
| `GET /today` | 레거시. 집중 스킬 카드가 쓴다 (`focus_skill`, `reason`, `next_learning_step` …) |

### 화면

`TodayPage.jsx` · `TodayFocus.jsx` · `WhyPlanPage.jsx`. 라벨은 한국어이고
**원시 우선순위 점수는 보이지 않는다** — 무엇의 87 인지 말할 수 없기 때문이다.

```
가장 먼저 할 일
SQL 윈도 함수 복습                         30분
[시작하기]

사흘 넘게 미뤄서 오늘 계획에서 뺐습니다
 EC2 실습    4일째    [그래도 할래요] [치우기]

오늘 할 일                계획 1시간 30분 · 강도 보통   [시간 · 강도 설정]
 □ …  완료하면 무엇이 바뀌는지   [오늘은 넘기기]   (이월 · 완료 · 넘김 배지)

다가오는 마감   D-3 …

근거                                     계산 근거 전체 보기 →

집중 스킬  AWS
 시장 수요 · 내 수준 · 학습 진행 · 프로젝트 증거   (분모와 함께)
```

### 향후 기능

```
Agent 문장("오늘 60분밖에 없어")은 저장된 계획을 바꾸지 않는다   레거시 계산으로 답만 한다
```

---

## 3. Learning Path — `구현됨 · UI 있음`

### 목적

강의 링크를 추천하는 기능이 아니라, 스킬을 구조화된 경로로 쪼개는 것.

```
Market Demand
      +
Current Skill
      +
Existing Evidence
      ↓
Learning Priority
      ↓
Learning Path
      ↓
Learning Step
      ↓
Today's Learning Session
      ↓
Resource
      ↓
Practice
      ↓
Completed
      ↓
Skill Evidence
```

### 필요한 데이터

Skill (선택) · 경로 제목/설명 · 단계 목록 (순서 있음) · 단계별 자료

### 사용자 행동

- 학습 경로를 만들고 스킬을 연결한다
- 단계를 순서대로 추가한다
- 경로를 펼쳐 단계 진행 상황을 본다
- 단계를 눌러 Learning Session 을 연다

### 시스템 행동

- 같은 경로 안에서 `position` 중복은 409 로 거부
- 경로 삭제 시 단계도 함께 삭제 (cascade)
- 단계가 바뀌면 경로 진행률을 즉시 재계산
- 경로 진행률이 그 스킬의 학습 우선순위에 반영

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /learning-paths` | 생성 / 목록 (skill_id, status 필터) |
| `GET/PATCH/DELETE /learning-paths/{id}` | 조회 / 부분수정 / 삭제 |
| `GET /learning-paths/{id}/progress` | 진행 상황 조회 (읽기 전용) |
| `POST/GET /learning-steps` | 단계 생성 / 목록 (position 순) |
| `GET/PATCH/DELETE /learning-steps/{id}` | 조회 / 부분수정 / 삭제 |
| `POST/DELETE /learning-steps/{id}/resources/{rid}` | 자료 연결 / 해제 |

### 화면

```
새 학습 경로
[ 예: AWS 배포 익히기 ]  [스킬 선택 ▾]  [만들기]
스킬을 연결하면 이 경로의 진행률이 그 스킬의 학습 우선순위에 반영됩니다.

─────────────────────────────────────────────
AWS 배포 익히기                          33%
진행 중 · 1/3 단계
████████░░░░░░░░░░░░░░░░

  01  EC2 Fundamentals              완료
  02  S3 와 IAM                     시작 전
  03  FastAPI 배포                  시작 전

  [ 단계 추가 ]  [추가]
```

### 향후 기능

```
경로 템플릿 (AWS 표준 경로 같은 것)
단계 순서 드래그 변경
경로 추천 (스킬을 고르면 경로를 제안)
```

---

## 3b. My Learning Library — `구현됨 · UI 있음`

> **이 제품의 성격을 결정하는 부분이다.**
> 자세한 설계는 [LEARNING.md](LEARNING.md).

### 목적

Career OS 가 해야 할 말은 이게 아니다.

```
❌ "AWS 공부하려면 이런 유튜브가 있습니다."
✅ "이미 가진 책 3장과 저장해둔 영상 하나면 오늘 45분은 충분합니다."
```

새 자료를 추천하는 게 아니라 **내가 이미 가진 것 중에서 고른다.**

### 필요한 데이터

```
Library Item     내가 가지고 있거나 저장해둔 것
  종류          resource_type 과 같다 (book · video · course · paper · practice · dataset …)
  소유 상태     owned(가짐) · saved(저장함) · wishlist(사고 싶음)
  출처          URL 또는 없음(종이책)
  분량          페이지 수 · 총 길이

Library Segment  그 안의 부분 — 오늘 실제로 소비하는 단위
  라벨          "3장 — EC2 기초"
  위치          페이지 범위 · 타임스탬프 범위
  예상 시간
  진행 상태
```

### 사용자 행동

가진 책과 저장한 영상을 등록하고, 챕터·구간 단위로 쪼갠다.
서가(지금 학습 · 다음 학습 · 보류 · 완료)를 옮기고, 자료의 다음 챕터를 오늘 계획에 올린다.

### 시스템 행동 — Resource Selector

```
현재 Learning Step 과 관련 있는 항목만 남긴다
        ↓
이미 완료한 Segment 를 제외한다
        ↓
중요도로 정렬한다
        ↓
가용 시간에 맞게 자른다
        ↓
나머지는 "지금은 볼 필요 없음" 으로 명시적으로 치운다
```

### 화면

```
TODAY · AWS EC2                          45분

PRIMARY
📕 보유 책 · 3장 「EC2 기초」              15분
💻 EC2 인스턴스 직접 띄우기                20분

SUPPLEMENTARY
▶ 저장한 영상 · EC2 개요 (0:00–10:00)     10분

──────────────────────────────────────────
나머지 AWS 자료 4개 → 지금은 볼 필요 없음
```

**마지막 줄이 핵심이다.** 치운 것을 보여주는 것이 "선별했다" 는 증거다.

`학습` 화면의 `내 자료` 탭(`#/library`, `LibraryShelf.jsx`)은 **서가처럼** 보인다.

```
내 학습 자료                    [전체] [책] [영상] [문서] [실습]

지금 학습   ▸ 가로 레일 (카드 모양이 종류를 닮는다 · HOT 1~3 배지)
다음 학습   ▸
보류        ▸
분류 전     ▸   직접 정한 서가가 없으면 기록으로 정하고 이유를 함께 준다
완료        ▸
```

- **HOT** — 최근 30일 동안 많이 다룬 자료 상위 3개. 이유 문장을 함께 준다 (`build_hot`)
- 카드를 열면 서랍에서 서가 옮기기(`다음 학습으로 보내기` · `지금 학습으로` · `보류로 이동` · `완료로 표시`) ·
  `오늘 학습에 꺼내기` (다음 챕터를 오늘 계획에 넣고 `지금 학습` 으로 옮김)
- 중요도(`primary` …)는 "얼마나 중요한가", 서가는 "언제 보는가" 다. 둘을 섞지 않는다

| 엔드포인트 | 설명 |
|---|---|
| `GET /library` | `summary` · `hot` · `items` (type · ownership · skill 필터) |
| `POST /resources/{id}/shelf?to=` | in_progress · queued · on_hold · completed (그 밖은 422) |
| `POST /resources/{id}/add-to-plan` | 다음 챕터를 오늘 계획에 |
| `GET/POST /resources/{id}/segments` | 챕터 목록 / 추가 |
| `PATCH/DELETE /segments/{id}` · `POST /segments/{id}/complete` | 챕터 수정 / 삭제 / 완료 |
| `GET /library/selection` · `GET /learning-steps/{id}/selection` | 가용 시간에 맞춘 선별 |

### 어떻게 만들었는가

**`LearningResource` 를 확장했다.** 별도 모델을 만들지 않았다.
라이브러리 항목이 학습 단계에 연결되면 그게 곧 "오늘의 자료" 이기 때문이다.
둘을 나누면 "내 것 중에서 고른다" 는 논지가 오히려 깨진다.

```
url          NOT NULL → nullable   종이책에는 URL 이 없다
ownership    owned · saved · wishlist
total_units  전체 분량,  unit_label  "쪽" · "분"
```

**Segment** 를 자식 테이블로 추가해 "3장 15분" 을 가리킬 수 있게 했다.
조각이 전부 끝나면 자료 자체가 완료로 올라간다.

### 아직 없는 것

```
자료 자동 분할 (책 목차에서 챕터 뽑기)
```

챕터 추가 · 완료 · 삭제 화면은 있다 (`LibraryPanel.jsx`).

---

## 4. Learning Session — `구현됨 · UI 있음`

### 목적

Today 나 Learning 에서 단계를 클릭하면 열리는 **집중 학습 화면**.
"왜 지금 이걸 하는가" 를 먼저 이해시킨다.

### 필요한 데이터

단계 · 소속 경로 · 연결된 스킬 · 우선순위 계산 결과 ·
단계 설명 (목표의 출처) · 연결된 자료

### 사용자 행동

- "왜 지금인가" 를 읽는다
- 목표를 체크한다 (체크는 이 브라우저에만 남는다)
- 자료를 연다 (중요도 순으로 배치됨)
- 학습을 시작하고, 끝나면 완료로 표시한다
- 완료 후 무엇이 바뀌었는지 보고 다음 단계로 넘어간다

### 시스템 행동

`GET /learning-steps/{id}/session` 이 화면에 필요한 것을 한 번에 준다.

| 구성 | 출처 |
|---|---|
| `why_now` | 저장된 공고 수 / 요구 공고 수 / 현재 레벨 / 프로젝트 증거 / 학습 진행률 |
| `goals` | **단계 설명의 각 줄.** 설명에 없는 것은 만들지 않는다 |
| `materials` | 연결된 자료를 중요도별로 묶음 |
| `material_minutes` | 자료 시간 합계 |

동작:

- `POST /learning-steps/{id}/start` — 진행 중으로 표시
- `POST /learning-steps/{id}/complete` — 완료 + 경로 진행률 갱신 +
  오늘 계획에 같은 단계가 있으면 함께 완료.
  응답에 `effects`(예: "학습 진행률 33% → 67%"), `next_step`,
  `learning_path.progress_before` 를 담아 **무엇이 바뀌었는지** 말한다

### 근거 규칙 — 타협 불가

`why_now` 는 **실제 데이터로만** 만든다.
공고가 없으면 "계산할 수 없습니다" 라고 말하고 수요를 지어내지 않는다.

```
✅ "저장된 공고 5건 중 4건이 AWS 를 요구합니다."
✅ "아직 저장된 공고가 없어 시장 수요를 계산할 수 없습니다."
❌ "AWS 는 요즘 가장 인기 있는 기술입니다."
```

### 화면

```
← 학습

AWS · AWS 배포 익히기 33%                   45분
EC2 Fundamentals                            예상
[진행 중]

왜 지금인가
 • 저장된 공고 1건 중 1건이 AWS 을(를) 요구합니다.
 • 현재 레벨은 0 입니다.
 • 학습 경로 진행률은 33% 입니다.
 [우선순위 1위] [기회 1건 중 1건이 요구] [레벨 0/4]

오늘의 목표
 □ EC2 가 무엇인지 설명하기
 □ Region 과 Availability Zone 구분하기
 체크는 이 브라우저에만 남아요. 단계 완료는 아래 버튼으로 합니다.

이번 세션 자료
   AWS 공식 문서 — EC2 개요   핵심 · 이번 단계에 꼭 볼 것
   AWS 교재 3장               보조 · 막히면 펼쳐 볼 것
   AWS 아키텍처 백서          깊이 파기 · 여유가 있을 때 더 볼 것

                    [학습 시작]  [이 단계 완료로 표시]

✓ 학습 세션 완료
 • 학습 진행률 33% → 67%
 • AWS 의 학습 진행이 우선순위 계산에 반영됩니다
 [다음 단계 보기 · S3 와 IAM]
```

원시 우선순위 점수는 보이지 않는다. 순위와 분모 있는 근거만 쓴다.

### 향후 기능

```
Career Agent 가 이 세션의 맥락을 이해하고 튜터 역할        (Phase 6)
  "지금 배우는 내용으로 AZ 를 설명해줘"
목표를 서버에 저장                (현재는 브라우저에만)
세션 시간 기록
```

---

## 5. Learning Progress — `구현됨 · UI 있음`

### 목적

학습한 것이 **다음 추천에 반영되게** 한다.
이게 없으면 Career OS 는 그냥 체크리스트 앱이다.

### 필요한 데이터

단계 상태 · 경로별 진행률 · 스킬-경로 연결

### 사용자 행동

Learning Session 에서 단계를 완료한다.

### 시스템 행동 — **Mission 022 에서 연쇄가 닫혔다**

```
Learning Step 완료
    → Learning Path 진행률       ✅ 스텝이 바뀔 때마다 자동 갱신
    → Skill Evidence             ✅ evidence_weight 에 반영
    → Learning Priority          ✅ 점수가 실제로 내려감
    → 다음 Today Plan            ✅ 집중 스킬이 바뀜
```

계산식 (`services/priority.py` — **단일 출처**):

```
market_percentage  = 이 스킬을 요구하는 Opportunity 수 / 전체 Opportunity 수
skill_gap          = max(0, 4 - level)

project_strength   = 가장 멀리 간 커리어 프로젝트 하나의 세기
                     started 0.10 · in_progress 0.25 · completed 0.50
                     shown 0.70 (GitHub · 데모 · 결과 중 하나 또는 경험으로 옮김)
                     used 0.85 (보여줄 것 + 경험으로 옮김)
learning_progress  = 이 스킬에 연결된 학습 경로들의 평균 진행률
learning_strength  = 0.4 × (learning_progress / 100)

evidence_strength  = project + learning - project × learning   (최대 0.85)
evidence_weight    = max(0.15, 1.0 - evidence_strength)

priority_score     = market_percentage × skill_gap × (evidence_weight × target_weight)
```

학습은 프로젝트보다 **약한 증거**로 본다.
프로젝트는 "만들어봤다", 학습은 "배웠다" 이기 때문이다.
경로를 100% 끝내도 학습 세기는 0.4 까지라 완료한 프로젝트 하나(0.50)를 넘지 않는다.

예전의 "커리어 프로젝트가 있으면 0.5" 는 없어졌다. 0% 짜리 빈 프로젝트를 만들기만 해도
우선순위가 반토막 났기 때문이다 (DECISIONS 3장).
증거가 아무리 강해도 가중치는 0.15 아래로 내려가지 않는다.
`target_weight` 는 0장 Target Career 참고.

### 상태 값

```
not_started   in_progress   completed   review_needed
```

`LearningStatus` 로 고정되어 있어 잘못된 값은 422 로 거부된다.

### 화면

Learning 페이지의 진행률 바, Learning Session 의 완료 버튼,
Today 의 집중 스킬 변화로 나타난다.

### 향후 기능

```
Skill.level 자동 상승 여부        현재는 사용자가 직접 정한다.
                                 시스템이 덮어쓰지 않기 위한 선택
review_needed 상태 활용 (복습 주기)
학습 시간 누적 기록
```

---

## 6. Resources — `구현됨 · UI 있음`

### 목적

자료를 쏟아붓지 않고 **지금 필요한 것부터** 보여준다.

### 필요한 데이터

제목 · URL · 종류 · 소요 시간 · 중요도 · 연결 스킬 · 연결 단계

### 사용자 행동

자료를 등록하고 중요도를 정한 뒤 학습 단계에 연결한다.

### 시스템 행동

종류와 중요도를 검증한다.

```
resource_type   official_doc · documentation · book · course · video
                article · paper · practice · problem · dataset · project_task

importance      primary        지금 이것부터
                supplementary  여유 있으면
                deep_dive      더 파고들고 싶으면
```

Learning Session 에서 중요도별로 묶어서 보여준다.

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /resources` | 생성 / 목록 |
| `GET /skills/{id}/resources` | 스킬별 자료 |
| `PATCH/DELETE /resources/{id}` | 부분수정 / 삭제 |

> Mission 022 이전에는 `resource_type` 이 자유 문자열이고 기본값이 `"youtube"` 였다.
> 마이그레이션 `0003_mission022` 가 기존 데이터를 `"video"` 로 옮겼다.

### 화면

Learning Session 의 `이번 세션 자료` 에서 중요도 라벨(핵심 · 보조 · 깊이 파기)과 함께 표시된다.

### 향후 기능

```
자료 자동 추천 (지금 필요한 것만 골라주기)   현재는 사람이 중요도 지정
Practice / 코딩 문제를 별도 개념으로
```

자료 완료는 챕터 완료와 `완료` 서가로 한다 (3b장).

---

## 7. Projects — `구현됨 · UI 있음`

### 목적

Project 는 할 일 목록이 아니라 **역량의 증거**다.

### 필요한 데이터

이름 · 설명 · 상태 · 연결 스킬 · 예상 시간 · 진행률 · 하루 투입 시간 · 목표 완료일 ·
커리어 관련 여부 · GitHub URL · 데모 URL · 결과

### 사용자 행동

프로젝트를 만들고 스킬을 연결한 뒤 진행률을 갱신한다.
완료하면 그 자리에서 결과 · 링크를 적고 경험으로 옮긴다.

### 시스템 행동

- ETA 계산 (`GET /projects/{id}/eta`): 남은 시간 → 필요 일수 → 예상 완료일.
  하루 투입 시간과 총 시간을 둘 다 적었을 때만 계산된다
- 증거의 세기를 진행 단계로 나눈다 (started → in_progress → completed → shown → used).
  세기가 셀수록 그 스킬의 학습 우선순위가 내려간다 (5장)

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /projects` | 생성 / 목록 |
| `PATCH /projects/{id}` | 부분수정 (상태 · 진행률 · 링크 · 결과) |
| `POST /projects/{id}/skills/{sid}` · `GET /projects/{id}/skills` | 스킬 연결 / 조회 |
| `GET /projects/{id}/eta` | 예상 완료일 |
| `GET /projects/{id}/evidence` | 증거화 제안 |
| `POST /projects/{id}/to-experience` | 경험으로 옮기기 |

### 화면

`ProjectsPage.jsx` (`#/projects`). 필터는 진행 중 · 완료 · 전체.

```
프로젝트

완료한 프로젝트 · 아직 증거로 안 남음
AWS Deployment Project 을(를) 증거로 남기기     [경험으로 저장] [포트폴리오 준비]

AWS Deployment Project                          진행 중
진행률  ████████░░░░░░░░░░░░  25%
목표 완료일 …   지금 속도면 … (남은 9시간)

✓ 프로젝트를 완료했습니다          ← 완료 직후 패널
  GitHub · 데모 · 결과 입력 → 경험으로 옮기기
```

### 향후 기능

```
프로젝트 삭제                  DELETE 엔드포인트 없음
완료 시각 기록                 Project 에 completed_at 이 없어 회고가 "이번 달에 끝낸 프로젝트" 를 세지 못한다
```

---

## 8. Opportunities — `구현됨 · UI 있음`

### 목적

Career OS 가 **한 채용 플랫폼에 종속되지 않게** 한다.
공고뿐 아니라 인턴십·공모전·대외활동을 하나로 다룬다.
기회는 쌓아두려고가 아니라 **고르기 위해** 보여준다.

### 필요한 데이터

종류 · 제목 · 주관 · 설명 · 수집원 · 외부 ID · 원본 URL · 마감일 · 예상 소요 시간 · 원본 응답

### 사용자 행동

- 읽은 공고 글을 **복사해 붙여넣고** 미리보기를 확인·고친 뒤 저장한다
- 검토 중 · 보류 · 관심 없음 · 전체 칸을 오가며 고른다
- 기회를 오늘 계획에 올리거나 지원서를 만든다

### 시스템 행동

- `opportunity_type` 은 `job` / `competition` / `external_activity` 로 고정
- `(source, source_external_id)` 조합이 유니크 — 같은 소스에서 중복 수집하면 409
- `legacy_job_id` 로 기존 `Job` 과 1:1 연결 가능
- `raw_payload` 에 원본 응답을 보존
- 만들 때 제목 · 설명에서 스킬을 자동 연결한다. 연결이 없으면 수요의 분모만 늘기 때문이다

**붙여넣기 가져오기** — `POST /opportunities/parse` (`services/posting_parser.py`, 규칙 기반)

- **앱은 공고 URL 을 열지 않는다.** 대부분의 채용 사이트가 약관에서 자동 수집을 막는다.
  사람이 붙여넣은 글만 다룬다
- 제목 · 기관 · 마감 · 요구 스킬 · 지원 자격 줄을 찾아 **미리보기로만** 돌려준다. 저장하지 않는다
- 찾은 칸마다 근거가 된 줄을 같이 준다. **못 찾으면 비워 둔다** — 날짜와 회사를 짐작하지 않는다
- 걸림돌이 될 수 있는 지원 자격을 `requirement_flags` 로 표시한다.
  **충족 여부는 판단하지 않는다**

```
career     경력 요건        "N년 이상" · 경력자 · 학계 · 실무 경력
degree     학력 · 졸업 요건  석사 · 박사 · 학위 · 졸업 예정
language   어학 요건        OPIc · 토익 · TOEFL · IELTS …
license    자격증 요건      자격증 필수/소지 · 기사 자격
```

어학 · 자격증 경고 옆에는 등록한 `my_certificates` 를 함께 보여준다 (21장).

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /opportunities` | 생성 / 목록 (type, source, status 필터) |
| `GET/PATCH/DELETE /opportunities/{id}` | 조회 / 부분수정 (상태 포함) / 삭제 |
| `POST /opportunities/parse` | 붙여넣은 글 → 미리보기 (저장 안 함) |
| `POST /opportunities/relink-skills` | 나중에 만든 스킬까지 다시 연결 (손으로 붙인 연결은 유지) |
| `POST/DELETE /opportunities/{id}/skills/{sid}` | 스킬 연결 / 해제 |
| `GET /opportunities/{id}/map` | 공고 하나 기준 스킬 → 공부 → 프로젝트 → 경험 지도 |
| `POST /opportunities/{id}/add-to-plan?minutes=` | 오늘 계획에 올림 (기본 30분, 5~480). 지원서가 없으면 관심 상태로 만든다 |

### 레거시 병행 설계

```
Job              레거시. 대시보드 초기 로드(/jobs) · Agent tools · /jobs/{id}/match 가 사용
  ▲
  │ legacy_job_id (1:1, nullable)
  │
Opportunity      소스 독립 상위 개념. 수요의 분모는 이것 하나다
```

Job 으로 들어온 것도 Opportunity 에 남긴다 (`bridge_from_legacy_job`, 마이그레이션 `0013`).
그래서 수요를 두 테이블이 다르게 세지 않는다.

### 화면

`OpportunitiesPage.jsx` (`#/opportunities`).

```
기회                                    [공고 붙여넣기] [수집 실행]

[검토 중] [보류] [관심 없음] [전체]      [모든 종류 ▾]

지금 할 만해요 · 고려해 볼 만해요 · 지금은 아니에요   ← 판정 라벨
 제목  D-day  [지원서 · 상태] [자격 확인]
   네 칸 점수 · 판정 근거 · 자격 경고와 내 어학 · 자격
   다음 행동  [지원서 만들기 | 지원서 열기] [오늘 계획에 준비 추가] [지금은 보류] [관심 없음]
   (치운 기회에는 [다시 검토하기])

선택한 기회의 지도 (OpportunityMap)
스킬별 수요 추세 ↑↓ (9장)
```

붙여넣기 미리보기는 칸마다 찾은/못 찾은 표시와 근거 줄을 보여주고, 사람이 고친 뒤 저장한다.

### Mission 023 에서 추가된 것

**Source Adapter 구조** — `app/collectors/`

```
collectors/
    base.py     정규화 계약 (normalize_opportunity, parse_deadline)
    mock.py     참고 구현. 운영(production)에서는 꺼진다
    saramin.py  사람인 공식 채용정보 API. 키가 있고 공개 데모가 아닐 때만 쓴다
    __init__.py 레지스트리
          ↓  fetch() → normalize()  ↓
      Opportunity
```

수집원은 `SOURCE_NAME` / `is_available()` / `fetch()` / `normalize()`
네 가지만 노출하면 된다. 비즈니스 로직은 수집원을 알지 못한다.

**수집이 Opportunity 를 채운다**

- `POST /opportunities/collect` — 등록된 수집원을 모두 실행
- `(source, source_external_id)` 로 upsert. 다시 수집해도 중복되지 않는다
- 설명·제목에서 스킬을 자동 연결 (`jd.extract_skills` — 단어 경계 · 한국어 조사 처리.
  "Go" 가 "Google" 에 걸리지 않는다)
- `opportunity_type == "job"` 이면 레거시 `Job` 도 만들어 `legacy_job_id` 로 잇는다
  → `/jobs/{id}/match` 가 그대로 동작한다
- 사용자가 바꾼 `status` 는 재수집해도 덮어쓰지 않는다

### 향후 기능

```
사람인 외 수집원
사람인 응답에는 공고 본문이 없다     직무명 · 키워드 필드로만 스킬을 찾아 손으로 넣은 공고보다 연결이 얕다
```

**제약**: 비즈니스 로직이 특정 수집원에 의존하면 안 된다.
각 소스의 약관과 허용된 접근 방식을 확인한 뒤 연결한다.
모든 사이트를 스크래핑할 수 있다고 가정하지 않는다.

---

## 9. Market Signals — `구현됨 · UI 있음` (추세)

### 목적

시장이 무엇을 원하는지 **실제 수집 데이터에서** 계산한다.

### 필요한 데이터

수집된 Opportunity · 기회-스킬 연결 · 시점별 스냅샷 (추세용)

### 사용자 행동

기회 화면에서 스킬별 수요와 오르내림을 확인한다.

### 시스템 행동

**현재 수요** — `GET /analytics/market-signals`

```
opportunity_count   이 스킬을 요구하는 기회 수
percentage          전체 기회 대비 비율
trend               up / down / flat / unknown
change_points       직전 스냅샷 대비 변화폭
```

**추세** — 시점별 값이 없으면 "올랐다/내렸다" 를 말할 수 없다.
수집이 끝날 때마다 스킬별 수요를 `MarketSnapshot` 에 한 줄씩 남기고,
가장 최근 두 스냅샷을 비교한다.

- 스냅샷이 하나뿐이면 `trend` 는 `unknown` 이다.
  **비교할 과거가 없는데 화살표를 그리지 않는다.**
- 3포인트 미만 변화는 `flat` 으로 본다. 기회 몇 건 차이로 화살표가 요동치지 않게.
- 순서는 `captured_at` 이 아니라 id 로 본다.
  SQLite 의 `CURRENT_TIMESTAMP` 는 초 단위라 같은 초에 저장된 스냅샷을
  시간으로 구분할 수 없다.

`POST /analytics/market-snapshots` 로 수동 기록도 가능하다.
보통은 자동화가 수집 직후에 부른다.

### 근거 규칙 — 타협 불가

**통계는 반드시 수집된 실제 데이터에서 계산한다. 임의로 만들지 않는다.**
데이터가 부족하면 부족하다고 표시한다.

### 화면

기회 화면 아래에 상위 6개 스킬을 `요구 기회 수 / 전체 기회 수건` 과 ↑ 늘었음 · ↓ 줄었음 으로 보인다.
비교할 과거가 없으면 "비교할 과거 기록이 아직 없어 추세를 표시하지 않습니다." 라고 쓴다.

화면은 레거시 `/analytics/skills` (Job 기반) 를 더 이상 부르지 않는다.
학습 우선순위(`/analytics/learning-priority`)의 분모도 Opportunity 다.

### 향후 기능

```
기간 선택 (주간 / 월간 추세)
```

## 10. Opportunity Matching — `구현됨 · UI 있음`

### 목적

기회를 많이 보여주는 것이 아니라
**"이걸 지금 하는 게 나에게 가치가 있는가"** 를 판단한다.

### 필요한 데이터

기회-스킬 연결 · 학습 우선순위 · 프로젝트 증거 · 마감일 · 예상 소요 시간 · 기회 종류

### 사용자 행동

기회 화면에서 판정과 근거를 보고 계획에 올리거나, 지원서를 만들거나, 보류 · 관심 없음으로 치운다.

### 시스템 행동

점수는 100점 만점이고 네 요소로 나뉜다.

| 요소 | 배점 | 근거 |
|---|---|---|
| **관련성** | 40 | 지금 우선순위가 높은 스킬을 요구하는가 (1위 스킬 대비 상대값) |
| **준비도** | 30 | 요구 스킬 중 이미 보유한 비율 |
| **포트폴리오 가치** | 15 | 공모전·대외활동이거나 증거 없는 스킬을 요구하는가 |
| **마감 실현 가능성** | 15 | 남은 일수 (7일 미만 촉박 · 30일 이상 여유). `estimated_hours` 가 있으면 하루에 필요한 시간(1 · 2 · 4시간 기준)으로 본다 |

판정:

```
70점 이상   recommended
40 ~ 69     consider
40점 미만   skip
마감 지남   점수와 무관하게 skip
```

| 엔드포인트 | 설명 |
|---|---|
| `GET /opportunities/matches` | 전체 채점, 점수 높은 순 |
| `GET /opportunities/{id}/match` | 개별 채점 (결과를 저장) |
| `GET /opportunities/recommended?limit=N` | 할 만한 것만 추림 |

점수는 `Opportunity.match_score` / `match_recommendation` / `scored_at` 에 저장된다.
매칭 응답에는 `requirement_flags` 와 `my_certificates` 도 붙는다 — 점수만 보고
"학계 1년 이상" 같은 자격 요건을 놓치지 않기 위해서다.

### 설명 가능해야 한다

모든 판정에 근거가 붙는다. 설명할 수 없으면 추천하지 않는다.

```
[83] recommended  AI 데이터 분석 공모전  (D-43)
   · 지금 우선순위가 높은 스킬을 요구합니다: Python.
   · 요구 스킬 1개 중 1개를 보유하고 있습니다.
   · 결과물이 포트폴리오 증거로 남습니다.
   · 마감까지 43일 남았습니다.
```

`"Skip this."` 도 1급 시민이다. 숨기지 않고 이유와 함께 말한다.

```
· 마감이 3일 지났습니다.
· 지금은 다른 것을 먼저 하는 편이 낫습니다.
```

추천할 게 없으면 **빈 목록이 정상이다.** 억지로 채우지 않는다.

### 화면

기회 화면 (8장). 판정은 `지금 할 만해요` · `고려해 볼 만해요` · `지금은 아니에요` 로,
근거 줄 · D-day · 자격 확인 배지와 함께 보인다.

### 향후 기능

```
필요 시간 자동 추정          estimated_hours 는 사람이 적는다
```

> **관련성은 여전히 학습 우선순위로 계산한다.** 기회 채점이 `TargetCareer` 를 직접 보지는 않는다.
> 다만 학습 우선순위에 `target_weight` 가 들어가므로 목표 직무 스킬을 요구하는 기회가
> 간접적으로 관련성이 높게 나온다 (0장).

## 11. Job Analysis — `구현됨 · UI 있음`

### 목적

관심 공고의 요구 역량을 내 상태와 대조한다.

### 필요한 데이터

지원서의 공고 설명(JD) · 공고에 연결된 스킬 · 스킬 별칭 · 내 스킬 레벨 · Experience

### 사용자 행동

지원서 Workspace 에서 JD 분석과 추천 경험을 보고, 추천 경험을 지원서에 저장한다.

### 시스템 행동

`services/jd.py` — **LLM 이 아니다.** 저장된 스킬 이름(별칭 포함)을 JD 텍스트에서 찾는다.

```
찾기        영문은 단어 경계 ("Go" ≠ "Google", "C" ≠ "CSS")
            한글은 뒤에 붙는 조사까지 허용 ("딥러닝을", "파이썬으로")
강조도      언급 횟수 × 10 + 앞쪽에 나올수록 최대 30
보유 판정   level ≥ 3 strong · ≥ 1 medium · 0 gap
match_score 강조도 가중 — gap 이 아닌 역량의 강조도 합 / 전체 강조도 합
경험 추천   요구 역량을 덮는 Experience 를 점수 순으로 최대 3개
```

JD 에서 역량을 하나도 못 찾으면 공고에 연결된 스킬로 대신한다 (`basis: "linked"`).
요구 역량을 찾지 못하면 매칭할 수 없다고 말한다.

| 엔드포인트 | 설명 |
|---|---|
| `GET /applications/{id}/analysis` | JD 분석 · 강/중/갭 · 추천 경험 · 한계 메모 |
| `POST /applications/{id}/auto-match` | 추천 경험을 지원서에 저장 |
| `GET /jobs/{id}/match` | 레거시. 연결된 스킬 중 level > 0 비율 (화면에서 쓰지 않음) |

### 현재 한계 — 정직하게

```
❌ JD 를 읽고 요약하거나 문장을 생성하지 않는다 (LLM 이 필요하다)
❌ 저장된 스킬 · 별칭에 없는 역량은 찾지 못한다
❌ 조사 목록에 없는 한글 합성어("딥러닝기술")는 같은 것으로 세지 않는다
```

### 화면

지원서 Workspace(`ApplicationWorkspace.jsx`) 안의 추천 경험 · JD 분석 · 한계 칸 (14장).
추천 경험이 없으면 "요구 역량을 덮는 경험이 없습니다." 와 경험 등록 · 프로젝트에서 가져오기 길을 준다.

---

## 12. Experience Bank — `구현됨 · UI 있음`

### 목적

자소서를 쓸 때마다 과거 경험을 **처음부터 떠올리지 않게** 한다.

### 필요한 데이터

```
experience_type      project · research · competition · award
                     internship · work · club
title, organization
short_description
problem              ← 명세의 Situation + Task 를 합친 필드
role, actions, results
technologies, metrics, tags
start_date, end_date
github_url, demo_url
blog_url             이 경험을 풀어쓴 글 (Velog 등)
project_id           기존 Project 와 1:1 연결
skills               Skill 과 M:N
```

### 사용자 행동

`경험` 화면(`#/experience`)에서 경험을 등록 · 수정하고, 완료한 프로젝트를 경험으로 가져오고,
포트폴리오로 승격한다. 같은 화면에서 GitHub · 블로그 링크와 자격증 · 어학(21장)을 관리한다.

### 시스템 행동

저장하고 조회한다. 공고에 맞는 경험 추천은 지원서의 JD 분석이 한다 (11장).

**어디에 쓰였는가** — `GET /experiences/usage` 가 경험마다 돌려준다.

```
project               옮겨온 프로젝트
portfolio_entry_ids   만든 포트폴리오 항목
applications          매칭한 지원서 (제목 · 기관 · 상태 · 매칭 점수)
missing               비어 있는 칸의 라벨
```

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /experiences` | 생성 / 목록 (type 필터) |
| `GET /experiences/usage` | 경험별 쓰임 · 빈 칸 |
| `GET/PATCH/DELETE /experiences/{id}` | 조회 / 부분수정 / 삭제 |
| `POST/DELETE /experiences/{id}/skills/{sid}` | 스킬 연결 / 해제 |
| `POST /projects/{id}/to-experience` | 프로젝트 → 경험 |

### 명세와 다른 점

명세는 `Situation` 과 `Task` 를 나눴지만 현재 모델은 **`problem` 하나로 합쳐져 있다.**
화면은 이 칸을 "상황과 과제" 라고 부른다.
STAR 구조를 엄격히 지키려면 필드 분리가 필요하다 — 아직 결정된 바 없다.

### 화면

`ProofPage.jsx` — 화면 이름은 `경험`.

```
경험

완료한 프로젝트 · 아직 경험으로 안 남음      ← 해당할 때만
내 링크 (GitHub · 블로그)
자격증 · 어학                              ← CertificatesCard

경험 카드
  제목 · 종류 · 상황과 과제 · 역할 · 행동 · 결과 …
  쓰인 곳: 프로젝트 · 지원서 · 코드 · 블로그 링크
  비어 있는 칸

포트폴리오
```

### 향후 기능

```
구조화된 태그 검색        현재 tags/metrics 는 자유 텍스트
Situation / Task 분리 여부 결정
```

---

## 13. Portfolio — `구현됨 · UI 있음`

### 목적

경험과 프로젝트를 **보여줄 수 있는 형태**로 전환한다.

```
Learn → Build → Evidence → Portfolio
```

### 필요한 데이터

제목 · 한 줄 설명 · 문제 · 역할 · 행동 · 결과 · 기술 ·
GitHub/demo URL · 이력서 한 줄(`resume_bullet`) · 상태 · 노출 순서 · 원본 경험/프로젝트

### 사용자 행동

경험을 포트폴리오로 승격시키고, 이력서 한 줄 초안을 만든다.

### 시스템 행동

`POST /experiences/{id}/portfolio-entry` 가 경험 내용을 복사해
`draft` 상태 항목을 만들고 원본과 연결한다.

`POST /portfolio-entries/{id}/resume-bullet` 은 기술 · 역할 · 행동 · 결과의 첫 줄로
이력서 한 줄을 **조립해 저장한다.** 템플릿 조립이지 LLM 생성이 아니다.
**없는 성과를 지어내지 않는다** — 재료가 부족하면 문장 대신 무엇이 비었는지 알려준다.

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /portfolio-entries` | 생성 / 목록 (status 필터, display_order 정렬) |
| `GET/PATCH/DELETE /portfolio-entries/{id}` | 조회 / 부분수정 / 삭제 |
| `POST /experiences/{id}/portfolio-entry` | 경험 → 포트폴리오 승격 |
| `POST /portfolio-entries/{id}/resume-bullet` | 이력서 한 줄 초안 저장 |

### 화면

`경험` 화면 아래 포트폴리오 칸 (12장).

### 향후 기능

```
"이건 포트폴리오에 넣을 가치가 있다" 자동 판단
```

---

## 14. Applications — `구현됨`

### 목적

관심 공고를 실제 지원 프로세스로 연결하고 상태를 추적한다.

### 필요한 데이터

대상 (Opportunity 또는 레거시 Job) · 상태 · 마감일 · JD 분석 · 메모 ·
관련 경험과 매칭 점수

### 사용자 행동

Applications 화면에 들어오면 맨 위에서 가장 먼저 할 일 하나를 보고,
지원서를 열어 상태를 옮기고 자기소개서를 쓴다.

### 시스템 행동

상태를 `ApplicationStatus` 로 고정한다.

```
interested → preparing → ready → applied
                                    │
                                    ├─► document_pass → interview → accepted
                                    │                             └─► rejected
                                    └─► rejected

언제든 → withdrawn
```

`Opportunity` 와 `legacy_job_id` 중 하나는 반드시 있어야 한다 (없으면 422).

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /applications` | 생성 / 목록 (status 필터) |
| `GET/PATCH/DELETE /applications/{id}` | 조회 / 부분수정 / 삭제 |
| `PUT /applications/{id}/experiences/{eid}` | 경험 매칭 (점수 + 메모) |
| `GET /applications/{id}/experiences` | 점수 높은 순 정렬 |
| `DELETE /applications/{id}/experiences/{eid}` | 경험 매칭 해제 |
| `GET /applications/board` | 지원서마다 마감 · 매칭(분모) · 자소서 진행 · 다음 행동 + 맨 위 요약 |
| `GET /applications/{id}/transitions` · `POST .../move` | 갈 수 있는 상태 · 규칙대로 옮기기 (막히면 409, 한국어 사유) |
| `GET /applications/{id}/analysis` · `POST .../auto-match` | JD 분석 · 추천 경험 저장 |

### 화면

`ApplicationsPage.jsx` · `ApplicationWorkspace.jsx` (DECISIONS 22장). 화면 이름은 `지원서` (`#/applications`, `#/applications/{id}`).

- 필터: 진행 중 · 지원 전 · 지원 후 · 끝남 · 전체. 저장된 기회를 골라 지원서를 만든다
- 목록: 이번 주 지원 준비(마감 7일 안 · 작성 중 · 다음 행동) → 줄마다 D-day · 상태 ·
  매칭 `보유/요구` · 자소서 `작성/문항` · 다음 행동 · 마지막 수정
- Workspace: 요약과 상태 흐름 → 다음 행동 → 자기소개서 → 추천 경험 → JD 분석 → 한계.
  좁은 화면에서도 이 순서다.

### 향후 기능

```
job_analysis 필드            여전히 쓰지 않는다 — 분석은 요청 때마다 계산한다
결과 피드백                  합격/불합격이 다음 추천에 반영되지 않는다
레거시 Job 으로 지원서 만들기  화면에서 지원하지 않는다 (API 로만)
```

---

## 15. Cover Letter Workspace — `구현됨`

### 목적

공고 하나를 위한 **지원 준비 작업 공간**.
왼쪽에 근거, 오른쪽에 작성.

### 필요한 데이터

지원서 · 문항 · 글자 수 제한 · 답변 초안 · 버전 · 관련 경험 · JD

### 사용자 행동

문항을 등록하고, 문항별로 직접 쓰고, 저장할 때마다 버전을 남긴다.
저장하지 않은 변경 · 남은 글자 수 · 제한 임박을 표시하고, 이전 버전은
읽기 전용으로 본 뒤 편집 칸에 불러올 수 있다.

### 시스템 행동

- 문항별 글자 수 제한을 검증한다 — **초과하면 422 로 거부**
- 버전 번호를 서버가 매긴다
- 새 버전이 생기면 이전 버전의 `is_current` 를 자동으로 내린다
- 같은 지원서 안에서 `position` 중복은 409

| 엔드포인트 | 설명 |
|---|---|
| `POST/GET /cover-letter-questions` | 문항 생성 / 목록 |
| `PATCH/DELETE /cover-letter-questions/{id}` | 부분수정 / 삭제 |
| `POST /cover-letter-questions/{id}/answers` | 새 답변 버전 |
| `GET .../answers?current_only=true` | 현재 버전만 |
| `GET /cover-letter-questions/{id}/outline` | 구조 잡기 — 어떤 경험을 어떤 순서로 쓸지만. 문장은 만들지 않는다 |
| `POST /cover-letter-questions/{id}/review?draft=` | 점검 — 글자 수와 근거 유무만. 문체 · 설득력은 판단하지 않는다 |

### 근거 규칙 — 타협 불가

AI 가 생성하는 모든 글은 **실제 Experience Bank 와 실제 JD 에 근거해야 한다.**
없는 경험이나 성과를 지어내면 안 된다.

경험이 부족하면 부족하다고 말해야 한다.

```
"지원 동기를 쓸 만한 관련 경험이 Experience Bank 에 없습니다.
 먼저 경험을 등록하거나 관련 프로젝트를 진행하는 걸 권합니다."
```

### 화면

`CoverLetterPanel.jsx` — Workspace 안에 있다.

```
문항 목록 (문항마다 작성 글자 수 / 제한 · 진행 막대)      [문항 추가하기]

선택한 문항
┌──────────────────────────┐
│  (작성 영역)              │     남은 글자 수 · 제한 임박 · 초과 표시
└──────────────────────────┘     저장하지 않은 변경 표시
[버전 ▾]  → vN 미리보기 (읽기 전용) → 편집 칸에 불러오기
[구조 잡기] [점검]                                 [저장]
```

아래는 처음 그린 목표 화면이다.
"초안 · 피드백 · 줄이기" 처럼 문장을 만드는 버튼은 만들지 않았다 (근거 규칙).
만든 것은 문장을 만들지 않는 `구조 잡기` 와 `점검` 둘이다.

```
← Applications      Data Scientist Intern      상태: preparing
─────────────────────────┬──────────────────────────────────
JOB ANALYSIS             │  자기소개서
                         │
MATCH 87%                │  1. 지원 동기를 작성해주세요
                         │  ┌──────────────────────────┐
요구 역량                │  │                          │
  Python      Strong     │  │  (작성 영역)              │
  SQL         Strong     │  └──────────────────────────┘
  실험설계     Gap       │                    438 / 500자
                         │
추천 경험                │  [문항 분석] [경험 추천]
  Data Station   92%     │  [구조 잡기] [초안] [피드백]
  Fake News      79%     │  [500자로 줄이기]
                         │
[원본 공고 보기]          │  [맞춤법 검사]      [ 저장 ]
```

### 향후 기능

```
Agent 기능: 문항 분석 · 초안 · 피드백 · N자로 줄이기      근거 규칙을 지킬 수 있을 때만
맞춤법 검사는 외부 서비스 링크로.  직접 만들지 않는다     현재 링크 없음
```

---

## 16. Career Agent — `구현됨 · UI 있음`

### 목적

별도의 챗봇이 아니라 **Career OS 전체의 intelligence layer**.

### 필요한 데이터

목표 직무 · 스킬 · 학습 진행도 · 프로젝트 · 경험 · 기회 · 지원 · 가용 시간

### 사용자 행동

자연어로 묻는다.

```
"오늘 뭐 해야 돼?"      "오늘 60분밖에 없어"
"지금 뭐 공부해야 해?"   "채용공고 보여줘"
"전체 업데이트 해줘"     "자동화 상태 알려줘"
```

### 시스템 행동

**LLM 이 아니다.** 키워드 부분문자열 매칭으로 의도를 고른다.

위에서부터 먼저 걸리는 것을 고른다.

| intent | 트리거 | 동작 |
|---|---|---|
| `today` | 오늘, today, 할 일, 뭐 해야 | 우선순위 + 프로젝트 + 자료로 계획 문장 생성 (저장된 오늘 계획은 바꾸지 않는다) |
| `jobs` | 공고, 채용, job, 회사 | 공고 목록 (레거시 Job) |
| `learning` | 공부, 학습, skill, 스킬, 배워 | 학습 우선순위 |
| `projects` | 프로젝트, project, 진행률 | 진행 중 프로젝트 |
| `automation_status` | 자동화 + 상태/언제/다음/확인 | 스케줄러 상태 |
| `automation` | 업데이트, 새로고침, 동기화, 자동화, update, refresh, sync | 파이프라인 실행 |
| `general` | 그 외 | 폴백 |

시간 추출: `"60분"` → 60, `"2시간"` → 120. 추출되면 분 단위로 배분한다.

**중요**: `tools.get_learning_priority` 는 `services/priority.py` 에 위임한다.
Mission 021 이전에는 자체 계산을 해서 API 와 점수가 달랐다.
**새 계산 로직을 tools.py 에 직접 쓰지 말 것.**

### 화면

`CareerCompanion.jsx` — 중심이 아니라 동반자다. 작업 화면 우하단에 작게 뜨고
(우주 홈에는 없다), 화면에 따라 이름이 바뀐다.

```
오늘 · (why)   오늘 계획 안내      캘린더   시간 안내
한눈에 보기    상태 안내           학습     학습 안내
프로젝트       프로젝트 안내       기회     기회 안내
경험           경험 안내           지원서   지원서 안내
회고           회고 안내
```

열면 입력칸에 포커스가 가고 `Esc` 로 닫힌다. 응답은 intent 별로 다르게 렌더링된다.

### 향후 기능

```
LLM 기반 추론
신규 데이터 접근      Learning Path / Opportunity / Experience / Application
                     현재 tools 는 레거시 4개 모델만 본다
쓰기 동작            "이 프로젝트 끝냈어" → 진행도 갱신 + 포트폴리오 제안
지원 준비 흐름        "이 공고 지원하고 싶어" → JD 분석 + 경험 매칭
Learning Session 튜터  "이 부분 이해 안 돼"
대화 맥락 유지        현재는 매 요청이 독립적
```

자세한 내용은 [AGENT.md](AGENT.md).

---

## 17. Automation — `구현됨 · UI 있음`

### 목적

사용자가 매번 챙기지 않아도 커리어 데이터가 최신으로 유지되게 한다.

### 필요한 데이터

수집원 응답 · 기존 공고 (중복 판정) · 스킬 목록 (자동 연결)

### 사용자 행동

Agent 에게 `"전체 업데이트 해줘"` 라고 하거나 그냥 둔다 (매일 08:00 자동).

### 시스템 행동

```
수집원 실행 (collectors/)        쓸 수 있는 것만: mock(운영에서는 꺼짐) · saramin(키 있고 공개 데모 아닐 때)
        ↓
Opportunity 저장 (upsert)        (source, external_id) 로 중복 판정
        ↓
스킬 연결                        jd.extract_skills — 단어 경계 · 조사 처리
        ↓
레거시 Job 브릿지                job 타입만. 대시보드 호환용
        ↓
기회 채점                        match_score / recommendation 저장
        ↓
시장 스냅샷 기록                 추세 계산의 근거
        ↓
career state 재계산
        ↓
결과 반환 + 상태 기록            ⚠ 메모리에만
```

- APScheduler 로 매일 08:00
- `POST /automation/run` 수동 실행
- `GET /automation/status` — 마지막 실행 / 상태 / 오류 / 다음 실행

프런트엔드는 Agent 가 `automation` 의도를 실행하면 대시보드를 자동 재조회한다.
기회 화면의 `수집 실행` 은 수집만 한다 (`POST /opportunities/collect`).

### 화면

Career Agent 동반자 응답 카드에 수집 결과가 표시된다.

### 향후 기능

```
사람인 수집원 실사용       코드는 있다. 키가 없거나 공개 데모면 건너뛴다
상태를 DB 에 저장           현재 메모리, 재시작하면 초기화
```

---

## 18. Calendar — `구현됨 · UI 있음`

### 목적

오늘 실제로 몇 분이 비었는지 알고, 마감까지 한 장에 본다.
**"수업이 없는 시간" 은 "공부할 수 있는 시간" 이 아니다.**

### 필요한 데이터

일정 블록(매주 반복이면 요일, 하루짜리면 날짜) · 활동 시간대 · 하루 상한 ·
지원서와 공고의 마감

### 사용자 행동

`캘린더` 화면(`#/calendar`)에서 월 · 주를 오가며 일정을 넣고, 날을 골라 오른쪽 칸에서 그날을 본다.
활동 시간대와 하루 상한을 고친다.

### 시스템 행동

```
kind        class 수업 · work 일 · 알바 · personal 개인 일정 · fixed 고정 · deadline 마감
all_day     종일 일정. 마감과 종일 일정은 빈 시간을 줄이지 않는다
            (all_day · deadline 은 날짜가 필수)
빈 시간     활동 시간대에서 겹치는 일정을 한 번만 빼고 계산
제안 시간   빈 시간과 하루 상한 중 작은 쪽
```

| 엔드포인트 | 설명 |
|---|---|
| `GET/POST /calendar/blocks` · `PATCH/DELETE /calendar/blocks/{id}` | 일정 |
| `GET /calendar/day?date=` | 그날 빈 시간과 제안 시간 |
| `GET /calendar/week` | 요일별 반복 일정과 빈 시간 |
| `GET /calendar/month?year&month` | 월요일부터 채운 주 격자. 반복 · 하루 일정 · 지원서와 공고 마감을 한 장에 |
| `PATCH /calendar/settings` | 활동 시간대 · 하루 상한 |

### 화면

`CalendarPage.jsx`. 월 격자(기본) · 주 시간 격자(종일 줄 포함) · 선택한 날 칸.

설정 칸은 **입력에서 벗어날 때(blur) 저장한다.** 저장 후
"이미 세운 오늘 계획은 오늘 화면에서 '이 설정으로 다시 세우기' 를 눌러야 반영돼요." 라고 알린다 —
설정을 바꿔도 오늘 계획을 몰래 다시 짜지 않는다.

### 향후 기능

```
학교 시간표 가져오기        하지 않는다. 직접 넣는다
```

---

## 19. 한눈에 보기 (Overview) — `구현됨 · UI 있음`

### 목적

Today 는 행동하는 곳, 여기는 **지금 상태를 한 장으로 이해하는 곳**이다.

### 필요한 데이터

오늘 계획 · 활성 목표와 준비도 · 이번 주 계획 기록 · 학습 경로 · 프로젝트 · 증거 · 지원서 마감 · 자격증

### 시스템 행동

`GET /overview` (`services/overview.py`) — 새로 판단하지 않고 각 서비스 값을 모은다.
모든 숫자는 분모와 함께 준다 — "실행률 50%" 가 아니라 "4개 중 2개".
이번 주 실행은 월요일부터 오늘까지이고, 오늘 아직 안 한 것은 분모에 넣지 않는다.

### 화면

`OverviewPage.jsx` (`#/overview`). 영역마다 한 칸, 칸마다 들어가는 길 하나.

```
한눈에 보기
오늘 (다음 할 일)
목표 · 준비도      이번 주 실행      학습 (다음 단계)
프로젝트 (증거 안 남은 것)   쌓인 증거   지원서 (7일 안 마감)
자격 · 어학 (만료됨 · 180일 안 만료)
```

전에는 옛 대시보드 데이터(주간 계획 · 원시 우선순위 점수 · 공고 목록)가 영어 라벨로 늘어서 있었다.

---

## 20. 회고 (Review) — `구현됨 · UI 있음`

### 목적

한 달을 모아 "무엇을 쌓았나" 와 **다음 달에 무엇을 바꿀까** 를 본다.

### 필요한 데이터

오늘 계획 기록(완료 · 넘김 · 이월) · 챕터 · 학습 단계 완료 시각 · 경험 · 포트폴리오 ·
모은 기회 · 지원 · 스킬 레벨 변경 기록

### 시스템 행동

`GET /analytics/review?year&month` (`services/review.py`)

```
execution    계획 대비 실행 — 계획 · 완료 · 넘김 · 놓침 · 남음, 영역별
postponed    반복해서 이월된 일과 횟수
next_month   규칙 기반 제안 (근거 문장 + 가는 화면)
               기록이 없으면   → 오늘 계획을 세우라고
               실행률이 낮으면 → 하루 계획을 줄이라고 (캘린더)
               자주 이월된 일  → 쪼개거나 빼라고
               프로젝트 미완이 많으면 → 더 작게 나누라고
learning · evidence · market · levels · done
```

**세지 못하는 것은 세지 않는다.** Project 에는 완료 시각이 없어 "이번 달에 끝낸 프로젝트" 는 세지 않는다.
스킬 레벨 변화는 `skill_level_events` 가 생긴 뒤부터만 센다.

| 엔드포인트 | 설명 |
|---|---|
| `GET /analytics/review?year&month` | 월 회고 |
| `GET /analytics/review/trend?months=` | 여러 달 추세 |
| `GET /analytics/activity?year&month` | 날마다 끝낸 것 (칸 격자) |

### 화면

`ReviewPage.jsx` (`#/review`).

```
회고  2026년 9월
다음 달에 바꿀 것
계획 대비 실행 · 끝낸 학습 · 쓴 시간 · 쌓은 증거 · 지원 활동
반복해서 미룬 일
어느 스킬에 쌓였는가 · 레벨이 바뀐 스킬
한 일
```

---

## 21. 자격증 · 어학 — `구현됨 · UI 있음`

### 목적

공고의 자격 요건 경고 옆에 **"내가 가진 것"** 을 보여주고, 만료를 미리 말한다.

### 필요한 데이터

```
category     language(어학) · job(직무 자격)
name · score · detail · issuer
status       held(보유) · planned(준비 중)
acquired_on · expires_on · note
```

**자격번호 · 수험번호 · 등록번호 칸은 일부러 없다.** 개인정보이고, 제출할 때는 원본 증빙을 쓴다.

### 시스템 행동

- 만료 180일 안이면 "만료 임박", 지나면 "만료됨"
- 공고의 `language` 경고에는 어학을, `license` 경고에는 직무 자격을 붙인다
- **충족 여부는 판단하지 않는다.** 공고마다 인정하는 시험과 기준이 다르다

| 엔드포인트 | 설명 |
|---|---|
| `GET/POST /certificates` | 목록 / 추가 |
| `PATCH/DELETE /certificates/{id}` | 수정 / 삭제 |

### 화면

`CertificatesCard.jsx` — `경험` 화면 안에 어학 · 직무 자격 두 칸.
기회 화면의 자격 경고 옆, 한눈에 보기의 `자격 · 어학` 칸에도 보인다.
