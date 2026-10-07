import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import LibraryPanel from "./LibraryPanel"
import LibraryShelf from "./LibraryShelf"
import LibraryToday from "./LibraryToday"
import { ChecklistImporter } from "./ChecklistPanel"
import "../Skill.css"
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  Notice,
  ProgressBar,
  StatusBadge
} from "./ui"
import {
  IMPORTANCE_HINTS,
  STEP_STATUS_TONES,
  importanceLabel,
  minutesText,
  ownershipLabel,
  stepStatusLabel
} from "../format"
import "../Learning.css"

/* Learning — 자료 모음이 아니라 학습을 실제로 끝내는 곳.

   맨 위는 "지금 이어서 할 단계" 하나다. 경로 목록과 만들기 폼은 그 아래.
   전에는 새 경로 폼이 화면 맨 위를 차지해서, 들어올 때마다 "무엇을 만들까"
   부터 물었다.

   탭 넷:
     학습 경로   어디까지 왔고 다음이 무엇인지
     내 자료     가진 것 중에서 지금 쓸 것 · 자료 등록
     세션 기록   진행 중이거나 끝낸 단계
     진행과 레벨 경로별 진행률 · 스킬 레벨 */

const TABS = [
  { key: "paths", label: "학습 경로" },
  { key: "library", label: "내 자료" },
  { key: "sessions", label: "세션 기록" },
  { key: "progress", label: "진행과 레벨" }
]

function findNextStep(path) {
  return (
    path.steps.find((step) => step.status === "in_progress") ??
    path.steps.find((step) => step.status === "not_started") ??
    null
  )
}

// 처음 열었을 때 볼 경로. 하던 것 → 남은 것이 있는 것 → 첫 번째.
function pickActivePath(paths) {
  return (
    paths.find((path) => path.steps.some((step) => step.status === "in_progress")) ??
    paths.find((path) => findNextStep(path)) ??
    paths[0] ??
    null
  )
}

function doneCount(path) {
  return path.steps.filter((step) => step.status === "completed").length
}

/* 단계 한 줄.
   전에는 줄 전체가 <button> 이라 안에 버튼을 넣을 수 없었다 — 그래서
   순서도 못 바꾸고 고치지도 못했다. 여는 자리만 버튼으로 두고 나머지를
   옆에 붙인다. */
function StepRow({ step, first, last, working, onOpen, onMove, onEdit, onRemove }) {
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(step.title)
  const [minutes, setMinutes] = useState(step.estimated_minutes || 0)

  if (editing) {
    return (
      <div className="step-item step-item-edit">
        <input
          className="agent-input step-edit-title"
          value={title}
          maxLength={200}
          aria-label="단계 이름"
          onChange={(event) => setTitle(event.target.value)}
        />
        <label className="step-edit-minutes">
          걸리는 시간
          <input
            className="plan-input"
            type="number"
            min="0"
            max="600"
            step="15"
            value={minutes}
            onChange={(event) => setMinutes(event.target.value)}
          />
          분
        </label>
        <Button
          writes
          disabled={working || !title.trim()}
          onClick={() => {
            onEdit({ title: title.trim(), estimated_minutes: Number(minutes) || 0 })
            setEditing(false)
          }}
        >
          저장
        </Button>
        <Button
          variant="quiet"
          disabled={working}
          onClick={() => {
            setTitle(step.title)
            setMinutes(step.estimated_minutes || 0)
            setEditing(false)
          }}
        >
          그만두기
        </Button>
      </div>
    )
  }

  return (
    <div className={`step-item step-${step.status}`}>
      <button className="step-open" onClick={onOpen}>
        <span className="step-position">
          {step.status === "completed" ? "✓" : String(step.position + 1).padStart(2, "0")}
        </span>
        <span className="step-title">{step.title}</span>
        <span className="step-status">{stepStatusLabel(step.status)}</span>
        <span className="step-percent">
          {step.estimated_minutes > 0 ? minutesText(step.estimated_minutes) : "시간 미정"}
        </span>
      </button>

      <span className="step-actions">
        <Button
          variant="quiet"
          writes
          disabled={working || first}
          aria-label={`${step.title} 위로`}
          onClick={() => onMove(-1)}
        >
          ↑
        </Button>
        <Button
          variant="quiet"
          writes
          disabled={working || last}
          aria-label={`${step.title} 아래로`}
          onClick={() => onMove(1)}
        >
          ↓
        </Button>
        <Button variant="quiet" disabled={working} onClick={() => setEditing(true)}>
          고치기
        </Button>
        <Button variant="quiet" writes disabled={working} onClick={onRemove}>
          지우기
        </Button>
      </span>
    </div>
  )
}


function LearningPage({ onOpenSession, initialTab = "paths" }) {
  const [data, setData] = useState(null)
  const [priority, setPriority] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [tab, setTab] = useState(initialTab)

  const [activePathId, setActivePathId] = useState(null)
  const [session, setSession] = useState(null)

  const [showPathForm, setShowPathForm] = useState(false)
  // 로드맵 한 장을 통째로 붙여넣는 칸.
  const [showRoadmap, setShowRoadmap] = useState(false)
  /* 전체에서 오늘 할 몫. 로드맵에 24시간이라고 적혀 있어도 오늘 몇 분인지
     안 나오면 계획이 안 된다. 펼친 경로만 불러온다. */
  const [pace, setPace] = useState(null)
  const [newPathTitle, setNewPathTitle] = useState("")
  const [newPathSkill, setNewPathSkill] = useState("")
  const [stepDrafts, setStepDrafts] = useState({})
  // 체크리스트를 붙여넣어 단계를 만드는 중인 경로. 한 번에 하나만 연다.
  const [importPathId, setImportPathId] = useState(null)
  const [working, setWorking] = useState(false)

  // 내 자료: 서가 아래 접힌 "자료 등록 · 챕터 관리" 와 서로 다시 읽게 한다.
  const [manageOpen, setManageOpen] = useState(false)
  const [registerNonce, setRegisterNonce] = useState(0)
  const [shelfKey, setShelfKey] = useState(0)

  const titleRef = useRef(null)

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)

      const [learning, lib, priorities] = await Promise.all([
        api.fetchLearning(),
        api.library.get(),
        api.analytics.learningPriority()
      ])

      setData({ ...learning, library: lib })
      setPriority(priorities.learning_priority ?? [])

      setActivePathId(
        (current) => current ?? pickActivePath(learning.paths)?.id ?? null
      )
    } catch (failure) {
      console.error("Failed to load learning data:", failure)
      setLoadError("학습 데이터를 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const paths = data?.paths ?? []
  const activePath = paths.find((path) => path.id === activePathId) ?? null
  const nextStep = activePath ? findNextStep(activePath) : null
  const nextStepId = nextStep?.id ?? null

  /* 오른쪽 패널은 다음 단계의 세션 데이터를 그대로 쓴다.
     여기서 자료를 다시 고르면 세션 화면과 다른 것을 권하게 된다. */
  useEffect(() => {
    if (!nextStepId) {
      setSession(null)
      return undefined
    }

    let cancelled = false

    api.learningSteps
      .session(nextStepId)
      .then((result) => {
        if (!cancelled) setSession(result)
      })
      .catch((failure) => {
        console.error("Failed to load next step:", failure)
        if (!cancelled) setSession(null)
      })

    return () => {
      cancelled = true
    }
  }, [nextStepId])

  const run = async (action, success, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const result = await action()
      await load(true)
      if (success) setNotice(typeof success === "function" ? success(result) : success)
      return result
    } catch (failure) {
      console.error("Learning action failed:", failure)
      setError(failure?.detail || fallback)
      return null
    } finally {
      setWorking(false)
    }
  }

  const openPathForm = (skillId) => {
    setTab("paths")
    setShowPathForm(true)
    if (skillId) setNewPathSkill(String(skillId))
    requestAnimationFrame(() => titleRef.current?.focus())
  }

  const createPath = async () => {
    const title = newPathTitle.trim()
    if (!title) return

    const created = await run(
      () =>
        api.learningPaths.create({
          title,
          skill_id: newPathSkill ? Number(newPathSkill) : null
        }),
      `'${title}' 경로를 만들었어요. 이제 단계를 추가하세요.`,
      "학습 경로를 만들지 못했습니다."
    )

    if (created) {
      setNewPathTitle("")
      setNewPathSkill("")
      setShowPathForm(false)
      setActivePathId(created.id)
    }
  }

  // 주차 체크리스트 한 장 → 경로의 새 단계. 만든 뒤 바로 그 단계를 연다.
  const createChecklistStep = async (path, structure, { title, dueDate }) => {
    let created = null

    await run(
      async () => {
        created = await api.checklists.createStep(path.id, {
          title,
          due_date: dueDate,
          ...structure
        })
      },
      `'${title}' 단계를 체크리스트와 함께 만들었어요.`,
      "체크리스트로 단계를 만들지 못했습니다."
    )

    if (created) {
      setImportPathId(null)
      onOpenSession(created.step_id)
    }
  }

  const createStep = (path) => {
    const title = (stepDrafts[path.id] ?? "").trim()
    if (!title) return

    return run(
      async () => {
        await api.learningSteps.create({
          learning_path_id: path.id,
          title,
          position: path.steps.length
        })
        setStepDrafts((current) => ({ ...current, [path.id]: "" }))
      },
      `'${title}' 단계를 추가했어요.`,
      "단계를 추가하지 못했습니다."
    )
  }

  // 스킬 추가. 목표 직무에 넣으면 준비도 계산에도 들어간다.
  const addSkill = async ({ name, category, level, aliases, toTarget }) => {
    let created = null
    let linked = false

    await run(
      async () => {
        created = await api.skills.create({ name, category, level, aliases })

        if (toTarget) {
          // 활성 목표가 없으면 { target_career: null } 이 온다 (오류가 아니다).
          const active = await api.targetCareers.active()
          const targetId = active?.target_career?.id

          if (targetId) {
            await api.targetCareers.linkSkill(targetId, created.id)
            linked = true
          }
        }
      },
      () =>
        `'${name}' 스킬을 추가했어요.` +
        (toTarget ? (linked ? " 목표 직무에도 넣었어요." : " 활성 목표 직무가 없어 목표에는 넣지 못했어요.") : "") +
        " 우선순위를 다시 계산했습니다.",
      "스킬을 추가하지 못했습니다."
    )

    return created
  }

  // 레벨이 바뀌면 우선순위가 통째로 다시 계산된다. 화면 값을 손으로
  // 고치지 않고 다시 읽는다 — 계산은 서버가 한다.
  const setLevel = (item, level) =>
    run(
      () => api.skills.setLevel(item.skill_id, level),
      `${item.skill} 레벨을 ${level}(으)로 바꿨어요. 우선순위를 다시 계산했습니다.`,
      "레벨을 바꾸지 못했습니다."
    )

  /* 단계 순서는 사람이 정한다. 앱이 마감이나 등록 순서로 줄 세우면
     "앞 수업을 못 들어서 복습부터 해야 한다" 를 넣을 자리가 없다. */
  const moveStep = (path, step, delta) => {
    const ordered = [...path.steps].sort((a, b) => a.position - b.position)
    const from = ordered.findIndex((row) => row.id === step.id)
    const to = from + delta

    if (to < 0 || to >= ordered.length) return

    const next = [...ordered]
    next.splice(to, 0, ...next.splice(from, 1))

    return run(
      () => api.learningSteps.reorder(path.id, next.map((row) => row.id)),
      `'${step.title}' 을(를) ${to + 1}번으로 옮겼어요.`,
      "순서를 바꾸지 못했습니다."
    )
  }

  const editStep = (step, body) =>
    run(() => api.learningSteps.update(step.id, body), "고쳤어요.", "고치지 못했습니다.")

  const removeStep = (step) =>
    run(
      () => api.learningSteps.remove(step.id),
      `'${step.title}' 단계를 지웠어요.`,
      "지우지 못했습니다."
    )

  /* 전공(도구) ↔ 교양(배경지식). 점수는 안 건드린다 — 놓는 자리만 옮긴다. */
  const setTrack = (item, track) =>
    run(
      () => api.skills.setTrack(item.skill_id, track),
      track === "general"
        ? `${item.skill} 을(를) 교양으로 옮겼어요. 읽고 아는 쪽으로 둡니다.`
        : `${item.skill} 을(를) 전공으로 옮겼어요. 손에 익히는 쪽으로 둡니다.`,
      "옮기지 못했습니다."
    )

  useEffect(() => {
    if (activePathId == null) {
      setPace(null)
      return
    }

    let alive = true

    api.learningPaths
      .pace(activePathId)
      .then((result) => alive && setPace({ pathId: activePathId, ...result }))
      .catch(() => alive && setPace(null))

    return () => {
      alive = false
    }
  }, [activePathId, paths])

  if (loading) {
    return <LoadingState label="학습 경로를 불러오는 중…" />
  }

  if (!data) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const { skills } = data
  const top = priority[0]

  const allSteps = paths.flatMap((path) =>
    path.steps.map((step) => ({ ...step, path }))
  )

  let hero

  if (paths.length === 0) {
    hero = (
      <EmptyState
        title="아직 학습 경로가 없습니다."
        body="경로를 만들고 단계를 넣으면, 다음 단계가 오늘 계획에 들어가고 끝낼 때마다 진행률이 쌓입니다."
        actions={[
          { label: "학습 경로 만들기", onClick: () => openPathForm(), primary: true, writes: true },
          ...(top
            ? [
                {
                  label: `우선순위 1위 ${top.skill} 로 만들기`,
                  onClick: () => openPathForm(top.skill_id),
                  writes: true
                }
              ]
            : [])
        ]}
      />
    )
  } else if (activePath && nextStep) {
    hero = (
      <NextActionCard
        eyebrow={`${activePath.title} · ${doneCount(activePath)}/${activePath.steps.length}단계 완료 · ${activePath.progress_percent}%`}
        icon="▶"
        title={nextStep.title}
        detail={
          nextStep.estimated_minutes > 0
            ? `예상 ${minutesText(nextStep.estimated_minutes)} · ${stepStatusLabel(nextStep.status)}`
            : "예상 시간이 없어 오늘 계획에 넣기 어려워요"
        }
        meta={session?.why_now?.reasons?.[0]}
        action={<Button onClick={() => onOpenSession(nextStep.id)}>세션 시작하기</Button>}
      />
    )
  } else if (activePath) {
    hero = (
      <NextActionCard
        eyebrow={activePath.title}
        tone={activePath.steps.length ? "ok" : "action"}
        icon={activePath.steps.length ? "✓" : "+"}
        title={
          activePath.steps.length
            ? "이 경로의 단계를 모두 끝냈어요"
            : "이 경로에 아직 단계가 없어요"
        }
        meta={
          activePath.steps.length
            ? "끝낸 단계는 회고의 날마다 칸에 쌓입니다. 다른 경로를 고르거나 새로 만드세요."
            : "아래 경로 카드에서 단계를 추가하면 다음 할 일이 여기에 나옵니다."
        }
      />
    )
  }

  return (
    <div className="learning-page learn">
      <section className="card learn-hero">
        <div>
          <h1 className="learn-title">학습</h1>
          <p className="learn-sub">필요한 역량을 단계로 나눠 실제로 끝냅니다.</p>
        </div>
        {hero}
      </section>

      <div className="learn-tabs" role="tablist" aria-label="학습 화면">
        {TABS.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab === item.key}
            className={tab === item.key ? "chip chip-on" : "chip"}
            onClick={() => setTab(item.key)}
          >
            {item.label}
            {item.key === "library" && data.library ? ` ${data.library.summary.total}` : ""}
          </button>
        ))}
      </div>

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

      {/* ---------- 내 자료 ---------- */}

      {tab === "library" && (
        <>
          <LibraryShelf
            refreshKey={shelfKey}
            onChanged={() => load(true)}
            onRegister={() => {
              setManageOpen(true)
              setRegisterNonce((current) => current + 1)
              requestAnimationFrame(() =>
                document.getElementById("library-manage")?.scrollIntoView({ block: "start" })
              )
            }}
          />

          <details className="card lib-manage">
            <summary>오늘 시간 안에서 고르면 — 지금 쓸 자료</summary>
            <LibraryToday />
          </details>

          <details
            id="library-manage"
            className="card lib-manage"
            open={manageOpen}
            onToggle={(event) => setManageOpen(event.currentTarget.open)}
          >
            <summary>자료 등록 · 챕터 관리</summary>
            <LibraryPanel
              key={registerNonce}
              skills={skills}
              initialShowForm={registerNonce > 0}
              onChanged={() => {
                load(true)
                setShelfKey((current) => current + 1)
              }}
            />
          </details>
        </>
      )}

      {/* ---------- 학습 경로 ---------- */}

      {tab === "paths" && (
        <div className="learn-grid">
          <div className="learn-left">
            {paths.map((path) => {
              const isOpen = activePathId === path.id
              const done = doneCount(path)

              return (
                <section
                  className={isOpen ? "card learn-path is-open" : "card learn-path"}
                  key={path.id}
                >
                  <button
                    className="path-header learn-path-head"
                    aria-expanded={isOpen}
                    onClick={() => setActivePathId(path.id)}
                  >
                    <span className="learn-path-main">
                      <strong>{path.title}</strong>
                      <span className="learn-path-meta">
                        <StatusBadge tone={STEP_STATUS_TONES[path.status]}>
                          {stepStatusLabel(path.status)}
                        </StatusBadge>
                        {done}/{path.steps.length}단계 완료
                      </span>
                    </span>
                    <span className="learn-path-percent">{path.progress_percent}%</span>
                  </button>

                  <ProgressBar
                    value={path.progress_percent}
                    label={`${path.title} 진행률`}
                  />

                  {isOpen && (
                    <PathEditor
                      key={`about-${path.id}`}
                      path={path}
                      skills={data.skills ?? []}
                      working={working}
                      onSave={(body) =>
                        run(
                          () => api.learningPaths.update(path.id, body),
                          "경로 설명을 저장했어요. 다른 세션에 넘길 프롬프트에 들어가요.",
                          "경로를 저장하지 못했습니다."
                        )
                      }
                    />
                  )}

                  {isOpen && pace?.pathId === path.id && pace.total_minutes > 0 && (
                    <p className={
                      pace.segment?.overdue || pace.behind
                        ? "path-pace path-pace-tight"
                        : "path-pace"
                    }>
                      {/* 구간이 있으면 **그 속도**를 말한다. 161시간을 먼 목표일까지
                          고르게 나누면 실제 계획과 다르다 — 12/10 까지 끝내야 할
                          57시간은 하루 53분인데, 전체로 나누면 1시간 7분이 나온다. */}
                      {pace.segment ? (
                        <>
                          {pace.segment.overdue ? (
                            <strong>
                              {pace.segment.due_date} 마감이 {-pace.segment.days_left}일
                              지났어요
                            </strong>
                          ) : (
                            <strong>오늘 {minutesText(pace.segment.minutes_per_day)}</strong>
                          )}
                          <span className="muted">
                            {" "}— {pace.segment.due_date} 까지{" "}
                            {minutesText(pace.segment.left_minutes)}
                            {!pace.segment.overdue && ` ÷ ${pace.segment.days_left}일`}
                            {" · "}
                            {pace.segment.title}
                          </span>
                          <span className="muted">
                            {" · "}전체 {minutesText(pace.total_minutes)} 중{" "}
                            {minutesText(pace.done_minutes)} 했음
                            {pace.target_date && ` · 끝은 ${pace.target_date}`}
                          </span>
                        </>
                      ) : pace.minutes_per_day != null ? (
                        <>
                          <strong>오늘 {minutesText(pace.minutes_per_day)}</strong>
                          <span className="muted">
                            {" "}— 남은 {minutesText(pace.left_minutes)} ÷ {pace.days_left}일
                            {" · "}전체 {minutesText(pace.total_minutes)} 중{" "}
                            {minutesText(pace.done_minutes)} 했음
                          </span>
                          {pace.behind && (
                            <span className="muted">
                              {" "}· 하루 3시간을 넘겨요. 목표일을 늦추거나 단계를 덜어내는 게 나아요.
                            </span>
                          )}
                        </>
                      ) : (
                        <span className="muted">
                          전체 {minutesText(pace.total_minutes)} 중{" "}
                          {minutesText(pace.done_minutes)} 했음 — 목표일이 없어 오늘 할 몫은
                          계산하지 않았어요.
                        </span>
                      )}
                    </p>
                  )}

                  {isOpen && (
                    <div className="step-list">
                      {path.steps.length === 0 ? (
                        <p className="muted">아직 단계가 없습니다. 아래에서 첫 단계를 넣으세요.</p>
                      ) : (
                        [...path.steps]
                          .sort((a, b) => a.position - b.position)
                          .map((step, index, rows) => (
                            <StepRow
                              key={step.id}
                              step={step}
                              first={index === 0}
                              last={index === rows.length - 1}
                              working={working}
                              onOpen={() => onOpenSession(step.id)}
                              onMove={(delta) => moveStep(path, step, delta)}
                              onEdit={(body) => editStep(step, body)}
                              onRemove={() => removeStep(step)}
                            />
                          ))
                      )}

                      <div className="step-form">
                        <input
                          className="agent-input"
                          aria-label={`${path.title} 에 단계 추가`}
                          placeholder="단계 추가 (예: EC2 기초)"
                          value={stepDrafts[path.id] ?? ""}
                          onChange={(event) =>
                            setStepDrafts({ ...stepDrafts, [path.id]: event.target.value })
                          }
                          onKeyDown={(event) => {
                            if (event.key === "Enter") createStep(path)
                          }}
                        />
                        <Button
                          variant="secondary"
                          writes
                          disabled={working || !(stepDrafts[path.id] ?? "").trim()}
                          onClick={() => createStep(path)}
                        >
                          단계 추가
                        </Button>
                      </div>

                      {importPathId === path.id ? (
                        <ChecklistImporter
                          mode="path"
                          busy={working}
                          onSave={(structure, options) =>
                            createChecklistStep(path, structure, options)
                          }
                          onCancel={() => setImportPathId(null)}
                        />
                      ) : (
                        <Button variant="quiet" writes onClick={() => setImportPathId(path.id)}>
                          주차 체크리스트를 붙여넣어 단계 만들기
                        </Button>
                      )}
                    </div>
                  )}
                </section>
              )
            })}

            {/* 로드맵은 "새 경로" 보다 위에 둔다 — 보통은 한 장을 통째로
                넣지, 빈 경로를 만들고 단계를 하나씩 치지 않는다. */}
            <section className="card learn-new">
              {showRoadmap ? (
                <RoadmapImporter
                  working={working}
                  skills={skills}
                  onCancel={() => setShowRoadmap(false)}
                  onDone={(result) => {
                    setShowRoadmap(false)
                    load(true)
                    setActivePathId(result.learning_path_id)
                    setNotice(
                      `'${result.title}' 을(를) 넣었어요 — 단계 ${result.steps}개 · 체크 ${result.checklist_items}개` +
                        (result.project_id
                          ? ". 마지막 프로젝트도 만들었습니다 (프로젝트 화면에서 보여요)."
                          : ".") +
                        (result.skill_id
                          ? ""
                          : " 스킬을 안 걸었어요 — '설명 · 스킬 · 목표일 고치기' 에서 고르면 이 경로에 자료를 연결할 수 있습니다.")
                    )
                  }}
                />
              ) : (
                <Button variant="secondary" writes onClick={() => setShowRoadmap(true)}>
                  로드맵 붙여넣어 경로 만들기
                </Button>
              )}
            </section>

            <section className="card learn-new">
              {showPathForm ? (
                <>
                  <p className="card-label">새 학습 경로</p>

                  <div className="path-form">
                    <label className="learn-field">
                      <span>경로 이름</span>
                      <input
                        ref={titleRef}
                        className="agent-input"
                        placeholder="예: AWS 배포 익히기"
                        value={newPathTitle}
                        onChange={(event) => setNewPathTitle(event.target.value)}
                      />
                    </label>

                    <label className="learn-field">
                      <span>연결할 스킬</span>
                      <select
                        className="path-select"
                        value={newPathSkill}
                        onChange={(event) => setNewPathSkill(event.target.value)}
                      >
                        <option value="">스킬 선택 안 함</option>
                        {skills.map((skill) => (
                          <option key={skill.id} value={skill.id}>
                            {skill.name}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="ui-row">
                    <Button writes disabled={working || !newPathTitle.trim()} onClick={createPath}>
                      만들기
                    </Button>
                    <Button variant="quiet" onClick={() => setShowPathForm(false)}>
                      취소
                    </Button>
                  </div>

                  <p className="muted form-hint">
                    스킬을 연결하면 이 경로의 진행률이 그 스킬의 우선순위에 반영됩니다.
                    자료 등록은 &lsquo;내 자료&rsquo; 탭에서 따로 합니다.
                  </p>
                </>
              ) : (
                <Button variant="secondary" writes onClick={() => openPathForm()}>
                  + 새 학습 경로
                </Button>
              )}
            </section>
          </div>

          {/* 오른쪽: 다음 단계의 이번 세션 자료와 이유 */}
          <div className="learn-right">
            {nextStep && (
              <section className="card">
                <p className="card-label">이번 세션 자료</p>

                {session?.selection?.selected?.length > 0 ? (
                  <>
                    <div className="learn-materials">
                      {session.selection.selected.map((item) => (
                        <div
                          className="learn-material"
                          key={`${item.kind}-${item.segment_id ?? item.resource_id}`}
                        >
                          <div>
                            <strong>{item.title}</strong>
                            <span className="muted">
                              {ownershipLabel(item.ownership)} · {minutesText(item.minutes)}
                            </span>
                          </div>
                          <StatusBadge tone={`imp-${item.importance}`}>
                            {importanceLabel(item.importance)}
                          </StatusBadge>
                        </div>
                      ))}
                    </div>

                    {session.selection.skipped_count > 0 && (
                      <p className="learn-aside">
                        <strong>지금 안 해도 되는 자료 {session.selection.skipped_count}개</strong>
                        <span>{session.selection.skipped_message}</span>
                      </p>
                    )}
                  </>
                ) : (
                  <EmptyState
                    title="이 단계에 쓸 자료가 아직 없어요."
                    body="가진 자료를 이 단계에 연결하면, 시간 예산 안에서 볼 것만 골라 드려요."
                    actions={[
                      { label: "세션에서 자료 연결하기", onClick: () => onOpenSession(nextStep.id), primary: true },
                      { label: "내 자료 보기", onClick: () => setTab("library") }
                    ]}
                  />
                )}
              </section>
            )}

            {session?.why_now?.reasons?.length > 0 && (
              <section className="card">
                <p className="card-label">왜 지금인가</p>
                <ul className="opp-reasons">
                  {session.why_now.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </section>
            )}

            {nextStep && session?.selection?.selected?.length > 0 && (
              <p className="muted form-hint learn-legend">
                {Object.entries(IMPORTANCE_HINTS)
                  .map(([key, hint]) => `${importanceLabel(key)} — ${hint}`)
                  .join(" · ")}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ---------- 세션 기록 ---------- */}

      {tab === "sessions" && (
        <SessionsTab
          steps={allSteps}
          onOpenSession={onOpenSession}
          onGoPaths={() => setTab("paths")}
        />
      )}

      {/* ---------- 진행과 레벨 ---------- */}

      {tab === "progress" && (
        <ProgressTab
          paths={paths}
          priority={priority}
          working={working}
          onSetLevel={setLevel}
          onSetTrack={setTrack}
          onAddSkill={addSkill}
        />
      )}
    </div>
  )
}

/* 진행 중이거나 끝낸 단계. 아직 시작 안 한 것은 여기 없다 —
   그건 학습 경로 탭의 일이다. */
function SessionsTab({ steps, onOpenSession, onGoPaths }) {
  const running = steps.filter((step) => step.status === "in_progress")
  const done = steps
    .filter((step) => step.status === "completed")
    .slice(-8)
    .reverse()

  return (
    <>
      <section className="card">
        <p className="card-label">진행 중 · {running.length}</p>

        {running.length === 0 ? (
          <EmptyState
            title="시작한 단계가 없습니다."
            body="학습 경로에서 단계를 열고 '학습 시작'을 누르면 여기에 나타납니다."
            actions={[{ label: "학습 경로 보기", onClick: onGoPaths, primary: true }]}
          />
        ) : (
          <div className="step-list">
            {running.map((step) => (
              <button
                className="step-item step-in_progress"
                key={step.id}
                onClick={() => onOpenSession(step.id)}
              >
                <span className="step-position">▶</span>
                <span className="step-title">{step.title}</span>
                <span className="step-status">{step.path.title}</span>
                <span className="step-percent">이어서 하기</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <p className="card-label">최근 완료 · {done.length}</p>

        {done.length === 0 ? (
          <p className="muted">아직 끝낸 단계가 없습니다. 하나를 끝내면 진행률과 회고에 쌓입니다.</p>
        ) : (
          <div className="step-list">
            {done.map((step) => (
              <button
                className="step-item step-completed"
                key={step.id}
                onClick={() => onOpenSession(step.id)}
              >
                <span className="step-position">✓</span>
                <span className="step-title">{step.title}</span>
                <span className="step-status">{step.path.title}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

/* 경로별 진행률과 스킬 레벨.
   우선순위 점수는 무엇의 점수인지 말할 수 없어 보이지 않는다.
   점수를 만든 재료(기회 수요 · 레벨 · 학습 진행)를 분모와 함께 쓴다. */
/* 경로 설명 · 목표일.

   전에는 화면에서 고칠 곳이 없었다. 설명은 다른 세션에 넘길 프롬프트의 "이 트랙" 이
   되고, 목표일은 14일 안에 들어오면 오늘 계획이 다음 단계를 챙긴다. */
function PathEditor({ path, skills = [], working, onSave }) {
  const [open, setOpen] = useState(false)
  const [description, setDescription] = useState(path.description ?? "")
  const [targetDate, setTargetDate] = useState(path.target_date ?? "")
  // 한 경로가 여러 스킬을 키운다 (Tave 논문 스터디 → PyTorch · Computer Vision).
  const linkedIds = (path.skills ?? []).map((skill) => skill.id)
  const [skillIds, setSkillIds] = useState(
    linkedIds.length ? linkedIds : path.skill_id ? [path.skill_id] : []
  )
  const written = (path.description ?? "").trim()
  const linkedNames = (path.skills ?? []).map((skill) => skill.name)

  if (!open) {
    return (
      <div className="path-about">
        {written ? (
          <p className="path-about-text">{written}</p>
        ) : (
          <p className="muted">
            경로 설명이 없어요. 다른 세션에 넘길 프롬프트의 "이 트랙" 칸이 비게 돼요.
          </p>
        )}
        <div className="ui-row">
          <span className="muted form-hint">
            키우는 스킬 {linkedNames.length ? linkedNames.join(" · ") : "없음"} · 목표일{" "}
            {path.target_date ?? "없음"}
          </span>
          <Button variant="quiet" writes onClick={() => setOpen(true)}>
            {written ? "설명 · 스킬 · 목표일 고치기" : "설명 · 스킬 · 목표일 적기"}
          </Button>
        </div>
      </div>
    )
  }

  const save = async () => {
    const saved = await onSave({
      description: description.trim(),
      target_date: targetDate || null,
      skill_ids: skillIds
    })
    if (saved) setOpen(false)
  }

  return (
    <div className="path-about path-about-edit">
      <label className="learn-field">
        <span>경로 설명 — 목표 · 진행 방식 · 기록 도구</span>
        <textarea
          className="learn-textarea"
          rows={4}
          maxLength={2000}
          placeholder="예: 매주 논문 1편 정독 후 토요일 발표. 핵심 메커니즘은 직접 구현하고 나머지는 clone-and-run. 코드는 GitHub, 메모는 Notion."
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      {/* 경로가 어떤 스킬을 키우는지. 연결하면 이 경로의 진행이 그 스킬의 학습으로 잡히고,
          그 스킬이 1위일 때 오늘 계획이 따로 자료를 찾지 않고 이 경로의 다음 단계를 꺼낸다. */}
      <fieldset className="path-skills">
        <legend>이 경로가 키우는 스킬 — 여러 개 고를 수 있어요. 진행이 고른 스킬 모두의 학습으로 잡혀요</legend>
        {skills.length === 0 ? (
          <p className="muted">등록된 스킬이 없어요. 진행 탭에서 먼저 추가하세요.</p>
        ) : (
          skills.map((skill) => (
            <label className="sk-check" key={skill.id}>
              <input
                type="checkbox"
                checked={skillIds.includes(skill.id)}
                onChange={() =>
                  setSkillIds((current) =>
                    current.includes(skill.id)
                      ? current.filter((id) => id !== skill.id)
                      : [...current, skill.id]
                  )
                }
              />
              {skill.name} · 레벨 {skill.level ?? 0}
            </label>
          ))
        )}
      </fieldset>

      <label className="learn-field">
        <span>목표일 (선택) — 14일 안으로 들어오면 오늘 계획이 다음 단계를 챙겨요</span>
        <input
          className="agent-input"
          type="date"
          value={targetDate}
          onChange={(event) => setTargetDate(event.target.value)}
        />
      </label>
      <div className="ui-row">
        <Button writes disabled={working} onClick={save}>
          저장
        </Button>
        <Button
          variant="quiet"
          onClick={() => {
            setDescription(path.description ?? "")
            setTargetDate(path.target_date ?? "")
            setSkillIds(linkedIds)
            setOpen(false)
          }}
        >
          취소
        </Button>
      </div>
    </div>
  )
}

const SKILL_CATEGORIES = ["데이터 · AI", "프로그래밍", "클라우드 · 인프라", "도구", "기타"]

const EMPTY_SKILL = {
  name: "",
  category: SKILL_CATEGORIES[0],
  level: 0,
  aliases: "",
  toTarget: true
}

/* 스킬 추가. 스킬이 없으면 공고 수요도, 우선순위도, 오늘 계획의 초점도 셀 수 없다.
   레벨은 사용자가 정한 기준(과목 · 성적 · 자격증 · 경험)으로 매긴다 — 앱이 추측하지 않는다. */
function AddSkillForm({ working, onAdd }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(EMPTY_SKILL)

  if (!open) {
    return (
      <Button variant="secondary" writes onClick={() => setOpen(true)}>
        스킬 추가
      </Button>
    )
  }

  const submit = async () => {
    const created = await onAdd({
      ...form,
      name: form.name.trim(),
      aliases: form.aliases.trim()
    })

    if (created) {
      setForm(EMPTY_SKILL)
      setOpen(false)
    }
  }

  return (
    <div className="sk-form">
      <div className="sk-row">
        <label className="learn-field">
          <span>스킬 이름</span>
          <input
            className="agent-input"
            maxLength={60}
            placeholder="예: PyTorch"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </label>

        <label className="learn-field">
          <span>분류</span>
          <select
            className="path-select"
            value={form.category}
            onChange={(event) => setForm({ ...form, category: event.target.value })}
          >
            {SKILL_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="learn-field">
        <span>지금 레벨</span>
        <span className="level-set" role="group" aria-label="새 스킬 레벨">
          {[0, 1, 2, 3, 4].map((value) => (
            <button
              type="button"
              key={value}
              className={value === form.level ? "level-dot level-dot-on" : "level-dot"}
              aria-pressed={value === form.level}
              onClick={() => setForm({ ...form, level: value })}
            >
              {value}
            </button>
          ))}
        </span>
        <small className="muted">
          기준: 관련 과목 이수 +1 · 그중 A0 이상 +1 · 관련 자격증 +1 · 경험으로 연결 +1
        </small>
      </div>

      <label className="learn-field">
        <span>다른 이름 (선택)</span>
        <input
          className="agent-input"
          maxLength={200}
          placeholder="쉼표로 — 예: 파이토치, torch (한글 공고에서도 찾게)"
          value={form.aliases}
          onChange={(event) => setForm({ ...form, aliases: event.target.value })}
        />
      </label>

      <label className="sk-check">
        <input
          type="checkbox"
          checked={form.toTarget}
          onChange={(event) => setForm({ ...form, toTarget: event.target.checked })}
        />
        목표 직무 스킬에도 넣기 — 넣으면 준비도 계산에 들어가요
      </label>

      <div className="ui-row">
        <Button writes disabled={working || !form.name.trim()} onClick={submit}>
          추가
        </Button>
        <Button
          variant="quiet"
          onClick={() => {
            setForm(EMPTY_SKILL)
            setOpen(false)
          }}
        >
          취소
        </Button>
      </div>
    </div>
  )
}

/* 스킬 한 줄. 전공 칸과 교양 칸이 같은 줄을 쓴다 — 모양이 다르면
   같은 것을 두 가지로 읽게 된다. */
function SkillRow({ item, index, working, onSetLevel, onSetTrack }) {
  const toGeneral = item.track !== "general"

  return (
    <div className="progress-row">
      <div className="progress-row-head">
        <strong>
          {index + 1}. {item.skill}
        </strong>

        <span className="muted">
          {item.total_demand > 0
            ? `기회 ${item.total_demand}건 중 ${item.demand_count}건이 요구`
            : "모아둔 기회 없음"}
          {" · "}학습 {item.learning_progress}%
        </span>

        {/* 레벨은 우선순위의 가장 큰 레버다. 고칠 수 없으면 배운 것이
            우선순위에 반영되지 않는다. */}
        <span className="level-set" role="group" aria-label={`${item.skill} 레벨`}>
          레벨
          {[0, 1, 2, 3, 4].map((value) => (
            <button
              key={value}
              className={value === item.my_level ? "level-dot level-dot-on" : "level-dot"}
              aria-pressed={value === item.my_level}
              aria-label={`${item.skill} 레벨 ${value}`}
              disabled={working}
              onClick={() => onSetLevel(item, value)}
            >
              {value}
            </button>
          ))}
        </span>

        <Button
          variant="quiet"
          writes
          disabled={working}
          onClick={() => onSetTrack(item, toGeneral ? "general" : "major")}
        >
          {toGeneral ? "교양으로 →" : "← 전공으로"}
        </Button>
      </div>

      <ProgressBar value={item.learning_progress} label={`${item.skill} 학습 진행`} />
      <span className="progress-row-percent">{item.learning_progress}%</span>
    </div>
  )
}


/* 로드맵 한 장을 통째로 붙여넣는 칸.

   체크리스트 붙여넣기는 **한 주차**를 만든다. 경로 하나를 세우려면 단계를
   하나씩 손으로 넣어야 했고, 그래서 경로가 "주제 목록" 에서 멈췄다.

   넣기 전에 먼저 읽어서 보여준다 — 경로 하나가 통째로 생기는 일이다. */
function RoadmapImporter({ working, skills = [], onDone, onCancel }) {
  const [text, setText] = useState("")
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  /* 스킬을 안 걸면 그 경로에서는 자료를 고를 수 없다 — 자료가 스킬로
     묶여 있기 때문이다. 넣고 나서야 막히는 것보다 여기서 묻는 게 낫다. */
  const [skillId, setSkillId] = useState("")

  const read = async () => {
    setBusy(true)
    setError(null)
    try {
      setPreview(await api.learningPaths.parseRoadmap(text))
    } catch (failure) {
      setPreview(null)
      setError(failure?.detail || "읽지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    setBusy(true)
    setError(null)
    try {
      onDone(await api.learningPaths.importRoadmap(text, skillId ? Number(skillId) : null))
    } catch (failure) {
      setError(failure?.detail || "넣지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="roadmap-import">
      <p className="card-label">로드맵 붙여넣기</p>

      <p className="muted form-hint">
        Claude 에 &ldquo;이 스킬 로드맵 짜줘&rdquo; 하고 받은 글을 그대로 넣으세요.
        경로 · 단계 · 체크 항목 · <strong>마지막 프로젝트</strong>까지 한 번에 생깁니다.
      </p>

      <details className="roadmap-format">
        <summary>어떤 형식이어야 하나요</summary>
        <pre>{`# 경로: 데이터 파이프라인 — 신입 포트폴리오용
목표: 공고 20/71건이 요구. 레벨 0 → 2
목표일: 2026-12-20

## 1주차 · SQL 로 원천 데이터 다루기 (180분)
- 윈도우 함수로 집계 쿼리 쓰기
- 조인 성능 확인하기

## 2주차 · Airflow 로 돌리기 (1시간 30분)
- DAG 하나 만들기

## 최종 프로젝트: 공고 수집 → 정제 → 적재 → 대시보드
증명: 데이터 파이프라인, SQL, BigQuery
남길 것: GitHub, 데모 링크`}</pre>
      </details>

      <textarea
        className="agent-input roadmap-text"
        rows={10}
        value={text}
        placeholder="여기에 붙여넣으세요"
        onChange={(event) => {
          setText(event.target.value)
          setPreview(null)
        }}
      />

      <label className="learn-field">
        <span>
          이 경로가 키우는 스킬 — 안 고르면 나중에 이 경로에서 자료를 못 고릅니다
        </span>
        <select
          className="path-select"
          value={skillId}
          onChange={(event) => setSkillId(event.target.value)}
        >
          <option value="">나중에 고르기</option>
          {skills.map((skill) => (
            <option key={skill.id} value={skill.id}>
              {skill.name} · 레벨 {skill.level ?? 0}
            </option>
          ))}
        </select>
      </label>

      {error && <p className="muted roadmap-error">{error}</p>}

      {preview && (
        <div className="roadmap-preview">
          <strong>{preview.title}</strong>
          <p className="muted opp-meta">
            단계 {preview.steps.length}개 · 모두 {minutesText(preview.total_minutes)}
            {preview.target_date && ` · 목표일 ${preview.target_date}`}
          </p>

          <ol className="roadmap-steps">
            {preview.steps.map((step, index) => (
              <li key={index}>
                {step.title}
                <span className="muted">
                  {" "}
                  {step.minutes > 0 ? minutesText(step.minutes) : "시간 미정"}
                  {step.items.length > 0 && ` · 체크 ${step.items.length}개`}
                </span>
              </li>
            ))}
          </ol>

          {preview.project ? (
            <p className="roadmap-project">
              <strong>최종 프로젝트 · {preview.project.name}</strong>
              {preview.project.skills.length > 0 && (
                <span className="muted"> — {preview.project.skills.join(" · ")} 를 증명</span>
              )}
            </p>
          ) : null}

          {/* 지어내지 않고, 빠진 것을 말한다. */}
          {preview.warnings.map((warning) => (
            <p className="muted roadmap-warning" key={warning}>
              ⚠ {warning}
            </p>
          ))}
        </div>
      )}

      <div className="ui-row">
        {preview ? (
          <Button writes disabled={working || busy} onClick={save}>
            이대로 넣기
          </Button>
        ) : (
          <Button disabled={working || busy || !text.trim()} onClick={read}>
            읽어보기
          </Button>
        )}
        <Button variant="quiet" disabled={busy} onClick={onCancel}>
          그만두기
        </Button>
      </div>
    </div>
  )
}


function ProgressTab({ paths, priority, working, onSetLevel, onSetTrack, onAddSkill }) {
  /* 전공(도구)과 교양(배경지식)을 나눠 놓는다.

     점수는 안 깎는다 — 교양이라고 수요를 낮다고 말하면 그건 거짓이다.
     **세는 건 그대로 두고 놓는 자리를 나눈다.** 한 줄에 세우면
     "Infrastructure 21%" 가 맨 위에 올라오는데, 그걸 보고 뭘 공부할지는
     알 수 없다. 전공은 "다음에 뭘 할까" 의 답이고 교양은 "틈날 때 읽을 것" 이다. */
  const major = priority.filter((item) => item.track !== "general")
  const general = priority.filter((item) => item.track === "general")

  return (
    <>
      <section className="card">
        <p className="card-label">경로별 진행</p>

        {paths.length === 0 ? (
          <p className="muted">아직 학습 경로가 없습니다.</p>
        ) : (
          <div className="progress-rows">
            {paths.map((path) => (
              <div className="progress-row" key={path.id}>
                <div className="progress-row-head">
                  <strong>{path.title}</strong>
                  <span className="muted">
                    {doneCount(path)} / {path.steps.length} 단계
                  </span>
                </div>
                <ProgressBar value={path.progress_percent} label={`${path.title} 진행률`} />
                <span className="progress-row-percent">{path.progress_percent}%</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <p className="card-label">전공 · 손에 익히는 도구 (우선순위 순)</p>

        {major.length === 0 ? (
          <p className="muted">전공으로 둔 스킬이 없습니다.</p>
        ) : (
          <div className="progress-rows">
            {major.map((item, index) => (
              <SkillRow
                key={item.skill}
                item={item}
                index={index}
                working={working}
                onSetLevel={onSetLevel}
                onSetTrack={onSetTrack}
              />
            ))}
          </div>
        )}

        <p className="muted form-hint">
          순서는 기회 수요 · 목표까지 남은 레벨 · 학습과 프로젝트 증거로 정합니다.
          레벨을 바꾸면 오늘 계획의 핵심 초점이 달라질 수 있어요.
        </p>

        <AddSkillForm working={working} onAdd={onAddSkill} />
      </section>

      {/* 교양 — 읽고 아는 것. 도구와 한 줄에 세우면 "다음에 뭘 할까" 의
          답이 안 나온다. 점수는 깎지 않았다, 자리만 나눴다. */}
      {general.length > 0 && (
        <section className="card">
          <p className="card-label">교양 · 읽고 아는 배경지식</p>

          <p className="muted opp-meta">
            수요는 같은 방식으로 셉니다 — 점수를 깎지 않았어요. 다만 이쪽은
            매일 붙잡는 것이 아니라 책 한 권 읽고 정리하는 쪽입니다.
          </p>

          <div className="progress-rows">
            {general.map((item, index) => (
              <SkillRow
                key={item.skill}
                item={item}
                index={index}
                working={working}
                onSetLevel={onSetLevel}
                onSetTrack={onSetTrack}
              />
            ))}
          </div>
        </section>
      )}
    </>
  )
}

export default LearningPage
