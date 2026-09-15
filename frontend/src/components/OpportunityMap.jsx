import { useEffect, useState } from "react"
import * as api from "../api"

/* 공고 하나를 기준으로 펼친 지도.

   공고 → 요구 스킬 → 레벨 → 공부 → 프로젝트 → 경험

   칸은 전부 앱에 이미 있었다. 여기서는 선만 잇는다. 각 스킬이
   어디까지 찼는지는 서버가 셀 수 있는 것으로만 정한다. */

const STAGE_TONE = {
  empty: "map-empty",
  studying: "map-studying",
  building: "map-building",
  covered: "map-covered"
}

function deadlineText(opportunity) {
  if (opportunity.status === "closed") {
    return "마감됨"
  }

  const days = opportunity.days_left

  if (days == null) {
    return "상시"
  }

  if (days < 0) {
    return "마감 지남"
  }

  return days === 0 ? "오늘 마감" : `D-${days}`
}

export default function OpportunityMap({ opportunityId }) {
  const [map, setMap] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true

    setMap(null)
    api
      .opportunityMap(opportunityId)
      .then((data) => alive && (setMap(data), setError(null)))
      .catch(() => alive && setError("지도를 불러오지 못했습니다."))

    return () => {
      alive = false
    }
  }, [opportunityId])

  if (error) {
    return <p className="agent-error">{error}</p>
  }

  if (!map) {
    return <p className="muted">지도를 그리는 중…</p>
  }

  const { summary } = map

  return (
    <div className="map">
      <div className="map-head">
        <p className="card-label">이 공고까지의 지도</p>
        <span
          className={
            map.opportunity.days_left === 0 ? "map-due map-due-now" : "map-due"
          }
        >
          {deadlineText(map.opportunity)}
        </span>
      </div>

      <p className="map-summary">
        요구 스킬 {summary.total}개 중{" "}
        <strong>쓸 수 있음 {summary.covered}</strong> · 만드는 중{" "}
        {summary.building} · 공부 중 {summary.studying} ·{" "}
        <span className={summary.empty ? "map-gap" : undefined}>
          비어 있음 {summary.empty}
        </span>
      </p>

      <div className="map-columns" aria-hidden="true">
        <span>스킬</span>
        <span>공부</span>
        <span>프로젝트</span>
        <span>경험</span>
      </div>

      <ul className="map-rows">
        {map.skills.map((row) => (
          <li key={row.skill_id} className={`map-row ${STAGE_TONE[row.stage]}`}>
            <div className="map-cell">
              <strong>{row.skill}</strong>
              <span className="map-sub">
                레벨 {row.level}/{row.max_level} · {row.stage_label}
              </span>
            </div>

            <div className="map-cell">
              {row.study.units_total > 0 ? (
                <span>
                  {row.study.units_done}/{row.study.units_total}
                </span>
              ) : (
                <span className="map-sub">
                  {row.study.resources > 0
                    ? `자료 ${row.study.resources}개`
                    : "자료 없음"}
                </span>
              )}
              {row.study.next && (
                <span className="map-sub map-next">다음 · {row.study.next}</span>
              )}
            </div>

            <div className="map-cell">
              {row.projects.length ? (
                row.projects.map((project) => (
                  <span key={project.id}>
                    {project.name} {project.progress_percent}%
                  </span>
                ))
              ) : (
                <span className="map-sub">—</span>
              )}
            </div>

            <div className="map-cell">
              {row.experiences.length ? (
                row.experiences.map((experience) => (
                  <span key={experience.id}>{experience.title}</span>
                ))
              ) : (
                <span className="map-sub">—</span>
              )}
            </div>
          </li>
        ))}
      </ul>

      {summary.empty > 0 && (
        <p className="muted map-note">
          비어 있는 칸은 실력이 없다는 뜻이 아니라 기록이 없다는 뜻입니다.
          이미 해본 경험이 있으면{" "}
          <a className="td-link" href="#/experience">
            경험에 등록하세요
          </a>{" "}
          — 칸이 바로 찹니다. 공부할 것이 남았다면{" "}
          <a className="td-link" href="#/learning">
            학습 경로
          </a>
          에서 이어가세요.
        </p>
      )}
    </div>
  )
}
