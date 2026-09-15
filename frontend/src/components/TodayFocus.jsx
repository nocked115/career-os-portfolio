/* 오늘 무엇에 집중할지, 그리고 왜 그것인지.

   DESIGN.md 원칙 1 — 근거 없는 추천은 없다.
   `/today` 는 reason 을 계산해서 내놓고 있었는데
   화면이 priority_score 숫자만 쓰고 나머지를 버리고 있었다.

   퍼센트는 절대 혼자 쓰지 않는다. 분모를 같이 쓴다.
   "100%" 는 공고가 1건일 때도 100% 다. */

const LEVEL_LABELS = [
  "아직 시작 안 함",
  "기초",
  "익히는 중",
  "실무 가능",
  "목표 도달"
]

function levelLabel(level) {
  return LEVEL_LABELS[level] ?? `레벨 ${level}`
}

/* reason 을 사람이 읽는 줄로 바꾼다.
   근거가 없으면 없다고 쓴다 — 지어내지 않는다. */
function buildReasons(reason, nextStep) {
  if (!reason) {
    return []
  }

  const rows = []

  rows.push({
    key: "market",
    label: "시장 수요",
    value:
      reason.total_demand > 0
        ? `모아둔 기회 ${reason.total_demand}건 중 ${reason.demand_count}건이 요구`
        : "모아둔 기회가 없어 아직 알 수 없습니다",
    strong: reason.total_demand > 0 && reason.demand_count > 0
  })

  rows.push({
    key: "level",
    label: "내 수준",
    value: `${levelLabel(reason.my_level)} · 목표까지 ${reason.skill_gap}단계`,
    strong: reason.skill_gap >= 3
  })

  rows.push({
    key: "learning",
    label: "학습 진행",
    value:
      reason.learning_progress > 0
        ? nextStep
          ? `${nextStep.learning_path_title} ${reason.learning_progress}%`
          : `${reason.learning_progress}%`
        : "아직 시작한 학습 경로가 없습니다",
    strong: reason.learning_progress === 0
  })

  rows.push({
    key: "project",
    label: "프로젝트 증거",
    value:
      reason.career_projects?.length > 0
        ? reason.career_projects.join(" · ")
        : "이 스킬을 쓰는 커리어 프로젝트가 없습니다",
    strong: !(reason.career_projects?.length > 0)
  })

  return rows
}

function TodayFocus({ today, onOpenStep }) {
  const nextStep = today.next_learning_step
  const reasons = buildReasons(today.reason, nextStep)

  return (
    <section className="card today-card">
      {/* 계획 아래로 내려왔으므로 "TODAY" 는 더 이상 맞는 이름이
          아니다 — 위 카드가 TODAY'S PLAN 이다. 이 카드가 하는 일은
          "왜 이 스킬인가" 하나다. 라벨도 세 겹이었다
          (TODAY → FOCUS SKILL → 이름). 한 겹으로 줄인다. */}
      <p className="card-label">집중 스킬</p>

      {/* 우선순위 점수(예: 87)는 무엇의 87 인지 말할 수 없어 보이지 않는다.
          그 점수를 만든 재료를 아래에 분모와 함께 적는다. */}
      <div className="focus-row">
        <div>
          <h2>{today.focus_skill}</h2>
        </div>

        {today.reason && (
          <div className="focus-score">
            <strong>{today.reason.skill_gap}단계</strong>
            <span>목표까지</span>
          </div>
        )}
      </div>

      <div className="why-block">
        <p className="why-head">왜 지금 {today.focus_skill} 인가</p>

        <dl className="why-rows">
          {reasons.map((row) => (
            <div
              className={row.strong ? "why-row why-row-strong" : "why-row"}
              key={row.key}
            >
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {nextStep && (
        <button
          className="next-step-link"
          onClick={() => onOpenStep(nextStep.step_id)}
        >
          <span>다음 학습 단계</span>
          <strong>{nextStep.title}</strong>
          {nextStep.estimated_minutes > 0 && (
            <span className="next-step-minutes">
              {nextStep.estimated_minutes}분
            </span>
          )}
          <span className="next-step-arrow">→</span>
        </button>
      )}

      {today.recommended_resource && (
        <a
          className="resource-link"
          href={today.recommended_resource.url}
          target="_blank"
          rel="noreferrer"
        >
          ▶ {today.recommended_resource.title}
          {today.recommended_resource.duration_minutes > 0 && (
            <span className="muted">
              {" "}
              · {today.recommended_resource.duration_minutes}분
            </span>
          )}
        </a>
      )}
    </section>
  )
}

export default TodayFocus
