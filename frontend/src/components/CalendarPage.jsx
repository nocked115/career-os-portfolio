import "../Overview.css"
import { useCallback, useEffect, useMemo, useState } from "react"
import * as api from "../api"
import RoutinesCard from "./RoutinesCard"

/* Calendar — 한 장에 다 보이는 달력.

   전에는 요일 격자와 입력 폼뿐이었다. 하루짜리 일정은 격자에 안 뜨고,
   공고 마감은 다른 화면에 있어서 "다음 주 목요일에 뭐가 있지?" 를
   답하지 못했다. 이제 한 달 격자에 매주 일정 · 하루 일정 · 마감을
   같이 놓고, 날짜를 누르면 오른쪽에서 그날을 보고 고친다.

   그대로 지키는 것 —
   **"수업이 없는 시간" 은 "공부할 수 있는 시간" 이 아니다.**
   빈 시간은 하루 상한과 비교해 작은 쪽을 제안한다.
   마감과 종일 일정은 빈 시간을 줄이지 않는다. */

const DAYS = ["월", "화", "수", "목", "금", "토", "일"]

const KINDS = [
  { key: "class", label: "수업" },
  { key: "work", label: "일 · 알바" },
  { key: "personal", label: "개인 일정" },
  { key: "fixed", label: "고정" },
  { key: "deadline", label: "마감" }
]

const APPLICATION_LABELS = {
  applied: "지원함",
  document_pass: "서류 합격",
  interview: "면접",
  rejected: "불합격",
  accepted: "합격"
}

const MAX_IN_CELL = 3
const HOUR_PX = 44

function toMinutes(value) {
  const [hour, minute] = value.split(":").map(Number)
  return hour * 60 + minute
}

function toTime(minutes) {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(
    minutes % 60
  ).padStart(2, "0")}`
}

function hours(minutes) {
  if (minutes === 0) return "0분"
  if (minutes < 60) return `${minutes}분`

  const h = Math.floor(minutes / 60)
  const m = minutes % 60

  return m === 0 ? `${h}시간` : `${h}시간 ${m}분`
}

function isoOf(year, month, day) {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`
}

function isoFromDate(value) {
  return isoOf(value.getFullYear(), value.getMonth() + 1, value.getDate())
}

function parseIso(iso) {
  const [year, month, day] = iso.split("-").map(Number)
  return new Date(year, month - 1, day)
}

function weekdayOf(iso) {
  return (parseIso(iso).getDay() + 6) % 7
}

function longDate(iso) {
  const value = parseIso(iso)
  return `${value.getMonth() + 1}월 ${value.getDate()}일 ${DAYS[weekdayOf(iso)]}요일`
}

function takesTime(block) {
  return !block.all_day && block.kind !== "deadline"
}

function postingLabel(item) {
  if (item.kind === "opportunity") return item.opportunity_type === "job_event" ? "채용 행사" : "공고 마감"
  return APPLICATION_LABELS[item.status] ?? "지원 준비"
}

// 한 칸에 보일 것. 마감이 먼저다 — 칸이 좁아서 위에 있는 것만 보인다.
function cellItems(day) {
  return [
    ...day.deadlines.map((item) => ({
      key: `p-${item.kind}-${item.id}`,
      tone: "deadline",
      text: item.title
    })),
    ...day.blocks.map((block) => ({
      key: `b-${block.id}`,
      tone: block.kind,
      repeats: block.repeats,
      text: takesTime(block) ? `${block.start} ${block.title}` : block.title
    }))
  ]
}

// 같은 시간에 겹친 일정은 옆으로 나눠 앉힌다.
function lanes(blocks) {
  const sorted = [...blocks].sort(
    (a, b) => a.start_minute - b.start_minute || a.id - b.id
  )
  const ends = []

  const placed = sorted.map((block) => {
    let lane = ends.findIndex((end) => end <= block.start_minute)

    if (lane === -1) {
      lane = ends.length
      ends.push(block.end_minute)
    } else {
      ends[lane] = block.end_minute
    }

    return { block, lane }
  })

  return { placed, count: Math.max(1, ends.length) }
}

const EMPTY_FORM = {
  title: "",
  kind: "personal",
  repeats: false,
  allDay: false,
  start: "10:00",
  end: "12:00"
}

export default function CalendarPage() {
  const todayIso = isoFromDate(new Date())

  const [cursor, setCursor] = useState(() => {
    const now = new Date()
    return { year: now.getFullYear(), month: now.getMonth() + 1 }
  })
  const [selected, setSelected] = useState(todayIso)
  const [view, setView] = useState("month")

  const [month, setMonth] = useState(null)
  const [settings, setSettings] = useState(null)
  const [error, setError] = useState(null)
  const [working, setWorking] = useState(false)
  const [confirming, setConfirming] = useState(null)
  const [changed, setChanged] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)

  const load = useCallback(async () => {
    try {
      setError(null)
      const [monthData, weekData] = await Promise.all([
        api.calendar.month(cursor.year, cursor.month),
        api.calendar.week()
      ])
      setMonth(monthData)
      setSettings(weekData)
    } catch (loadError) {
      console.error("Failed to load calendar:", loadError)
      setError("달력을 불러오지 못했습니다.")
    }
  }, [cursor])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action) => {
    try {
      setWorking(true)
      setError(null)
      setChanged(false)
      await action()
      await load()
      // 일정과 설정은 오늘 계획의 시간 예산을 바꾼다. 이미 세운 계획은
      // 저절로 다시 짜이지 않으므로 그 사실을 말한다.
      setChanged(true)
    } catch (actionError) {
      console.error("Calendar action failed:", actionError)
      setError(
        "요청을 처리하지 못했습니다. 시간이나 형식이 맞지 않을 수 있습니다."
      )
    } finally {
      setWorking(false)
      setConfirming(null)
    }
  }

  const days = useMemo(() => (month ? month.weeks.flat() : []), [month])
  const day = days.find((item) => item.date === selected) ?? null
  const week =
    month?.weeks.find((row) => row.some((item) => item.date === selected)) ??
    month?.weeks[0]

  const select = (iso) => {
    const value = parseIso(iso)

    setSelected(iso)
    setConfirming(null)

    if (
      value.getFullYear() !== cursor.year ||
      value.getMonth() + 1 !== cursor.month
    ) {
      setCursor({ year: value.getFullYear(), month: value.getMonth() + 1 })
    }
  }

  const shift = (delta) => {
    if (view === "week") {
      const value = parseIso(selected)
      value.setDate(value.getDate() + 7 * delta)
      select(isoFromDate(value))
      return
    }

    let year = cursor.year
    let next = cursor.month + delta

    if (next < 1) {
      next = 12
      year -= 1
    } else if (next > 12) {
      next = 1
      year += 1
    }

    setCursor({ year, month: next })
    setSelected(isoOf(year, next, 1))
  }

  const isDeadline = form.kind === "deadline"
  const allDay = isDeadline || form.allDay
  const repeats = form.repeats && !allDay

  const add = () =>
    run(async () => {
      await api.calendar.addBlock({
        title: form.title.trim(),
        kind: form.kind,
        weekday: repeats ? weekdayOf(selected) : null,
        date: repeats ? null : selected,
        all_day: allDay,
        start_minute: allDay ? null : toMinutes(form.start),
        end_minute: allDay ? null : toMinutes(form.end)
      })
      setForm((current) => ({ ...current, title: "" }))
    })

  const setSetting = (key, value) =>
    run(() => api.calendar.settings({ [key]: value }))

  if (error && !month) {
    return (
      <div className="card">
        <p className="agent-error">{error}</p>
      </div>
    )
  }

  if (!month || !settings || !week) {
    return (
      <div className="card">
        <p className="muted">불러오는 중...</p>
      </div>
    )
  }

  const title =
    view === "month"
      ? `${month.year}년 ${month.month}월`
      : `${longDate(week[0].date).split(" ").slice(0, 2).join(" ")} – ${
          week[6].day
        }일`

  return (
    <div className="calendar-page">
      <section className="card cal-head">
        <div>
          <p className="card-label">일정</p>
          <h2 className="cal-title">{title}</h2>
        </div>

        <div className="cal-controls">
          <div className="cal-nav">
            <button className="chip" onClick={() => shift(-1)}>
              ←
            </button>
            <button
              className="chip"
              onClick={() => {
                const now = new Date()
                setCursor({ year: now.getFullYear(), month: now.getMonth() + 1 })
                setSelected(todayIso)
              }}
            >
              오늘
            </button>
            <button className="chip" onClick={() => shift(1)}>
              →
            </button>
          </div>

          <div className="cal-nav">
            <button
              className={view === "month" ? "chip chip-on" : "chip"}
              onClick={() => setView("month")}
            >
              월
            </button>
            <button
              className={view === "week" ? "chip chip-on" : "chip"}
              onClick={() => setView("week")}
            >
              주
            </button>
          </div>
        </div>

        <div className="cal-legend">
          {KINDS.map((kind) => (
            <span key={kind.key} className="cal-legend-item">
              <i className={`cal-swatch tone-${kind.key}`} />
              {kind.label}
            </span>
          ))}
          <span className="cal-legend-item muted">
            흐린 칸 = 매주 반복
          </span>
        </div>

        {error && <p className="agent-error">{error}</p>}

        {changed && (
          <p className="cal-changed" role="status">
            저장했어요. 오늘 쓸 수 있는 시간이 달라졌을 수 있어요 — 이미 세운 오늘 계획은{" "}
            <a className="td-link" href="#/today">
              오늘 화면
            </a>
            에서 &lsquo;이 설정으로 다시 세우기&rsquo;를 눌러야 반영돼요.
          </p>
        )}
      </section>

      <div className="cal-layout">
        {view === "month" ? (
          <section className="card calm">
            <div className="calm-weekdays">
              {DAYS.map((label, index) => (
                <span key={label} className={`calm-wd wd-${index}`}>
                  {label}
                </span>
              ))}
            </div>

            <div className="calm-grid">
              {days.map((item) => {
                const items = cellItems(item)

                const classes = [
                  "calm-cell",
                  !item.in_month && "calm-out",
                  item.date === selected && "calm-selected",
                  item.is_today && "calm-today"
                ]
                  .filter(Boolean)
                  .join(" ")

                return (
                  <button
                    key={item.date}
                    className={classes}
                    aria-label={longDate(item.date)}
                    onClick={() => select(item.date)}
                  >
                    <span className={`calm-date wd-${item.weekday}`}>
                      {item.day}
                    </span>

                    <span className="calm-items">
                      {items.slice(0, MAX_IN_CELL).map((entry) => (
                        <span
                          key={entry.key}
                          className={
                            entry.repeats
                              ? `calm-chip tone-${entry.tone} calm-repeat`
                              : `calm-chip tone-${entry.tone}`
                          }
                        >
                          {entry.text}
                        </span>
                      ))}

                      {items.length > MAX_IN_CELL && (
                        <span className="calm-more">
                          +{items.length - MAX_IN_CELL}
                        </span>
                      )}
                    </span>
                  </button>
                )
              })}
            </div>
          </section>
        ) : (
          <WeekGrid
            week={week}
            settings={settings}
            selected={selected}
            onSelect={select}
          />
        )}

        <aside className="card cal-rail">
          <p className="card-label">
            {selected === todayIso ? "오늘" : "선택한 날"}
          </p>
          <h3 className="cal-rail-date">{longDate(selected)}</h3>

          {day && (
            <p className="cal-rail-budget">
              빈 시간 <strong>{hours(day.free_minutes)}</strong>
              <span className="cal-op">→</span>
              제안 <strong className="cal-accent">
                {hours(day.suggested_minutes)}
              </strong>
              <span className="muted">
                {" "}
                · 상한 {hours(month.daily_cap_minutes)}
              </span>
            </p>
          )}

          {day && day.deadlines.length > 0 && (
            <ul className="cal-rail-list">
              {day.deadlines.map((item) => (
                <li key={`${item.kind}-${item.id}`} className="cal-rail-row">
                  <span className="cal-rail-time tone-text-deadline">
                    {postingLabel(item)}
                  </span>
                  <a
                    className="cal-rail-title"
                    href={
                      item.kind === "application"
                        ? "#/applications"
                        : "#/opportunities"
                    }
                  >
                    {item.title}
                    {item.organization && (
                      <span className="muted"> · {item.organization}</span>
                    )}
                  </a>
                </li>
              ))}
            </ul>
          )}

          {day && day.blocks.length > 0 && (
            <ul className="cal-rail-list">
              {day.blocks.map((block) => (
                <li key={block.id} className="cal-rail-row">
                  <span className={`cal-rail-time tone-text-${block.kind}`}>
                    {takesTime(block)
                      ? `${block.start}–${block.end}`
                      : block.kind_label}
                  </span>

                  <span className="cal-rail-title">
                    {block.title}
                    <span className="muted">
                      {" "}
                      · {takesTime(block) ? block.kind_label : "종일"}
                      {block.repeats && ` · 매주 ${DAYS[block.weekday]}요일`}
                    </span>
                  </span>

                  {confirming === block.id ? (
                    <button
                      className="chip cal-danger"
                      disabled={working}
                      onClick={() =>
                        run(() => api.calendar.removeBlock(block.id))
                      }
                    >
                      {block.repeats ? "매주 전부 삭제" : "삭제"}
                    </button>
                  ) : (
                    <button
                      className="chip"
                      disabled={working}
                      onClick={() => setConfirming(block.id)}
                    >
                      삭제
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {day && day.blocks.length === 0 && day.deadlines.length === 0 && (
            <p className="muted cal-rail-empty">
              이날은 비어 있습니다. 아래에서 일정이나 마감을 넣으세요.
            </p>
          )}

          <div className="cal-add">
            <p className="card-label">이날에 추가</p>

            <input
              className="agent-input"
              placeholder={
                isDeadline ? "예: 캡스톤 중간 발표" : "예: 논문 미팅"
              }
              value={form.title}
              onChange={(event) =>
                setForm({ ...form, title: event.target.value })
              }
            />

            <div className="cal-chip-row">
              {KINDS.map((kind) => (
                <button
                  key={kind.key}
                  className={form.kind === kind.key ? "chip chip-on" : "chip"}
                  onClick={() => setForm({ ...form, kind: kind.key })}
                >
                  {kind.label}
                </button>
              ))}
            </div>

            {!isDeadline && (
              <div className="cal-chip-row">
                <button
                  className={repeats ? "chip" : "chip chip-on"}
                  onClick={() => setForm({ ...form, repeats: false })}
                >
                  이날만
                </button>
                <button
                  className={repeats ? "chip chip-on" : "chip"}
                  disabled={form.allDay}
                  onClick={() => setForm({ ...form, repeats: true })}
                >
                  매주 {DAYS[weekdayOf(selected)]}요일
                </button>

                <label className="cal-check">
                  <input
                    type="checkbox"
                    checked={form.allDay}
                    onChange={(event) =>
                      setForm({
                        ...form,
                        allDay: event.target.checked,
                        repeats: false
                      })
                    }
                  />
                  종일
                </label>
              </div>
            )}

            {!allDay && (
              <div className="cal-chip-row">
                <input
                  className="plan-input"
                  type="time"
                  value={form.start}
                  onChange={(event) =>
                    setForm({ ...form, start: event.target.value })
                  }
                />
                <span className="muted">–</span>
                <input
                  className="plan-input"
                  type="time"
                  value={form.end}
                  onChange={(event) =>
                    setForm({ ...form, end: event.target.value })
                  }
                />
              </div>
            )}

            <button
              className="agent-button"
              disabled={
                working ||
                !form.title.trim() ||
                (!allDay && toMinutes(form.end) <= toMinutes(form.start))
              }
              onClick={add}
            >
              추가
            </button>

            <p className="muted form-hint">
              {isDeadline
                ? "마감은 빈 시간을 줄이지 않습니다. 가까워지면 Today 의 D-day 띠에 뜹니다."
                : "겹치는 일정은 한 번만 셉니다. 종일 일정은 빈 시간에서 빼지 않습니다."}
            </p>
          </div>
        </aside>
      </div>

      {/* 루틴은 오늘 계획의 시간을 먼저 떼어 간다. 시간을 정하는 곳에 둔다. */}
      <RoutinesCard />

      <details className="card cal-settings-card">
        <summary>
          <span className="card-label">활동 시간대와 하루 상한</span>
          <span className="muted">
            {settings.window_label} · 상한 {hours(settings.daily_cap_minutes)}
          </span>
        </summary>

        <div className="cal-settings">
          <label>
            <span className="plan-key">시작</span>
            {/* 글자를 칠 때마다 저장하지 않는다. 칸을 벗어날 때 한 번. */}
            <input
              key={`start-${settings.window_start}`}
              className="plan-input"
              type="time"
              defaultValue={toTime(settings.window_start)}
              onBlur={(event) => {
                const value = event.target.value
                if (value && toMinutes(value) !== settings.window_start) {
                  setSetting("day_start_minute", toMinutes(value))
                }
              }}
            />
          </label>

          <label>
            <span className="plan-key">끝</span>
            <input
              key={`end-${settings.window_end}`}
              className="plan-input"
              type="time"
              defaultValue={toTime(settings.window_end)}
              onBlur={(event) => {
                const value = event.target.value
                if (value && toMinutes(value) !== settings.window_end) {
                  setSetting("day_end_minute", toMinutes(value))
                }
              }}
            />
          </label>

          <label>
            <span className="plan-key">하루 상한 (분)</span>
            <input
              key={`cap-${settings.daily_cap_minutes}`}
              className="plan-input"
              type="number"
              min="0"
              max="1440"
              step="30"
              defaultValue={settings.daily_cap_minutes}
              onBlur={(event) => {
                const value = Number(event.target.value) || 0
                if (value !== settings.daily_cap_minutes) {
                  setSetting("daily_cap_minutes", value)
                }
              }}
            />
          </label>
        </div>

        <p className="muted form-hint">
          빈 시간이 9시간이어도 9시간 공부하지는 않습니다. 상한은 그 차이를
          메웁니다.
        </p>
      </details>
    </div>
  )
}

/* 주 보기 — 시간 축이 있는 격자. 한 달 칸으로는 몇 시에 비는지 안 보인다. */
function WeekGrid({ week, settings, selected, onSelect }) {
  const timed = week.flatMap((day) => day.blocks.filter(takesTime))

  const startHour = Math.floor(
    Math.min(settings.window_start, ...timed.map((b) => b.start_minute)) / 60
  )
  const endHour = Math.ceil(
    Math.max(settings.window_end, ...timed.map((b) => b.end_minute)) / 60
  )
  const hourCount = Math.max(1, endHour - startHour)

  const top = (minute) => ((minute - startHour * 60) / 60) * HOUR_PX

  return (
    <section className="card calw">
      <div className="calw-row calw-head">
        <span />
        {week.map((day) => (
          <button
            key={day.date}
            className={
              day.date === selected ? "calw-day calw-day-on" : "calw-day"
            }
            onClick={() => onSelect(day.date)}
          >
            <span className={`wd-${day.weekday}`}>{DAYS[day.weekday]}</span>
            <strong className={day.is_today ? "calw-today" : undefined}>
              {day.day}
            </strong>
          </button>
        ))}
      </div>

      <div className="calw-row calw-allday">
        <span className="calw-axis-label">종일</span>
        {week.map((day) => (
          <div key={day.date} className="calw-allday-cell">
            {day.deadlines.map((item) => (
              <span
                key={`${item.kind}-${item.id}`}
                className="calm-chip tone-deadline"
              >
                {item.title}
              </span>
            ))}
            {day.blocks
              .filter((block) => !takesTime(block))
              .map((block) => (
                <span
                  key={block.id}
                  className={`calm-chip tone-${block.kind}`}
                >
                  {block.title}
                </span>
              ))}
          </div>
        ))}
      </div>

      <div className="calw-scroll">
        <div
          className="calw-row calw-body"
          style={{ height: hourCount * HOUR_PX }}
        >
          <div className="calw-axis">
            {Array.from({ length: hourCount }, (_, index) => (
              <span key={index} style={{ top: index * HOUR_PX }}>
                {String(startHour + index).padStart(2, "0")}:00
              </span>
            ))}
          </div>

          {week.map((day) => {
            const { placed, count } = lanes(day.blocks.filter(takesTime))

            return (
              <div
                key={day.date}
                className={
                  day.date === selected ? "calw-col calw-col-on" : "calw-col"
                }
                style={{ backgroundSize: `100% ${HOUR_PX}px` }}
                onClick={() => onSelect(day.date)}
              >
                {placed.map(({ block, lane }) => (
                  <div
                    key={block.id}
                    className={
                      block.repeats
                        ? `calw-block tone-${block.kind} calm-repeat`
                        : `calw-block tone-${block.kind}`
                    }
                    style={{
                      top: top(block.start_minute),
                      height: Math.max(
                        18,
                        ((block.end_minute - block.start_minute) / 60) *
                          HOUR_PX -
                          2
                      ),
                      left: `${(lane / count) * 100}%`,
                      width: `${100 / count}%`
                    }}
                    title={`${block.start}–${block.end} ${block.title}`}
                  >
                    <span className="calw-block-time">{block.start}</span>
                    <span className="calw-block-title">{block.title}</span>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
