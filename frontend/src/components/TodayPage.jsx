import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  Notice,
  ProgressBar,
  StatusBadge,
  WhyPanel
} from "./ui"
import { InlineCode } from "./ChecklistPanel"
import { areaLabel, ddayLabel, greeting, minutesText, todayText } from "../format"
import "../Today.css"
import "../Checklist.css"
import "../Routine.css"

/* Today — 지금 무엇을 할지.

   맨 위에 세 가지만 둔다: 오늘 쓸 수 있는 시간, 핵심 초점, 가장 먼저
   할 일. 설정은 접어 둔다 — 매일 설정부터 만지게 하면 도구가 아니라 폼이다.

   항목마다 반드시 두 줄이 있다.
     선택 이유   이유를 못 쓰면 계획에 넣지 않는다 (DESIGN.md 원칙 1)
     완료하면    누르기 전에 무엇이 바뀌는지. 안 바뀌는 것은 안 바뀐다고.

   좁은 화면 순서: 요약 → 가장 먼저 할 일 → 작업 목록 → 근거. */

const PRESETS = [30, 60, 120, 180]

// 레일에는 결정에 직접 쓰인 것만. 아홉 개를 다 올리면 계산 설명 화면이 된다.
const RAIL_KEYS = ["market", "gap", "learning", "time"]

// 크게 보여줄 항목 수. 나머지는 지우지 않고 접는다.
const VISIBLE_TASKS = 3

function TaskCard({ task, index, working, onComplete, onSkip, onStart }) {
  const planned = task.status === "planned"
  // 루틴에 목표 개수가 있으면 실제로 한 개수를 적고 끝낸다. 기본은 목표만큼.
  const target = task.routine?.target_count ?? null
  const [count, setCount] = useState(target ?? "")
  const finish = () => onComplete(target != null && count !== "" ? Number(count) : undefined)

  return (
    <li className={`td-task td-task-${task.status}`}>
      <Button
        variant="check"
        writes
        className="td-check"
        disabled={working || !planned}
        onClick={finish}
        aria-label={`${task.title} 완료로 표시`}
      >
        {task.status === "done" ? "✓" : index + 1}
      </Button>

      <div className="td-task-body">
        <div className="td-task-top">
          <StatusBadge tone={`area-${task.task_type}`}>
            {areaLabel(task.task_type)}
          </StatusBadge>
          {task.carried_from && <StatusBadge tone="warn">이월</StatusBadge>}
          {task.status === "done" && <StatusBadge tone="ok">완료</StatusBadge>}
          {task.status === "skipped" && <StatusBadge>넘김</StatusBadge>}
          <span className="td-task-minutes">{minutesText(task.minutes)}</span>
        </div>

        <strong className="td-task-title">{task.title}</strong>

        {/* 학습 단계는 하루에 안 끝난다. 오늘 실제로 할 줄을 보인다. */}
        {task.checklist && (
          <div className="td-task-line td-checklist">
            <span className="td-task-key">
              체크 {task.checklist.done}/{task.checklist.total}
            </span>
            {task.checklist.next.length > 0 ? (
              <ul className="td-checklist-next">
                {task.checklist.next.map((line) => (
                  <li key={line}>
                    <InlineCode text={line} />
                  </li>
                ))}
              </ul>
            ) : (
              <span>모두 체크했어요 — 끝났으면 완료로 표시하세요</span>
            )}
          </div>
        )}

        {task.reason && (
          <p className="td-task-line">
            <span className="td-task-key">선택 이유</span>
            <span>{task.reason}</span>
          </p>
        )}

        {planned && task.on_complete && (
          <p className="td-task-line">
            <span className="td-task-key">완료하면</span>
            <span>{task.on_complete}</span>
          </p>
        )}

        {planned && (
          <div className="ui-row td-task-actions">
            {target != null && (
              <label className="td-routine-count">
                한 개수
                <input
                  className="plan-input"
                  type="number"
                  min="0"
                  max="100"
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                />
                {task.routine.unit_label || "개"} / 목표 {target}
              </label>
            )}
            <Button onClick={onStart}>시작</Button>
            <Button variant="quiet" writes disabled={working} onClick={onSkip}>
              오늘은 넘기기
            </Button>
          </div>
        )}
      </div>
    </li>
  )
}

function TodayPage({ onOpenStep, onWhy, onNavigate, onChanged }) {
  const [minutes, setMinutes] = useState(120)
  const [intensity, setIntensity] = useState("normal")
  const [intensities, setIntensities] = useState([])

  const [plan, setPlan] = useState(null)
  const [why, setWhy] = useState(null)
  const [calendar, setCalendar] = useState(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [showSettings, setShowSettings] = useState(false)

  // quiet: 버튼을 누른 뒤 다시 읽을 때는 화면 전체를 "불러오는 중" 으로
  // 바꾸지 않는다. 방금 누른 자리가 사라지면 무엇이 됐는지 볼 수 없다.
  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setError(null)

      // 기본 예산은 캘린더가 정한다. 120 은 어디서 나온 숫자냐는
      // 질문에 답할 수 없는 값이었다.
      const day = await api.calendar.day()
      const budget = day.suggested_minutes

      const [options, current, reasoning] = await Promise.all([
        api.todayPlan.intensities(),
        api.todayPlan.get(budget, "normal"),
        api.todayPlan.why(budget, "normal")
      ])

      setIntensities(options.intensities)
      setPlan(current)
      setWhy(reasoning)
      setCalendar(day)
      setMinutes(budget)

      // 이미 만들어둔 계획이 있으면 그 설정으로 컨트롤을 맞춘다.
      if (current.total_tasks > 0) {
        setMinutes(current.available_minutes)
        setIntensity(current.intensity)
      }
    } catch (loadError) {
      console.error("Failed to load today:", loadError)
      setError("오늘 계획을 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action, fallback = "요청을 처리하지 못했습니다.") => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const message = await action()
      await load(true)
      onChanged?.()
      if (message) setNotice(message)
    } catch (actionError) {
      console.error("Today action failed:", actionError)
      setError(actionError?.detail || fallback)
    } finally {
      setWorking(false)
    }
  }

  const createPlan = () =>
    run(async () => {
      await api.todayPlan.create(minutes, intensity)
      return "오늘 계획을 세웠어요."
    }, "계획을 세우지 못했습니다.")

  const complete = (task, count) =>
    run(async () => {
      const result = await api.todayPlan.complete(
        task.id,
        count != null ? { count } : undefined
      )
      return result.effects?.length
        ? `완료했어요 — ${result.effects.join(" · ")}`
        : "완료했어요. 오늘 한 기록이 남았습니다."
    }, "완료로 표시하지 못했습니다.")

  const skip = (task) =>
    run(async () => {
      await api.todayPlan.skip(task.id)
      return `'${task.title}' 은(는) 오늘 넘겼어요.`
    }, "넘기지 못했습니다.")

  /* 그 항목이 있는 실제 화면으로 데려간다.
     "시작" 이 아무 데도 데려가지 않으면 버튼이 아니라 장식이다. */
  const start = (task) => {
    if (task.learning_step_id) return onOpenStep(task.learning_step_id)
    if (task.application_id) return onNavigate(["applications", String(task.application_id)])
    if (task.opportunity_id) return onNavigate("opportunities")
    if (task.project_id) return onNavigate("projects")
    if (task.learning_resource_id) return onNavigate("library")
    return onNavigate("learning")
  }

  if (loading) {
    return <LoadingState label="오늘 계획을 불러오는 중…" />
  }

  if (!plan) {
    return <ErrorState message={error} onRetry={() => load()} />
  }

  const tasks = plan.tasks ?? []
  const active = tasks.filter((task) => task.status !== "skipped")
  const done = tasks.filter((task) => task.status === "done")
  const next = active.find((task) => task.status === "planned")

  const visible = tasks.slice(0, VISIBLE_TASKS)
  const rest = tasks.slice(VISIBLE_TASKS)

  const inputs = why?.inputs ?? []
  const market = inputs.find((cell) => cell.key === "market" && cell.available)
  const gap = inputs.find((cell) => cell.key === "gap")
  const rail = inputs.filter(
    (cell) => RAIL_KEYS.includes(cell.key) && cell.available
  )

  const conclusion = why?.focus_skill
    ? [why.headline, market?.detail].filter(Boolean).join(" ")
    : null

  let hero

  if (tasks.length === 0) {
    hero = (
      <NextActionCard
        eyebrow="가장 먼저 할 일"
        icon="+"
        title="아직 오늘 계획이 없어요"
        meta="우선순위 · 마감 · 어제 못 한 일을 보고 Career OS 가 골라 드려요."
        action={
          <Button writes disabled={working} onClick={createPlan}>
            계획 세우기
          </Button>
        }
      />
    )
  } else if (!next) {
    hero = (
      <NextActionCard
        eyebrow="오늘"
        tone="ok"
        icon="✓"
        title="오늘 계획을 모두 끝냈어요"
        detail={`${done.length}개 · ${minutesText(plan.done_minutes)}`}
        meta="한 일은 회고의 날마다 칸에 쌓입니다."
        action={
          <a className="ui-btn ui-btn-secondary" href="#/review">
            회고 보기
          </a>
        }
      />
    )
  } else {
    hero = (
      <NextActionCard
        eyebrow="가장 먼저 할 일"
        icon="▶"
        title={next.title}
        detail={`${areaLabel(next.task_type)} · ${minutesText(next.minutes)}`}
        meta={next.reason}
        action={<Button onClick={() => start(next)}>시작하기</Button>}
      />
    )
  }

  return (
    <div className="today-page td">
      {/* ---------- 요약 ---------- */}
      <section className="card td-hero">
        <p className="td-greet">
          {greeting()}
          <span className="td-date">{todayText()}</span>
        </p>

        <div className="td-facts">
          <div className="td-fact">
            <span className="td-fact-key">오늘 사용할 수 있는 시간</span>
            <strong className="td-fact-value">
              {minutesText(plan.available_minutes)}
            </strong>
            <span className="td-fact-hint">
              {calendar
                ? `일정을 빼고 빈 ${minutesText(calendar.free_minutes)} 중 하루 상한까지`
                : "캘린더를 읽지 못해 기본값을 썼어요"}
            </span>
          </div>

          <div className="td-fact">
            <span className="td-fact-key">오늘의 핵심 초점</span>
            <strong className="td-fact-value">{why?.focus_skill ?? "아직 없음"}</strong>
            <span className="td-fact-hint">
              {why?.focus_skill
                ? [
                    market && `시장 수요 ${market.value.split("·").pop().trim()}건`,
                    gap?.value
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "스킬과 공고가 쌓이면 정해져요"}
            </span>
          </div>

          <div className="td-fact">
            <span className="td-fact-key">오늘 진행</span>
            <strong className="td-fact-value">
              {done.length} / {active.length}
            </strong>
            <ProgressBar
              value={done.length}
              max={Math.max(1, active.length)}
              label="오늘 계획 진행"
            />
          </div>
        </div>

        {hero}
      </section>

      {error && (
        <Notice tone="bad" onClose={() => setError(null)}>
          {error}
        </Notice>
      )}
      {notice && (
        <Notice tone="ok" onClose={() => setNotice(null)}>
          {notice}
        </Notice>
      )}

      {/* 사흘 넘게 밀린 것. 계획에서 빠졌다는 사실을 말해주지
          않으면 조용히 버린 것과 같다. 두 답이 다 가능해야 질문이다. */}
      {plan.stale?.length > 0 && (
        <section className="card stale-box">
          <p className="stale-head">
            이건 안 할 건가요?
            <span className="stale-why">사흘 넘게 미뤄서 오늘 계획에서 뺐습니다</span>
          </p>

          {plan.stale.map((item) => (
            <div className="stale-row" key={item.task_id}>
              <span className="stale-title">{item.title}</span>
              <span className="stale-days">{item.days_carried}일째</span>
              <Button
                variant="secondary"
                writes
                disabled={working}
                onClick={() =>
                  run(async () => {
                    await api.todayPlan.revive(item.task_id)
                    return `'${item.title}' 을(를) 다시 계획 후보로 돌렸어요.`
                  })
                }
              >
                그래도 할래요
              </Button>
              <Button
                variant="quiet"
                writes
                disabled={working}
                onClick={() =>
                  run(async () => {
                    await api.todayPlan.skip(item.task_id)
                    return `'${item.title}' 을(를) 치웠어요.`
                  })
                }
              >
                치우기
              </Button>
            </div>
          ))}
        </section>
      )}

      <div className="today-grid">
        {/* ---------- 작업 목록 ---------- */}
        <section className="card td-plan">
          <div className="td-plan-head">
            <div>
              <h2 className="td-plan-title">오늘 할 일</h2>
              <p className="td-plan-sub">
                {tasks.length > 0
                  ? `계획 ${minutesText(plan.planned_minutes)} · 강도 ${plan.intensity_label}`
                  : "아직 계획 전"}
              </p>
            </div>

            <Button
              variant="secondary"
              aria-expanded={showSettings}
              onClick={() => setShowSettings(!showSettings)}
            >
              {showSettings ? "설정 닫기" : "시간 · 강도 설정"}
            </Button>
          </div>

          {showSettings && (
            <div className="plan-controls td-settings">
              <div className="plan-field">
                <span className="plan-key">사용 가능 시간</span>
                <div className="plan-minutes">
                  {PRESETS.map((preset) => (
                    <button
                      key={preset}
                      className={minutes === preset ? "chip chip-on" : "chip"}
                      aria-pressed={minutes === preset}
                      onClick={() => setMinutes(preset)}
                    >
                      {minutesText(preset)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="plan-field">
                <span className="plan-key">강도</span>
                <div className="plan-minutes">
                  {intensities.map((option) => (
                    <button
                      key={option.key}
                      className={intensity === option.key ? "chip chip-on" : "chip"}
                      aria-pressed={intensity === option.key}
                      title={`최대 ${option.max_tasks}개 · 한 덩어리 ${option.max_block}분까지`}
                      onClick={() => setIntensity(option.key)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <Button writes disabled={working} onClick={createPlan}>
                이 설정으로 다시 세우기
              </Button>

              {/* 기본값이 어디서 나왔는지. 답할 수 없는 숫자를 기본값으로 두지 않는다. */}
              {calendar && (
                <p className="muted form-hint plan-source">
                  캘린더 기준 · 활동 시간대 {calendar.window_label} 중 일정{" "}
                  {minutesText(calendar.busy_minutes)}을 빼면{" "}
                  {minutesText(calendar.free_minutes)}이 비고, 하루 상한{" "}
                  {minutesText(calendar.daily_cap_minutes)}과 비교해{" "}
                  <strong>{minutesText(calendar.suggested_minutes)}</strong>을
                  제안했습니다. 일정을 바꾸면{" "}
                  <a className="td-link" href="#/calendar">
                    캘린더
                  </a>
                  에서 이 값이 바뀌고, 다시 세우면 계획에 반영됩니다.
                </p>
              )}
            </div>
          )}

          {plan.deadlines?.length > 0 && (
            <div className="td-deadlines" aria-label="다가오는 마감">
              {plan.deadlines.slice(0, 3).map((item) => (
                <StatusBadge
                  key={`${item.kind}-${item.id}`}
                  tone={item.days_left <= 3 ? "warn" : "neutral"}
                >
                  {ddayLabel(item.days_left)} · {item.title}
                </StatusBadge>
              ))}
            </div>
          )}

          {tasks.length === 0 ? (
            <EmptyState
              title="아직 오늘 계획이 없습니다."
              body="우선순위 · 마감 · 어제 못 한 일을 보고 오늘 할 일을 1~3개 고릅니다."
              actions={[
                { label: "계획 세우기", onClick: createPlan, primary: true, writes: true, disabled: working },
                { label: "캘린더에서 시간 확인", href: "#/calendar" }
              ]}
            />
          ) : (
            <>
              <ol className="td-tasks">
                {visible.map((task, index) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    index={index}
                    working={working}
                    onComplete={(count) => complete(task, count)}
                    onSkip={() => skip(task)}
                    onStart={() => start(task)}
                  />
                ))}
              </ol>

              {rest.length > 0 && (
                <details className="td-more">
                  <summary>나머지 {rest.length}개 더 보기</summary>
                  <ol className="td-tasks" start={VISIBLE_TASKS + 1}>
                    {rest.map((task, index) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={VISIBLE_TASKS + index}
                        working={working}
                        onComplete={(count) => complete(task, count)}
                        onSkip={() => skip(task)}
                        onStart={() => start(task)}
                      />
                    ))}
                  </ol>
                </details>
              )}
            </>
          )}
        </section>

        {/* ---------- 근거 ---------- */}
        <section className="card today-why">
          {why?.focus_skill ? (
            <WhyPanel conclusion={conclusion}>
              {rail.length > 0 && (
                <dl className="today-why-list">
                  {rail.map((cell) => (
                    <div key={cell.key}>
                      <dt>{cell.ko}</dt>
                      <dd>{cell.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </WhyPanel>
          ) : (
            <EmptyState
              title="아직 판단할 데이터가 없어요."
              body="스킬과 공고가 있어야 무엇이 중요한지 고를 수 있어요."
              actions={[
                { label: "공고 모으기", href: "#/opportunities", primary: true },
                { label: "학습 경로 만들기", href: "#/learning" }
              ]}
            />
          )}

          {why && (
            <button className="today-why-more" onClick={onWhy}>
              계산 근거 전체 보기 →
              <span>
                쓰인 데이터 {why.used_count ?? 0} / {inputs.length}종
              </span>
            </button>
          )}
        </section>
      </div>
    </div>
  )
}

export default TodayPage
