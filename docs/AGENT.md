# Career OS — Career Agent

> **현재 상태**: LLM 이 아니다. 키워드 부분문자열 매칭으로 의도를 고른다.
> `backend/app/agents/career_agent.py` (307줄), `tools.py`.

---

## 1. Career Agent 의 위치

Career Agent 는 **별도의 챗봇이 아니다.**
Career OS 전체를 관통하는 intelligence layer 다.

```
Career Data
  Target Career / Skills / Learning Progress
  Projects / Experiences / Opportunities
  Applications / Available Time
        │
        ▼
   Career Agent
        │
        ▼
"지금 가장 가치가 높은 다음 행동은 무엇인가?"
        │
        ▼
    Today Plan
```

챗봇처럼 "무엇이든 물어보세요" 가 아니라,
**Career OS 의 데이터를 근거로 결정을 내려주는 층**이다.

---

## 2. 현재 구현

### 2.1 파이프라인

```
사용자 메시지
      │
      ▼
detect_intent()          키워드 부분문자열 매칭
      │
      ▼
handler 선택
      │
      ▼
tool 실행                 DB 조회
      │
      ▼
결과 조합
      │
      ▼
응답 (dict)
```

### 2.2 의도 (7개)

| intent | 트리거 키워드 | 동작 |
|---|---|---|
| `today` | 오늘, today, 할 일, 뭐 해야 | 우선순위+프로젝트+자료로 계획 생성 |
| `jobs` | 공고, 채용, job, jobs, 회사 | 공고 목록 |
| `learning` | 공부, 학습, skill, 스킬, 배워 | 학습 우선순위 |
| `projects` | 프로젝트, project, 진행률 | 진행 중 프로젝트 |
| `automation_status` | 자동화 + (상태/언제/다음/확인) | 스케줄러 상태 |
| `automation` | 업데이트, 새로고침, 동기화, 자동화, update, refresh, sync | 파이프라인 실행 |
| `general` | 그 외 | 폴백 |

> 순서 주의: 위 표 순서대로 판정하고 처음 맞는 것을 쓴다.
> `automation_status` 판정이 `automation` 보다 먼저다.
> "자동화 상태" 가 실행으로 잘못 빠지지 않게 하려는 것.
> 반대로 "오늘" 이 들어가면 다른 키워드가 있어도 `today` 가 된다.

### 2.3 시간 인식

```python
"오늘 60분밖에 없어"   → 60
"2시간 있어"           → 120
```

정규식 `(\d+)\s*분`, `(\d+)\s*시간` 으로 추출한다.
추출되면 후보 행동들에 분 단위로 배분한다.

```
가용 60분
  ├─ 학습 자료 45분   (자료 길이만큼)
  └─ 프로젝트 15분    (남은 시간만큼)
총 60분
```

시간을 말하지 않으면 배분 없이 후보를 그대로 돌려준다.
후보는 1순위 스킬 하나에 맞는 자료 1개 · 프로젝트 1개까지다.

### 2.4 도구 (4개)

`backend/app/agents/tools.py`

| 도구 | 반환 |
|---|---|
| `get_learning_priority(db)` | 스킬별 우선순위 (services/priority.py 에 위임) |
| `get_active_projects(db)` | 미완료 프로젝트 |
| `get_saved_resources(db)` | `status == "saved"` 인 자료 |
| `get_jobs(db)` | 전체 공고 |

> **중요**: `get_learning_priority` 는 이제 `services/priority.py` 를 호출한다.
> Mission 021 이전에는 자체 계산을 해서 API 와 점수가 달랐다.
> **새로운 계산 로직을 tools.py 에 직접 쓰지 말 것.**
> 서비스 모듈에 넣고 호출할 것.

### 2.5 화면 — 동반자 캡슐

`frontend/src/components/CareerCompanion.jsx` · 엔드포인트 `POST /agent`

화면 맨 위 입력창이 아니라 우하단 작은 캡슐이다. 화면(view)에 따라
역할 이름과 예시 질문이 바뀐다. 이름은 할 수 있는 일에 맞춘다 —
저장된 것을 찾아 보여주는 **안내**다.

| 화면 | 역할 이름 |
|---|---|
| dashboard · why | 오늘 계획 안내 |
| overview | 상태 안내 |
| calendar | 시간 안내 |
| learning · library | 학습 안내 |
| projects | 프로젝트 안내 |
| opportunities | 기회 안내 |
| proof | 경험 안내 |
| applications | 지원서 안내 |
| review | 회고 안내 |

모르는 화면이면 `오늘 계획 안내` 로 떨어진다.

- 응답은 한 줄 요약으로만 그린다 (`summarize`). `today` · `learning` ·
  `jobs` · `projects` 만 요약하고, 나머지는 "결과를 받았습니다." 한 줄이다
- **원시 우선순위 점수는 보이지 않는다.** 학습 우선순위는
  `순위 · 스킬 · 레벨 n/4 · 기회 N건 중 M건` 으로 적는다
- 열면 입력 칸으로 포커스가 가고, **Esc 로 닫는다**
- 화면이 바뀌면 이전 답변을 지운다 (다른 역할이 답한 것처럼 읽히지 않게)
- `automation` 응답이 오면 대시보드를 새로 불러온다

---

## 3. 현재 한계

정직하게 적는다.

| 한계 | 영향 |
|---|---|
| **LLM 아님** | 키워드가 안 맞으면 `general` 폴백. 문장 이해 못 함 |
| **새 데이터 못 봄** | tools 가 레거시 4개 모델만 본다. Learning Path, Opportunity, Experience, Application 접근 불가 |
| **맥락 없음** | 대화 기록을 유지하지 않는다. 매 요청이 독립적 |
| **쓰기 못 함** | 조회와 자동화 실행만 가능. 상태 변경 불가 |
| **설명 부족** | "왜 이걸 추천하는지" 를 문장으로 말하지 못한다. 화면은 레벨과 기회 수만 보여준다 |
| **읽기 전용 배포본에서 안 됨** | `/agent` 가 POST 라 `ReadOnlyMiddleware` 가 403 으로 막는다. 캡슐은 연결 오류 문구를 띄운다 |

### 폴백 메시지

백엔드는 영어 문자열을 그대로 돌려준다.

```
"I could not determine which Career OS action to run."
```

화면은 이를 "어떤 동작을 실행할지 알아내지 못했습니다." 로 바꿔 보여준다.
무엇을 물으면 되는지는 캡슐의 예시 질문 버튼이 대신 알려줄 뿐,
폴백 응답 자체가 다음 행동을 안내하지는 않는다. 개선 필요.

---

## 4. 목표 동작

### 4.1 시간 제약

```
사용자: "오늘 60분밖에 없어"

Agent:
  현재 우선순위 확인
  진행 중 프로젝트 확인
  마감 임박 항목 확인          ← 아직 없음
  미완료 태스크 확인            ← 아직 없음
  → 현실적인 60분 계획
```

**현재 부분 구현.** 마감과 미완료 반영이 빠져 있다.

### 4.2 학습 방향

```
사용자: "지금 뭘 공부해야 해?"

Agent:
  시장 수요 확인
  스킬 격차 확인
  현재 학습 진행도 확인          ← 아직 없음
  → 다음 Learning Step 추천      ← 아직 없음 (스킬까지만)
```

### 4.3 프로젝트 완료 ❌

```
사용자: "이 프로젝트 끝냈어"

Agent:
  진행도 100% 로 갱신
  증명되는 스킬 판단
  Experience Bank 저장 제안
  Portfolio 항목 생성 제안
```

**전부 미구현.** 쓰기 동작 자체가 없다.

### 4.4 지원 준비 ❌

```
사용자: "이 공고 지원하고 싶어"

Agent:
  JD 분석
  내 스킬과 비교
  Experience Bank 에서 관련 경험 검색
  Application Workspace 준비
```

**전부 미구현.**

### 4.5 학습 튜터 ❌

Learning Session 안에서:

```
사용자: "이 부분 이해 안 돼"

Agent:
  현재 스킬 / 단계 / 자료를 알고
  그 맥락에 맞춰 설명
```

**미구현.** Learning Session 화면(`LearningSession.jsx`)은 있지만
Agent 가 그 맥락을 받지 못하고, 설명을 생성할 LLM 도 없다.

---

## 5. 맥락 소스

Agent 가 최종적으로 참조해야 할 것들.

| 소스 | 현재 접근 | 목표 |
|---|---|---|
| Skills | ✅ | ✅ |
| Jobs | ✅ | Opportunity 로 확장 |
| Projects | ✅ | ✅ |
| Learning Resources | ✅ | ✅ |
| Learning Path / Step | ❌ | 필요 |
| Learning Progress | ❌ | 필요 |
| Opportunities | ❌ | 필요 |
| Experiences | ❌ | 필요 |
| Applications | ❌ | 필요 |
| Available Time | ✅ (문장에서 추출) | 화면 입력도 |
| Target Career | ❌ | 모델은 있음 (`TargetCareer`). Agent 가 못 봄 |
| 현재 Learning Session | ❌ | 필요 |

---

## 6. 근거 규칙 — 타협 불가

LLM 을 도입하더라도 다음은 반드시 지킨다.

### 6.1 경험을 지어내지 않는다

자기소개서나 이력서 문장을 생성할 때:

```
✅ Experience Bank 에 저장된 실제 경험만 사용
✅ 실제 JD 텍스트만 참조
❌ 그럴듯한 성과를 만들어내기
❌ 하지 않은 활동을 추가하기
❌ 수치를 추정해서 넣기
```

경험이 부족하면 **부족하다고 말해야 한다.**

```
"지원 동기를 쓸 만한 관련 경험이 Experience Bank 에 없습니다.
 먼저 경험을 등록하거나, 관련 프로젝트를 진행하는 걸 권합니다."
```

### 6.2 통계를 지어내지 않는다

Market Signals 는 반드시 수집된 실제 데이터에서 계산한다.

```
❌ "AWS 수요가 68% 입니다" (근거 없이)
✅ 저장된 공고 N건 중 AWS 를 요구하는 공고 수로 계산
```

데이터가 부족하면 부족하다고 표시한다.

### 6.3 추천에 이유를 붙인다

```
❌ "AWS 를 공부하세요"

✅ "AWS 를 공부하세요.
    저장된 공고 5건 중 4건이 AWS 를 요구하는데
    현재 레벨이 0 이고 관련 프로젝트도 없습니다."
```

### 6.4 할 일을 늘리지 않는다

Agent 는 **줄이는 쪽**으로 작동해야 한다.
목록을 길게 반환하는 것은 실패다.

필요하면 "지금 하지 마세요" 라고 말한다.

---

## 7. 확장할 때의 규칙

1. **계산 로직은 `services/` 에 둔다.** Agent 핸들러에 직접 쓰지 않는다
2. **API 와 Agent 가 같은 함수를 쓴다.** 두 개의 진실을 만들지 않는다
   (이미 한 번 어긋났고 Mission 021 에서 고쳤다)
3. **도구는 얇게.** 도구는 데이터를 가져오고, 판단은 핸들러/서비스가 한다
4. **표현 로직을 Agent 에 넣지 않는다.** Agent 는 데이터를 반환하고
   화면이 그린다 (현재 프런트가 intent 별로 분기해서 그린다)
5. **LLM 도입 시에도 도구 기반 구조를 유지한다.**
   모델이 DB 를 직접 쿼리하게 하지 말고 도구를 호출하게 한다
