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
  StatusBadge
} from "./ui"
import { PROJECT_STATUS_LABELS, dateText, minutesText } from "../format"
import { externalHref } from "../safeUrl"
import "../Learning.css"
import "../Evidence.css"

/* 프로젝트 — 역량을 결과물로 만들고, 증거로 남긴다.

   전에는 진행률 칩뿐이었다. GitHub · 데모 · 결과를 적을 칸이 없는데
   "끝났지만 보여줄 것이 없습니다" 라고만 경고했고, 완료해도 증거화
   제안은 다른 화면(경험)에 가야 보였다.

   이제 카드마다 기록 칸을 두고, 100% 가 되는 순간 그 자리에서
   "무엇을 증명할 수 있는지" 와 다음 행동을 띄운다. */

const FILTERS = [
  { key: "active", label: "진행 중" },
  { key: "done", label: "완료" },
  { key: "all", label: "전체" }
]

const PROGRESS_STEPS = [0, 25, 50, 75, 100]

function isDone(project) {
  return project.status === "completed" || project.progress_percent >= 100
}

function dateKey(project) {
  const time = Date.parse(String(project.target_date || "").slice(0, 10))
  return Number.isNaN(time) ? Infinity : time
}

function ProjectEditor({ project, skills, working, onSave, onLinkSkill, onCancel }) {
  const [draft, setDraft] = useState({
    target_date: String(project.target_date || "").slice(0, 10),
    daily_minutes: project.daily_minutes || "",
    estimated_hours: project.estimated_hours || "",
    github_url: project.github_url || "",
    demo_url: project.demo_url || "",
    results: project.results || ""
  })
  const [skillId, setSkillId] = useState("")

  const unlinked = skills.filter(
    (skill) => !project.skills.some((linked) => linked.id === skill.id)
  )

  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  return (
    <div className="prj-editor">
      <div className="prj-editor-grid">
        <label className="learn-field">
          <span>목표 완료일</span>
          <input
            className="plan-input"
            type="date"
            value={draft.target_date}
            onChange={(event) => set("target_date", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>하루에 쓸 시간(분)</span>
          <input
            className="plan-input"
            type="number"
            min="0"
            value={draft.daily_minutes}
            onChange={(event) => set("daily_minutes", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>예상 총 시간(시간)</span>
          <input
            className="plan-input"
            type="number"
            min="0"
            value={draft.estimated_hours}
            onChange={(event) => set("estimated_hours", event.target.value)}
          />
        </label>

        <label className="learn-field prj-wide">
          <span>GitHub 링크</span>
          <input
            className="agent-input"
            placeholder="https://github.com/…"
            value={draft.github_url}
            onChange={(event) => set("github_url", event.target.value)}
          />
        </label>

        <label className="learn-field prj-wide">
          <span>데모 링크</span>
          <input
            className="agent-input"
            placeholder="https://…"
            value={draft.demo_url}
            onChange={(event) => set("demo_url", event.target.value)}
          />
        </label>

        <label className="learn-field prj-full">
          <span>결과 — 실제로 이룬 것 (수치가 있으면 함께)</span>
          <textarea
            className="learn-textarea"
            rows={3}
            value={draft.results}
            onChange={(event) => set("results", event.target.value)}
          />
        </label>
      </div>

      <div className="ui-row">
        <Button
          writes
          disabled={working}
          onClick={() =>
            onSave({
              target_date: draft.target_date,
              daily_minutes: Number(draft.daily_minutes) || 0,
              estimated_hours: Number(draft.estimated_hours) || 0,
              github_url: draft.github_url.trim(),
              demo_url: draft.demo_url.trim(),
              results: draft.results.trim()
            })
          }
        >
          저장
        </Button>
        <Button variant="quiet" onClick={onCancel}>
          취소
        </Button>
      </div>

      <div className="prj-skill-link">
        <label className="learn-field">
          <span>이 프로젝트가 쓰는 스킬 연결</span>
          <select
            className="path-select"
            value={skillId}
            onChange={(event) => setSkillId(event.target.value)}
          >
            <option value="">스킬 고르기</option>
            {unlinked.map((skill) => (
              <option key={skill.id} value={skill.id}>
                {skill.name}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="secondary"
          writes
          disabled={working || !skillId}
          onClick={() => {
            onLinkSkill(Number(skillId))
            setSkillId("")
          }}
        >
          연결
        </Button>
      </div>
    </div>
  )
}

function CompletionPanel({ evidence, working, onExperience, onPortfolio, onLater }) {
  const hasExperience = evidence.experience_id != null
  const hasPortfolio = evidence.portfolio_entry_id != null

  return (
    <div className="prj-done" role="status">
      <p className="prj-done-title">✓ 프로젝트를 완료했습니다</p>

      {evidence.proves.length > 0 ? (
        <>
          <p className="prj-done-text">이 프로젝트로 다음 역량의 증거를 만들 수 있습니다.</p>
          <ul className="prj-proves">
            {evidence.proves.map((name) => (
              <li key={name}>✓ {name}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className="prj-done-text">{evidence.message}</p>
      )}

      <div className="ui-row">
        {!hasExperience && (
          <Button writes disabled={working} onClick={onExperience}>
            경험으로 저장
          </Button>
        )}
        {!hasPortfolio && (
          <Button
            variant={hasExperience ? "primary" : "secondary"}
            writes
            disabled={working}
            onClick={onPortfolio}
          >
            포트폴리오 준비
          </Button>
        )}
        <Button variant="quiet" onClick={onLater}>
          나중에 하기
        </Button>
      </div>
    </div>
  )
}

function ProjectsPage({ onChanged }) {
  const [projects, setProjects] = useState([])
  const [evidence, setEvidence] = useState({})
  const [etas, setEtas] = useState({})
  const [skills, setSkills] = useState([])

  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [working, setWorking] = useState(false)

  const [filter, setFilter] = useState("active")
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: "", description: "", target_date: "" })
  const [editingId, setEditingId] = useState(null)
  const [dismissed, setDismissed] = useState([])

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)

      const list = await api.projects.list()

      const [suggestions, estimates, skillList] = await Promise.all([
        Promise.all(list.map((project) => api.projects.evidence(project.id))),
        // 예상일은 하루 시간과 총 시간을 둘 다 적었을 때만 계산된다.
        Promise.all(
          list.map((project) =>
            !isDone(project) && project.daily_minutes > 0 && project.estimated_hours > 0
              ? api.projects.eta(project.id).catch(() => null)
              : null
          )
        ),
        api.get("/skills")
      ])

      setProjects(list)
      setEvidence(Object.fromEntries(suggestions.map((item) => [item.project_id, item])))
      setEtas(Object.fromEntries(list.map((project, index) => [project.id, estimates[index]])))
      setSkills(skillList)
    } catch (failure) {
      console.error("Failed to load projects:", failure)
      setLoadError("프로젝트를 불러오지 못했습니다.")
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
      const result = await action()
      await load(true)
      onChanged?.()
      if (success) setNotice(typeof success === "function" ? success(result) : success)
      return true
    } catch (failure) {
      console.error("Project action failed:", failure)
      setError(failure?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  const openForm = () => {
    setShowForm(true)
    requestAnimationFrame(() => document.getElementById("new-project-name")?.focus())
  }

  const openEditor = (project) => {
    setFilter(isDone(project) ? "done" : "active")
    setEditingId(project.id)
    requestAnimationFrame(() =>
      document.getElementById(`project-${project.id}`)?.scrollIntoView({ block: "start" })
    )
  }

  const create = async () => {
    const name = form.name.trim()
    if (!name) return

    const ok = await run(
      () =>
        api.projects.create({
          name,
          description: form.description.trim(),
          target_date: form.target_date,
          status: "in_progress",
          career_related: true
        }),
      `'${name}' 프로젝트를 만들었어요. 스킬을 연결하면 무엇을 증명하는지 셀 수 있어요.`,
      "프로젝트를 만들지 못했습니다. 같은 이름이 이미 있을 수 있어요."
    )

    if (ok) {
      setForm({ name: "", description: "", target_date: "" })
      setShowForm(false)
    }
  }

  const setProgress = (project, percent) => {
    if (percent === 100) {
      setDismissed((current) => current.filter((id) => id !== project.id))
    }

    return run(
      () =>
        api.projects.update(project.id, {
          progress_percent: percent,
          status: percent >= 100 ? "completed" : percent === 0 ? "planned" : "in_progress"
        }),
      percent === 100
        ? `'${project.name}' 을(를) 완료했어요. 아래에서 증거로 남기세요.`
        : `진행률을 ${percent}% 로 바꿨어요.`,
      "진행률을 바꾸지 못했습니다."
    )
  }

  const saveRecord = async (project, fields) => {
    const ok = await run(
      () => api.projects.update(project.id, fields),
      "기록을 저장했어요.",
      "기록을 저장하지 못했습니다."
    )
    if (ok) setEditingId(null)
  }

  const linkSkill = (project, skillId) =>
    run(
      () => api.projects.linkSkill(project.id, skillId),
      "스킬을 연결했어요.",
      "스킬을 연결하지 못했습니다."
    )

  const toExperience = (project) =>
    run(
      () => api.projects.toExperience(project.id),
      (experience) =>
        `'${experience.title}' 을(를) 경험으로 저장했어요. 경험 화면에서 역할과 한 일을 채워 주세요.`,
      "경험으로 저장하지 못했습니다."
    )

  const toPortfolio = (project) =>
    run(
      async () => {
        const experienceId =
          evidence[project.id]?.experience_id ??
          (await api.projects.toExperience(project.id)).id
        return api.experiences.promoteToPortfolio(experienceId)
      },
      (entry) => `'${entry.title}' 포트폴리오 초안을 만들었어요. 경험 화면에서 다듬을 수 있어요.`,
      "포트폴리오를 준비하지 못했습니다."
    )

  if (loading) {
    return <LoadingState label="프로젝트를 불러오는 중…" />
  }

  if (loadError) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const unproven = projects.filter((project) => {
    const item = evidence[project.id]
    return isDone(project) && item && (item.experience_id == null || item.portfolio_entry_id == null)
  })

  const active = projects
    .filter((project) => !isDone(project))
    .sort((a, b) => dateKey(a) - dateKey(b) || b.progress_percent - a.progress_percent)

  let hero

  if (projects.length === 0) {
    hero = (
      <EmptyState
        title="아직 프로젝트가 없습니다."
        body="학습만으로는 증거가 남지 않아요. 지금 배우는 것으로 작은 것 하나를 만들어 보세요."
        actions={[
          { label: "새 프로젝트 만들기", onClick: openForm, primary: true, writes: true },
          { label: "학습 경로 보기", href: "#/learning" }
        ]}
      />
    )
  } else if (unproven.length > 0) {
    const project = unproven[0]
    const item = evidence[project.id]

    hero = (
      <NextActionCard
        eyebrow="완료한 프로젝트 · 아직 증거로 안 남음"
        icon="★"
        title={`${project.name} 을(를) 증거로 남기기`}
        detail={item.message}
        action={
          item.experience_id == null ? (
            <Button writes disabled={working} onClick={() => toExperience(project)}>
              경험으로 저장
            </Button>
          ) : (
            <Button writes disabled={working} onClick={() => toPortfolio(project)}>
              포트폴리오 준비
            </Button>
          )
        }
      />
    )
  } else if (active.length > 0) {
    const project = active[0]

    hero = (
      <NextActionCard
        eyebrow={`진행 중 · ${project.progress_percent}%`}
        icon="▲"
        title={`${project.name} 이어서 만들기`}
        detail={
          project.target_date
            ? `목표 완료일 ${dateText(project.target_date)}`
            : "목표 완료일이 없어요"
        }
        meta={
          project.daily_minutes > 0
            ? `오늘 계획이 이 프로젝트에 하루 ${minutesText(project.daily_minutes)}을 배정합니다.`
            : "하루에 쓸 시간을 적으면 오늘 계획에 들어가요."
        }
        action={
          <Button variant="secondary" onClick={() => openEditor(project)}>
            기록 열기
          </Button>
        }
      />
    )
  } else {
    hero = (
      <NextActionCard
        eyebrow="프로젝트"
        tone="ok"
        icon="✓"
        title="완료한 프로젝트를 모두 증거로 남겼어요"
        meta="다음 프로젝트는 지금 배우는 스킬로 작게 시작하세요."
        action={
          <Button variant="secondary" writes onClick={openForm}>
            새 프로젝트
          </Button>
        }
      />
    )
  }

  const shown = projects.filter((project) => {
    if (filter === "done") return isDone(project)
    if (filter === "active") return !isDone(project)
    return true
  })

  const counts = {
    active: projects.filter((project) => !isDone(project)).length,
    done: projects.filter(isDone).length,
    all: projects.length
  }

  return (
    <div className="projects-page learn evd">
      <section className="card learn-hero">
        <div className="evd-head">
          <div>
            <h1 className="learn-title">프로젝트</h1>
            <p className="learn-sub">역량을 실제 결과물로 만들고, 증거로 남깁니다.</p>
          </div>
          {!showForm && projects.length > 0 && (
            <Button variant="secondary" writes onClick={openForm}>
              + 새 프로젝트
            </Button>
          )}
        </div>

        {hero}

        {showForm && (
          <div className="prj-editor">
            <div className="prj-editor-grid">
              <label className="learn-field prj-wide">
                <span>프로젝트 이름</span>
                <input
                  id="new-project-name"
                  className="agent-input"
                  placeholder="예: AWS 배포 파이프라인"
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </label>
              <label className="learn-field prj-wide">
                <span>한 줄 설명</span>
                <input
                  className="agent-input"
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </label>
              <label className="learn-field">
                <span>목표 완료일</span>
                <input
                  className="plan-input"
                  type="date"
                  value={form.target_date}
                  onChange={(event) => setForm({ ...form, target_date: event.target.value })}
                />
              </label>
            </div>
            <div className="ui-row">
              <Button writes disabled={working || !form.name.trim()} onClick={create}>
                만들기
              </Button>
              <Button variant="quiet" onClick={() => setShowForm(false)}>
                취소
              </Button>
            </div>
          </div>
        )}
      </section>

      {projects.length > 0 && (
        <div className="learn-tabs" role="tablist" aria-label="프로젝트 거르기">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={filter === item.key}
              className={filter === item.key ? "chip chip-on" : "chip"}
              onClick={() => setFilter(item.key)}
            >
              {item.label} {counts[item.key]}
            </button>
          ))}
        </div>
      )}

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

      {projects.length > 0 && shown.length === 0 && (
        <section className="card">
          <EmptyState
            title="이 조건에 맞는 프로젝트가 없습니다."
            actions={[{ label: "전체 보기", onClick: () => setFilter("all") }]}
          />
        </section>
      )}

      {shown.map((project) => {
        const item = evidence[project.id]
        const eta = etas[project.id]
        const done = isDone(project)
        const editing = editingId === project.id
        const github = externalHref(project.github_url)
        const demo = externalHref(project.demo_url)

        return (
          <section className="card prj-card" id={`project-${project.id}`} key={project.id}>
            <div className="prj-head">
              <div className="prj-head-main">
                <strong className="prj-name">{project.name}</strong>
                {project.description && <p className="prj-desc">{project.description}</p>}
                {project.skills.length > 0 ? (
                  <div className="prj-skills">
                    {project.skills.map((skill) => (
                      <span className="lib-chip" key={skill.id}>
                        {skill.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="prj-warn">
                    연결된 스킬이 없어 무엇을 증명하는지 알 수 없어요
                  </span>
                )}
              </div>

              <StatusBadge tone={done ? "ok" : project.status === "paused" ? "warn" : "action"}>
                {PROJECT_STATUS_LABELS[project.status] ?? "상태 모름"}
              </StatusBadge>
            </div>

            <div className="prj-facts">
              <div className="prj-fact">
                <span className="prj-fact-key">진행률</span>
                <strong>{project.progress_percent}%</strong>
                <ProgressBar value={project.progress_percent} label={`${project.name} 진행률`} />
              </div>

              <div className="prj-fact">
                <span className="prj-fact-key">목표 완료일</span>
                <strong>{project.target_date ? dateText(project.target_date) : "없음"}</strong>
                {!done &&
                  (eta?.estimated_finish_date ? (
                    <span className="prj-fact-hint">
                      지금 속도면 {dateText(eta.estimated_finish_date)} (남은 {eta.remaining_hours}시간)
                    </span>
                  ) : (
                    <span className="prj-fact-hint">하루 시간과 총 시간을 적으면 예상일을 계산해요</span>
                  ))}
              </div>

              <div className="prj-fact prj-fact-wide">
                <span className="prj-fact-key">
                  증거 {item ? `${item.actions.length - item.remaining_count}/${item.actions.length}` : ""}
                </span>
                <div className="prj-checks">
                  {item?.actions.map((action) => (
                    <StatusBadge key={action.key} tone={action.done ? "ok" : "neutral"}>
                      {action.done ? "✓" : "○"} {action.label}
                    </StatusBadge>
                  ))}
                </div>
              </div>
            </div>

            {(github || demo) && (
              <div className="evidence-links evidence-links-inline">
                {github && (
                  <a href={github} target="_blank" rel="noopener noreferrer">
                    GitHub ↗
                  </a>
                )}
                {demo && (
                  <a href={demo} target="_blank" rel="noopener noreferrer">
                    데모 ↗
                  </a>
                )}
              </div>
            )}

            <div className="prj-progress-row" role="group" aria-label={`${project.name} 진행률 바꾸기`}>
              <span className="prj-fact-key">진행률 바꾸기</span>
              {PROGRESS_STEPS.map((value) => (
                <Button
                  key={value}
                  variant={project.progress_percent === value ? "primary" : "secondary"}
                  className="prj-step"
                  writes
                  aria-pressed={project.progress_percent === value}
                  disabled={working || project.progress_percent === value}
                  onClick={() => setProgress(project, value)}
                >
                  {value}%
                </Button>
              ))}
            </div>

            <div className="ui-row">
              <Button
                variant="secondary"
                aria-expanded={editing}
                onClick={() => setEditingId(editing ? null : project.id)}
              >
                {editing ? "기록 닫기" : "결과 · 링크 · 일정 기록"}
              </Button>
            </div>

            {editing && (
              <ProjectEditor
                project={project}
                skills={skills}
                working={working}
                onSave={(fields) => saveRecord(project, fields)}
                onLinkSkill={(skillId) => linkSkill(project, skillId)}
                onCancel={() => setEditingId(null)}
              />
            )}

            {done &&
              item &&
              (item.experience_id == null || item.portfolio_entry_id == null) &&
              !dismissed.includes(project.id) && (
                <CompletionPanel
                  evidence={item}
                  working={working}
                  onExperience={() => toExperience(project)}
                  onPortfolio={() => toPortfolio(project)}
                  onLater={() => setDismissed((current) => [...current, project.id])}
                />
              )}
          </section>
        )
      })}
    </div>
  )
}

export default ProjectsPage
