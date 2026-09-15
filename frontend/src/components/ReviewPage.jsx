import { useEffect, useState } from "react"
import * as api from "../api"
import ActivityGrid from "./ActivityGrid"
import ReflectionCard from "./ReflectionCard"
import { ErrorState, LoadingState, ProgressBar } from "./ui"
import { areaLabel, minutesText } from "../format"
import "../Overview.css"

/* 회고 — 통계가 아니라 다음 달을 고치는 곳.

   하루치로는 아무것도 안 보인다. 한 달을 모아야 "이걸 배웠다" 가 되고,
   계획한 것과 실제로 한 것을 나란히 놓아야 "무엇을 바꿀지" 가 보인다.

   다음 달 제안은 규칙으로만 고르고, 근거 숫자를 함께 보인다.
   기록이 적으면 말하지 않는다 — 계획 두 개로 잔소리하지 않는다. */

const ROUTES = {
  today: "#/today",
  calendar: "#/calendar",
  projects: "#/projects",
  learning: "#/learning"
}

function monthLabel(year, month) {
  return `${year}년 ${month}월`
}

export default function ReviewPage() {
  const now = new Date()

  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [review, setReview] = useState(null)
  const [error, setError] = useState(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    let alive = true

    // 달을 바꾸면 이전 달 숫자를 먼저 치운다. 남아 있으면 새 달 숫자로 읽힌다.
    setReview(null)
    setError(null)

    api.review
      .get(year, month)
      .then((data) => alive && setReview(data))
      .catch(() => alive && setError("회고를 불러오지 못했습니다."))

    return () => {
      alive = false
    }
  }, [year, month, nonce])

  const shift = (delta) => {
    const next = month + delta

    if (next < 1) {
      setYear(year - 1)
      setMonth(12)
    } else if (next > 12) {
      setYear(year + 1)
      setMonth(1)
    } else {
      setMonth(next)
    }
  }

  const isThisMonth = year === now.getFullYear() && month === now.getMonth() + 1

  const header = (
    <section className="card">
      <div className="review-head">
        <div>
          <p className="card-label">회고</p>
          <h2 className="review-month">{monthLabel(year, month)}</h2>
        </div>

        <div className="review-nav">
          <button className="chip" onClick={() => shift(-1)}>
            ← 이전 달
          </button>
          <button className="chip" disabled={isThisMonth} onClick={() => shift(1)}>
            다음 달 →
          </button>
        </div>
      </div>
    </section>
  )

  if (error) {
    return (
      <>
        {header}
        <ErrorState message={error} onRetry={() => setNonce((value) => value + 1)} />
      </>
    )
  }

  if (!review) {
    return (
      <>
        {header}
        <LoadingState label={`${monthLabel(year, month)} 기록을 모으는 중…`} />
      </>
    )
  }

  const { learning, evidence, market, execution } = review
  const nothing =
    learning.segments_done === 0 &&
    learning.steps_done === 0 &&
    learning.tasks_done === 0 &&
    evidence.experiences === 0 &&
    evidence.portfolio_entries === 0 &&
    market.opportunities_collected === 0 &&
    execution.planned === 0

  return (
    <>
      {header}

      {/* ---------- 다음 달에 바꿀 것 — 가장 위 ---------- */}
      <section className="card">
        <p className="card-label">다음 달에 바꿀 것</p>

        {review.next_month.length === 0 ? (
          <p className="muted">
            기록으로 보이는 문제가 없어요. 지금 흐름을 이어가세요.
          </p>
        ) : (
          <ul className="review-suggestions">
            {review.next_month.map((item) => (
              <li key={item.title}>
                <strong>{item.title}</strong>
                <span>{item.evidence}</span>
                {ROUTES[item.route] && (
                  <a className="ov-link" href={ROUTES[item.route]}>
                    바로 가기
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}

        <p className="muted form-hint">규칙으로 고른 제안이에요. 근거 숫자를 함께 보여 드려요.</p>
      </section>

      {/* 기록이 말해주지 않는 것 — 스스로 매긴 한 달. 달이 바뀌면 새로 그린다. */}
      <ReflectionCard
        key={`${year}-${month}`}
        year={year}
        month={month}
        reflection={review.reflection}
        onSaved={(reflection) => setReview((current) => ({ ...current, reflection }))}
      />

      {nothing ? (
        <section className="card">
          <p className="muted review-empty">
            이 달에는 기록된 것이 없습니다. 비어 있다는 것도 정확한 상태입니다.
          </p>
        </section>
      ) : (
        <section className="card">
          <div className="review-stats">
            <div>
              <p className="card-label">계획 대비 실행</p>
              <strong>
                {execution.rate != null ? `${execution.done} / ${execution.decided}` : "—"}
              </strong>
              <span className="muted">
                {execution.rate != null
                  ? `${execution.rate}% · 넘김 ${execution.skipped} · 못 함 ${execution.missed}`
                  : "끝난 날의 계획이 없어요"}
              </span>
              {execution.rate != null && (
                <ProgressBar value={execution.done} max={execution.decided} label="계획 대비 실행" />
              )}
            </div>

            <div>
              <p className="card-label">끝낸 학습</p>
              <strong>{learning.segments_done + learning.steps_done}</strong>
              <span className="muted">챕터 · 학습 단계</span>
            </div>

            <div>
              <p className="card-label">쓴 시간</p>
              <strong>{minutesText(learning.minutes)}</strong>
              <span className="muted">계획을 실제로 끝낸 시간</span>
            </div>

            <div>
              <p className="card-label">쌓은 증거</p>
              <strong>{evidence.experiences + evidence.portfolio_entries}</strong>
              <span className="muted">경험 · 포트폴리오</span>
            </div>

            <div>
              <p className="card-label">지원 활동</p>
              <strong>{market.applications_sent}</strong>
              <span className="muted">지원 · 모은 기회 {market.opportunities_collected}</span>
            </div>
          </div>

          {Object.keys(execution.by_area).length > 0 && (
            <p className="muted form-hint">
              영역별 끝냄 / 못 끝냄 ·{" "}
              {Object.entries(execution.by_area)
                .map(([area, row]) => `${areaLabel(area)} ${row.done}/${row.not_done}`)
                .join(" · ")}
            </p>
          )}
        </section>
      )}

      <ActivityGrid year={year} month={month} />

      {review.postponed.length > 0 && (
        <section className="card">
          <p className="card-label">반복해서 미룬 일</p>
          <ul className="review-done">
            {review.postponed.map((row) => (
              <li key={row.title}>
                <span className="review-done-date">{row.first_planned} 부터</span>
                <span className="review-done-title">{row.title}</span>
                <span className="review-done-skill">{row.times}번 이월</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {learning.by_skill.length > 0 && (
        <section className="card">
          <p className="card-label">어느 스킬에 쌓였는가</p>

          <div className="review-skills">
            {learning.by_skill.map((row) => (
              <div className="review-skill" key={row.skill}>
                <span className="review-skill-name">{row.skill}</span>
                <span className="review-skill-count">{row.segments + row.steps}개</span>
                <span className="muted review-skill-time">
                  {row.minutes > 0 ? minutesText(row.minutes) : "—"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {review.levels.length > 0 && (
        <section className="card">
          <p className="card-label">레벨이 바뀐 스킬</p>

          <ul className="review-done">
            {review.levels.map((move) => (
              <li key={move.skill}>
                <span className="review-done-date">{move.at}</span>
                <span className="review-done-title">{move.skill}</span>
                <span className="review-done-skill">
                  레벨 {move.from} → {move.to}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {review.done.length > 0 && (
        <section className="card">
          <p className="card-label">한 일</p>

          <ul className="review-done">
            {review.done.map((item) => (
              <li key={`${item.kind}-${item.title}-${item.at}`}>
                <span className="review-done-date">{item.at}</span>
                <span className="review-done-title">{item.title}</span>
                {item.skill && <span className="review-done-skill">{item.skill}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 못 세는 것을 숨기지 않는다. */}
      <p className="muted review-note">
        프로젝트 완료 시점은 아직 세지 않습니다 — 기록에 시각이 없어 지어내지 않습니다.
      </p>
    </>
  )
}
