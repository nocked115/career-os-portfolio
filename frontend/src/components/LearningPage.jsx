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

                  {isOpen && (
                    <div className="step-list">
                      {path.steps.length === 0 ? (
                        <p className="muted">아직 단계가 없습니다. 아래에서 첫 단계를 넣으세요.</p>
                      ) : (
                        path.steps.map((step) => (
                          <button
                            className={`step-item step-${step.status}`}
                            key={step.id}
                            onClick={() => onOpenSession(step.id)}
                          >
                            <span className="step-position">
                              {step.status === "completed"
                                ? "✓"
                                : String(step.position + 1).padStart(2, "0")}
                            </span>
                            <span className="step-title">{step.title}</span>
                            <span className="step-status">{stepStatusLabel(step.status)}</span>
                            <span className="step-percent">
                              {step.estimated_minutes > 0
                                ? minutesText(step.estimated_minutes)
                                : "시간 미정"}
                            </span>
                          </button>
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
            {written ? "설명 · 목표일 고치기" : "설명 · 목표일 적기"}
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

function ProgressTab({ paths, priority, working, onSetLevel, onAddSkill }) {
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
        <p className="card-label">스킬별 수요 · 레벨 (우선순위 순)</p>

        {priority.length === 0 ? (
          <p className="muted">등록된 스킬이 없습니다.</p>
        ) : (
          <div className="progress-rows">
            {priority.map((item, index) => (
              <div className="progress-row" key={item.skill}>
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
                </div>

                <ProgressBar value={item.learning_progress} label={`${item.skill} 학습 진행`} />
                <span className="progress-row-percent">{item.learning_progress}%</span>
              </div>
            ))}
          </div>
        )}

        <p className="muted form-hint">
          순서는 기회 수요 · 목표까지 남은 레벨 · 학습과 프로젝트 증거로 정합니다.
          레벨을 바꾸면 오늘 계획의 핵심 초점이 달라질 수 있어요.
        </p>

        <AddSkillForm working={working} onAdd={onAddSkill} />
      </section>
    </>
  )
}

export default LearningPage
