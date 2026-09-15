import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import { externalHref } from "../safeUrl"
import { errorText, savedTime } from "./applicationLabels"

/* 자소서 작성.

   AI 가 대신 써주지 않는다. 쓰는 것은 사용자가 한다.
   Career OS 가 하는 것은:
     · 어떤 경험을 어떤 순서로 쓸지 구조를 잡아주고
     · 글자 수와 근거 유무를 기계적으로 확인하는 것

   문체와 설득력은 판단하지 않는다. 그건 LLM 이 있어야 한다.

   쓰는 동안 잃지 않게 한다 —
     · 문항을 옮겨 다녀도 저장 전 글은 문항별로 남는다
     · 저장하지 않은 변경은 표시하고, 창을 닫으려 하면 묻는다
     · 이전 버전은 읽기 전용으로 보고, 원하면 편집 칸에 불러온다 */

// 이만큼 차면 "제한에 가까워요" 를 띄운다.
const NEAR_LIMIT = 0.9

function CoverLetterPanel({
  applicationId,
  initialQuestionId,
  focus,
  sourceUrl,
  onSaved,
  onDirtyChange
}) {
  const [questions, setQuestions] = useState([])
  const [answers, setAnswers] = useState({})
  const [drafts, setDrafts] = useState({})
  const [activeId, setActiveId] = useState(null)

  const [outline, setOutline] = useState(null)
  const [review, setReview] = useState(null)
  const [preview, setPreview] = useState(null)
  const [savedAt, setSavedAt] = useState(null)

  const [newQuestion, setNewQuestion] = useState("")
  const [newLimit, setNewLimit] = useState(500)

  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)

  const addRef = useRef(null)
  const textRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setError(null)

      const list = await api.coverLetter.questions(applicationId)
      const versions = await Promise.all(
        list.map((question) => api.coverLetter.answers(question.id))
      )

      setQuestions(list)
      setAnswers(
        Object.fromEntries(list.map((question, index) => [question.id, versions[index]]))
      )
      setActiveId((current) => {
        if (current && list.some((question) => question.id === current)) {
          return current
        }
        if (list.some((question) => question.id === initialQuestionId)) {
          return initialQuestionId
        }
        return list[0]?.id ?? null
      })
    } catch (loadError) {
      console.error("Failed to load cover letter:", loadError)
      setError("자기소개서를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.")
    } finally {
      setLoading(false)
    }
  }, [applicationId, initialQuestionId])

  useEffect(() => {
    load()
  }, [load])

  // 위의 "다음 행동" 버튼이 여기로 보낸다.
  useEffect(() => {
    if (!focus) return

    if (focus.add) {
      addRef.current?.focus()
      return
    }

    if (focus.questionId) {
      setActiveId(focus.questionId)
      setPreview(null)
      requestAnimationFrame(() => textRef.current?.focus())
    }
  }, [focus])

  const savedDraft = (questionId) =>
    (answers[questionId] ?? []).find((answer) => answer.is_current)?.draft ?? ""

  const draftOf = (questionId) => drafts[questionId] ?? savedDraft(questionId)

  const isDirty = (questionId) =>
    drafts[questionId] !== undefined && drafts[questionId] !== savedDraft(questionId)

  const anyDirty = questions.some((question) => isDirty(question.id))

  useEffect(() => {
    onDirtyChange?.(anyDirty)
  }, [anyDirty, onDirtyChange])

  useEffect(() => {
    if (!anyDirty) return undefined

    const warn = (event) => {
      event.preventDefault()
      event.returnValue = ""
    }

    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [anyDirty])

  const run = async (action, fallback) => {
    try {
      setWorking(true)
      setError(null)
      await action()
    } catch (actionError) {
      console.error("Cover letter action failed:", actionError)
      setError(errorText(actionError, fallback))
    } finally {
      setWorking(false)
    }
  }

  const active = questions.find((question) => question.id === activeId) ?? null
  const draft = active ? draftOf(active.id) : ""
  const limit = active?.character_limit ?? null
  const length = draft.length
  const remaining = limit != null ? limit - length : null
  const over = remaining != null && remaining < 0
  const near = !over && limit != null && length >= limit * NEAR_LIMIT
  const dirty = active ? isDirty(active.id) : false

  const versions = active
    ? [...(answers[active.id] ?? [])].sort((a, b) => b.version - a.version)
    : []
  const current = versions.find((version) => version.is_current) ?? null
  const justSaved = savedAt && active && savedAt.questionId === active.id && !dirty

  const answeredCount = questions.filter(
    (question) => savedDraft(question.id).trim() !== ""
  ).length

  // 빈 줄로 나눈 문단을 구조 칸에 차례로 잇는다. 문장을 만들지 않는다.
  const paragraphs = draft
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)

  const selectQuestion = (questionId) => {
    setActiveId(questionId)
    setPreview(null)
    setOutline(null)
    setReview(null)
  }

  const setDraft = (value) =>
    setDrafts((current) => ({ ...current, [active.id]: value }))

  const save = () =>
    run(async () => {
      const questionId = active.id
      const created = await api.coverLetter.saveAnswer(questionId, draft)
      const list = await api.coverLetter.answers(questionId)

      setAnswers((current) => ({ ...current, [questionId]: list }))
      setDrafts((current) => {
        const next = { ...current }
        delete next[questionId]
        return next
      })
      setSavedAt({ questionId, version: created.version, at: created.updated_at })
      setPreview(null)
      onSaved?.()
    }, "저장하지 못했습니다. 잠시 뒤 다시 시도해 주세요.")

  const addQuestion = () =>
    run(async () => {
      // 지운 문항이 있으면 개수로 정한 자리가 이미 쓰였을 수 있다 (409).
      const position = questions.reduce(
        (max, question) => Math.max(max, question.position + 1),
        0
      )

      const created = await api.coverLetter.addQuestion({
        application_id: applicationId,
        question: newQuestion.trim(),
        character_limit: Number(newLimit) || null,
        position
      })

      setNewQuestion("")
      await load()
      selectQuestion(created.id)
      onSaved?.()
    }, "문항을 추가하지 못했습니다.")

  const getOutline = () =>
    run(async () => {
      setOutline(await api.coverLetter.outline(active.id))
    }, "구조를 잡지 못했습니다.")

  const getReview = () =>
    run(async () => {
      setReview(await api.coverLetter.review(active.id, draft))
    }, "점검하지 못했습니다.")

  const sourceHref = externalHref(sourceUrl)

  if (loading) {
    return (
      <section className="card">
        <p className="card-label">자기소개서</p>
        <p className="muted">불러오는 중…</p>
      </section>
    )
  }

  return (
    <>
      <section className="card cl2">
        <div className="cl2-head">
          <p className="card-label">자기소개서</p>
          {questions.length > 0 && (
            <span className="cl2-progress">
              작성 <strong>{answeredCount}</strong> / {questions.length} 문항
            </span>
          )}
        </div>

        {questions.length === 0 ? (
          <div className="ws2-empty">
            <strong>자기소개서 문항이 없습니다.</strong>
            <span>
              공고의 문항을 그대로 옮겨 적으면 문항별로 쓰고 버전을 남길 수 있어요.
            </span>
            <div className="ws2-empty-actions">
              <button className="apl-cta" onClick={() => addRef.current?.focus()}>
                문항 추가하기
              </button>
              {sourceHref ? (
                <a
                  className="chip"
                  href={sourceHref}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  공고에서 문항 가져오기 ↗
                </a>
              ) : (
                <span className="muted">공고 링크가 없어 원문을 열 수 없어요.</span>
              )}
            </div>
            {sourceHref && (
              <span className="muted form-hint">
                원문을 열어 문항을 복사해 오세요. 공고를 자동으로 읽어 오지는 않아요.
              </span>
            )}
          </div>
        ) : (
          <div className="cl2-tabs" role="tablist" aria-label="문항">
            {questions.map((question, index) => {
              const text = draftOf(question.id)
              const done = savedDraft(question.id).trim() !== ""
              const percent = question.character_limit
                ? Math.min(100, Math.round((text.length / question.character_limit) * 100))
                : text.length > 0
                  ? 100
                  : 0

              return (
                <button
                  key={question.id}
                  role="tab"
                  aria-selected={question.id === activeId}
                  className={question.id === activeId ? "cl2-tab is-on" : "cl2-tab"}
                  onClick={() => selectQuestion(question.id)}
                >
                  <span className="cl2-tab-top">
                    <strong>{index + 1}번</strong>
                    {isDirty(question.id) ? (
                      <span className="cl2-dot" title="저장하지 않은 변경" />
                    ) : (
                      done && <span className="cl2-tab-done">✓</span>
                    )}
                  </span>
                  <span className="cl2-tab-bar" aria-hidden="true">
                    <span style={{ width: `${percent}%` }} />
                  </span>
                  <span className="cl2-tab-meta">
                    {question.character_limit
                      ? `${text.length}/${question.character_limit}자`
                      : `${text.length}자`}
                  </span>
                </button>
              )
            })}
          </div>
        )}

        {active && (
          <div className="cl2-editor">
            <p className="cl2-question">
              <span className="cl2-question-no">
                {questions.findIndex((question) => question.id === active.id) + 1}.
              </span>{" "}
              {active.question}
            </p>

            {versions.length > 0 && (
              <label className="cl2-versions">
                <span>버전</span>
                <select
                  className="path-select"
                  value={preview?.id ?? current?.id ?? ""}
                  onChange={(event) => {
                    const chosen = versions.find(
                      (version) => version.id === Number(event.target.value)
                    )
                    setPreview(chosen && !chosen.is_current ? chosen : null)
                  }}
                >
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      v{version.version}
                      {version.is_current ? " · 현재" : ""} ·{" "}
                      {savedTime(version.updated_at)} · {version.draft.length}자
                    </option>
                  ))}
                </select>
              </label>
            )}

            {preview && (
              <div className="cl2-preview">
                <div className="cl2-preview-head">
                  <strong>v{preview.version} 미리보기</strong>
                  <span className="muted">
                    {savedTime(preview.updated_at)} · {preview.draft.length}자 · 읽기 전용
                  </span>
                </div>
                <p className="cl2-preview-text">{preview.draft || "(빈 글)"}</p>
                <div className="cl2-row">
                  <button
                    className="chip"
                    onClick={() => {
                      setDraft(preview.draft)
                      setPreview(null)
                    }}
                  >
                    이 버전을 편집 칸에 불러오기
                  </button>
                  <button className="chip" onClick={() => setPreview(null)}>
                    닫기
                  </button>
                </div>
                <p className="muted form-hint">
                  불러와도 저장하기 전까지는 새 버전이 생기지 않아요.
                </p>
              </div>
            )}

            <textarea
              ref={textRef}
              className={over ? "cl2-textarea is-over" : "cl2-textarea"}
              value={draft}
              placeholder="여기에 직접 작성하세요. 빈 줄로 문단을 나누면 아래 구조 칸과 이어집니다."
              aria-label={`${active.question} 답변`}
              onChange={(event) => setDraft(event.target.value)}
            />

            <div className="cl2-bar">
              <div className="cl2-bar-info">
                <div
                  className={`cl2-count ${over ? "is-over" : near ? "is-near" : ""}`}
                  aria-live="polite"
                >
                  <strong>{length.toLocaleString()}</strong>
                  {limit != null ? (
                    <>
                      {" "}/ {limit.toLocaleString()}자
                      <span className="cl2-count-rest">
                        {over ? `${(-remaining).toLocaleString()}자 초과` : `${remaining.toLocaleString()}자 남음`}
                      </span>
                    </>
                  ) : (
                    "자 · 제한 없음"
                  )}
                </div>

                {limit != null && (
                  <span className="cl2-limitbar" aria-hidden="true">
                    <span
                      className={over ? "is-over" : near ? "is-near" : ""}
                      style={{ width: `${Math.min(100, (length / limit) * 100)}%` }}
                    />
                  </span>
                )}

                <span
                  className={`cl2-save-state ${
                    dirty ? "is-dirty" : justSaved ? "is-saved" : ""
                  }`}
                >
                  {dirty
                    ? "● 저장하지 않은 변경"
                    : justSaved
                      ? `✓ 저장됨 · v${savedAt.version} · ${savedTime(savedAt.at)}`
                      : current
                        ? `v${current.version} 저장됨 · ${savedTime(current.updated_at)}`
                        : "아직 저장한 버전이 없어요"}
                </span>
              </div>

              <div className="cl2-row">
                <button className="chip" disabled={working} onClick={getOutline}>
                  구조 잡기
                </button>
                <button className="chip" disabled={working} onClick={getReview}>
                  점검
                </button>
                <button
                  className="apl-cta"
                  disabled={working || over || !dirty}
                  onClick={save}
                >
                  {working ? "저장 중…" : "저장"}
                </button>
              </div>
            </div>

            {near && (
              <p className="cl2-warn">
                제한에 가까워요. 남은 {remaining}자 안에서 마무리하세요.
              </p>
            )}
            {over && (
              <p className="agent-error">
                제한을 {-remaining}자 넘어 저장할 수 없어요. 줄인 뒤 저장하세요.
              </p>
            )}
          </div>
        )}

        {error && <p className="agent-error">{error}</p>}

        <div className="cl2-add">
          <label className="cl2-add-label" htmlFor={`add-question-${applicationId}`}>
            문항 추가
          </label>
          <input
            id={`add-question-${applicationId}`}
            ref={addRef}
            className="agent-input"
            placeholder="예: 지원 동기를 작성해주세요."
            value={newQuestion}
            onChange={(event) => setNewQuestion(event.target.value)}
          />
          <label className="cl2-limit">
            <span>글자 수 제한</span>
            <input
              className="plan-input"
              type="number"
              min="1"
              value={newLimit}
              onChange={(event) => setNewLimit(event.target.value)}
            />
          </label>
          <button
            className="ghost-button"
            disabled={working || !newQuestion.trim()}
            onClick={addQuestion}
          >
            추가
          </button>
        </div>

        <p className="muted form-hint">
          직접 쓰는 칸입니다. Career OS 는 구조와 점검만 돕고, 경험이나 성과를
          지어내지 않습니다.
        </p>
      </section>

      {outline && (
        <section className="card cl2">
          <div className="cl2-head">
            <p className="card-label">구조</p>
            <button className="chip" onClick={() => setOutline(null)}>
              닫기
            </button>
          </div>

          {outline.sections.length === 0 ? (
            <div className="ws2-empty">
              <strong>{outline.message}</strong>
              <div className="ws2-empty-actions">
                <a className="apl-cta" href="#/experience">
                  경험 등록하기
                </a>
                <a className="chip" href="#/projects">
                  관련 프로젝트 보기
                </a>
              </div>
            </div>
          ) : (
            <>
              <p className="muted cl2-outline-basis">
                기준 경험 · <strong>{outline.based_on.title}</strong> (
                {outline.based_on.score}%, {outline.based_on.covered.join(", ")})
              </p>

              <ol className="cl2-sections">
                {outline.sections.map((section, index) => {
                  const written = paragraphs[index]?.length ?? 0
                  const ratio = section.suggested_chars
                    ? written / section.suggested_chars
                    : 0

                  return (
                    <li className="cl2-section" key={section.key}>
                      <div className="cl2-section-head">
                        <strong>
                          문단 {index + 1} · {section.label}
                        </strong>
                        <span
                          className={
                            ratio > 1.3 ? "cl2-section-count is-over" : "cl2-section-count"
                          }
                        >
                          {written}자 / 약 {section.suggested_chars}자
                        </span>
                      </div>

                      <span className="cl2-section-bar" aria-hidden="true">
                        <span style={{ width: `${Math.min(100, ratio * 100)}%` }} />
                      </span>

                      <p
                        className={
                          section.content ? "cl2-section-source" : "cl2-section-source muted"
                        }
                      >
                        {section.content
                          ? `경험 원문 — ${section.content}`
                          : "(경험에 비어 있음 — 지어내지 않습니다)"}
                      </p>
                    </li>
                  )
                })}
              </ol>

              <p className="muted form-hint">
                편집 칸에서 빈 줄로 나눈 문단이 순서대로 위 칸과 이어집니다.
                {outline.message && ` ${outline.message}`}
              </p>
            </>
          )}
        </section>
      )}

      {review && (
        <section className="card cl2">
          <div className="cl2-head">
            <p className="card-label">점검</p>
            <span className="cl2-progress">
              통과 <strong>{review.passed}</strong> / {review.total}
            </span>
          </div>

          <ul className="cl2-checks">
            {review.checks.map((check) => (
              <li className="cl2-check" key={check.key}>
                <span className={check.ok ? "cl2-mark is-ok" : "cl2-mark is-no"}>
                  {check.ok ? "✓" : "!"}
                </span>
                <span>{check.message}</span>
              </li>
            ))}
          </ul>

          <p className="muted form-hint">{review.note}</p>
        </section>
      )}
    </>
  )
}

export default CoverLetterPanel
