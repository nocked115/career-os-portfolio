import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { EmptyState, ErrorState, LoadingState } from "./ui"
import { minutesText, resourceTypeLabel } from "../format"

/* 지금 쓸 자료 — 라이브러리 전체에서 오늘 필요한 것만.

   DESIGN.md 원칙 2 — 안 해도 되는 것을 말한다.

   추천 서비스는 계속 뭘 더 보라고 한다. Career OS 는 반대다.
   "영상 43개 · 책 11권 — 지금은 볼 필요 없습니다" 가 이 제품에서
   가장 중요한 문장이다. 치운 것을 조용히 감추면 선별이 아니라 필터다.
   개수를 밝히고, 펼쳐 볼 수 있게 둔다. */

function LibraryToday({ minutes = 120 }) {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      setData(await api.library.todaySelection(minutes))
    } catch (failure) {
      console.error("Failed to load library selection:", failure)
      setError("지금 쓸 자료를 고르지 못했습니다.")
    }
  }, [minutes])

  useEffect(() => {
    load()
  }, [load])

  if (error) {
    return <ErrorState message={error} onRetry={load} />
  }

  if (!data) {
    return <LoadingState label="지금 쓸 자료를 고르는 중…" />
  }

  const selected = data.selected
  const aside = data.set_aside

  return (
    <section className="card">
      <p className="card-label">지금 쓸 자료</p>

      {data.focus_skill ? (
        <p className="muted opp-meta">
          핵심 초점 {data.focus_skill}
          {data.current_step && <> · 현재 단계 {data.current_step}</>}
          {" · "}
          {minutesText(data.available_minutes)} 기준
        </p>
      ) : (
        <p className="muted">핵심 초점 스킬이 정해지지 않아 고를 근거가 없습니다.</p>
      )}

      {selected.length === 0 ? (
        <EmptyState
          title="지금 바로 볼 수 있는 자료가 없습니다."
          body="핵심 초점 스킬에 맞는 자료를 등록하거나, 자료에 예상 시간 · 챕터를 넣어 주세요."
        />
      ) : (
        <div className="pick-list">
          {selected.map((item, index) => (
            <div className="pick-row" key={`${item.kind}-${item.segment_id ?? item.resource_id}`}>
              <span className="pick-no">{String(index + 1).padStart(2, "0")}</span>

              <div className="pick-body">
                <strong>{item.title}</strong>
                <span className="muted">
                  {resourceTypeLabel(item.resource_type)}
                  {item.ownership === "owned" && " · 가지고 있음"}
                  {" · "}
                  {item.why}
                </span>
              </div>

              <span className="pick-minutes">{minutesText(item.minutes)}</span>
            </div>
          ))}

          <div className="pick-total">
            <span>
              합계 {minutesText(data.selected_minutes)}
              {data.remaining_minutes > 0 && (
                <span className="muted"> · {minutesText(data.remaining_minutes)} 남음</span>
              )}
            </span>
            {data.completed_count > 0 && (
              <span className="muted">이미 끝낸 자료 {data.completed_count}개</span>
            )}
          </div>
        </div>
      )}

      {/* 치운 것. 개수를 밝히는 게 핵심이다. */}
      {aside.length > 0 && (
        <div className="set-aside">
          <button className="set-aside-head" aria-expanded={open} onClick={() => setOpen(!open)}>
            <strong>
              지금 안 해도 되는 자료 ·{" "}
              {data.set_aside_by_type
                .map((entry) => `${resourceTypeLabel(entry.resource_type)} ${entry.count}개`)
                .join(" · ")}
            </strong>
            <span className="set-aside-toggle">{open ? "접기" : "펼치기"}</span>
          </button>

          <p className="set-aside-message">{data.message}</p>

          {open && (
            <div className="set-aside-list">
              {aside.map((item) => (
                <div className="set-aside-item" key={`${item.kind}-${item.segment_id ?? item.resource_id}`}>
                  <span>{item.title}</span>
                  <span className="muted">{item.skip_reason}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export default LibraryToday
