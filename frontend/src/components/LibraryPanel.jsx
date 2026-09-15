import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import {
  Button,
  ConfirmButton,
  EmptyState,
  ErrorState,
  LoadingState,
  Notice,
  StatusBadge
} from "./ui"
import {
  IMPORTANCE_HINTS,
  IMPORTANCE_LABELS,
  OWNERSHIP_LABELS,
  RESOURCE_TYPES,
  minutesText,
  ownershipLabel,
  resourceTypeLabel
} from "../format"

/* 내 자료 — 등록과 관리.

   Career OS 는 새 자료를 추천하지 않는다. 이미 가진 것 중에서 오늘 볼
   것만 고른다(위의 "지금 쓸 자료"). 그러려면 먼저 "가진 것" 을 넣을 수
   있어야 한다. 이 카드가 그 자리다. */

const EMPTY_FORM = {
  title: "",
  resource_type: "book",
  ownership: "owned",
  importance: "primary",
  url: "",
  duration_minutes: "",
  total_units: "",
  unit_label: "쪽",
  skill_id: ""
}

// 입력 폼에서 고를 종류. 같은 이름(영상)이 두 번 나오지 않게 youtube 는 뺀다.
const FORM_TYPES = RESOURCE_TYPES.filter((type) => type.key !== "youtube")

function LibraryPanel({ skills, onChanged, initialShowForm = false }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [filter, setFilter] = useState("all")
  const [form, setForm] = useState(EMPTY_FORM)
  const [showForm, setShowForm] = useState(initialShowForm)
  const [expanded, setExpanded] = useState(null)
  const [segmentDrafts, setSegmentDrafts] = useState({})

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)
      setData(await api.library.get())
    } catch (failure) {
      console.error("Failed to load library:", failure)
      setLoadError("내 자료를 불러오지 못했습니다.")
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
      await load(true)
      onChanged?.()
      if (success) setNotice(success)
      return true
    } catch (failure) {
      console.error("Library action failed:", failure)
      setError(failure?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  const addResource = async () => {
    if (!form.title.trim() || !form.skill_id) {
      setError("제목과 스킬을 골라 주세요.")
      return
    }

    const title = form.title.trim()

    const ok = await run(
      () =>
        api.resources.create({
          title,
          resource_type: form.resource_type,
          ownership: form.ownership,
          importance: form.importance,
          // 종이책에는 URL 이 없다. 빈 값은 보내지 않는다.
          url: form.url.trim() || null,
          duration_minutes: Number(form.duration_minutes) || 0,
          total_units: form.total_units === "" ? null : Number(form.total_units),
          unit_label: form.unit_label.trim(),
          skill_id: Number(form.skill_id)
        }),
      `'${title}' 을(를) 등록했어요. 챕터로 쪼개면 오늘 계획에 들어갈 수 있어요.`,
      "자료를 등록하지 못했습니다."
    )

    if (ok) {
      setForm(EMPTY_FORM)
      setShowForm(false)
    }
  }

  const addSegment = (item) => {
    const draft = segmentDrafts[item.id] ?? {}

    if (!draft.label?.trim()) {
      setError("챕터 이름을 적어 주세요.")
      return
    }

    return run(
      async () => {
        await api.library.addSegment(item.id, {
          label: draft.label.trim(),
          position: item.segments.length,
          start_ref: draft.start ? Number(draft.start) : null,
          end_ref: draft.end ? Number(draft.end) : null,
          estimated_minutes: Number(draft.minutes) || 0
        })
        setSegmentDrafts((current) => ({ ...current, [item.id]: {} }))
      },
      `'${draft.label.trim()}' 챕터를 추가했어요.`,
      "챕터를 추가하지 못했습니다."
    )
  }

  const setDraft = (id, key, value) =>
    setSegmentDrafts((current) => ({
      ...current,
      [id]: { ...(current[id] ?? {}), [key]: value }
    }))

  if (loading) {
    return <LoadingState label="내 자료를 불러오는 중…" />
  }

  if (!data) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const items = data.items.filter(
    (item) => filter === "all" || item.resource_type === filter
  )

  const presentTypes = [...new Set(data.items.map((item) => item.resource_type))]
  const unused = data.items.filter((item) => !item.linked_steps?.length).length

  return (
    <div className="library-panel">
      <section className="card">
        <div className="opp-head">
          <div>
            <p className="card-label">자료 등록 · 관리</p>
            {data.summary.total > 0 && (
              <p className="muted opp-meta">
                가지고 있음 {data.summary.by_ownership.owned ?? 0} · 저장해 둠{" "}
                {data.summary.by_ownership.saved ?? 0} · 사고 싶음{" "}
                {data.summary.by_ownership.wishlist ?? 0} · 챕터{" "}
                {data.summary.segments_done}/{data.summary.segments} 완료 · 학습 단계에
                아직 안 쓰는 자료 {unused}개
              </p>
            )}
          </div>

          <Button
            variant={showForm ? "quiet" : "secondary"}
            writes={!showForm}
            aria-expanded={showForm}
            onClick={() => setShowForm(!showForm)}
          >
            {showForm ? "닫기" : "+ 자료 등록"}
          </Button>
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

        {showForm && (
          <div className="lib-form">
            <div className="lib-row">
              <label className="learn-field lib-grow">
                <span>제목</span>
                <input
                  className="agent-input"
                  placeholder="예: AWS 완벽 가이드"
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                />
              </label>

              <label className="learn-field">
                <span>관련 스킬</span>
                <select
                  className="path-select"
                  value={form.skill_id}
                  onChange={(event) => setForm({ ...form, skill_id: event.target.value })}
                >
                  <option value="">스킬 고르기</option>
                  {skills.map((skill) => (
                    <option key={skill.id} value={skill.id}>
                      {skill.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="lib-row">
              <label className="learn-field">
                <span>종류</span>
                <select
                  className="path-select"
                  value={form.resource_type}
                  onChange={(event) => {
                    const type = FORM_TYPES.find((item) => item.key === event.target.value)
                    setForm({ ...form, resource_type: event.target.value, unit_label: type?.unit ?? "" })
                  }}
                >
                  {FORM_TYPES.map((type) => (
                    <option key={type.key} value={type.key}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="learn-field">
                <span>보유</span>
                <select
                  className="path-select"
                  value={form.ownership}
                  onChange={(event) => setForm({ ...form, ownership: event.target.value })}
                >
                  {Object.entries(OWNERSHIP_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="learn-field">
                <span>중요도</span>
                <select
                  className="path-select"
                  value={form.importance}
                  onChange={(event) => setForm({ ...form, importance: event.target.value })}
                >
                  {Object.entries(IMPORTANCE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label} — {IMPORTANCE_HINTS[key]}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="lib-row">
              <label className="learn-field lib-grow">
                <span>링크 (종이책이면 비워 두세요)</span>
                <input
                  className="agent-input"
                  placeholder="https://"
                  value={form.url}
                  onChange={(event) => setForm({ ...form, url: event.target.value })}
                />
              </label>

              <label className="learn-field">
                <span>전체 시간(분)</span>
                <input
                  className="plan-input"
                  type="number"
                  min="0"
                  value={form.duration_minutes}
                  onChange={(event) => setForm({ ...form, duration_minutes: event.target.value })}
                />
              </label>

              <label className="learn-field">
                <span>분량</span>
                <input
                  className="plan-input"
                  type="number"
                  min="0"
                  value={form.total_units}
                  onChange={(event) => setForm({ ...form, total_units: event.target.value })}
                />
              </label>

              <label className="learn-field">
                <span>단위</span>
                <input
                  className="plan-input"
                  placeholder="쪽"
                  value={form.unit_label}
                  onChange={(event) => setForm({ ...form, unit_label: event.target.value })}
                />
              </label>
            </div>

            <div className="ui-row">
              <Button writes disabled={working} onClick={addResource}>
                등록
              </Button>
              <span className="muted form-hint">
                등록한 자료는 학습 세션에서 단계에 연결합니다.
              </span>
            </div>
          </div>
        )}

        {data.summary.total === 0 ? (
          <EmptyState
            title="아직 등록한 자료가 없습니다."
            body="가지고 있는 책과 저장해 둔 영상을 넣어 두면, 학습 단계에 맞는 것만 골라 드려요."
            actions={[
              { label: "자료 등록하기", onClick: () => setShowForm(true), primary: true, writes: true }
            ]}
          />
        ) : (
          <div className="opp-tabs" role="tablist" aria-label="자료 종류">
            <button
              role="tab"
              aria-selected={filter === "all"}
              className={filter === "all" ? "chip chip-on" : "chip"}
              onClick={() => setFilter("all")}
            >
              전체 {data.summary.total}
            </button>
            {presentTypes.map((type) => (
              <button
                key={type}
                role="tab"
                aria-selected={filter === type}
                className={filter === type ? "chip chip-on" : "chip"}
                onClick={() => setFilter(type)}
              >
                {resourceTypeLabel(type)} {data.summary.by_type[type]}
              </button>
            ))}
          </div>
        )}
      </section>

      {items.map((item) => {
        const open = expanded === item.id
        const draft = segmentDrafts[item.id] ?? {}

        return (
          <section className="card" key={item.id}>
            <button
              className="path-header lib-head"
              aria-expanded={open}
              onClick={() => setExpanded(open ? null : item.id)}
            >
              <span className="lib-head-main">
                <strong>{item.title}</strong>
                <span className="muted">
                  {resourceTypeLabel(item.resource_type)} · {ownershipLabel(item.ownership)}
                  {item.total_units ? ` · ${item.total_units}${item.unit_label}` : ""}
                  {item.duration_minutes > 0 ? ` · ${minutesText(item.duration_minutes)}` : ""}
                  {!item.url && " · 오프라인"}
                  {item.segments_total > 0 && ` · 챕터 ${item.segments_done}/${item.segments_total}`}
                </span>
                <span className="lib-linked">
                  {item.linked_steps?.length
                    ? `쓰는 단계: ${item.linked_steps.map((step) => `${step.path_title} › ${step.title}`).join(", ")}`
                    : "아직 어느 학습 단계에도 연결되지 않았어요"}
                </span>
              </span>

              <StatusBadge tone={`imp-${item.importance}`}>
                {IMPORTANCE_LABELS[item.importance] ?? "중요도 미정"}
              </StatusBadge>
            </button>

            {open && (
              <div className="step-list">
                {item.segments.length === 0 ? (
                  <p className="muted">
                    아직 챕터가 없습니다. &ldquo;책 한 권&rdquo;이 아니라 &ldquo;3장 45분&rdquo;으로
                    쪼개면 오늘 계획에 들어갑니다.
                  </p>
                ) : (
                  item.segments.map((segment) => (
                    <div className={`seg-item seg-${segment.status}`} key={segment.id}>
                      <Button
                        variant="check"
                        className="td-check lib-check"
                        writes
                        disabled={working || segment.status === "completed"}
                        onClick={() =>
                          run(
                            () => api.library.completeSegment(segment.id),
                            `'${segment.label}' 을(를) 완료했어요.`,
                            "완료로 표시하지 못했습니다."
                          )
                        }
                        aria-label={`${segment.label} 완료로 표시`}
                      >
                        {segment.status === "completed" ? "✓" : ""}
                      </Button>

                      <span className="seg-label">{segment.label}</span>

                      <span className="muted seg-range">
                        {segment.start_ref != null &&
                          `${segment.start_ref}~${segment.end_ref ?? ""}${item.unit_label}`}
                      </span>

                      <span className="seg-minutes">{minutesText(segment.estimated_minutes)}</span>

                      <ConfirmButton
                        label="삭제"
                        confirmLabel="정말 삭제"
                        disabled={working}
                        onConfirm={() =>
                          run(
                            () => api.library.removeSegment(segment.id),
                            `'${segment.label}' 챕터를 지웠어요.`,
                            "챕터를 지우지 못했습니다."
                          )
                        }
                      />
                    </div>
                  ))
                )}

                <div className="seg-form">
                  <label className="learn-field lib-grow">
                    <span>챕터 이름</span>
                    <input
                      className="agent-input"
                      placeholder="예: 3장 — EC2 기초"
                      value={draft.label ?? ""}
                      onChange={(event) => setDraft(item.id, "label", event.target.value)}
                    />
                  </label>
                  <label className="learn-field">
                    <span>시작</span>
                    <input
                      className="plan-input"
                      type="number"
                      min="0"
                      value={draft.start ?? ""}
                      onChange={(event) => setDraft(item.id, "start", event.target.value)}
                    />
                  </label>
                  <label className="learn-field">
                    <span>끝</span>
                    <input
                      className="plan-input"
                      type="number"
                      min="0"
                      value={draft.end ?? ""}
                      onChange={(event) => setDraft(item.id, "end", event.target.value)}
                    />
                  </label>
                  <label className="learn-field">
                    <span>분</span>
                    <input
                      className="plan-input"
                      type="number"
                      min="0"
                      value={draft.minutes ?? ""}
                      onChange={(event) => setDraft(item.id, "minutes", event.target.value)}
                    />
                  </label>
                  <Button variant="secondary" writes disabled={working} onClick={() => addSegment(item)}>
                    챕터 추가
                  </Button>
                </div>
              </div>
            )}
          </section>
        )
      })}
    </div>
  )
}

export default LibraryPanel
