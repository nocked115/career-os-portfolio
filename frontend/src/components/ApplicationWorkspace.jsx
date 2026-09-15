import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import CoverLetterPanel from "./CoverLetterPanel"
import { externalHref } from "../safeUrl"
import {
  MAIN_STEPS,
  ddayText,
  ddayTone,
  deadlineText,
  errorText,
  initialOf,
  savedDate,
  statusLabel,
  tileTone
} from "./applicationLabels"

/* Application Workspace

   순서가 곧 우선순위다.
     지원서 요약 → 다음 행동 → 자기소개서 → 추천 경험 → JD 분석 → 분석의 한계

   넓은 화면에서는 왼쪽에 근거(JD · 경험 · 한계), 오른쪽에 작성.
   좁은 화면에서는 작성이 분석보다 먼저 온다 — 지원서를 여는 이유는
   대부분 쓰기 위해서다. */

const RESULT = ["accepted", "rejected"]

const MISSING = {
  deadline: "마감일이 없어 D-day 를 셀 수 없어요.",
  description: "공고 본문이 비어 있어 요구 역량을 뽑을 수 없어요.",
  questions: "자기소개서 문항이 아직 없어요."
}

const EXPERIENCE_FIELDS = [
  ["problem", "상황과 과제"],
  ["role", "내 역할"],
  ["actions", "한 일"],
  ["results", "결과"],
  ["metrics", "수치"]
]

const ICONS = {
  write: "✎",
  revise: "✎",
  add_questions: "+",
  move: "→",
  submit: "↗",
  overdue: "!",
  wait: "…",
  interview: "◎"
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
}

function Stepper({ card, working, onMove }) {
  if (card.status === "withdrawn") {
    return (
      <p className="ws2-withdrawn">
        철회한 지원서입니다. 기록으로 남겨 둡니다.
      </p>
    )
  }

  const currentKey = RESULT.includes(card.status) ? "result" : card.status
  const currentIndex = MAIN_STEPS.findIndex((step) => step.key === currentKey)

  return (
    <ol className="ws2-steps" aria-label="지원 단계">
      {MAIN_STEPS.map((step, index) => {
        const clickable = card.allowed.includes(step.key)

        let state = "later"
        if (index < currentIndex) state = "done"
        if (index === currentIndex) state = "current"
        if (clickable) state = "next"

        const label =
          step.key === "result" && RESULT.includes(card.status)
            ? statusLabel(card.status)
            : step.label

        return (
          <li
            key={step.key}
            className={`ws2-step step-${state}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            {clickable ? (
              <button
                className="ws2-dot"
                disabled={working}
                onClick={() => onMove(step.key)}
                aria-label={`'${step.label}'(으)로 옮기기`}
              >
                →
              </button>
            ) : (
              <span className="ws2-dot" aria-hidden="true">
                {state === "done" ? "✓" : ""}
              </span>
            )}
            <span className="ws2-step-label">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

function NextStep({ card, working, sourceHref, onWrite, onAddQuestions, onMove }) {
  const next = card.next_action

  if (!next) {
    return (
      <div className="ws2-next-row">
        <span className="apl-next-icon" aria-hidden="true">
          ✓
        </span>
        <div className="apl-next-body">
          <span className="apl-next-key">다음 행동</span>
          <strong>끝난 지원서입니다</strong>
          <span className="apl-next-meta">결과는 기록으로 남습니다.</span>
        </div>
      </div>
    )
  }

  let action = null

  if (next.kind === "write" || next.kind === "revise") {
    action = (
      <button className="apl-cta" onClick={() => onWrite(next.question_id)}>
        작성하러 가기
      </button>
    )
  } else if (next.kind === "add_questions") {
    action = (
      <button className="apl-cta" onClick={onAddQuestions}>
        문항 추가하기
      </button>
    )
  } else if (next.kind === "move") {
    action = (
      <button
        className="apl-cta"
        disabled={working}
        onClick={() => onMove(next.target_status)}
      >
        '{statusLabel(next.target_status)}'(으)로 옮기기
      </button>
    )
  } else if (next.kind === "submit") {
    action = (
      <>
        {sourceHref && (
          <a
            className="apl-cta"
            href={sourceHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            공고에서 제출하기 ↗
          </a>
        )}
        <button
          className="chip"
          disabled={working}
          onClick={() => onMove("applied")}
        >
          제출했어요 → 지원함
        </button>
      </>
    )
  }

  return (
    <div className="ws2-next-row">
      <span className={`apl-next-icon kind-${next.kind}`} aria-hidden="true">
        {ICONS[next.kind] ?? "→"}
      </span>
      <div className="apl-next-body">
        <span className="apl-next-key">다음 행동</span>
        <strong>{next.label}</strong>
        {next.detail && <span className="apl-next-meta">{next.detail}</span>}
      </div>
      {action && <div className="ws2-next-actions">{action}</div>}
    </div>
  )
}

function EmptyState({ title, body, actions }) {
  return (
    <div className="ws2-empty">
      <strong>{title}</strong>
      {body && <span>{body}</span>}
      <div className="ws2-empty-actions">
        {actions.map((action) => (
          <a
            key={action.label}
            className={action.primary ? "apl-cta" : "chip"}
            href={action.href}
          >
            {action.label}
          </a>
        ))}
      </div>
    </div>
  )
}

function ApplicationWorkspace({ applicationId, onBack, onChanged }) {
  const [card, setCard] = useState(null)
  const [urgentDays, setUrgentDays] = useState(7)
  const [analysis, setAnalysis] = useState(null)
  const [experiences, setExperiences] = useState([])

  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [openExperience, setOpenExperience] = useState(null)
  const [confirmWithdraw, setConfirmWithdraw] = useState(false)
  const [deadlineInput, setDeadlineInput] = useState("")
  const [focus, setFocus] = useState(null)
  const [dirty, setDirty] = useState(false)

  const letterRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setError(null)

      const [board, analysisData, experienceList] = await Promise.all([
        api.applications.board(),
        api.applications.analysis(applicationId),
        api.experiences.list()
      ])

      setCard(
        board.applications.find((item) => item.id === Number(applicationId)) ??
          null
      )
      setUrgentDays(board.urgent_days)
      setAnalysis(analysisData)
      setExperiences(experienceList)
    } catch (loadError) {
      console.error("Failed to load workspace:", loadError)
      setError("지원서를 불러오지 못했습니다. 목록으로 돌아가 다시 열어 주세요.")
    } finally {
      setLoading(false)
    }
  }, [applicationId])

  useEffect(() => {
    load()
  }, [load])

  const act = async (action, success, failure) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      await action()
      await load()
      onChanged?.()
      if (success) setNotice(success)
    } catch (actionError) {
      console.error("Workspace action failed:", actionError)
      setError(errorText(actionError, failure))
    } finally {
      setWorking(false)
      setConfirmWithdraw(false)
    }
  }

  const move = (status) =>
    act(
      () => api.applications.move(card.id, status),
      `상태를 '${statusLabel(status)}'(으)로 바꿨습니다.`,
      "상태를 바꾸지 못했습니다."
    )

  const saveDeadline = () =>
    act(
      () =>
        api.applications.update(card.id, {
          deadline: `${deadlineInput}T23:59:00`
        }),
      "마감일을 등록했습니다.",
      "마감일을 저장하지 못했습니다."
    )

  const autoMatch = () =>
    act(
      async () => {
        const result = await api.applications.autoMatch(card.id)
        if (result.matched === 0) throw new Error("no match")
      },
      "추천 경험을 이 지원서의 매칭으로 저장했습니다.",
      "저장할 추천 경험이 없습니다."
    )

  const goToLetter = (questionId = null, add = false) => {
    setFocus({ questionId, add, nonce: Date.now() })
    letterRef.current?.scrollIntoView({
      behavior: prefersReducedMotion() ? "auto" : "smooth",
      block: "start"
    })
  }

  const back = () => {
    if (
      dirty &&
      !window.confirm("저장하지 않은 자기소개서가 있어요. 그래도 목록으로 갈까요?")
    ) {
      return
    }

    onBack()
  }

  if (loading) {
    return (
      <div className="card">
        <p className="muted">지원서를 불러오는 중…</p>
      </div>
    )
  }

  if (!card) {
    return (
      <div className="card">
        <p className="agent-error">
          {error ?? "이 지원서를 찾지 못했습니다. 삭제되었을 수 있어요."}
        </p>
        <button className="chip" onClick={onBack}>
          ← 지원서 목록
        </button>
      </div>
    )
  }

  const name = card.organization || card.title
  const sourceHref = externalHref(card.source_url)
  const forward = card.allowed.filter((status) => status !== "withdrawn")
  const { match } = card
  const recommended = analysis?.recommended_experiences ?? []

  const haveSkills = match.skills.filter((skill) => skill.strength !== "gap")
  const gapSkills = match.skills.filter((skill) => skill.strength === "gap")

  return (
    <div className="workspace ws2">
      <button className="ghost-button back-link ws2-back" onClick={back}>
        ← 지원서 목록
      </button>

      {/* ---------- 지원서 요약 · 상태 ---------- */}
      <section className="card ws2-summary">
        <div className="ws2-head">
          <span
            className={`apl-tile apl-tile-lg tile-${tileTone(name)}`}
            aria-hidden="true"
          >
            {initialOf(name)}
          </span>

          <div className="ws2-head-main">
            <p className="card-label">지원서</p>
            <h2 className="ws2-title">{card.title}</h2>
            <p className="ws2-org">
              {card.organization || "기관 미상"}
              {card.target === "legacy_job" &&
                " · 예전 방식(Job)으로 만든 지원서 — 마감일은 여기서 따로 등록하세요"}
            </p>
          </div>

          <div className="ws2-head-side">
            <span className={`apl-dday dday-${ddayTone(card.days_left, urgentDays)}`}>
              {ddayText(card.days_left)}
            </span>
            <span className="ws2-deadline">
              {card.deadline
                ? `${deadlineText(card.deadline)} 마감${
                    card.deadline_source === "opportunity" ? " · 공고 기준" : ""
                  }`
                : "마감일 미등록"}
            </span>
            <span className="ws2-updated">마지막 수정 {savedDate(card.updated_at)}</span>
            {sourceHref && (
              <a
                className="apl-link"
                href={sourceHref}
                target="_blank"
                rel="noopener noreferrer"
              >
                공고 원문 ↗
              </a>
            )}
          </div>
        </div>

        <Stepper card={card} working={working} onMove={move} />

        {!card.is_terminal && (
          <div className="ws2-moves">
            <span className="ws2-moves-key">
              지금 <strong>{statusLabel(card.status)}</strong> · 다음 단계
            </span>

            {forward.map((status) => (
              <button
                key={status}
                className={status === "rejected" ? "chip" : "chip ws2-move-primary"}
                disabled={working}
                onClick={() => move(status)}
              >
                → {statusLabel(status)}
              </button>
            ))}

            {card.allowed.includes("withdrawn") &&
              (confirmWithdraw ? (
                <span className="ws2-confirm">
                  <button
                    className="chip ws2-danger"
                    disabled={working}
                    onClick={() => move("withdrawn")}
                  >
                    정말 철회하기
                  </button>
                  <button className="chip" onClick={() => setConfirmWithdraw(false)}>
                    취소
                  </button>
                </span>
              ) : (
                <button
                  className="ghost-button ws2-withdraw"
                  onClick={() => setConfirmWithdraw(true)}
                >
                  지원 철회
                </button>
              ))}
          </div>
        )}

        {error && <p className="agent-error">{error}</p>}
        {notice && <p className="opp-notice">{notice}</p>}
      </section>

      {/* ---------- 다음 행동 ---------- */}
      <section className="card ws2-next">
        <NextStep
          card={card}
          working={working}
          sourceHref={sourceHref}
          onWrite={(questionId) => goToLetter(questionId)}
          onAddQuestions={() => goToLetter(null, true)}
          onMove={move}
        />

        {card.missing.length > 0 && !card.is_terminal && (
          <ul className="ws2-missing">
            {card.missing.map((key) => (
              <li key={key}>
                <span className="ws2-missing-mark" aria-hidden="true">
                  !
                </span>
                <span>{MISSING[key]}</span>

                {key === "deadline" && (
                  <span className="ws2-inline-form">
                    <input
                      className="plan-input"
                      type="date"
                      aria-label="마감일"
                      value={deadlineInput}
                      onChange={(event) => setDeadlineInput(event.target.value)}
                    />
                    <button
                      className="chip"
                      disabled={working || !deadlineInput}
                      onClick={saveDeadline}
                    >
                      등록
                    </button>
                  </span>
                )}

                {key === "description" && (
                  <a className="apl-link" href="#/opportunities">
                    공고 본문 채우기 →
                  </a>
                )}

                {key === "questions" && (
                  <button className="chip" onClick={() => goToLetter(null, true)}>
                    문항 추가하기
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------- 자기소개서 ---------- */}
      <div className="ws2-letter" ref={letterRef}>
        <CoverLetterPanel
          applicationId={card.id}
          initialQuestionId={card.next_action?.question_id ?? null}
          focus={focus}
          sourceUrl={card.source_url}
          onSaved={load}
          onDirtyChange={setDirty}
        />
      </div>

      {/* ---------- 추천 경험 ---------- */}
      <section className="card ws2-exp">
        <div className="ws2-section-head">
          <p className="card-label">추천 경험</p>
          {recommended.length > 0 && (
            <button className="ghost-button" disabled={working} onClick={autoMatch}>
              이 지원서에 매칭 저장
            </button>
          )}
        </div>

        {recommended.length === 0 ? (
          <EmptyState
            title="요구 역량을 덮는 경험이 없습니다."
            body="관련 없는 경험을 억지로 추천하지 않아요. 해 본 일이 있다면 Experience Bank 에 먼저 적어 주세요."
            actions={[
              { href: "#/experience", label: "경험 등록하기", primary: true },
              { href: "#/experience", label: "프로젝트에서 경험 가져오기" },
              { href: "#/projects", label: "관련 프로젝트 보기" }
            ]}
          />
        ) : (
          <>
            <ul className="ws2-exp-list">
              {recommended.map((item) => {
                const open = openExperience === item.experience_id
                const full = experiences.find(
                  (experience) => experience.id === item.experience_id
                )
                const filled = full
                  ? EXPERIENCE_FIELDS.filter(([key]) => (full[key] || "").trim())
                  : []

                return (
                  <li
                    key={item.experience_id}
                    className={open ? "ws2-exp-item is-open" : "ws2-exp-item"}
                  >
                    <button
                      className="ws2-exp-toggle"
                      aria-expanded={open}
                      onClick={() =>
                        setOpenExperience(open ? null : item.experience_id)
                      }
                    >
                      <span className="ws2-exp-score">{item.score}%</span>
                      <span className="ws2-exp-body">
                        <strong>{item.title}</strong>
                        <span>덮는 역량 · {item.covered.join(", ")}</span>
                      </span>
                      <span className="ws2-exp-caret">
                        {open ? "접기" : "원문 보기"}
                      </span>
                    </button>

                    {open && (
                      <div className="ws2-exp-detail">
                        {filled.length === 0 ? (
                          <p className="muted">
                            이 경험에는 상황 · 역할 · 한 일 · 결과가 비어 있어요.
                            채워 두면 자기소개서의 근거로 쓸 수 있어요.{" "}
                            <a className="apl-link" href="#/experience">
                              경험 채우기 →
                            </a>
                          </p>
                        ) : (
                          <dl>
                            {filled.map(([key, label]) => (
                              <div key={key}>
                                <dt>{label}</dt>
                                <dd>{full[key]}</dd>
                              </div>
                            ))}
                          </dl>
                        )}
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>

            <p className="muted form-hint">
              점수 = 이 공고의 요구 역량 강조도 가운데 이 경험이 덮는 비율.
              원문을 참고해 직접 쓰세요 — 그대로 옮겨 붙이는 칸이 아닙니다.
            </p>
          </>
        )}
      </section>

      {/* ---------- JD 분석 ---------- */}
      <section className="card ws2-jd">
        <p className="card-label">JD 분석 · 요구 역량</p>

        {!match.available ? (
          <EmptyState
            title={match.reason}
            body="공고 본문을 채우거나, 공고에 요구 스킬을 직접 연결하면 분석할 수 있어요."
            actions={[{ href: "#/opportunities", label: "공고 확인하기", primary: true }]}
          />
        ) : (
          <>
            <p className="ws2-match-head">
              요구 역량 <strong>{match.total}개</strong> 중{" "}
              <strong className="ws2-good">{match.have}개</strong>를 이미 갖고 있어요
            </p>

            <div
              className="ws2-meter"
              role="img"
              aria-label={`요구 역량 ${match.total}개 중 ${match.have}개 보유`}
            >
              {match.skills.map((skill) => (
                <span
                  key={skill.skill}
                  className={
                    skill.strength === "gap" ? "ws2-seg seg-gap" : "ws2-seg seg-have"
                  }
                />
              ))}
            </div>

            <p className="muted ws2-basis">
              보유 = 스킬 레벨 1 이상.{" "}
              {match.basis === "linked"
                ? "본문에서 스킬 이름을 찾지 못해, 공고에 직접 연결한 스킬로 봤어요."
                : `본문에 자주 · 앞쪽에 나온 역량에 가중치를 주면 ${match.weighted_score}%.`}
            </p>

            {haveSkills.length > 0 && (
              <div className="ws2-group">
                <p className="ws2-group-title">갖고 있는 역량</p>
                <ul className="ws2-skills">
                  {haveSkills.map((skill) => (
                    <li key={skill.skill} className="ws2-skill is-have">
                      <span className="ws2-skill-mark" aria-hidden="true">
                        ✓
                      </span>
                      <strong>{skill.skill}</strong>
                      <span className="ws2-skill-meta">
                        Lv {skill.level}
                        {skill.mentions > 0 && ` · 본문 ${skill.mentions}회`}
                      </span>
                      {skill.backed && <span className="ws2-tag">경험 있음</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {gapSkills.length > 0 && (
              <div className="ws2-group">
                <p className="ws2-group-title">부족한 역량</p>
                <ul className="ws2-skills">
                  {gapSkills.map((skill) => (
                    <li key={skill.skill} className="ws2-skill is-gap">
                      <span className="ws2-skill-mark" aria-hidden="true">
                        !
                      </span>
                      <strong>{skill.skill}</strong>
                      <span className="ws2-skill-meta">
                        Lv 0{skill.mentions > 0 && ` · 본문 ${skill.mentions}회`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      {/* ---------- 분석의 한계 ---------- */}
      {analysis?.notes?.length > 0 && (
        <section className="card ws2-notes">
          <p className="card-label">이 분석의 한계</p>
          <ul className="ws2-note-list">
            {analysis.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

export default ApplicationWorkspace
