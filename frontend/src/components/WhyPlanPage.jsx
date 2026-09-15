import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { EmptyState, ErrorState, LoadingState } from "./ui"
import { areaLabel, minutesText } from "../format"

/* Why this plan? — 판단의 근거.

   DESIGN.md 8장. 결론 문장이 먼저, 입력 칸은 그 아래, 원본 숫자는
   칸을 펼쳐야 보인다.

   데이터가 없는 입력도 지우지 않는다. 흐리게 남겨서 무엇을 못 봤는지까지
   보여주는 것이 근거다. */

function WhyPlanPage({ onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      /* 설정을 밖에서 받지 않는다. 주소를 직접 열거나 새로고침해도
         "지금 있는 계획" 을 설명해야 하므로 그 계획이 쓴 설정을 읽는다. */
      const day = await api.calendar.day()
      const plan = await api.todayPlan.get(day.suggested_minutes, "normal")

      setData(await api.todayPlan.why(plan.available_minutes, plan.intensity))
    } catch (loadError) {
      console.error("Failed to load plan reasoning:", loadError)
      setError("판단 근거를 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return <LoadingState label="판단 근거를 불러오는 중…" />
  }

  if (error || !data) {
    return <ErrorState message={error} onRetry={load} />
  }

  const decision = data.decision
  const tasks = decision?.tasks ?? []

  return (
    <div className="why-page">
      <button className="ghost-button back-link" onClick={onBack}>
        ← 오늘 계획
      </button>

      <section className="card">
        <p className="card-label">왜 이 계획인가?</p>

        {data.focus_skill ? (
          <>
            <h2 className="why-title">{data.headline}</h2>
            <p className="muted opp-meta">
              {data.date} · 집중 스킬 {data.focus_skill} · 쓰인 데이터{" "}
              {data.used_count} / {data.inputs.length}종
            </p>
          </>
        ) : (
          <EmptyState
            title={data.limits[0]}
            body="스킬을 등록하고 공고를 모으면 무엇이 중요한지 판단할 수 있어요."
            actions={[
              { label: "공고 모으기", href: "#/opportunities", primary: true },
              { label: "학습 경로 만들기", href: "#/learning" }
            ]}
          />
        )}
      </section>

      {data.inputs.length > 0 && (
        <section className="card">
          <p className="card-label">판단에 쓴 것 · 눌러서 원본 숫자 보기</p>

          <div className="why-rows">
            {data.inputs.map((cell) => {
              const open = expanded === cell.key

              return (
                <div
                  className={cell.available ? "why-line" : "why-line why-line-off"}
                  key={cell.key}
                >
                  <button
                    className="why-line-head"
                    aria-expanded={open}
                    aria-label={`${cell.ko} — ${cell.value}`}
                    onClick={() => setExpanded(open ? null : cell.key)}
                  >
                    <span className="why-glyph" aria-hidden="true">
                      {cell.glyph}
                    </span>

                    <span className="why-line-label">{cell.ko}</span>

                    <span className="why-line-text">
                      <strong>{cell.value}</strong>
                      <span>{cell.detail}</span>
                    </span>

                    <span className="why-chevron" aria-hidden="true">
                      {open ? "⌃" : "›"}
                    </span>
                  </button>

                  {open && cell.evidence.length > 0 && (
                    <ul className="why-evidence">
                      {cell.evidence.map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  )}

                  {open && cell.evidence.length === 0 && (
                    <p className="why-evidence muted">
                      이 입력은 데이터가 없어 판단에 쓰지 못했습니다.
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {decision && (
        <section className="card why-decision">
          <p className="card-label">그래서 고른 것</p>

          {tasks.length === 0 ? (
            <EmptyState
              title="아직 오늘 계획이 없습니다."
              body="오늘 계획에서 계획 세우기를 누르면 위 근거로 할 일을 고릅니다."
              actions={[{ label: "오늘 계획으로 가기", onClick: onBack, primary: true }]}
            />
          ) : (
            <>
              <div className="why-tasks">
                {tasks.map((task) => (
                  <div
                    className={
                      task.status === "skipped" ? "why-task why-task-skipped" : "why-task"
                    }
                    key={task.id}
                  >
                    <span className="why-task-type">{areaLabel(task.task_type)}</span>

                    <div className="why-task-body">
                      <strong>{task.title}</strong>
                      <span className="muted">{task.reason}</span>
                    </div>

                    <span className="why-task-minutes">{minutesText(task.minutes)}</span>
                  </div>
                ))}
              </div>

              <div className="why-total">
                <span>
                  합계 {minutesText(decision.planned_minutes)}
                  <span className="muted"> / {minutesText(decision.available_minutes)}</span>
                </span>
                <span className="muted">이 판단에 쓰인 데이터 {data.used_count}종</span>
              </div>
            </>
          )}
        </section>
      )}

      {data.limits.length > 0 && data.focus_skill && (
        <section className="card">
          <p className="card-label">이 판단의 한계</p>
          <ul className="opp-reasons">
            {data.limits.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export default WhyPlanPage
