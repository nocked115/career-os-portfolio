import { useEffect, useState } from "react"
import * as api from "../api"

/* 잔디 — 그 달에 날마다 끝낸 것.

   별이 아니라 칸이다. "우주는 홈에만, 작업 화면은 평범하게"
   (DESIGN.md). 칸이어야 날짜가 읽힌다.

   색은 개수로 칠한다. 분은 오늘 할 일을 완료할 때만 남아서,
   챕터를 따로 끝낸 날이 0분으로 보인다. */

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

function mondayIndex(isoDate) {
  // 월요일 0 … 일요일 6
  return (new Date(`${isoDate}T00:00:00`).getDay() + 6) % 7
}

export default function ActivityGrid({ year, month }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    let alive = true
    setData(null)
    api.activity
      .get(year, month)
      .then((body) => alive && setData(body))
      .catch(() => alive && setData({ error: true }))
    return () => {
      alive = false
    }
  }, [year, month])

  if (!data) {
    return null
  }

  if (data.error) {
    return (
      <section className="card">
        <p className="agent-error">활동 기록을 불러오지 못했습니다.</p>
      </section>
    )
  }

  // 주 단위 열로 쌓는다. 첫 주 앞은 빈칸으로 채운다.
  const cells = [
    ...Array(mondayIndex(data.days[0].date)).fill(null),
    ...data.days
  ]
  const weeks = []
  for (let i = 0; i < cells.length; i += 7) {
    weeks.push(cells.slice(i, i + 7))
  }

  return (
    <section className="card">
      <div className="grid-head">
        <p className="card-label">날마다</p>
        <span className="muted">
          {data.active_days}일 · 끝낸 것 {data.total}개
        </span>
      </div>

      <div className="grid-body">
        <div className="grid-weekdays" aria-hidden="true">
          {WEEKDAYS.map((day) => (
            <span key={day}>{day}</span>
          ))}
        </div>

        <div className="grid-weeks">
          {weeks.map((week, w) => (
            <div className="grid-week" key={w}>
              {Array.from({ length: 7 }, (_, d) => week[d] ?? null).map(
                (cell, d) =>
                  cell ? (
                    <span
                      key={cell.date}
                      className={`grid-cell grid-l${cell.level}`}
                      title={
                        cell.count
                          ? `${cell.date} · ${cell.count}개\n` +
                            cell.items.map((item) => `· ${item.title}`).join("\n")
                          : `${cell.date} · 없음`
                      }
                    />
                  ) : (
                    <span key={`e${w}${d}`} className="grid-cell grid-blank" />
                  )
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid-legend" aria-hidden="true">
        <span>적음</span>
        <span className="grid-cell grid-l0" />
        <span className="grid-cell grid-l1" />
        <span className="grid-cell grid-l2" />
        <span className="grid-cell grid-l3" />
        <span>많음</span>
      </div>
    </section>
  )
}
