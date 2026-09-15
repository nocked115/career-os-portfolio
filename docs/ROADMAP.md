# Career OS — Roadmap

> Mission 번호 체계를 **Phase 로 교체했다.**
> 기능 단위가 아니라 제품 흐름 단위로 가는 것이 이해하기 쉽기 때문이다.
>
> 이미 만들어진 것은 아래 "기존 작업 매핑" 에 있다.
> **다시 만들지 말 것.** 실제 상태는 [CURRENT_STATE.md](CURRENT_STATE.md) 가 기준이다.

---

## 현재 위치

```
✅ PHASE 0   PROJECT RESET        완료
✅ PHASE 1   CORE                 완료
✅ PHASE 2   LEARNING             완료
✅ PHASE 3   OPPORTUNITIES        완료
✅ PHASE 4   BUILD & PROVE        완료
✅ PHASE 5   APPLICATION          완료
✅ PHASE 5.5 LIBRARY 화면          완료
✅ PHASE 5.6 CALENDAR             완료 — 수동 입력으로. ICS 는 안 함
   PHASE 6   CAREER AGENT         LLM 도입 결정 필요
◐  PHASE 7   POLISH · 배포 + Basic Auth   홈 · 라우팅 · 인증 · 데모 · Docker 는 됨
```

---

## 기존 작업 매핑 — 이미 되어 있는 것

Mission 021~023 에서 만든 것이 Phase 어디에 해당하는지.

| 기존 | 결과물 | 해당 Phase | 상태 |
|---|---|---|---|
| Mission 021 | Alembic, 11개 테이블, 라우터 구조, `services/priority.py` 통합 | Phase 1 기반 | ✅ 완료 |
| Mission 022 | Learning Path/Step/Session, 진행률 연쇄, 자료 중요도 | Phase 2 일부 | ✅ 완료 |
| Mission 023 | `collectors/` 어댑터, 기회 수집·매칭, 시장 스냅샷 | Phase 3 일부 | ✅ 완료 |

**즉 Phase 2 와 Phase 3 은 백엔드가 상당 부분 이미 있다.**
남은 것은 My Learning Library, Target Career, 그리고 화면이다.

---

## ✅ PHASE 0 — PROJECT RESET

**상태: 완료.** (아래 목록의 문서는 모두 `docs/` 에 있다.)

당시 원칙 — 코드를 쓰지 않는다.

세션마다 기능이 하나씩 붙으면서
"이 앱을 켜면 나는 무엇을 하게 되는가" 가 흐려졌다. 기준점을 다시 세운다.

```
□ 제품 정의 고정              PRODUCT.md
□ 기능 명세 고정              FEATURES.md + 영역별 문서
□ 시각 정체성 고정            DESIGN.md — Career Universe
□ 현재 코드 Audit             CURRENT_STATE.md
□ 데이터 구조 확정            DATA_MODEL.md
□ 인수인계 갱신               CODEX_HANDOFF.md
□ 살릴 것 / 수정할 것 / 새로 만들 것 분류
```

분류 기준:

```
현재 이미 있음           → 그대로 살림
현재 있지만 방향이 다름   → 수정
아직 없음                → 새로 구현
v1 에 필요 없음          → Backlog
```

분류 결과는 [CURRENT_STATE.md 8장](CURRENT_STATE.md) 에 있다.

---

## ✅ PHASE 1 — CORE

**상태: 완료.**

목표였던 것 — 북극성("오늘 뭘 해야 하지?")이 실제로 동작하게 한다.

### 만든 것

**Target Career** — 모든 우선순위 계산의 기준점

```
target_weight = 1.0  목표가 요구하는 스킬 · 또는 목표 없음
              = 0.6  목표는 있는데 무관한 스킬
```

`services/priority.py` 안에 가중치 하나로 넣었다. 새 계산 지점을 만들지 않았다.
목표가 없으면 전부 1.0 이라 이전과 결과가 같다.
기회 매칭은 우선순위를 읽으므로 **별도 구현 없이 따라왔다.**

**Today Plan** — 시스템이 오늘 할 일을 결정한다

```
가용 시간 입력      화면에서 직접 (30/60/120/180 또는 직접 입력)
강도                가볍게 / 보통 / 몰입
마감 반영           3일 이내 지원 준비를 맨 앞에
완료 체크           학습 단계면 실제 진행도까지 갱신
미완료 이월         어제 못 한 것이 오늘로 넘어온다
```

계획을 DB 에 저장한다. 완료 체크와 이월은 기록이 있어야 가능하다.
계획을 만들 때 쓴 설정도 함께 저장한다 — 안 그러면 조회 시
실제와 다른 "남은 시간" 이 나온다.

**증거 집계** — `GET /analytics/evidence`

홈의 별 개수. 총합과 구성을 함께 준다. 떨어진 지원도 센다.

### 고친 것

**다크 모드에서 화면 제목이 전부 보이지 않던 버그.**
`src/index.css` 가 Vite 스타터 템플릿 그대로였고,
다크 미디어쿼리가 `h1/h2` 를 `#f3f4f6` 으로 칠하는데
`App.css` 배경은 `#f5f6f8` 이었다. 흰 글씨에 흰 배경.
같은 파일이 `text-align: center` 와 정체불명의 세로선도 만들고 있었다.

### 남긴 것

```
Job vs Opportunity 이중 구조 정리 방향       모수는 Opportunity 로 모았다.
                                             레거시 Job 과 브리지(legacy_job_id)는 남아 있다
대시보드를 Opportunity 기반 집계로 전환      /analytics/skills 는 아직 레거시
자동화 상태를 DB 로                          현재 메모리
```

~~수동 생성 기회의 스킬 자동 연결~~ — 됐다. 기회를 만들 때 스킬을 연결하고
(`routers/opportunities.py` 의 `link_skills`), 나중에 등록한 스킬은
`POST /opportunities/relink-skills` 로 다시 잇는다.

### 테스트

186개 (Phase 0 시점 130개 + 56개)

---

## 참고 — Phase 1 에서 정리하려던 것 (일부는 남음)

### 새로 만들 것

**Target Career** — 지금 제품 전체에서 가장 크게 빠진 조각

```
목표 직무가 없어서:
  · 학습 우선순위가 "전체 공고" 기준으로 계산된다
  · 기회 매칭의 "목표 직무 관련성" 을 계산할 수 없다
  · 우주 홈 중앙 행성이 보여줄 정체성이 없다
```

최소 형태로 시작한다. 직무명 + 관련 키워드 + 목표 시점 정도.
`services/priority.py` 안에서만 반영한다. 새 계산 지점을 만들지 않는다.

**Today 보강**

```
가용 시간 입력       화면에서 직접 (현재는 Agent 문장으로만)
Intensity            Light / Normal / Deep Focus
마감 반영            공고·지원 마감을 계획에 넣기
태스크 완료 체크      체크하면 진행도로 이어지기
미완료 이월          어제 못 한 일이 오늘로
```

### 정리할 것

```
Job vs Opportunity 이중 구조 정리 방향 결정
  현재 legacy_job_id 로 병행 중. 언제 어떻게 끝낼지
대시보드를 Opportunity 기반 집계로 전환
자동화 상태를 DB 로 (현재 메모리)
index.css 의 Vite 기본값 text-align:center 전역 정리
```

---

## ✅ PHASE 2 — LEARNING

**상태: 완료.**

목표였던 것 — 내가 이미 가진 것 중에서 오늘 필요한 것만 고른다.

### 설계 결정 — 방향 A (기존 확장)

`LEARNING.md` 3.3 이 남겨둔 A/B 중 **A 를 골랐다.**

`LearningResource` 는 이미 10곳에서 쓰이고 있었고(학습 단계 연결,
Learning Session 렌더링, 우선순위, 주간 계획, Agent 도구),
별도 `LibraryItem` 을 만들면 그 전부를 이중화하거나 이전해야 했다.

그리고 A 의 우려로 적혀 있던 "라이브러리 항목과 스텝 자료의 성격이 섞인다" 는
실제로는 문제가 아니라 **제품 논지 그 자체**였다.
내 라이브러리 항목이 학습 단계에 연결되면 그게 곧 오늘의 자료다.

### 만든 것

```
url          NOT NULL → nullable      종이책에는 URL 이 없다
ownership    owned · saved · wishlist
total_units / unit_label              "420쪽" 같은 전체 분량

Segment      "3장 — EC2 기초" · 88~112쪽 · 15분 · 진행 상태
             조각이 전부 끝나면 자료도 완료로 올라간다
```

**Resource Selector** — 오늘 볼 것만 고르고 나머지는 치운다

```
정렬   중요도 → 소유(가진 것 우선)
제외   끝낸 조각 · 예상 시간 없는 자료 · 남은 시간에 안 맞는 것
```

치운 것을 이유와 함께 함께 돌려준다.
**"나머지 3개 → 지금은 볼 필요 없음" 을 빼면 그냥 목록이다.**

### 화면

- Learning 페이지에 라이브러리 요약 (종류별 개수 · 소유 구분 · 조각 진행)
- Learning Session 의 자료 목록을 선별 결과로 교체.
  URL 없는 자료는 링크 대신 "오프라인" 으로 표시

### 남긴 것

```
자료 자동 분할 (책 목차에서 챕터 뽑기)
학습 목표 체크를 서버에 저장                 지금은 이 브라우저에만 남는다
```

~~Segment 관리 화면~~ — Phase 5.5 에서 만들었다.

### 테스트

205개 (Phase 1 시점 186개 + 19개)

---

## 참고 — Phase 2 계획 원문

### 새로 만들 것 — My Learning Library

```
막고 있는 것:
  LearningResource.url = Column(String, nullable=False)
      → 내가 가진 종이책은 URL 이 없다
  "책 3장" 같은 부분 단위 개념이 없다
  소유("내 책") 와 참조("추천 자료") 를 구분하지 않는다
```

필요한 구조:

```
📕 Books           소유 여부 · 챕터 단위 · 페이지
▶  Saved Videos    저장 출처 · 구간(타임스탬프)
📄 Documents       공식 문서 · 논문 · 아티클
💻 Practice        코딩 문제 · 데이터셋 · 실습
```

그 위에 **Resource Selector** — Learning Step 에 맞는 자료를
내 Library 에서 골라주고, **나머지는 "지금 볼 필요 없음" 으로 치운다.**

자세한 설계는 [LEARNING.md](LEARNING.md).

### 이미 있는 것 (살림)

```
Learning Path / Step / 순서 / 진행률
Learning Session — WHY NOW · 목표 · 중요도별 자료
학습 완료 → 우선순위 반영 연쇄
자료 중요도 (primary / supplementary / deep_dive)
```

### 화면

```
Learning 페이지 보강 (My Library 포함)
Learning Session 에 내 자료 연결
```

---

## ✅ PHASE 3 — OPPORTUNITIES

**상태: 완료.**

목표였던 것 — 많이 가져오는 게 아니라 선별한다.

### 만든 것

**필요 시간** (`Opportunity.estimated_hours`)

남은 날짜만으로는 "할 수 있는가" 를 판단할 수 없었다.
40시간짜리를 5일 안에 끝내는 것과 4시간짜리를 5일 안에 끝내는 것은 다르다.

```
하루 1시간 이하 comfortable · 2시간 이하 workable
하루 4시간 이하 tight "빠듯합니다"
하루 4시간 초과 unrealistic "지금 일정으로는 끝내기 어렵습니다"
```

필요 시간을 모르면 예전처럼 남은 날짜로 판단한다. 추정해서 넣지 않는다.

**계획에 추가** — `POST /opportunities/{id}/add-to-plan`

DISCOVER 가 북마크 목록으로 끝나지 않게 하는 연결이다.
지원서가 없으면 관심 상태로 만들고 오늘 계획에 태스크를 올린다.
지원서를 함께 만드는 이유는 나중에 결과를 추적할 곳이 필요해서다.

**Opportunities 화면**

```
탭        전체 / 공고 / 공모전 / 활동
카드      Match% · D-day · 예상 시간 · 판정 · 근거 · 점수 구성
Skip      "지금은 아닌 것" 을 접지 않고 이유와 함께 보여준다
```

탭에 "인턴" 을 넣지 않았다. 모델의 종류는 셋이고 인턴은
`job` 의 `employment_type` 이다. **없는 구분을 있는 척하지 않는다.**

**Market Signals 화면** — 스킬별 수요와 추세.
비교할 과거가 없으면 화살표를 그리지 않고 그 사실을 적는다.

### 이미 해결돼 있던 것

**목표 직무 관련성** — Phase 1 에서 Target Career 를 만들 때
관련성 항목이 학습 우선순위를 읽으므로 **별도 구현 없이 따라왔다.**
계산을 한 곳에만 둔 덕분이다.

### 고친 것

`OpportunityUpdate` 스키마에 `estimated_hours` 를 빠뜨려
PATCH 가 조용히 무시하던 문제. Mission 022 에서 `create_resource` 가
`importance` 를 빠뜨린 것과 같은 유형이라 테스트로 고정했다.

### 남긴 것

```
대시보드 시장 신호를 Opportunity 기반으로 전환  현재 레거시 /analytics/skills
실제 외부 수집원                                사람인 API 수집원은 있다.
                                                API 승인 대기라 아직 못 켠다
스킬 연결 정확도 (부분문자열 매칭)
```

~~Opportunities 화면을 사이드바로 통합~~ — 사이드바의 "기회" 로 들어갔다.
외부 수집 대신 **공고 붙여넣기**(`POST /opportunities/parse`, 규칙 기반,
링크를 열지 않는다)를 넣었다. DECISIONS 26장.

### 테스트

218개 (Phase 2 시점 205개 + 13개)

---

## 참고 — Phase 3 계획 원문

목표: **많이 가져오는 게 아니라 선별한다.**

### 이미 있는 것 (살림)

```
collectors/ 어댑터 계약과 레지스트리
Opportunity upsert · 스킬 연결 · 레거시 Job 브릿지
매칭 점수 (관련성 40 / 준비도 30 / 포트폴리오 15 / 마감 15)
"Skip this" 판정과 근거
MarketSnapshot 기반 추세
```

### 남은 것

```
Opportunities 화면          탭(전체/공고/인턴/공모전/활동) · Match% · D-day
목표 직무 관련성 반영        Phase 1 의 Target Career 선행
필요 시간 추정              Opportunity 에 소요 시간 개념 없음
Market Signals 화면         추세 ↑↓ 표시
```

자세한 설계는 [OPPORTUNITIES.md](OPPORTUNITIES.md).

---

## ✅ PHASE 4 — BUILD & PROVE

**상태: 완료.**

목표였던 것 — 한 활동이 취업에 쓸 수 있는 증거로 변환된다.

### 만든 것

```
Project 완료 → 증거화 제안 → Experience Bank → Portfolio → Resume Bullet
```

**증거화 제안** — `GET /projects/{id}/evidence`

무엇을 증명하는지와 남은 행동 6가지를 돌려준다.
프로젝트를 끝내도 아무 제안이 없으면 사용자는 그냥 잊는다.

```
[x] 결과 기록          무엇을 이뤘는지 한 줄이라도 남겨야 증거가 된다
[x] GitHub URL 추가    코드가 있으면 가장 강한 증거다
[ ] 데모 URL 추가
[ ] Experience Bank 에 저장
[ ] Portfolio 항목 만들기
[ ] 이력서 문장 만들기
```

완료되지 않은 프로젝트에도 답한다. "아직 아니다" 도 정확한 상태다.

**모델 보강** — `Project` 에 `github_url` · `demo_url` · `results`,
`PortfolioEntry` 에 `resume_bullet`.
`PATCH /projects/{id}` 도 추가했다. 이전에는 프로젝트 수정 수단이 아예 없었다.

**이력서 문장** — LLM 이 아니라 저장된 조각을 조립한다.

```
{기술} 기반 {제목} — {행동} → {결과}
```

무엇을 했고 어떤 결과가 있었는지가 둘 다 비면 **문장을 만들지 않는다.**
"지어내지 않습니다" 라고 답하고 무엇이 비었는지 알려준다.

**Experience 화면** — 증거의 별, 증거화 제안, Experience Bank, Portfolio.

### 설계 결정 — Situation / Task 는 나누지 않는다

`LEARNING.md` 와 마찬가지로 미결로 남아 있던 항목이다.

STAR 의 S 와 T 는 실제로 쓸 때 한 문단으로 나온다.
필드를 둘로 나누면 한쪽이 비어 있는 경우가 많아지고,
반쯤 찬 필드 두 개는 잘 찬 필드 하나보다 나쁘다.

`problem`(상황과 과제) + `role`(내 역할) 로 이미 S 와 T 를 담고 있다.
**나누지 않는다.**

### 고친 것

```
create_project/skill/job 이 새 필드를 조용히 누락하던 문제
  → 세 번째였다. 전부 **model_dump() 로 통일하고 회귀 테스트 추가

Project.results 에 server_default 누락
  → 기존 행이 NULL 이 되어 /projects 가 500 으로 죽었다.
     Phase 2 의 unit_label 과 같은 실수. 마이그레이션을 고쳐 재적용

add-to-plan 의 minutes 에 제약 누락
  → minutes=-5 가 통과해 "-5분" 태스크가 계획에 들어갔다.
     ge=5, le=480 추가
```

### 남긴 것

```
프로젝트 "다음 작업" 칸      담을 모델이 없다. 목표일과 하루 시간으로 계획에 들어가는 것까지
```

### 테스트

239개 (Phase 3 시점 218개 + 21개)

---

## 참고 — Phase 4 계획 원문

목표: **한 활동이 취업에 쓸 수 있는 증거로 변환된다.**

지금 가장 크게 끊긴 구간이다. 데이터 구조는 다 있는데 이어주는 판단이 없다.

```
Project 완료
   ↓  ❌ 제안 없음
Experience Bank
   ↓  🟡 수동 API
Portfolio Entry
   ↓  ❌ resume_bullet 없음
Resume Bullet
```

### 할 것

```
프로젝트 완료 감지 → 증거화 제안
   "이 프로젝트가 증명하는 역량: AWS · FastAPI · Docker
    ✓ Experience Bank 에 저장   ✓ Portfolio 준비
    ○ Resume Bullet 생성        ○ Demo URL 추가"

Project 에 GitHub URL / demo URL / results 필드
PortfolioEntry 에 resume_bullet
Experience Bank 화면
Portfolio 화면
Situation / Task 분리 여부 결정 (현재 problem 하나로 합쳐져 있음)
```

---

## ✅ PHASE 5 — APPLICATION

**상태: 완료.** (백엔드 · 화면 둘 다)

목표였던 것 — 지원 준비가 처음부터 다시 쓰는 일이 아니게 한다.

### 만든 것

**JD 분석** — 등록된 스킬 이름을 본문에서 찾는다. LLM 이 아니다.

```
기존:  "go" in description   → "Google" 에도 걸렸다
지금:  단어 경계 + 언급 횟수 + 첫 등장 위치 → 강조도
```

실제 결과:

```
Python  strong  언급 2회  첫 등장 0자   강조도 50
SQL     strong  언급 1회  첫 등장 11자  강조도 36
AWS     gap     언급 1회  첫 등장 69자  강조도 14
```

**경험 자동 매칭** — 요구 역량을 얼마나 덮는지로 채점한다.
사람이 직접 넣던 점수를 대체한다. 사람이 쓴 메모는 덮어쓰지 않는다.

**상태 전이 규칙** — 순서를 건너뛰면 409.
잘못 누른 것을 되돌릴 길로 `force=true` 를 남겼다.

**자소서 지원** — 구조를 잡아주고 기계적으로 점검한다.

### 할 수 없는 것을 명시했다

```
문장 생성       LLM 이 있어야 한다. 구조만 잡는다
N자로 줄이기    요약은 LLM 이 있어야 한다. 만들지 않았다
문체·설득력     판단하지 않는다고 응답에 적는다
등록 안 된 역량  찾지 못한다고 notes 에 적는다
```

### 화면 (완료)

```
Applications      상태별 집계 · 전이 버튼 · Workspace 진입
                  버튼은 갈 수 있는 상태만 보인다.
                  순서를 건너뛸 방법이 화면에 없다

Workspace 좌      JD 분석 (강조도 막대 · Strong/Medium/Gap)
                  추천 경험 + 자동 매칭
                  **이 분석의 한계** 를 화면에 그대로 띄운다

Workspace 우      문항 · 작성 · 실시간 글자 수
                  구조 잡기 — 빈 칸은 "(비어 있음 — 지어내지 않습니다)"
                  점검 — 무엇을 못 보는지 화면에 적는다
```

제한을 넘으면 저장 버튼이 잠긴다.

### 남긴 것

```
PATCH /applications/{id}     상태 전이 규칙을 거치지 않는다.
                             규칙은 /move 에만 걸려 있다
```

### 테스트

268개 (Phase 4 시점 239개 + 29개)

---

## ✅ PHASE 5.5 — LIBRARY 화면

**상태: 완료.**

Phase 2 에서 만든 기능이 화면이 없어 실제로는 못 쓰고 있었다.

### 만든 것

```
Learning 페이지를 탭 두 개로   [학습 경로] [내 라이브러리]
자료 등록 폼                   종류 11가지 · 소유 3가지 · 중요도 3단계
                               URL 은 선택 (종이책은 비워둔다)
                               분량과 단위 (420쪽 · 90분)
조각 관리                      "3장 — EC2 기초 · 88~112쪽 · 15분"
                               추가 · 완료 체크 · 삭제
```

### 확인한 것

조각 하나를 완료하니 선별에서 빠지고 **다음 조각이 자동으로 올라왔다.**

```
완료 전:  3장 — EC2 기초 (15분)  선택됨
완료 후:  5장 — IAM 기초 (20분)  선택됨   ← 3장은 빠짐
          나머지 자료 3개 → 지금은 볼 필요 없음
```

보유 자료가 저장 자료보다 앞선다.

### 남긴 것 — 사용자가 하겠다고 한 것

```
자료 작업 완료 → 챕터 체크     오늘 계획의 자료 작업을 끝내도 챕터는
                              자동으로 안 바뀐다. 내 자료 화면에서 직접 체크

유튜브 재생목록 자동 가져오기
  "나중에 볼 동영상" 을 손으로 옮기지 않아도 되게 하는 것.
  YouTube Data API + OAuth 가 필요하다.
  범위를 따로 잡아야 하는 항목이라 여기서는 하지 않았다
```

---

## 참고 — Phase 5.5 계획 원문

**Phase 2 에서 만든 기능이 화면이 없어 실제로는 못 쓴다.**

```
✅ 백엔드    내 책(URL 없어도 됨) · 저장한 영상 · 조각(챕터/구간) · 선별기
❌ 화면      개수 요약만 있다. 등록도 쪼개기도 API 로만 가능하다
```

새 기능보다 우선한다. 만들어둔 것이 죽어 있는 상태이기 때문이다.

### 할 것

```
자료 등록 폼          책(소유·쪽수) · 영상(URL·길이) · 문서 · 실습
조각 관리             "3장 88~112쪽 15분" 추가 · 완료 체크
학습 단계에 연결       라이브러리에서 골라 붙이기
```

### 하지 않을 것 (지금은)

```
유튜브 재생목록 자동 가져오기
  YouTube Data API + OAuth 가 필요하다. 계획에 없던 항목이라
  범위를 정하고 별도로 잡는다
```

---

## PHASE 5 — APPLICATION (계획 원문)

목표: **지원 준비가 처음부터 다시 쓰는 일이 아니게 한다.**

### 이미 있는 것 (살림)

```
Application 9단계 상태
경험 매칭 저장 구조
자소서 문항 · 글자 수 검증 · 답변 버전 관리
```

### 남은 것

```
JD 텍스트 분석              현재는 수동 연결된 스킬만 봄
경험 자동 매칭 점수          현재는 사람이 입력
Application Workspace 화면   좌: 분석 / 우: 작성
실시간 글자 수 카운트
Agent 지원: 문항 분석 · 경험 추천 · 구조 · 초안 · 피드백 · N자로 줄이기
상태 전이 규칙
```

**절대 규칙**: AI 가 쓰는 모든 글은 실제 Experience Bank 와 실제 JD 에 근거한다.
없는 경험을 지어내지 않는다. 경험이 부족하면 부족하다고 말한다.

자세한 설계는 [APPLICATIONS.md](APPLICATIONS.md).

---

## ✅ PHASE 5.6 — CALENDAR

**상태: 완료 — 2순위(수동 입력)로.**

### 만든 것

```
일정 모델              매주 반복(weekday) · 하루짜리(date) · 종류 · 마감(deadline) · 종일
가용 시간 계산          활동 시간대 − 일정(겹침은 한 번) → 빈 시간, 하루 상한까지
Today 에 반영          Today 가 GET /calendar/day 의 제안 분으로 계획을 세운다
한 달 격자             매주 일정 · 하루 일정 · 지원서/공고 마감 (DECISIONS 21장)
```

마감과 종일 일정은 빈 시간을 줄이지 않는다. 달력의 마감은 Today 의 D-day 띠에
뜨지만 할 일로 만들지 않는다.

### 남긴 것

```
ICS 구독 URL · Google Calendar    둘 다 안 했다
```

---

아래는 계획 원문이다.

**가용 시간을 매번 손으로 넣는 것을 없앤다.**

지금 Today 는 "오늘 몇 분 쓸 수 있나" 를 사용자가 직접 입력한다.
이 제품에서 가장 어색한 지점이고, 북극성에 가장 가까운 미완성이다.

```
지금        [30분] [60분] [120분] [180분]  ← 사용자가 고른다
목표        수업 3개 · 과제 마감 2개 → 남는 시간 자동 계산
```

수업 일정과 과제 마감이 계획에 들어가지 않으면
"현실적인 계획" 이라고 말할 수 없다.

### 할 것

```
일정 모델              제목 · 시작/종료 · 반복(수업) · 종류
가용 시간 자동 계산      하루 총량에서 일정을 뺀 나머지
Today Plan 에 반영      마감이 임박한 과제를 계획 후보로
```

### 붙이는 방법

```
1순위   ICS 구독 URL      학교 시간표는 대개 .ics 로 내보낼 수 있다.
                         OAuth 없이 읽기만 하면 된다
2순위   수동 입력         반복 일정을 직접 넣는다
나중에  Google Calendar   OAuth 가 필요하다. 범위를 따로 잡는다
```

**OAuth 없이 절반은 된다.** ICS 부터 시작한다.

---

## PHASE 6 — CAREER AGENT

목표: **Agent 가 Career OS 를 조작하는 인터페이스가 된다.**

Agent 자체가 제품의 중심은 아니다. Career OS 가 중심이고 Agent 는 인터페이스다.

### 현재 한계

```
LLM 아님 — 키워드 부분문자열 매칭
도구가 레거시 4개 모델만 본다
   Learning Path · Opportunity · Experience · Application 접근 불가
대화 맥락 없음 — 매 요청이 독립적
쓰기 동작 없음 — 조회와 자동화 실행만
```

### 먼저 정할 것 — LLM 도입 여부

아래가 전부 여기에 묶여 있다. LLM 없이는 흉내만 난다.

```
자소서 초안 생성 · N자로 줄이기 · 문체와 설득력 판단
학습 내용을 이해했는지 파악
Learning Session 튜터
자연어 이해 (지금은 키워드 매칭)
```

### 할 것

```
전체 Context 연결
Today Planning        마감·미완료까지 반영한 계획
Learning Tutor        현재 세션의 스킬/단계/자료를 알고 설명
Application Assistant  JD 분석 → 경험 매칭 → Workspace 준비
쓰기 동작             "이 프로젝트 끝냈어" → 진행도 갱신 + 제안
```

### 보류 — 증거 자동 수집

지금 "완료" 체크는 **자기신고**다. 체크만 하면 우선순위가 내려가고
증거의 별이 늘어난다. 실제로 안 했어도 그렇다. 이건 실제 구멍이다.

다만 **"진짜 했는지 검사한다"** 는 방향으로 풀지 않는다.

```
❌ 검증   "정말 했어? Velog 확인해볼게"       감시하는 앱은 안 쓰게 된다
✅ 수집   Velog 글을 쓰면 자동으로 Experience 가 된다
```

증거를 자동으로 모아주면 자기신고 문제가 저절로 줄어든다.
벌이 아니라 보상 구조다. Notion / Velog 연동과 이해도 판단은
둘 다 LLM 결정 이후에 다시 본다.

자세한 설계는 [AGENT.md](AGENT.md).

---

## PHASE 7 — POLISH

```
✅ Career Universe 홈 구현      Universe.jsx · services/universe.py
✅ 전체 UI 정리                 한국어 사이드바 · 해시 라우터(router.js) ·
                               공통 컴포넌트(ui.jsx) — DECISIONS 23~29장
□  실제 외부 데이터 연결         사람인 수집원은 있으나 API 승인 대기
□  Automation 안정화            상태는 아직 메모리(main.py automation_status)
   테스트 보강                  계속
```

### 배포 — Basic Auth 로 간다

**이 앱에는 로그인이 없다.** 사용자 개념 자체가 없어서,
공개 URL 에 그냥 올리면 주소를 아는 누구나 커리어 데이터를 보고 고친다.

정한 방향:

```
실제 사용    로컬 (진짜 커리어 데이터)
배포본       Basic Auth + 데모 데이터 (포트폴리오용)
```

두 개를 분리하면 유출 위험이 사라진다.
모든 테이블에 `user_id` 를 붙이는 제대로 된 인증은 규모가 크고,
지금 목적(본인 사용 + 가끔 보여주기)에는 과하다.

### 단계

```
✅ 1  환경 설정 정리       CORS · DB 주소를 환경변수로 (CAREER_OS_DATABASE_URL)
✅ 2  Basic Auth          로컬에서는 꺼둔다 (auth.py)
✅ 3  데모 데이터 시드     demo.py
□  4  PostgreSQL 전환      안 했다. 배포본도 SQLite 파일(/data)을 쓴다
◐  5  백엔드 배포          Dockerfile 하나로
◐  6  프런트 배포          따로 올리지 않고 같은 컨테이너가 빌드 결과를 서빙한다
```

실제로 간 방향은 조금 다르다. 공개 데모는 Basic Auth 없이 열되
**반드시 읽기 전용**(`CAREER_OS_PUBLIC_DEMO`)이고, 실사용 배포본은
자격 증명이 없으면 뜨지 않는다. 자세한 것은 [DEPLOY.md](DEPLOY.md).

---

## 규칙

1. **한 번에 한 Phase.** 끝났다고 자동으로 다음으로 넘어가지 않는다
2. 코드를 먼저 읽고 수정한다
3. 동작하는 기능을 문서에 맞추려고 다시 쓰지 않는다
4. 모델을 바꾸면 마이그레이션을 만든다
5. Phase 마다 테스트를 돌린다
6. 새 기능은 [PRODUCT.md](PRODUCT.md) 3장의 필터를 통과해야 한다
7. 코드가 이 순서보다 나은 순서를 시사하면 조정할 수 있다
