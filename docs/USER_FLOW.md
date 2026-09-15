# Career OS — User Flows

> 각 단계에 구현 상태를 표시했다.
> ✅ 구현됨 · UI 있음 / 🟡 구현됨 · API만 / ❌ 계획
>
> **이 문서가 Career OS 에서 가장 중요한 문서 중 하나다.**
> 개별 기능이 아니라 기능들이 **어떻게 연결되는지**를 정의한다.

---

## 1. 핵심 시나리오 — 공고 하나에서 지원까지

Career OS 가 존재하는 이유를 한 흐름으로 보여주는 시나리오.

```
공고 발견                                    ✅
  기회 화면 "공고 붙여넣기" → POST /opportunities/parse (규칙 기반 미리보기)
  → 틀린 칸을 고쳐 "이대로 저장" (POST /opportunities)
  → 스킬 연결 → 채점
  (보조: "수집 실행" POST /opportunities/collect)
  "Data Scientist Intern — AWS 우대"  [78] 지금 할 만해요 D-28
      ↓
"지원서 만들기"                              ✅
  Application 생성 (status: interested)
      ↓
JD 분석                                      ✅ 규칙 기반
  GET /applications/{id}/analysis
  (등록된 스킬 이름을 본문에서 찾는다. LLM 아님)
      ↓
Skill Gap 발견                               ✅
  Python 있음 · SQL 있음 · AWS 없음
      ↓
AWS 부족                                     ✅
      ↓
Learning Priority 상승                       ✅
  market 100% × gap 4 × evidence 1.0 = 400
      ↓
AWS Learning Path 생성                       ✅
  EC2 → S3/IAM → FastAPI 배포
      ↓
오늘 EC2 45분                                ✅
  오늘 화면 → 계획의 학습 단계 → 학습 세션 (#/learning/sessions/:id)
  WHY NOW: "공고 1건 중 1건이 AWS 를 요구하는데
            현재 레벨 0 이고 프로젝트 증거가 없습니다"
      ↓
단계 완료                                    ✅
  결과 카드 "✓ 학습 세션 완료" — 진행률 전→후, 오늘 계획에서 함께 끝낸 일
  "다음 단계 보기 · S3/IAM" 로 이어짐
  학습 진행률이 evidence_weight 를 낮춰 우선순위 하락
      ↓
AWS Deployment Project                       ✅
  진행률·ETA 추적
      ↓
Project Completed                            ✅
  완료 패널 "✓ 프로젝트를 완료했습니다" + 증명되는 역량
      ↓
경험으로 저장                                ✅ 한 번 누르기
  POST /projects/{id}/to-experience (내용 복사, 지어내지 않음)
      ↓
Portfolio Entry                              ✅ "포트폴리오 준비"
  POST /experiences/{id}/portfolio-entry
      ↓
다른 AWS 공고 발견                            ✅
      ↓
Experience Match                             ✅ 규칙 기반 자동 매칭
  지원서 화면 "추천 경험" → POST /applications/{id}/auto-match
  (사람이 쓴 메모는 덮어쓰지 않음)
      ↓
Application Workspace                        ✅ #/applications/:id
      ↓
자기소개서 작성                               🟡 규칙 기반 도움만
  글자 수 검증 ✅  /  구조 잡기(outline) ✅  /  기계적 점검(review) ✅
  AI 문장 생성 ❌
      ↓
지원                                         ✅
  POST /applications/{id}/move   status: applied  (전이 규칙 있음)
      ↓
결과가 다시 Career OS 로 피드백               ❌
```

### 지금 어디가 이어져 있고 어디가 끊겼나

```
DISCOVER → DECIDE                        ✅ 이어짐
                                         (붙여넣기·수집 → 기회 점수 → 추천)
DECIDE → LEARN → BUILD                   ✅ 이어짐
           ↑         │
           └─────────┘                   ✅ Mission 022 에서 닫힘
         (학습이 우선순위를 바꾼다)

BUILD → PROVE                            ✅ 완료 패널이 경험·포트폴리오를 제안
PROVE → APPLY                            ✅ 규칙 기반 추천 경험 · 자동 매칭
APPLY → DISCOVER                         ❌ 결과 피드백 없음
```

**가장 큰 남은 구멍**: `APPLY → DISCOVER`.
지원 결과(합격·불합격)가 우선순위나 기회 판단으로 돌아오지 않는다.
연결된 구간도 판단은 규칙 기반이다 — 문장을 만드는 AI 는 없다.

---

## 2. 오늘 계획 흐름

```
오늘 화면 (#/today)
  │  쓸 수 있는 시간: 캘린더 기준 제안값
  │    (활동 시간대에서 일정을 뺀 빈 시간 중 하루 상한까지, GET /calendar/day)
  │  강도: 가볍게 · 보통 · 몰입
  │  "계획 세우기" → POST /today/plan
  ▼
후보 모으기                                      ✅ services/today.py
  │  앞쪽이 먼저: 마감(14일 안, 3일 안이면 맨 앞) → 어제 못 한 일(이월) → …
  │
  ├─► 지원서 · 기회 마감                          ✅
  ├─► 이월된 일 (carried_from)                   ✅ 오래 밀린 이월은 계획에 넣지 않고 물어본다
  ├─► 다음 학습 단계 / 내 자료                    ✅ 우선순위 계산(services/priority.py) 기준
  └─► 미완료 커리어 프로젝트                      ✅
  │
  ▼
시간 배분                                        ✅
  │  강도별 최대 개수 · 블록 길이 안에서 나눈다
  ▼
오늘 할 일 (daily_plan_tasks 에 저장)
  │  완료 · 넘김 · 되살리기
  │  "왜 이 계획인가?" → #/today/why (GET /today/why)
```

Career Agent 는 우하단 동반자(CareerCompanion)로 남아 있다.
"오늘 뭐 해야 돼?" 같은 질문에 답하지만 계획을 저장하는 곳은 오늘 화면이다.

### 우선순위 계산식 (실제 코드)

```
market_percentage = round(요구 기회 수 / 전체 기회 수 × 100)   ← 모수는 Opportunity

skill_gap         = max(0, 4 - 내 레벨)              ← 음수 방지

project_strength  = 가장 멀리 간 커리어 프로젝트 하나의 세기
                    시작 0.10 · 진행 중 0.25 · 완료 0.50
                    · 보여줄 것 있음(GitHub·데모·결과) 또는 경험 전환 0.70
                    · 둘 다 0.85
learning_strength = 0.4 × (평균 경로 진행률 / 100)
evidence_strength = project + learning - project × learning   (최대 0.85)
evidence_weight   = max(0.15, 1 - evidence_strength)
target_weight     = 1.0 (활성 목표 스킬 · 목표 없음) / 0.6 (목표와 무관)

priority_score    = round(market_percentage × skill_gap
                          × evidence_weight × target_weight)
```

> **주의**: Mission 021 이전에는 이 계산이 4곳에 복사되어 있었고 서로 다른 값을 냈다.
> 지금은 API 와 Agent 가 같은 함수를 쓴다.
> **새로운 계산 지점을 만들지 말고 이 모듈을 호출할 것.**

### 캘린더와의 연결

```
캘린더 화면에서 일정 · 활동 시간대 · 하루 상한을 바꾼다
  설정은 칸을 벗어날 때(blur) 저장된다
  → "저장했어요 … 이미 세운 오늘 계획은 오늘 화면에서
     '이 설정으로 다시 세우기'를 눌러야 반영돼요" 안내
  이미 세운 계획은 저절로 다시 짜이지 않는다
```

---

## 3. 학습 완료 흐름 — Mission 022 에서 연결됨

```
학습 세션 열기  (#/learning/sessions/:id)              ✅
  GET /learning-steps/{id}/session
  why_now / goals / materials
              │
              ▼
학습 시작                                             ✅
  POST /learning-steps/{id}/start
              │
              ▼
단계 완료                                             ✅
  POST /learning-steps/{id}/complete
  오늘 계획에 같은 단계가 있으면 함께 완료 처리
              │
              ▼
결과 카드 "✓ 학습 세션 완료"                          ✅
  무엇이 바뀌었는지(effects): 학습 진행률 전 → 후,
  우선순위 반영 안내, 함께 끝낸 오늘 계획
  "다음 단계 보기 · {제목}" / 오늘 화면으로 돌아가기
              │
              ▼
Learning Path 진행률 갱신                             ✅
  스텝이 바뀌는 즉시 자동 계산
              │
              ▼
Skill Evidence                                        ✅
  learning_strength = 0.4 × (진행률/100)
              │
              ▼
Learning Priority 재계산                              ✅
  evidence_weight = max(0.15, 1 - (project ⊕ learning))
              │
              ▼
다음 Today Plan 변화                                  ✅
  집중 스킬과 다음 학습 단계가 바뀜
```

### 남은 것

```
❌ Skill.level 자동 상승
   학습은 evidence_weight 로만 반영되고 레벨은 사용자가 직접 정한다.
   (학습 화면 "진행과 레벨" 탭에서 바꾸면 skill_level_events 에 이력이 남는다)
   시스템이 사용자 설정을 덮어쓰지 않기 위한 선택.
❌ 목표 체크를 서버에 저장  (현재 브라우저 localStorage 에만)
```

---

## 4. 프로젝트 완료 흐름

```
프로젝트 진행률 100%  (프로젝트 화면)                 ✅
  status 가 completed 로 바뀜
  "'{이름}' 을(를) 완료했어요. 아래에서 증거로 남기세요."
              │
              ▼
완료 패널 "✓ 프로젝트를 완료했습니다"                  ✅
  증명되는 역량 목록 (GET /projects/{id}/evidence)
              │
              ├─► "경험으로 저장"                     ✅
              │     POST /projects/{id}/to-experience
              │     → 경험 화면에서 역할과 한 일을 채우라고 안내
              │
              ├─► "포트폴리오 준비"                   ✅
              │     (경험이 없으면 먼저 만들고)
              │     POST /experiences/{id}/portfolio-entry
              │
              ├─► "나중에 하기"
              │     완료했지만 증거로 안 남은 프로젝트는 다음 행동 카드로 다시 뜬다
              │
              ├─► GitHub · 데모 URL, 결과              ✅ Project 에 필드 있음
              │
              └─► 이력서 문장 생성                     ✅ 경험 화면의 포트폴리오 항목에서
                    POST /portfolio-entries/{id}/resume-bullet
                    저장된 내용으로만 만들고, 빈 칸이 있으면 "약해요" 로 알린다
```

증거 단계는 우선순위에도 반영된다. 완료 0.50 → 보여줄 것 또는 경험 전환 0.70 → 둘 다 0.85.

---

## 5. 지원 흐름 — 규칙으로 돕고, 문장은 사람이 쓴다

```
기회 화면에서 공고 선택
              ▼
지원서 생성  "지원서 만들기"                          ✅
  POST /applications   status = interested
  (또는 "오늘 계획에 준비 추가" — 지원서가 없으면 관심 상태로 함께 만든다)
              ▼
지원서 목록  (#/applications)                         ✅
  맨 위에 가장 먼저 할 일 하나 (GET /applications/board)
  줄마다 마감 · 매칭 · 자소서 진행 · 다음 행동
  필터: 진행 중 · 지원 전 · 지원 후 · 끝남
              ▼
지원서 화면  (#/applications/:id)                     ✅
              ▼
JD 분석 · 요구 역량                                   ✅ 규칙 기반
  GET /applications/{id}/analysis
  등록된 스킬 이름을 단어 경계로 본문에서 찾고 강조도를 낸다
  한계는 "이 분석의 한계" 로 화면에 적는다
              ▼
추천 경험 → 자동 매칭                                 ✅ 규칙 기반
  POST /applications/{id}/auto-match
  (사람이 쓴 메모는 덮어쓰지 않음)
              ▼
자소서 문항 등록                                      ✅
  POST /cover-letter-questions   (글자 수 제한 포함)
              ▼
답변 작성                                             🟡 규칙 기반 도움만
  ✅ 글자 수 초과 시 422 거부
  ✅ 버전 자동 증가, 이전 버전 is_current 해제, 이전 버전 미리보기
  ✅ 구조 잡기 GET /cover-letter-questions/{id}/outline (어떤 경험을 어떤 순서로)
  ✅ 점검 POST /cover-letter-questions/{id}/review (글자 수 · 근거 유무만)
  ❌ AI 초안 / 문체 피드백 / 줄이기 없음
              ▼
상태 전이                                             ✅
  POST /applications/{id}/move?status=applied
  허용된 다음 상태만 갈 수 있다 (GET /applications/{id}/transitions)
  잘못 누른 것은 force 로 되돌린다
```

### 상태 흐름

```
관심 → 준비 중 → 준비 완료 → 지원함
interested → preparing → ready → applied
                                    │
                                    ├─► document_pass(서류 통과) → interview(면접) → accepted(합격)
                                    │         │                            └─► rejected
                                    │         └─► rejected
                                    └─► rejected(불합격)

끝나지 않은 상태에서 언제든 → withdrawn(철회)
accepted · rejected · withdrawn 은 끝 상태 (services/application.py TRANSITIONS)
```

---

## 6. 자동화 흐름

```
매일 08:00 (APScheduler)                              ✅
   또는 POST /automation/run
   또는 Agent "전체 업데이트 해줘"
              ▼
수집원 실행 (collectors/)                             ⚠ 쓸 수 있는 것만
   mock     운영 환경이 아닐 때만
   saramin  API 키가 있고 공개 데모가 아닐 때만
              ▼
Opportunity 저장 (upsert)                             ✅ 재수집해도 중복 없음
              ▼
스킬 연결                                             ✅ 단어 경계 · 별칭(aliases) 매칭
                                                         (services/jd.py, LLM 아님)
              ▼
레거시 Job 브릿지                                     ✅ job 타입만, /jobs 호환
              ▼
기회 채점                                             ✅ 점수 + 판정 저장
              ▼
시장 스냅샷 기록                                       ✅ 추세의 근거
              ▼
career state 재계산                                    ✅
              ▼
결과 반환 + 상태 기록                                  ⚠ 메모리에만
```

프런트엔드는 동반자(CareerCompanion)에서 Agent 가 `automation` 을 실행하면
대시보드 API 를 자동 재조회한다. ✅

---

## 7. 현재 사용자가 실제로 할 수 있는 것

정직하게, 지금 **화면에서** 가능한 것.
홈(`#/`)은 우주 화면이고, 천체를 누르면 각 작업 화면으로 들어간다.
작업 화면은 사이드바의 한국어 이름으로 오간다.
모든 작업 화면 우하단에 동반자(화면마다 역할이 바뀌는 Career Agent)가 있다.

### 한눈에 보기 (`#/overview`)

```
영역마다 한 칸 — 숫자는 분모와 함께, 칸마다 들어가는 링크 하나
  목표 · 준비도 → 학습      이번 주 실행 → 회고      학습 → 다음 단계 열기
  프로젝트 → 프로젝트       쌓인 증거 → 경험         지원서 → 지원서
  N일 안 마감 → 기회        자격 · 어학 → #/experience/certificates
행동은 여기서 하지 않는다. 오늘 화면에서 한다
```

### 오늘 (`#/today`, `#/today/why`)

```
1. 쓸 시간(캘린더 기준 제안)과 강도(가볍게 · 보통 · 몰입)를 고르고 "계획 세우기"
2. 오늘 할 일 완료 · 넘김 · 되살리기, 이월 표시 확인, 다가오는 마감 확인
3. "이 설정으로 다시 세우기"
4. "왜 이 계획인가?" — 판단에 쓴 것과 원본 숫자
5. 계획의 학습 단계에서 학습 세션으로 바로 이동
```

### 캘린더 (`#/calendar`)

```
1. 한 달 격자에서 매주 일정 · 하루 일정 · 마감 보기
2. 날짜를 골라 일정 추가 (수업 · 일 · 알바 · 개인 일정 · 고정 · 마감, 종일 가능)
3. 활동 시간대와 하루 상한 — 칸을 벗어나면 저장, 오늘 계획을 다시 세우라고 안내
```

### 학습 (`#/learning`, `#/learning/sessions/:id`)

```
탭: 학습 경로 · 내 자료 · 세션 기록 · 진행과 레벨
1. 학습 경로 만들기 (스킬 연결), 단계 추가
2. 단계를 눌러 학습 세션 열기
3. WHY NOW 확인 — 왜 지금 이걸 배우는지
4. 목표 체크, 자료 열기 (URL 없는 자료는 "오프라인")
5. 단계 완료 → 결과 카드 → 다음 단계 보기
6. 진행과 레벨 탭에서 스킬 레벨 바꾸기
```

### 내 자료 (`#/library`)

```
1. 서가 — 전체 · 책 · 영상 · 문서 · 실습 가로 레일
2. 자료 등록 · 챕터(조각) 관리
3. 오늘 계획에 추가
```

### 프로젝트 (`#/projects`)

```
1. 진행률 · 목표 완료일 기록, 스킬 연결
2. 100% → 완료 패널 → 경험으로 저장 / 포트폴리오 준비 / 나중에 하기
```

### 기회 (`#/opportunities`)

```
1. 공고 붙여넣기 → 미리보기(찾은 칸 · 지원 자격 경고) → 고쳐서 저장
2. 매칭 점수와 판정, 요구 스킬 지도, 시장 수요 추세 확인
3. 지원서 만들기 / 오늘 계획에 준비 추가 / 보류 · 관심 없음으로 옮기기
4. 수집 실행
```

### 지원서 (`#/applications`, `#/applications/:id`)

```
1. 가장 먼저 할 일, 필터별 목록
2. JD 분석 · 추천 경험 · 자동 매칭
3. 상태 이동 (허용된 다음 상태만)
4. 자기소개서 — 문항, 버전, 구조 잡기, 점검
```

### 경험 (`#/experience`, `#/experience/:section`)

```
section: projects · experience · activities · portfolio · certificates
1. 경험으로 남길 수 있는 프로젝트
2. 프로젝트 · 연구 · 대회 / 활동 편집
3. 포트폴리오로 만들기, 이력서 문장 만들기
4. 내 GitHub · 블로그 링크
5. 자격증 · 어학 (번호는 받지 않음, 만료 미리 표시)
```

### 회고 (`#/review`)

```
1. 달 넘기기
2. 다음 달에 바꿀 것 — 맨 위. 규칙으로 고르고 근거 숫자를 함께 보인다
     기록 없음 → 오늘 계획 세우기
     실행률 50% 미만(5개 이상) → 하루 계획 줄이기 (캘린더)
     같은 일 3번 이상 이월 → 쪼개거나 빼기
     프로젝트 작업 3개 이상 미완 → 더 작게 나누기
3. 계획 대비 실행 · 끝낸 학습 · 쓴 시간 · 쌓은 증거 · 지원 활동
4. 반복해서 미룬 일 · 어느 스킬에 쌓였는가 · 레벨이 바뀐 스킬 · 한 일
```

### 아직 API 로만 가능한 것

목표 직무(TargetCareer) 만들기 · 활성화 · 데이터 내보내기/가져오기(`/transfer`)

```
http://127.0.0.1:8000/docs
```
