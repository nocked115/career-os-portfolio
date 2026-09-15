import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { Button, EmptyState, ErrorState, LoadingState, Notice, StatusBadge } from "./ui"
import "../Routine.css"

/* 매일 하는 것 — 코테 30분 · coding rehab 30분.

   오늘 계획은 루틴의 시간을 먼저 떼어 두고 남은 시간으로 학습 · 프로젝트를
   고른다. 그래서 캘린더(시간을 정하는 곳)에 둔다.

   목표는 저절로 오르지 않는다. 지난 7일 기록이 받쳐 줄 때만 올리기를 권하고,
   누르는 건 사람이다. */

const DAYS = ["월", "화", "수", "목", "금", "토", "일"]

const EMPTY_FORM = {
  title: "",
  minutes: 30,
  weekdays: [0, 1, 2, 3, 4, 5, 6],
  target: "",
  unit: "",
  pathId: ""
}

function Dots({ recent }) {
  return (
    <ol className="rt-dots" aria-label="최근 7일">
      {recent.map((day) => {
        const state = !day.due ? "off" : day.done ? "done" : "miss"
        const label = !day.due
          ? `${day.weekday} 쉬는 날`
          : day.done
            ? `${day.weekday} 함${day.count != null ? ` ${day.count}개` : ""}`
            : `${day.weekday} 기록 없음`

        return (
          <li key={day.date} className={`rt-dot rt-dot-${state}`} title={label} aria-label={label}>
            <span aria-hidden="true">{day.weekday}</span>
          </li>
        )
      })}
    </ol>
  )
}

export default function RoutinesCard({ onChanged }) {
  const [data, setData] = useState(null)
  const [paths, setPaths] = useState([])
  const [loading, setLoading] = useState(true)
  const [failure, setFailure] = useState(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [confirmId, setConfirmId] = useState(null)

  const load = useCallback(async () => {
    try {
      setFailure(null)
      const [routines, learningPaths] = await Promise.all([
        api.routines.list(),
        api.learningPaths.list()
      ])
      setData(routines)
      setPaths(learningPaths)
    } catch (loadError) {
      console.error("Failed to load routines:", loadError)
      setFailure("루틴을 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action, success, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      await action()
      await load()
      onChanged?.()
      if (success) setNotice(success)
      return true
    } catch (actionError) {
      console.error("Routine action failed:", actionError)
      setError(actionError?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  const toggleDay = (day) =>
    setForm((current) => ({
      ...current,
      weekdays: current.weekdays.includes(day)
        ? current.weekdays.filter((item) => item !== day)
        : [...current.weekdays, day].sort()
    }))

  const create = async () => {
    const ok = await run(
      () =>
        api.routines.create({
          title: form.title.trim(),
          minutes: Number(form.minutes) || 30,
          weekdays: form.weekdays,
          target_count: form.target ? Number(form.target) : null,
          unit_label: form.unit.trim(),
          learning_path_id: form.pathId ? Number(form.pathId) : null
        }),
      `'${form.title.trim()}' 루틴을 만들었어요. 오늘 화면에서 계획을 다시 세우면 들어가요.`,
      "루틴을 만들지 못했습니다."
    )

    if (ok) {
      setForm(EMPTY_FORM)
      setShowForm(false)
    }
  }

  if (loading) return <LoadingState label="루틴을 불러오는 중…" />
  if (!data) return <ErrorState message={failure} onRetry={load} />

  const canCreate =
    form.title.trim() && form.weekdays.length > 0 && Number(form.minutes) >= 5

  return (
    <section className="card rt" aria-labelledby="rt-title">
      <div className="rt-head">
        <div>
          <p className="card-label" id="rt-title">
            매일 하는 것
          </p>
          <p className="muted rt-sub">
            {data.routines.length > 0
              ? `오늘 ${data.daily_minutes}분을 먼저 떼어 두고, 남은 시간으로 학습 · 프로젝트를 골라요.`
              : "코테처럼 정한 요일마다 하는 일은 오늘 계획이 시간을 먼저 떼어 둬요."}
          </p>
        </div>
        {!showForm && (
          <Button variant="secondary" writes onClick={() => setShowForm(true)}>
            루틴 추가
          </Button>
        )}
      </div>

      {error && (
        <Notice tone="bad" onClose={() => setError(null)}>
          {error}
        </Notice>
      )}
      {notice && (
        <Notice tone="ok" onClose={() => setNotice(null)}>
          {notice}{" "}
          <a className="td-link" href="#/today">
            오늘 화면
          </a>
        </Notice>
      )}

      {data.routines.length === 0 && !showForm && (
        <EmptyState
          title="아직 루틴이 없어요."
          body="예: 코테 · 매일 30분 · 목표 3문제"
          actions={[{ label: "루틴 추가", primary: true, writes: true, onClick: () => setShowForm(true) }]}
        />
      )}

      <ul className="rt-list">
        {data.routines.map((routine) => (
          <li className={routine.active ? "rt-item" : "rt-item rt-paused"} key={routine.id}>
            <div className="rt-main">
              <div className="rt-title-row">
                <strong>{routine.title}</strong>
                {!routine.active && <StatusBadge>쉬는 중</StatusBadge>}
                {routine.today_log && <StatusBadge tone="ok">오늘 함</StatusBadge>}
              </div>
              <p className="rt-meta">
                {routine.weekday_label} · {routine.minutes}분
                {routine.target_text && ` · 목표 ${routine.target_text}`}
                {routine.learning_path && ` · ${routine.learning_path.title}`}
              </p>
              {routine.next_step && (
                <p className="rt-meta">다음 단계 · {routine.next_step.title}</p>
              )}
            </div>

            <div className="rt-week">
              <Dots recent={routine.recent} />
              <span className="muted">
                {routine.week.due > 0
                  ? `이번 주 ${routine.week.due}일 중 ${routine.week.done}일`
                  : "이번 주 아직 차례 없음"}
              </span>
            </div>

            {routine.suggestion && routine.active && (
              <div className="rt-suggest">
                <span>{routine.suggestion.evidence}</span>
                <Button
                  variant="secondary"
                  writes
                  disabled={working}
                  onClick={() =>
                    run(
                      () => api.routines.update(routine.id, { target_count: routine.suggestion.to }),
                      `목표를 ${routine.suggestion.to}${routine.unit_label || "개"}로 올렸어요.`,
                      "목표를 바꾸지 못했습니다."
                    )
                  }
                >
                  목표 {routine.suggestion.to}
                  {routine.unit_label || "개"}로 올리기
                </Button>
              </div>
            )}

            <div className="ui-row rt-actions">
              <Button
                variant="quiet"
                writes
                disabled={working}
                onClick={() =>
                  run(
                    () => api.routines.update(routine.id, { active: !routine.active }),
                    routine.active ? "잠시 쉬게 했어요. 오늘 계획에 넣지 않아요." : "다시 켰어요.",
                    "루틴을 바꾸지 못했습니다."
                  )
                }
              >
                {routine.active ? "잠시 쉬기" : "다시 켜기"}
              </Button>

              {confirmId === routine.id ? (
                <>
                  <Button
                    variant="quiet"
                    writes
                    disabled={working}
                    onClick={() =>
                      run(
                        () => api.routines.remove(routine.id),
                        "루틴을 지웠어요. 이미 한 날의 계획 기록은 남아요.",
                        "루틴을 지우지 못했습니다."
                      )
                    }
                  >
                    정말 지우기
                  </Button>
                  <Button variant="quiet" onClick={() => setConfirmId(null)}>
                    취소
                  </Button>
                </>
              ) : (
                <Button variant="quiet" writes onClick={() => setConfirmId(routine.id)}>
                  지우기
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>

      {showForm && (
        <div className="rt-form">
          <label className="learn-field">
            <span>이름</span>
            <input
              className="agent-input"
              maxLength={120}
              placeholder="예: 코테 (프로그래머스 Lv.1)"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
            />
          </label>

          <fieldset className="rt-days">
            <legend>요일</legend>
            {DAYS.map((name, day) => (
              <button
                type="button"
                key={name}
                className={form.weekdays.includes(day) ? "rt-day rt-day-on" : "rt-day"}
                aria-pressed={form.weekdays.includes(day)}
                onClick={() => toggleDay(day)}
              >
                {name}
              </button>
            ))}
          </fieldset>

          <div className="rt-form-row">
            <label className="learn-field">
              <span>하루 시간 (분)</span>
              <input
                className="agent-input"
                type="number"
                min="5"
                max="600"
                step="5"
                value={form.minutes}
                onChange={(event) => setForm({ ...form, minutes: event.target.value })}
              />
            </label>
            <label className="learn-field">
              <span>하루 목표 (선택)</span>
              <input
                className="agent-input"
                type="number"
                min="1"
                max="100"
                placeholder="3"
                value={form.target}
                onChange={(event) => setForm({ ...form, target: event.target.value })}
              />
            </label>
            <label className="learn-field">
              <span>단위</span>
              <input
                className="agent-input"
                maxLength={20}
                placeholder="문제"
                value={form.unit}
                onChange={(event) => setForm({ ...form, unit: event.target.value })}
              />
            </label>
          </div>

          <label className="learn-field">
            <span>학습 경로 연결 (선택) — 연결하면 그 경로의 다음 단계를 열어요</span>
            <select
              className="path-select"
              value={form.pathId}
              onChange={(event) => setForm({ ...form, pathId: event.target.value })}
            >
              <option value="">연결 안 함</option>
              {paths.map((path) => (
                <option key={path.id} value={path.id}>
                  {path.title}
                </option>
              ))}
            </select>
          </label>

          <div className="ui-row">
            <Button writes disabled={working || !canCreate} onClick={create}>
              만들기
            </Button>
            <Button
              variant="quiet"
              onClick={() => {
                setShowForm(false)
                setForm(EMPTY_FORM)
              }}
            >
              취소
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
