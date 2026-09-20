import { useCallback, useEffect, useRef, useState } from "react"
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

/* 시작할 곳이 정해지지 않은 루틴 — 여기서 바로 정하고 시작한다.

   전에는 "캘린더에서 넣어 두세요" 한 줄만 떴다. 누른 사람 입장에선 아무 일도
   안 일어난 것과 같았다. 경로를 고르면 그 경로의 다음 단계를 바로 열고,
   주소를 넣으면 바로 열 수 있는 링크를 준다. */
function RoutineStart({ routine, working, onOpenStep, onSaved }) {
  const [paths, setPaths] = useState([])
  const [pathId, setPathId] = useState("")
  const [link, setLink] = useState("")
  const [savedLink, setSavedLink] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const panelRef = useRef(null)

  // 맨 위 "시작하기" 에서 눌렀으면 패널이 화면 밖에 뜬다. 뜨자마자 그 자리로 간다 —
  // 전에는 카드로 스크롤했는데 패널이 그려지기 전이라 엉뚱한 곳에 멈춰 아무 일도 안 난 것처럼 보였다.
  useEffect(() => {
    panelRef.current?.scrollIntoView({ block: "center" })
    panelRef.current?.querySelector("select")?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    let cancelled = false
    api.learningPaths
      .list()
      .then((rows) => {
        if (!cancelled) setPaths(Array.isArray(rows) ? rows : rows?.paths ?? [])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const connect = async () => {
    try {
      setBusy(true)
      setMessage(null)
      const saved = await api.routines.update(routine.id, { learning_path_id: Number(pathId) })
      onSaved?.()
      if (saved.next_step) return onOpenStep(saved.next_step.id)
      setMessage("연결했지만 그 경로에 남은 단계가 없어요. 학습 화면에서 단계를 추가하세요.")
    } catch (failure) {
      setMessage(failure?.detail || "연결하지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  const saveLink = async () => {
    try {
      setBusy(true)
      setMessage(null)
      const saved = await api.routines.update(routine.id, { link_url: link.trim() })
      setSavedLink(saved.link_url)
      onSaved?.()
    } catch (failure) {
      setMessage(failure?.detail ? "주소는 http 또는 https 로 시작해야 해요." : "저장하지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div ref={panelRef} className="td-howto" role="region" aria-label="시작할 곳 정하기">
      <strong className="td-howto-title">어디서 시작할지 아직 정해지지 않았어요</strong>
      {routine.note && <p className="td-howto-note">메모 · {routine.note}</p>}

      <div className="td-howto-row">
        <label className="learn-field">
          <span>학습 경로에 연결 — 체크리스트대로 오늘 할 문제가 보여요</span>
          <select className="path-select" value={pathId} onChange={(event) => setPathId(event.target.value)}>
            <option value="">경로 고르기</option>
            {paths.map((path) => (
              <option key={path.id} value={path.id}>
                {path.title}
              </option>
            ))}
          </select>
        </label>
        <Button writes disabled={working || busy || !pathId} onClick={connect}>
          연결하고 시작
        </Button>
      </div>

      <div className="td-howto-row">
        <label className="learn-field">
          <span>또는 문제 목록 주소</span>
          <input
            className="agent-input"
            maxLength={500}
            placeholder="https://school.programmers.co.kr/learn/challenges"
            value={link}
            onChange={(event) => setLink(event.target.value)}
          />
        </label>
        <Button variant="secondary" writes disabled={working || busy || !link.trim()} onClick={saveLink}>
          저장
        </Button>
      </div>

      {savedLink && (
        <p className="td-howto-note">
          저장했어요. 다음부터는 &lsquo;시작&rsquo;이 바로 엽니다 —{" "}
          <a className="td-link" href={savedLink} target="_blank" rel="noopener noreferrer">
            지금 열기
          </a>
        </p>
      )}
      {message && <p className="td-howto-note">{message}</p>}
    </div>
  )
}

function TaskCard({
  task,
  index,
  working,
  onComplete,
  onSkip,
  onStart,
  onReopen,
  onOpenStep,
  onSaved,
  showHow
}) {
  const planned = task.status === "planned"
  // 루틴에 목표 개수가 있으면 실제로 한 개수를 적고 끝낸다. 기본은 목표만큼.
  const target = task.routine?.target_count ?? null
  const [count, setCount] = useState(target ?? "")
  const finish = () => onComplete(target != null && count !== "" ? Number(count) : undefined)

  return (
    <li id={`td-task-${task.id}`} className={`td-task td-task-${task.status}`}>
      <Button
        variant="check"
        writes
        tryInDemo
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
            <Button variant="quiet" writes tryInDemo disabled={working} onClick={onSkip}>
              오늘은 넘기기
            </Button>
          </div>
        )}

        {/* 잘못 누른 완료 · 넘김은 되돌린다. 완료가 남긴 기록도 같이 지워진다. */}
        {!planned && (
          <div className="ui-row td-task-actions">
            <Button variant="quiet" writes tryInDemo disabled={working} onClick={onReopen}>
              {task.status === "done" ? "완료 되돌리기" : "넘김 되돌리기"}
            </Button>
          </div>
        )}

        {showHow && planned && task.routine && (
          <RoutineStart
            routine={task.routine}
            working={working}
            onOpenStep={onOpenStep}
            onSaved={onSaved}
          />
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
  // 시작할 곳이 없는 루틴에서 "시작" 을 누른 카드
  const [howToId, setHowToId] = useState(null)

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
  const reopen = (task) =>
    run(async () => {
      const result = await api.todayPlan.reopen(task.id)
      return result.effects?.length
        ? `되돌렸어요 — ${result.effects.join(" · ")}`
        : "되돌렸어요. 다시 할 일로 돌아갔습니다."
    }, "되돌리지 못했습니다.")

  const start = (task) => {
    // 계획을 세운 뒤 루틴에 경로를 연결했어도 바로 열린다 — 다음 단계는 지금 계산한 값.
    const stepId = task.learning_step_id ?? task.routine?.next_step?.id
    if (stepId) return onOpenStep(stepId)
    /* 루틴은 학습 화면으로 보내지 않는다 — 코테를 눌렀는데 늘 보던 학습 화면이
       나오면 시작한 게 아니다. 적어 둔 곳을 열거나, 없으면 그 자리에서 알려 준다. */
    if (task.routine) {
      if (task.routine.link_url) {
        window.open(task.routine.link_url, "_blank", "noopener,noreferrer")
        return
      }
      // 스크롤은 패널이 그려진 뒤 패널이 직접 한다 (RoutineStart).
      setHowToId(task.id)
      return
    }
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

          {/* 계획은 세운 순간의 판단으로 저장된다. 그 뒤 공고가 들어와 1위가 바뀌면
              할 일의 "선택 이유" 와 아래 "왜 이 계획인가" 가 서로 다른 말을 한다. */}
          {plan?.outdated && (
            <Notice tone="warn">
              <strong>계획을 세운 뒤 바뀐 것이 있어요.</strong>{" "}
              {plan.outdated.reasons.join(" · ")}.{" "}
              <Button variant="secondary" writes disabled={working} onClick={createPlan}>
                지금 기준으로 다시 세우기
              </Button>
            </Notice>
          )}

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
                    onReopen={() => reopen(task)}
                    onOpenStep={onOpenStep}
                    onSaved={() => load(true)}
                    showHow={howToId === task.id}
                  />
                ))}
              </ol>

              {/* "무엇을 하지 않아도 되는가" 를 말하지 않으면 고른 게 아니라 나열한 것이다. */}
              {rest.length > 0 && (
                <details className="td-more">
                  <summary>
                    나머지 {rest.length}개는 오늘 안 해도 됩니다 — 오늘 시간
                    {" "}{minutesText(plan.available_minutes)} 안에 들어간 건 위의 {visible.length}개예요
                  </summary>
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
                    onReopen={() => reopen(task)}
                    onOpenStep={onOpenStep}
                    onSaved={() => load(true)}
                    showHow={howToId === task.id}
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
