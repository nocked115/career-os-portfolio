import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import { externalHref } from "../safeUrl"
import CertificatesCard from "./CertificatesCard"
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  Notice,
  StatusBadge
} from "./ui"
import {
  EXPERIENCE_TYPES,
  PORTFOLIO_STATUS_LABELS,
  experienceTypeLabel
} from "../format"
import "../Learning.css"
import "../Evidence.css"

/* 경험 — 프로젝트와 활동을 다시 꺼내 쓸 수 있는 증거로.

   전에는 결과 · 수치 · 기술만 보였고, 경험을 새로 만들거나 고칠 곳이
   없었다. 지원서의 "경험 등록하기" 버튼이 이 화면으로 오는데 정작
   등록할 수가 없었다. 어느 지원서에 매칭해 뒀는지도 안 보였다.

   이제 카드마다 무엇을 · 상황 · 역할 · 한 일 · 결과 · 수치를 보여주고,
   비어 있으면 비었다고, 결과가 없으면 채우자고 말한다.
   Career OS 는 여기 적힌 내용으로만 자기소개서 구조와 이력서 문장을 만든다. */

// 결과물이 있는 작업이 아닌 것. 포트폴리오를 권하지 않는다.
const ACTIVITY_TYPES = ["activity"]

const DETAIL_FIELDS = [
  ["short_description", "무엇을 했나"],
  ["problem", "상황과 과제"],
  ["role", "내 역할"],
  ["actions", "한 일"],
  ["results", "결과"],
  ["metrics", "수치"]
]

const BLANK = {
  experience_type: "project",
  title: "",
  organization: "",
  start_date: "",
  end_date: "",
  short_description: "",
  problem: "",
  role: "",
  actions: "",
  results: "",
  metrics: "",
  technologies: "",
  github_url: "",
  blog_url: ""
}

function period(experience) {
  if (!experience.start_date) return ""
  const start = String(experience.start_date).slice(0, 7)
  const end = experience.end_date ? String(experience.end_date).slice(0, 7) : "진행 중"
  return `${start} ~ ${end}`
}

function ExperienceEditor({ experience, working, focusField, onSave, onCancel }) {
  const key = experience?.id ?? "new"

  const [draft, setDraft] = useState(() => {
    const base = { ...BLANK }
    if (experience) {
      for (const field of Object.keys(BLANK)) {
        base[field] = experience[field] ?? ""
      }
    }
    return base
  })

  useEffect(() => {
    if (focusField) {
      document.getElementById(`exp-${key}-${focusField}`)?.focus()
    }
  }, [focusField, key])

  const set = (field, value) => setDraft((current) => ({ ...current, [field]: value }))

  return (
    <div className="exp-editor">
      <div className="prj-editor-grid">
        <label className="learn-field">
          <span>종류</span>
          <select
            className="path-select"
            value={draft.experience_type}
            onChange={(event) => set("experience_type", event.target.value)}
          >
            {EXPERIENCE_TYPES.map((type) => (
              <option key={type.key} value={type.key}>
                {type.label}
              </option>
            ))}
          </select>
        </label>

        <label className="learn-field prj-wide">
          <span>제목</span>
          <input
            id={`exp-${key}-title`}
            className="agent-input"
            value={draft.title}
            onChange={(event) => set("title", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>기관 · 소속</span>
          <input
            className="agent-input"
            value={draft.organization}
            onChange={(event) => set("organization", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>시작</span>
          <input
            className="plan-input"
            type="date"
            value={String(draft.start_date || "").slice(0, 10)}
            onChange={(event) => set("start_date", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>끝</span>
          <input
            className="plan-input"
            type="date"
            value={String(draft.end_date || "").slice(0, 10)}
            onChange={(event) => set("end_date", event.target.value)}
          />
        </label>

        {DETAIL_FIELDS.map(([field, label]) => (
          <label className="learn-field prj-full" key={field}>
            <span>{label}</span>
            <textarea
              id={`exp-${key}-${field}`}
              className="learn-textarea"
              rows={field === "short_description" ? 2 : 3}
              value={draft[field]}
              onChange={(event) => set(field, event.target.value)}
            />
          </label>
        ))}

        <label className="learn-field prj-full">
          <span>사용 기술 (쉼표로 구분)</span>
          <input
            className="agent-input"
            value={draft.technologies}
            onChange={(event) => set("technologies", event.target.value)}
          />
        </label>

        <label className="learn-field prj-wide">
          <span>코드 링크</span>
          <input
            className="agent-input"
            placeholder="https://github.com/…"
            value={draft.github_url}
            onChange={(event) => set("github_url", event.target.value)}
          />
        </label>

        <label className="learn-field prj-wide">
          <span>글 링크</span>
          <input
            className="agent-input"
            placeholder="https://velog.io/…"
            value={draft.blog_url}
            onChange={(event) => set("blog_url", event.target.value)}
          />
        </label>
      </div>

      <p className="muted form-hint">
        실제로 한 일만 적어 주세요. Career OS 는 여기 적힌 내용으로만 자기소개서
        구조와 이력서 문장을 만들고, 없는 성과를 채우지 않습니다.
      </p>

      <div className="ui-row">
        <Button
          writes
          disabled={working || !draft.title.trim()}
          onClick={() =>
            onSave({
              ...draft,
              title: draft.title.trim(),
              start_date: draft.start_date || null,
              end_date: draft.end_date || null
            })
          }
        >
          저장
        </Button>
        <Button variant="quiet" onClick={onCancel}>
          취소
        </Button>
      </div>
    </div>
  )
}

function ExperienceCard({
  experience,
  usage,
  hasPortfolio,
  isActivity,
  working,
  editing,
  focusField,
  onEdit,
  onSave,
  onCancel,
  onPortfolio
}) {
  const filled = DETAIL_FIELDS.filter(([field]) => (experience[field] || "").trim())
  const missing = usage?.missing ?? []
  const applications = usage?.applications ?? []
  const technologies = (experience.technologies || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
  const code = externalHref(experience.github_url)
  const blog = externalHref(experience.blog_url)
  const meta = [experienceTypeLabel(experience.experience_type), experience.organization, period(experience)]
    .filter(Boolean)
    .join(" · ")

  return (
    <article className="exp-card" id={`experience-${experience.id}`}>
      <div className="prj-head">
        <div className="prj-head-main">
          <strong className="prj-name">{experience.title}</strong>
          <span className="prj-desc">{meta}</span>
        </div>

        <div className="exp-badges">
          {!isActivity && (
            <StatusBadge tone={hasPortfolio ? "ok" : "neutral"}>
              {hasPortfolio ? "포트폴리오 있음" : "포트폴리오 없음"}
            </StatusBadge>
          )}
          <StatusBadge tone={applications.length ? "action" : "neutral"}>
            {applications.length ? `지원서 ${applications.length}곳에 매칭` : "아직 지원서에 안 씀"}
          </StatusBadge>
        </div>
      </div>

      {editing ? (
        <ExperienceEditor
          experience={experience}
          working={working}
          focusField={focusField}
          onSave={onSave}
          onCancel={onCancel}
        />
      ) : (
        <>
          {filled.length > 0 && (
            <dl className="exp-fields">
              {filled.map(([field, label]) => (
                <div key={field}>
                  <dt>{label}</dt>
                  <dd>{experience[field]}</dd>
                </div>
              ))}
            </dl>
          )}

          {technologies.length > 0 && (
            <div className="prj-skills">
              {technologies.map((item) => (
                <span className="lib-chip" key={item}>
                  {item}
                </span>
              ))}
            </div>
          )}

          {(usage?.project || applications.length > 0 || code || blog) && (
            <ul className="exp-links">
              {usage?.project && (
                <li>
                  <span>연결된 프로젝트</span>
                  <a href="#/projects">{usage.project.name}</a>
                </li>
              )}
              {applications.map((application) => (
                <li key={application.application_id}>
                  <span>매칭한 지원서</span>
                  <a href={`#/applications/${application.application_id}`}>
                    {application.title}
                    {application.organization && ` · ${application.organization}`}
                  </a>
                </li>
              ))}
              {code && (
                <li>
                  <span>코드</span>
                  <a href={code} target="_blank" rel="noopener noreferrer">
                    열기 ↗
                  </a>
                </li>
              )}
              {blog && (
                <li>
                  <span>글</span>
                  <a href={blog} target="_blank" rel="noopener noreferrer">
                    열기 ↗
                  </a>
                </li>
              )}
            </ul>
          )}

          {!isActivity && !(experience.results || "").trim() && (
            <div className="exp-nudge" role="note">
              <span>
                아직 결과가 비어 있습니다. 지원서에 쓰기 전에 결과를 보완하는 것을 권합니다.
              </span>
              <Button variant="secondary" writes onClick={() => onEdit("results")}>
                결과 기록하기
              </Button>
            </div>
          )}

          {missing.length > 0 && <p className="exp-missing">비어 있는 칸 · {missing.join(" · ")}</p>}

          <div className="ui-row">
            <Button variant="secondary" writes onClick={() => onEdit(null)}>
              고치기
            </Button>
            {!isActivity && !hasPortfolio && (
              <Button variant="quiet" writes disabled={working} onClick={onPortfolio}>
                포트폴리오로 만들기
              </Button>
            )}
          </div>
        </>
      )}
    </article>
  )
}

function ProofPage({ onChanged, focus }) {
  const rootRef = useRef(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [editingLinks, setEditingLinks] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)
      setData(await api.fetchProof())
    } catch (failure) {
      console.error("Failed to load proof data:", failure)
      setLoadError("경험 데이터를 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // action 은 알림 문장({ text, tone }) 또는 문자열을 돌려준다.
  const run = async (action, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const message = await action()
      await load(true)
      onChanged?.()
      if (message) setNotice(typeof message === "string" ? { text: message, tone: "ok" } : message)
      return true
    } catch (failure) {
      console.error("Proof action failed:", failure)
      setError(failure?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  /* 천체나 다른 화면에서 들어온 경우 가리킨 자리로 데려간다. */
  useEffect(() => {
    if (!focus || !data) return

    rootRef.current
      ?.querySelector(`[data-section="${focus}"]`)
      ?.scrollIntoView({ block: "start" })
  }, [focus, data])

  const openEditor = (id, field = null) => {
    setEditing({ id, field })
    requestAnimationFrame(() =>
      document
        .getElementById(id === "new" ? "experience-new" : `experience-${id}`)
        ?.scrollIntoView({ block: "start" })
    )
  }

  const saveExperience = async (id, fields) => {
    const ok = await run(async () => {
      if (id === "new") {
        const created = await api.experiences.create(fields)
        return `'${created.title}' 을(를) 경험으로 등록했어요.`
      }
      await api.experiences.update(id, fields)
      return "경험을 저장했어요."
    }, "경험을 저장하지 못했습니다.")

    if (ok) setEditing(null)
  }

  const toExperience = (project) =>
    run(async () => {
      const experience = await api.projects.toExperience(project.id)
      return `'${experience.title}' 을(를) 경험으로 저장했어요. 역할과 한 일을 채워 주세요.`
    }, "경험으로 저장하지 못했습니다.")

  const toPortfolio = (experience) =>
    run(async () => {
      const entry = await api.experiences.promoteToPortfolio(experience.id)
      return `'${entry.title}' 포트폴리오 초안을 만들었어요.`
    }, "포트폴리오를 만들지 못했습니다.")

  const makeBullet = (entry) =>
    run(async () => {
      const result = await api.portfolio.resumeBullet(entry.id)

      if (result.saved && !result.missing?.length) return "이력서 문장을 만들었어요."

      return {
        tone: "warn",
        text: result.saved
          ? `이력서 문장을 만들었지만 약해요 — 비어 있음: ${result.missing_labels.join(" · ")}`
          : result.message
      }
    }, "이력서 문장을 만들지 못했습니다.")

  if (loading) {
    return <LoadingState label="경험을 불러오는 중…" />
  }

  if (!data) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const { projects, evidence, experiences, portfolio, stars, links, usage } = data

  const usageById = Object.fromEntries((usage ?? []).map((row) => [row.experience_id, row]))
  const hasPortfolio = (experience) =>
    portfolio.some((entry) => entry.experience_id === experience.id)

  // 데이터를 꺼낸 뒤에 나눈다. 위에서 나누면 선언 전 접근으로 화면이 죽는다.
  const works = experiences.filter((item) => !ACTIVITY_TYPES.includes(item.experience_type))
  const activities = experiences.filter((item) => ACTIVITY_TYPES.includes(item.experience_type))

  const byProject = Object.fromEntries(evidence.map((item) => [item.project_id, item]))

  const readyToProve = projects.filter((project) => {
    const item = byProject[project.id]
    return item?.is_complete && item.experience_id === null
  })

  const withoutResults = works.filter((item) => !(item.results || "").trim())
  const withoutPortfolio = works.filter((item) => !hasPortfolio(item))

  let hero

  if (experiences.length === 0 && readyToProve.length === 0) {
    hero = (
      <EmptyState
        title="아직 저장된 경험이 없습니다."
        body="해 본 프로젝트 · 연구 · 활동을 적어 두면 자기소개서를 쓸 때마다 처음부터 떠올리지 않아도 됩니다."
        actions={[
          { label: "경험 등록하기", onClick: () => openEditor("new"), primary: true, writes: true },
          { label: "프로젝트에서 가져오기", href: "#/projects" }
        ]}
      />
    )
  } else if (readyToProve.length > 0) {
    const project = readyToProve[0]

    hero = (
      <NextActionCard
        eyebrow="완료한 프로젝트 · 아직 경험으로 안 남음"
        icon="★"
        title={`${project.name} 을(를) 경험으로 저장`}
        detail={byProject[project.id].message}
        action={
          <Button writes disabled={working} onClick={() => toExperience(project)}>
            경험으로 저장
          </Button>
        }
      />
    )
  } else if (withoutResults.length > 0) {
    const experience = withoutResults[0]

    hero = (
      <NextActionCard
        eyebrow={`결과가 빈 경험 ${withoutResults.length}개`}
        icon="!"
        title={`${experience.title} 결과 기록하기`}
        detail="결과가 없으면 자기소개서와 이력서 문장이 약해집니다. 수치가 있으면 함께 적어 주세요."
        action={
          <Button writes onClick={() => openEditor(experience.id, "results")}>
            결과 기록하기
          </Button>
        }
      />
    )
  } else if (withoutPortfolio.length > 0) {
    const experience = withoutPortfolio[0]

    hero = (
      <NextActionCard
        eyebrow={`포트폴리오가 없는 경험 ${withoutPortfolio.length}개`}
        icon="▣"
        title={`${experience.title} 포트폴리오로 만들기`}
        detail="저장된 내용을 그대로 옮겨 초안을 만듭니다. 새로 지어내지 않습니다."
        action={
          <Button writes disabled={working} onClick={() => toPortfolio(experience)}>
            포트폴리오로 만들기
          </Button>
        }
      />
    )
  } else {
    hero = (
      <NextActionCard
        eyebrow="경험"
        tone="ok"
        icon="✓"
        title="결과와 포트폴리오까지 모두 정리돼 있어요"
        meta="지원서에서 이 경험들을 추천 경험으로 꺼내 쓸 수 있어요."
      />
    )
  }

  return (
    <div className="proof-page learn evd" ref={rootRef}>
      <section className="card learn-hero">
        <div className="evd-head">
          <div>
            <h1 className="learn-title">경험</h1>
            <p className="learn-sub">프로젝트와 활동을 다시 꺼내 쓸 수 있는 증거로 정리합니다.</p>
          </div>

          <div className="evidence-links">
            {externalHref(links.github_url) && (
              <a href={externalHref(links.github_url)} target="_blank" rel="noopener noreferrer">
                GitHub ↗
              </a>
            )}
            {externalHref(links.blog_url) && (
              <a href={externalHref(links.blog_url)} target="_blank" rel="noopener noreferrer">
                Velog ↗
              </a>
            )}
            <Button variant="quiet" aria-expanded={editingLinks} onClick={() => setEditingLinks(!editingLinks)}>
              {editingLinks ? "닫기" : "링크 편집"}
            </Button>
          </div>
        </div>

        {editingLinks && (
          <form
            className="evidence-link-form"
            onSubmit={(event) => {
              event.preventDefault()
              const form = new FormData(event.currentTarget)
              run(async () => {
                await api.profile.update({
                  github_url: form.get("github_url"),
                  blog_url: form.get("blog_url")
                })
                setEditingLinks(false)
                return "링크를 저장했어요."
              }, "링크를 저장하지 못했습니다.")
            }}
          >
            <label>
              GitHub
              <input name="github_url" defaultValue={links.github_url} placeholder="https://github.com/…" />
            </label>
            <label>
              Velog
              <input name="blog_url" defaultValue={links.blog_url} placeholder="https://velog.io/@…" />
            </label>
            <Button type="submit" writes disabled={working}>
              저장
            </Button>
          </form>
        )}

        <div className="star-row">
          <div className="star-total">
            <strong>{stars.total}</strong>
            <span>★ 증거</span>
          </div>

          <div className="star-breakdown">
            {stars.breakdown.map((item) => (
              <span key={item.key}>
                {item.label} <strong>{item.count}</strong>
              </span>
            ))}
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
        <Notice tone={notice.tone} onClose={() => setNotice(null)}>
          {notice.text}
        </Notice>
      )}

      <CertificatesCard />

      {readyToProve.length > 0 && (
        <section className="card" data-section="projects">
          <p className="card-label">경험으로 남길 수 있는 프로젝트</p>

          {readyToProve.map((project) => {
            const item = byProject[project.id]

            return (
              <div className="prove-item" key={project.id}>
                <div className="prove-head">
                  <div>
                    <strong>{project.name}</strong>
                    <p className="muted opp-meta">{item.message}</p>
                  </div>
                </div>

                <div className="prj-checks">
                  {item.actions.map((action) => (
                    <StatusBadge key={action.key} tone={action.done ? "ok" : "neutral"}>
                      {action.done ? "✓" : "○"} {action.label}
                    </StatusBadge>
                  ))}
                </div>

                <div className="ui-row">
                  <Button writes disabled={working} onClick={() => toExperience(project)}>
                    경험으로 저장
                  </Button>
                  <a className="ui-btn ui-btn-secondary" href="#/projects">
                    결과 · 링크 기록하러 가기
                  </a>
                </div>
              </div>
            )
          })}
        </section>
      )}

      <section className="card" data-section="experience">
        <div className="evd-head">
          <p className="card-label">프로젝트 · 연구 · 대회</p>
          {editing?.id !== "new" && (
            <Button variant="secondary" writes onClick={() => openEditor("new")}>
              + 경험 등록
            </Button>
          )}
        </div>

        {editing?.id === "new" && (
          <div className="exp-card" id="experience-new">
            <p className="prj-name">새 경험</p>
            <ExperienceEditor
              working={working}
              focusField="title"
              onSave={(fields) => saveExperience("new", fields)}
              onCancel={() => setEditing(null)}
            />
          </div>
        )}

        {works.length === 0 ? (
          <p className="muted">아직 프로젝트 · 연구 경험이 없습니다. 위에서 등록하거나 완료한 프로젝트를 옮기세요.</p>
        ) : (
          <div className="exp-list">
            {works.map((experience) => (
              <ExperienceCard
                key={experience.id}
                experience={experience}
                usage={usageById[experience.id]}
                hasPortfolio={hasPortfolio(experience)}
                isActivity={false}
                working={working}
                editing={editing?.id === experience.id}
                focusField={editing?.id === experience.id ? editing.field : null}
                onEdit={(field) => openEditor(experience.id, field)}
                onSave={(fields) => saveExperience(experience.id, fields)}
                onCancel={() => setEditing(null)}
                onPortfolio={() => toPortfolio(experience)}
              />
            ))}
          </div>
        )}
      </section>

      {/* 활동은 결과물이 있는 작업이 아니다. 포트폴리오를 권하지 않는다. */}
      {activities.length > 0 && (
        <section className="card" data-section="activities">
          <p className="card-label">활동</p>
          <p className="muted opp-meta">결과물은 없지만 자기소개서 · 면접에서 꺼내 쓸 경험입니다.</p>

          <div className="exp-list">
            {activities.map((experience) => (
              <ExperienceCard
                key={experience.id}
                experience={experience}
                usage={usageById[experience.id]}
                hasPortfolio={false}
                isActivity
                working={working}
                editing={editing?.id === experience.id}
                focusField={editing?.id === experience.id ? editing.field : null}
                onEdit={(field) => openEditor(experience.id, field)}
                onSave={(fields) => saveExperience(experience.id, fields)}
                onCancel={() => setEditing(null)}
                onPortfolio={() => {}}
              />
            ))}
          </div>
        </section>
      )}

      <section className="card" data-section="portfolio">
        <p className="card-label">포트폴리오</p>

        {portfolio.length === 0 ? (
          <p className="muted">아직 포트폴리오 항목이 없습니다. 경험 카드에서 포트폴리오로 만들 수 있어요.</p>
        ) : (
          portfolio.map((entry) => (
            <div className="prove-item" key={entry.id}>
              <div className="prove-head">
                <div>
                  <strong>{entry.title}</strong>
                  <p className="muted opp-meta">{PORTFOLIO_STATUS_LABELS[entry.status] ?? "상태 모름"}</p>
                </div>
              </div>

              {entry.resume_bullet ? (
                <p className="resume-bullet">{entry.resume_bullet}</p>
              ) : (
                <p className="muted opp-meta">이력서 문장이 아직 없습니다. 저장된 내용에서만 만듭니다.</p>
              )}

              <div className="ui-row">
                <Button variant="secondary" writes disabled={working} onClick={() => makeBullet(entry)}>
                  {entry.resume_bullet ? "이력서 문장 다시 만들기" : "이력서 문장 만들기"}
                </Button>
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  )
}

export default ProofPage
