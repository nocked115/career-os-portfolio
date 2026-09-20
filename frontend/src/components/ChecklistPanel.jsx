import { useState } from "react"
import * as api from "../api"
import { Button, EmptyState, Notice, ProgressBar, StatusBadge } from "./ui"
import { useReadOnly } from "../readOnly"
import { STATIC_DEMO } from "../api"
import "../Checklist.css"

/* 학습 단계 체크리스트.

   단계("2주차 — 인기 기반 추천")는 하루에 끝나지 않는다. 오늘 실제로 하는 건
   그 아래 한 줄("movie_stats 생성")이라 여기서 체크한다. 체크는 서버에 남는다.

   다른 세션에서 만든 주차 체크리스트를 붙여넣거나 파일로 불러오면
   규칙으로 읽어 미리 보여주고, 뺄 줄을 끈 뒤 저장한다. 앱은 링크를 열지 않는다.

   모두 체크해도 단계를 저절로 끝내지 않는다 — 끝났다고 말하는 건 사람이다. */

const FILE_TYPES = ".html,.htm,.md,.markdown,.txt"
const MAX_FILE_BYTES = 1_000_000

/* 체크리스트 글의 `코드` 표시를 <code> 로. 나머지는 글자 그대로 둔다. */
export function InlineCode({ text }) {
  const parts = String(text ?? "").split(/(`[^`]+`)/)

  return (
    <>
      {parts.map((part, index) =>
        part.length > 2 && part.startsWith("`") && part.endsWith("`") ? (
          <code key={index}>{part.slice(1, -1)}</code>
        ) : (
          <span key={index}>{part}</span>
        )
      )}
    </>
  )
}

function toDraft(parsed) {
  return {
    title: parsed.title ?? "",
    warnings: parsed.warnings ?? [],
    sections: parsed.sections.map((section, s) => ({
      ...section,
      key: `s${s}`,
      items: section.items.map((item, i) => ({ ...item, key: `s${s}-${i}`, include: true }))
    })),
    links: parsed.links.map((link, i) => ({ ...link, key: `l${i}`, include: true }))
  }
}

function fromDraft(draft) {
  return {
    sections: draft.sections
      .map((section) => ({
        title: section.title,
        note: section.note,
        items: section.items
          .filter((item) => item.include)
          .map(({ text, done }) => ({ text, done }))
      }))
      .filter((section) => section.items.length > 0 || section.note),
    links: draft.links.filter((link) => link.include).map(({ text, url }) => ({ text, url }))
  }
}

export function ChecklistImporter({ mode = "step", hasExisting = false, busy = false, onSave, onCancel }) {
  const [text, setText] = useState("")
  const [draft, setDraft] = useState(null)
  const [title, setTitle] = useState("")
  const [dueDate, setDueDate] = useState("")
  const [replace, setReplace] = useState(false)
  const [reading, setReading] = useState(false)
  const [error, setError] = useState(null)

  const read = async (source) => {
    if (!source.trim()) {
      setError("붙여넣은 내용이 비어 있어요.")
      return
    }

    try {
      setReading(true)
      setError(null)
      const next = toDraft(await api.checklists.parse(source))
      setDraft(next)
      setTitle(next.title)
    } catch (failure) {
      setError(failure?.detail || "체크리스트를 읽지 못했습니다.")
    } finally {
      setReading(false)
    }
  }

  const readFile = (event) => {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return

    if (file.size > MAX_FILE_BYTES) {
      setError("파일이 너무 커요. 1MB 까지 읽을 수 있어요.")
      return
    }

    // 파일은 브라우저에서 글자로 읽고, 서버에는 그 글자만 보낸다.
    const reader = new FileReader()
    reader.onload = () => {
      const content = String(reader.result ?? "")
      setText(content)
      read(content)
    }
    reader.onerror = () => setError("파일을 읽지 못했습니다.")
    reader.readAsText(file)
  }

  const toggleItem = (sectionKey, itemKey) =>
    setDraft((current) => ({
      ...current,
      sections: current.sections.map((section) =>
        section.key !== sectionKey
          ? section
          : {
              ...section,
              items: section.items.map((item) =>
                item.key !== itemKey ? item : { ...item, include: !item.include }
              )
            }
      )
    }))

  const toggleLink = (key) =>
    setDraft((current) => ({
      ...current,
      links: current.links.map((link) =>
        link.key !== key ? link : { ...link, include: !link.include }
      )
    }))

  const structure = draft ? fromDraft(draft) : null
  const count = structure
    ? structure.sections.reduce((sum, section) => sum + section.items.length, 0)
    : 0
  const canSave = count > 0 && (mode !== "path" || title.trim().length > 0)

  return (
    <div className="ck-import">
      {!draft ? (
        <>
          <label className="learn-field">
            <span>체크리스트 붙여넣기 — 아티팩트 HTML · Markdown · 한 줄에 하나</span>
            <textarea
              className="learn-textarea"
              rows={6}
              value={text}
              placeholder={"예:\n## 수업 실습\n- [ ] movie_stats 생성\n- [ ] Gradio 앱 실행"}
              onChange={(event) => setText(event.target.value)}
            />
          </label>
          <p className="muted form-hint">
            붙여넣은 글만 읽어요. 링크는 열지 않고, 저장하기 전에 미리 보여 드려요.
          </p>

          <div className="ui-row">
            <Button disabled={reading || !text.trim()} onClick={() => read(text)}>
              {reading ? "읽는 중…" : "읽어 보기"}
            </Button>
            <label className="ck-file">
              파일에서 불러오기
              <input type="file" accept={FILE_TYPES} onChange={readFile} />
            </label>
            {onCancel && (
              <Button variant="quiet" onClick={onCancel}>
                취소
              </Button>
            )}
          </div>
        </>
      ) : (
        <>
          {mode === "path" && (
            <label className="learn-field">
              <span>단계 이름</span>
              <input
                className="agent-input"
                maxLength={200}
                value={title}
                placeholder="예: 2주차 — 인기 기반 추천"
                onChange={(event) => setTitle(event.target.value)}
              />
            </label>
          )}

          {mode === "path" && (
            <label className="learn-field">
              <span>마감 (선택) — 발표일 · 제출일이 있으면 14일 안에 오늘 계획이 챙겨요</span>
              <input
                className="agent-input"
                type="date"
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
              />
            </label>
          )}

          {draft.warnings.map((warning) => (
            <p className="ck-warn" key={warning}>
              {warning}
            </p>
          ))}

          <p className="ck-preview-count">
            넣을 항목 {count}개{structure.links.length > 0 && ` · 링크 ${structure.links.length}개`}
            <span className="muted"> — 뺄 줄은 체크를 끄세요</span>
          </p>

          <div className="ck-preview">
            {draft.sections.map((section) => (
              <div className="ck-section" key={section.key}>
                {section.title && <p className="ck-section-title">{section.title}</p>}
                {section.note && <p className="ck-note">{section.note}</p>}
                <ul className="ck-list">
                  {section.items.map((item) => (
                    <li className="ck-item" key={item.key}>
                      <label className="ck-row">
                        <input
                          type="checkbox"
                          checked={item.include}
                          aria-label={`${item.text} 넣기`}
                          onChange={() => toggleItem(section.key, item.key)}
                        />
                        <span className={item.include ? "ck-text" : "ck-text ck-excluded"}>
                          <InlineCode text={item.text} />
                        </span>
                        {item.done && <StatusBadge tone="ok">체크된 채로</StatusBadge>}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            ))}

            {draft.links.length > 0 && (
              <div className="ck-section">
                <p className="ck-section-title">자료 링크</p>
                <ul className="ck-list">
                  {draft.links.map((link) => (
                    <li className="ck-item" key={link.key}>
                      <label className="ck-row">
                        <input
                          type="checkbox"
                          checked={link.include}
                          aria-label={`${link.text} 넣기`}
                          onChange={() => toggleLink(link.key)}
                        />
                        <span className={link.include ? "ck-text" : "ck-text ck-excluded"}>
                          {link.text}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {mode === "step" && hasExisting && (
            <fieldset className="ck-mode">
              <legend>이미 있는 체크리스트</legend>
              <label>
                <input type="radio" name="ck-mode" checked={!replace} onChange={() => setReplace(false)} />
                뒤에 이어 붙이기
              </label>
              <label>
                <input type="radio" name="ck-mode" checked={replace} onChange={() => setReplace(true)} />
                통째로 바꾸기 — 지금까지 체크한 기록도 사라져요
              </label>
            </fieldset>
          )}

          <div className="ui-row">
            <Button
              writes
              disabled={busy || !canSave}
              onClick={() =>
                onSave(structure, { title: title.trim(), replace, dueDate: dueDate || null })
              }
            >
              {mode === "path" ? "이 체크리스트로 단계 만들기" : replace ? "바꿔서 저장" : "저장"}
            </Button>
            <Button variant="quiet" onClick={() => setDraft(null)}>
              다시 붙여넣기
            </Button>
            {onCancel && (
              <Button variant="quiet" onClick={onCancel}>
                취소
              </Button>
            )}
          </div>
        </>
      )}

      {error && (
        <p className="agent-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

function withDone(checklist, id, done) {
  const sections = checklist.sections.map((section) => {
    const items = section.items.map((item) => (item.id === id ? { ...item, done } : item))
    return { ...section, items, done: items.filter((item) => item.done).length }
  })
  const all = sections.flatMap((section) => section.items)
  const count = all.filter((item) => item.done).length

  return {
    ...checklist,
    sections,
    progress: { done: count, total: all.length },
    all_done: all.length > 0 && count === all.length
  }
}

export default function ChecklistPanel({
  stepId,
  checklist,
  goals = [],
  isCompleted,
  onUpdated,
  onStarted,
  onComplete
}) {
  const readOnly = useReadOnly()

  const [importing, setImporting] = useState(false)
  const [draft, setDraft] = useState("")
  const [pendingId, setPendingId] = useState(null)
  const [confirmId, setConfirmId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const sections = checklist?.sections ?? []
  const links = checklist?.links ?? []
  const progress = checklist?.progress ?? { done: 0, total: 0 }
  const hasContent = sections.length > 0 || links.length > 0

  const act = async (action, fallback) => {
    try {
      setBusy(true)
      setError(null)
      setNotice(null)
      return await action()
    } catch (failure) {
      console.error("Checklist action failed:", failure)
      setError(failure?.detail || fallback)
      return null
    } finally {
      setBusy(false)
    }
  }

  const toggle = async (item) => {
    const before = checklist
    // 체크는 바로 보이게 먼저 바꾸고, 서버가 거절하면 되돌린다.
    onUpdated(withDone(checklist, item.id, !item.done))
    setPendingId(item.id)

    try {
      setError(null)
      const response = await api.checklists.update(item.id, { done: !item.done })
      onUpdated(response.checklist)
      if (response.started) onStarted?.()
    } catch (failure) {
      onUpdated(before)
      setError(failure?.detail || "체크를 저장하지 못했습니다.")
    } finally {
      setPendingId(null)
    }
  }

  const saveImport = async (structure, { replace }) => {
    const response = await act(
      () => api.checklists.importTo(stepId, { ...structure, replace }),
      "체크리스트를 저장하지 못했습니다."
    )

    if (response) {
      onUpdated(response.checklist)
      setImporting(false)
      setNotice(`${response.added}개 항목을 넣었어요.`)
    }
  }

  const moveGoals = async () => {
    const response = await act(async () => {
      const parsed = await api.checklists.parse(goals.join("\n"))
      return api.checklists.importTo(stepId, { sections: parsed.sections, links: parsed.links })
    }, "목표를 체크리스트로 옮기지 못했습니다.")

    if (response) {
      onUpdated(response.checklist)
      setNotice(`목표 ${response.added}줄을 체크리스트로 옮겼어요. 이제 체크가 서버에 남아요.`)
    }
  }

  const addItem = async () => {
    const text = draft.trim()
    if (!text) return

    const response = await act(() => api.checklists.add(stepId, { text }), "항목을 추가하지 못했습니다.")

    if (response) {
      onUpdated(response.checklist)
      setDraft("")
    }
  }

  const removeItem = async (item) => {
    const response = await act(() => api.checklists.remove(item.id), "항목을 지우지 못했습니다.")

    if (response) {
      onUpdated(response.checklist)
      setConfirmId(null)
    }
  }

  const removeControl = (item, label) =>
    readOnly ? null : confirmId === item.id ? (
      <span className="ck-confirm">
        <button type="button" className="ck-mini ck-mini-bad" disabled={busy} onClick={() => removeItem(item)}>
          지우기
        </button>
        <button type="button" className="ck-mini" onClick={() => setConfirmId(null)}>
          취소
        </button>
      </span>
    ) : (
      <button
        type="button"
        className="ck-mini"
        aria-label={`${label} 지우기`}
        onClick={() => setConfirmId(item.id)}
      >
        ✕
      </button>
    )

  return (
    <section className="card ck" aria-labelledby={`ck-title-${stepId}`}>
      <div className="materials-header">
        <p className="card-label" id={`ck-title-${stepId}`}>
          체크리스트
        </p>
        {progress.total > 0 && (
          <span className="muted">
            {progress.total}개 중 {progress.done}개 체크
          </span>
        )}
      </div>

      {progress.total > 0 && (
        <ProgressBar value={progress.done} max={progress.total} label="체크리스트 진행" />
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

      {checklist?.all_done && !isCompleted && (
        <div className="ck-all-done" role="status">
          <strong>모두 체크했어요.</strong>
          <span>끝났다고 판단되면 이 단계를 완료로 표시하세요. 저절로 완료되지는 않아요.</span>
          <Button writes onClick={onComplete}>
            이 단계 완료로 표시
          </Button>
        </div>
      )}

      {!hasContent && !importing && (
        <EmptyState
          title="이 단계에는 아직 체크리스트가 없어요."
          body="다른 세션에서 만든 주차 체크리스트를 붙여넣거나 파일로 불러오세요. 한 줄씩 직접 추가해도 돼요."
          actions={[
            { label: "붙여넣어 가져오기", primary: true, writes: true, onClick: () => setImporting(true) },
            ...(goals.length > 0
              ? [{ label: `단계 설명의 목표 ${goals.length}줄 옮기기`, writes: true, onClick: moveGoals }]
              : [])
          ]}
        />
      )}

      {sections.map((section) => (
        <div className="ck-section" key={section.title || "_"}>
          {section.title && (
            <p className="ck-section-title">
              {section.title}
              {section.total > 0 && (
                <span className="muted">
                  {" "}
                  {section.done}/{section.total}
                </span>
              )}
            </p>
          )}
          {section.note && <p className="ck-note">{section.note}</p>}

          <ul className="ck-list">
            {section.items.map((item) => (
              <li className={item.done ? "ck-item ck-done" : "ck-item"} key={item.id}>
                <label className="ck-row">
                  <input
                    type="checkbox"
                    checked={item.done}
                    disabled={(readOnly && !STATIC_DEMO) || pendingId === item.id}
                    onChange={() => toggle(item)}
                  />
                  <span className="ck-text">
                    <InlineCode text={item.text} />
                  </span>
                </label>
                {removeControl(item, item.text)}
              </li>
            ))}
          </ul>
        </div>
      ))}

      {links.length > 0 && (
        <div className="ck-section">
          <p className="ck-section-title">자료 링크</p>
          <ul className="ck-list">
            {links.map((link) => (
              <li className="ck-item" key={link.id}>
                <a className="ck-link" href={link.url} target="_blank" rel="noreferrer noopener">
                  {link.text} ↗
                </a>
                {removeControl(link, link.text)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasContent && !importing && (
        <div className="ck-add">
          <input
            className="agent-input"
            aria-label="체크 항목 추가"
            placeholder="항목 추가 (예: 점검 퀴즈 8문항 풀기)"
            maxLength={300}
            value={draft}
            disabled={readOnly}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") addItem()
            }}
          />
          <Button variant="secondary" writes disabled={busy || !draft.trim()} onClick={addItem}>
            추가
          </Button>
          <Button variant="quiet" writes onClick={() => setImporting(true)}>
            붙여넣어 더 가져오기
          </Button>
        </div>
      )}

      {importing && (
        <ChecklistImporter
          mode="step"
          hasExisting={hasContent}
          busy={busy}
          onSave={saveImport}
          onCancel={() => setImporting(false)}
        />
      )}
    </section>
  )
}
