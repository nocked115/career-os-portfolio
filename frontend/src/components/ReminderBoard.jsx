/* 알리미 — 날짜가 있는 것을 한 판에.
 *
 * 수현: "오늘 할 일에 들어가는 거 말고 게시판처럼. 오늘 마감 ·
 * 역량검사 대비 (10/18 일) 이런 것도 알리미처럼."
 *
 * **일을 시키는 판이 아니라 알려 주는 판이다.** 시간을 재지 않고,
 * 진행률을 움직이지 않고, 오늘 쓸 수 있는 시간에서 빠지지 않는다.
 *
 * 알릴 것의 대부분은 앱이 이미 안다 — 공고 마감 · 지원서 마감 · 시험 ·
 * 학습 마감. 흩어져 있던 것을 모으고, 앱이 모르는 것만 사람이 적는다.
 */
import { useCallback, useEffect, useState } from "react"

import * as api from "../api"
import { Button } from "./ui"
import "../Reminder.css"

const TONE = {
  mine: "mine",
  deadline: "deadline",
  exam: "exam",
  learning: "learning"
}

const tomorrow = () => {
  const date = new Date()
  date.setDate(date.getDate() + 1)
  return date.toISOString().slice(0, 10)
}

const awayLabel = (days) =>
  days === 0 ? "오늘" : days === 1 ? "내일" : `${days}일 뒤`

export function ReminderBoard() {
  const [data, setData] = useState(null)
  const [working, setWorking] = useState(false)
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState("")
  const [due, setDue] = useState(tomorrow())
  const [at, setAt] = useState("")

  const load = useCallback(async () => {
    setData(await api.reminders.list().catch(() => null))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action) => {
    try {
      setWorking(true)
      await action()
      await load()
    } finally {
      setWorking(false)
    }
  }

  const add = () => {
    const text = title.trim()
    if (!text) return

    return run(async () => {
      await api.reminders.create({ title: text, due, at: at.trim() })
      setTitle("")
      setAt("")
      setAdding(false)
    })
  }

  const days = data?.days ?? []

  return (
    <section className="card reminders">
      <p className="card-label">알리미</p>

      <p className="muted opp-meta">
        앞으로 2주간 날짜가 걸린 것들이에요. 공고 마감 · 시험 · 학습
        마감은 앱이 알아서 올리고, 그 밖의 것만 적어 두시면 됩니다.
        할 일이 아니라 알림이라 오늘 시간에서 빠지지 않아요.
      </p>

      {days.length === 0 ? (
        <p className="muted form-hint">앞으로 2주간 알릴 것이 없어요.</p>
      ) : (
        <ul className="rem-days">
          {days.map((day) => (
            <li key={day.date} className="rem-day">
              <p className="rem-date">
                <strong>
                  {day.date.slice(5).replace("-", "/")} ({day.weekday})
                </strong>
                <span className={day.days_away <= 1 ? "rem-soon" : "muted"}>
                  {" "}
                  {awayLabel(day.days_away)}
                </span>
              </p>

              <ul className="rem-items">
                {day.items.map((item, index) => (
                  <li
                    key={`${item.kind}-${item.id ?? index}`}
                    className={`rem-item rem-${TONE[item.kind] ?? "mine"}`}
                  >
                    <span className="rem-label">{item.label}</span>

                    <span className="rem-title">
                      {item.at && <strong>{item.at} </strong>}
                      {item.title}
                      {item.where && (
                        <span className="muted"> · {item.where}</span>
                      )}
                    </span>

                    {/* 앱이 아는 것은 여기서 지우지 않는다 — 공고를
                        지우는 일과 알림을 끄는 일은 다르다. */}
                    {item.source === "mine" && (
                      <Button
                        variant="quiet"
                        writes
                        disabled={working}
                        onClick={() => run(() => api.reminders.done(item.id))}
                      >
                        됐어요
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      {adding ? (
        <div className="rem-new">
          <input
            className="plan-input"
            type="text"
            placeholder="무엇을 알릴까요 (예: 친구에게 논문 전달)"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
          />
          <input
            className="plan-input rem-when"
            type="date"
            value={due}
            onChange={(event) => setDue(event.target.value)}
          />
          <input
            className="plan-input rem-at"
            type="text"
            placeholder="10:00"
            value={at}
            onChange={(event) => setAt(event.target.value)}
          />
          <Button writes disabled={working || !title.trim()} onClick={add}>
            넣기
          </Button>
          <Button variant="quiet" onClick={() => setAdding(false)}>
            취소
          </Button>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setAdding(true)}>
          + 알림 적어 두기
        </Button>
      )}
    </section>
  )
}

export default ReminderBoard
