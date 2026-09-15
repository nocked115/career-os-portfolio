# Career OS — Applications

> Applications 영역의 상세 설계. Experience Bank · Portfolio · 자기소개서를 포함한다.
> 전체 방향은 [PRODUCT.md](PRODUCT.md), 현재 구현은 [CURRENT_STATE.md](CURRENT_STATE.md).

---

## 1. 이 영역이 하는 일

지원 준비가 **매번 처음부터 다시 쓰는 일이 아니게** 한다.

```
프로젝트를 했다
    ↓  (지금은 여기서 기억이 끊긴다)
자소서를 쓸 때 그 경험을 떠올린다
```

Career OS 는 그 사이를 저장 구조로 잇는다.

```
Project Completed
       ↓
Experience Bank        구조화해서 저장
       ↓
Portfolio Entry        보여줄 수 있는 형태로
       ↓
Application            공고에 맞춰 꺼내 쓴다
```

---

## 2. Experience Bank

### 저장 형태

```
EXPERIENCE

Data Analysis Project

TYPE        Project
SITUATION   신용카드 이탈 분석 프로젝트
MY ROLE     데이터 분석 및 모델링
ACTIONS     전처리 · EDA · RandomForest 모델링 · 결과 해석
RESULT      우수상
SKILLS      Python · Pandas · Machine Learning
TAGS        #problem-solving #analysis #collaboration
```

### 현재 구현과의 차이

| 명세 | 현재 모델 |
|---|---|
| `Situation` 과 `Task` 분리 | **`problem` 하나로 합쳐져 있다** |
| 나머지 필드 | 있음 (role · actions · results · technologies · metrics · tags) |
| 스킬 연결 | 있음 (M:N) |
| Project 연결 | 있음 (1:1) |

### 결정: 나누지 않는다 (Phase 4)

STAR 의 Situation 과 Task 는 실제로 쓸 때 한 문단으로 나온다.
필드를 둘로 나누면 한쪽이 비는 경우가 많아지고,
**반쯤 찬 필드 두 개는 잘 찬 필드 하나보다 나쁘다.**

`problem`(상황과 과제) + `role`(내 역할) 이 이미 S 와 T 를 담는다.

### 아직 없는 것 (2026-09-15 확인)

```
구조화된 태그 검색       현재 tags 는 자유 텍스트
```

화면(Experience · `ProofPage.jsx`)과 공고에 맞는 경험 추천
(`jd.recommend_experiences`)은 이제 있다.

---

## 3. Project → Experience 전환

예전에 가장 크게 끊긴 구간이었다. 지금은 이어져 있다 (2026-09-15 확인).

```
프로젝트 진행률 100%                    ✅ 저장됨 (status 를 안 바꿔도 proof.is_complete 가 완료로 본다)
        ↓
Career OS 가 제안                       ✅ GET /projects/{id}/evidence — proof.build_suggestions
        ↓
Experience Bank 저장                    ✅ POST /projects/{id}/to-experience (이미 있으면 그것을 쓴다)
        ↓
Portfolio 항목                          ✅ POST /experiences/{id}/portfolio-entry
        ↓
이력서 문장                              ✅ POST /portfolio-entries/{id}/resume-bullet
```

제안은 순서가 있는 할 일 목록이다 — 결과 기록 → GitHub 링크 → 데모 링크 →
경험으로 저장 → 포트폴리오 항목 → 이력서 문장. 남은 것 중 첫 번째가
`next_action` 이다. 프로젝트 화면이 프로젝트마다 이 응답을 읽고, 맨 위에
`완료한 프로젝트 · 아직 증거로 안 남음` 카드를 띄운다 (`ProjectsPage.jsx`).
경험 화면은 `완료한 프로젝트 · 아직 경험으로 안 남음` 카드에서 바로
`to-experience` 를 부른다 (`ProofPage.jsx`).

### 처음 그렸던 목표 — 프로젝트 완료 시점

```
🎉 PROJECT COMPLETED

AWS Deployment Project

You've created evidence for
  AWS · FastAPI · Docker · Deployment

Recommended next actions
  ✓ Save to Experience Bank
  ✓ Prepare Portfolio Entry
  ○ Generate Resume Bullet
  ○ Add Demo URL
```

이 제안이 없으면 사용자는 프로젝트를 끝내고 그냥 잊는다.
**증거화는 자동 제안이 있어야 실제로 일어난다.**

### 막고 있던 것 — 풀림

```
Project 에 GitHub URL / demo URL / results 필드가 없다   → 생김 (models.Project)
프로젝트 완료를 감지하는 지점이 없다                     → 이벤트는 없고, 읽을 때
                                                          proof.is_complete 로 판정한다
```

`🎉` 축하 화면은 만들지 않았다. 원칙대로 남은 할 일과 이유(`hint`)만 보여준다.

---

## 4. Portfolio

독립적으로 처음부터 쓰는 게 아니다.

```
Project Completed → Experience Bank → Portfolio Entry
```

### 구성

```
TITLE
ONE-LINE SUMMARY
PROBLEM
MY ROLE
APPROACH
RESULT
TECH STACK
GITHUB
DEMO
RESUME BULLET
```

### 현재

`POST /experiences/{id}/portfolio-entry` 가 경험 내용을 복사해
`draft` 상태 항목을 만들고 원본과 연결한다.

`resume_bullet` 필드가 있고(`models.PortfolioEntry`),
`POST /portfolio-entries/{id}/resume-bullet` 이 저장된 역할 · 한 일 · 결과 ·
기술에서만 초안을 만든다 (`proof.build_resume_bullet`). **재료가 부족하면 문장
대신 무엇이 비었는지 돌려준다.** 경험 화면의 포트폴리오 카드에
`이력서 문장 만들기` 버튼이 있다.

---

## 5. Applications — 지원 과정 전체

```
Interested
    ↓
Preparing
    ↓
Ready
    ↓
Applied
    ↓
Document Pass
    ↓
Interview
    ↓
Accepted / Rejected

언제든 → Withdrawn
```

지원/불합격만 기록하는 게 아니라 **준비 과정 전체**를 관리한다.

### 현재

- 9단계 상태가 스키마로 고정되어 있다
- `Opportunity` 또는 레거시 `Job` 중 하나에 연결된다
- 경험 매칭을 점수·메모와 함께 저장한다

### 지금 (2026-09-15 확인)

```
화면                      ApplicationsPage · ApplicationWorkspace
상태 전이 규칙            services/application.py TRANSITIONS — 건너뛰면 409
경험 자동 매칭 점수        jd.auto_match — 사람이 쓴 메모는 덮지 않는다
다음 행동                  services/application_board.py — 목록 · Workspace · 요약이 같은 규칙
보드                      GET /applications/board
```

### 보드 — "그래서 지금 무엇을 해야 하지?"

`GET /applications/board` 가 지원서마다 한 번에 모은다. 목록과 Workspace 가
같은 응답을 쓴다.

```
카드마다
  마감        지원서에 적은 날. 없으면 공고의 마감 (deadline_source 로 구분)
  매칭        JD 에서 찾은 요구 역량 중 레벨 1 이상인 것 — have / total, 분모와 함께
  자소서      저장된 답이 비어 있지 않은 문항 수 — answered / total
  다음 행동   next_action (아래 순서)
  빠진 것     missing — deadline · description · questions

요약
  before_applying   지원 전(관심 · 준비 중 · 준비 완료)
  urgent            지원 전 중 7일 안에 마감
  writing           지원 전 중 문항을 일부만 씀
  next              지원 전 카드 중 행동할 수 있는 것, 마감이 가까운 순 첫 번째
```

다음 행동은 순서가 곧 규칙이다.

```
끝남(합격 · 불합격 · 철회)  → 없음
지원함 · 서류 통과          → 결과 기다리기
면접                        → 면접 준비
마감 지남                   → 마감이 지났습니다 (철회로 정리)
문항 없음                   → 자기소개서 문항 등록
안 쓴 문항                  → N번 문항 작성
제한의 절반보다 짧은 문항    → N번 문항 보완
준비 완료                   → 지원서 제출 (공고에서 제출 후 '지원함')
그 밖                       → '준비 중' 또는 '준비 완료' 로 옮기기
```

**고를 근거가 없으면 `next` 를 비운다.** 화면이 "아직 다음 행동을 정할 정보가
부족합니다" 라고 말한다. 다음 행동을 지어내지 않는다.

목록 화면의 거르기 칩은 `진행 중 · 지원 전 · 지원 후 · 끝남 · 전체` 다. 상태
이름은 화면 어디서나 `applicationLabels.js` 한 곳의 한국어를 쓴다
(관심 · 준비 중 · 준비 완료 · 지원함 · 서류 통과 · 면접 · 합격 · 불합격 · 철회).

### 아직 없는 것

```
결과 피드백               합격/불합격이 다음 추천에 반영되지 않는다
```

---

## 6. Cover Letter Workspace

공고 하나를 위한 작업 공간. 넓은 화면에서는 **왼쪽에 근거, 오른쪽에 작성.**
위에는 지원서 요약 · 상태 단계 · 다음 행동이 가로로 걸친다
(`ApplicationWorkspace.jsx` · `Applications.css .ws2`).

```
┌───────────────────────────────────────────────────────────────┐
│ ← 지원서 목록                                                  │
│ 지원서 · Data Scientist Intern · D-5 · 공고 원문 ↗             │
│ 관심 ─ 준비 중 ─ 준비 완료 ─ 지원함 ─ 서류 통과 ─ 면접 ─ 결과   │
│ 다음 행동  2번 문항 작성                     [ 작성하러 가기 ] │
├──────────────────────────┬────────────────────────────────────┤
│ JD 분석 · 요구 역량       │ 자기소개서            작성 1 / 2 문항│
│ 요구 역량 3개 중 2개 보유 │ [1번 ✓ 438/500자] [2번 0/500자]     │
│ 갖고 있는 역량            │ 2. 입사 후 포부를 작성해주세요       │
│  ✓ Python Lv 2 · 본문 3회 │ 버전 [v1 · 현재 · … ▾]               │
│ 부족한 역량               │ ┌────────────────────────────────┐ │
│  ! 실험설계 Lv 0          │ │  작성 영역                      │ │
├──────────────────────────┤ └────────────────────────────────┘ │
│ 추천 경험                 │ 438 / 500자 · 62자 남음              │
│ 92% Data Project  원문 보기│ v1 저장됨 · 9월 14일 10:20          │
│ [이 지원서에 매칭 저장]    │         [구조 잡기] [점검] [ 저장 ] │
├──────────────────────────┤ 문항 추가 [ … ] 글자 수 제한 [500]   │
│ 이 분석의 한계            │                                    │
└──────────────────────────┴────────────────────────────────────┘
```

화면 라벨은 한국어다. 예전 시안의 `JD ANALYSIS` · `COVER LETTER` ·
`RECOMMENDED EXPERIENCE` 와 문항 분석 · AI 피드백 · 500자로 줄이기 ·
맞춤법 검사 버튼은 없다.

`구조 잡기` 는 `GET /cover-letter-questions/{id}/outline`,
`점검` 은 `POST /cover-letter-questions/{id}/review` 다 (`routers/workspace.py`).

### 현재 되는 것

```
문항 등록 (글자 수 제한 포함)
글자 수 초과 시 422 로 거부
답변 버전을 서버가 매김
새 버전이 생기면 이전 버전의 is_current 자동 해제
```

### 지금 (2026-09-15 확인)

```
화면                      CoverLetterPanel — Workspace 안
실시간 글자 수            남은 글자 · 제한 임박(90%) · 초과 표시. 초과면 저장 버튼이 막힌다
문항별 진행              탭마다 글자 수 막대 · 저장 여부 · 저장 안 한 변경 점
버전                      이전 버전 읽기 전용 보기 · 편집 칸에 불러오기
구조 잡기                  경험 원문을 STAR 칸에 배치, 빈 줄로 나눈 문단과 칸을 잇는다
                          경험에 빈 칸은 "(경험에 비어 있음 — 지어내지 않습니다)"
점검                      글자 수 · 경험 언급 · 수치 유무
잃지 않게                  문항을 옮겨도 저장 전 글이 남고, 창을 닫거나 목록으로 가면 묻는다
문항 없음                  [문항 추가하기] · [공고에서 문항 가져오기 ↗] — 공고를 자동으로 읽지 않는다
```

### 아직 없는 것

```
Agent 기능 일체           문장을 만들거나 고치는 기능은 없다 — 근거 규칙 때문에 일부러
맞춤법 검사 링크
```

---

## 7. 근거 규칙 — 타협 불가

AI 가 생성하는 모든 글은
**실제 Experience Bank 와 실제 JD 에 근거해야 한다.**

```
✅ 저장된 경험만 사용
✅ 실제 JD 텍스트만 참조
❌ 그럴듯한 성과를 만들어내기
❌ 하지 않은 활동을 추가하기
❌ 수치를 추정해서 넣기
```

### 경험이 부족하면 부족하다고 말한다

```
"지원 동기를 쓸 만한 관련 경험이 Experience Bank 에 없습니다.
 먼저 경험을 등록하거나, 관련 프로젝트를 진행하는 걸 권합니다."
```

이게 Career OS 가 자소서 생성기와 다른 지점이다.
**없는 경험을 채워주는 게 아니라, 없다는 사실을 알려준다.**

### 맞춤법 검사

한국어 맞춤법 검사기를 직접 만들지 않는다.
외부 서비스 링크로 위임하고, 아키텍처가 그 서비스에 의존하지 않게 한다.

---

## 8. 전체 연결

```
Opportunity
     ↓
Job Analysis          요구 역량 · 내 격차
     ↓
Experience Matching   Experience Bank 에서 관련 경험 검색
     ↓
Application           상태 추적
     ↓
Cover Letter          경험을 근거로 작성
     ↓
지원 · 면접
     ↓
결과가 다시 Career OS 로
```

마지막 화살표(결과 피드백)는 아직 설계되지 않았다.
합격/불합격이 다음 추천에 어떻게 반영될지는 Phase 5 에서 정한다.
