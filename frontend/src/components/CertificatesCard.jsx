import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { Button, ConfirmButton, EmptyState, ErrorState, LoadingState, Notice, StatusBadge } from "./ui"
import { dateText } from "../format"
import "../Certificates.css"

/* 자격증 · 어학 — 프로필에 붙는 증빙.

   번호(자격번호 · 수험번호)를 적는 칸이 없다. 제출할 때는 원본 증빙
   파일을 쓴다. 여기 적은 것은 기회 화면의 자격 경고 옆에 "내 어학 · 자격"
   으로 함께 보인다. 충족 여부는 앱이 판단하지 않는다. */

const COLUMNS = [
  {
    key: "language",
    title: "어학",
    hint: "TOEIC · TOEFL · OPIc · 토익스피킹",
    add: "어학 추가",
    empty: "등록한 어학 점수가 없어요."
  },
  {
    key: "job",
    title: "직무 자격",
    hint: "빅데이터분석기사 · ADsP · SQLD",
    add: "자격증 추가",
    empty: "등록한 직무 자격증이 없어요."
  }
]

const BLANK = {
  category: "language",
  name: "",
  score: "",
  detail: "",
  issuer: "",
  status: "held",
  acquired_on: "",
  expires_on: "",
  note: ""
}

function ExpiryBadge({ item }) {
  if (item.status === "planned") return <StatusBadge tone="action">준비 중</StatusBadge>
  if (item.expiry_state === "expired") return <StatusBadge tone="bad">만료됨</StatusBadge>
  if (item.expiry_state === "soon") return <StatusBadge tone="warn">만료 {item.days_to_expiry}일 전</StatusBadge>
  if (item.expiry_state === "ok") return <StatusBadge>{dateText(item.expires_on)}까지</StatusBadge>
  return <StatusBadge tone="ok">기한 없음</StatusBadge>
}

function CertificateForm({ initial, working, onSave, onCancel }) {
  const [draft, setDraft] = useState(() => {
    const base = { ...BLANK }
    for (const field of Object.keys(BLANK)) {
      if (initial?.[field] != null) base[field] = initial[field]
    }
    return base
  })

  const set = (field, value) => setDraft((current) => ({ ...current, [field]: value }))
  const badDates = draft.acquired_on && draft.expires_on && draft.expires_on < draft.acquired_on

  return (
    <div className="cert-form">
      <div className="prj-editor-grid">
        <label className="learn-field">
          <span>구분</span>
          <select className="path-select" value={draft.category} onChange={(event) => set("category", event.target.value)}>
            <option value="language">어학</option>
            <option value="job">직무 자격</option>
          </select>
        </label>

        <label className="learn-field prj-wide">
          <span>이름</span>
          <input
            className="agent-input"
            placeholder={draft.category === "language" ? "예: TOEIC" : "예: 빅데이터분석기사"}
            value={draft.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>점수 · 등급</span>
          <input className="agent-input" placeholder="예: 900 · IH" value={draft.score} onChange={(event) => set("score", event.target.value)} />
        </label>

        <label className="learn-field prj-wide">
          <span>세부</span>
          <input className="agent-input" placeholder="예: LC 450 · RC 450" value={draft.detail} onChange={(event) => set("detail", event.target.value)} />
        </label>

        <label className="learn-field">
          <span>상태</span>
          <select className="path-select" value={draft.status} onChange={(event) => set("status", event.target.value)}>
            <option value="held">보유</option>
            <option value="planned">준비 중</option>
          </select>
        </label>

        <label className="learn-field">
          <span>취득 · 응시일</span>
          <input className="plan-input" type="date" value={draft.acquired_on || ""} onChange={(event) => set("acquired_on", event.target.value)} />
        </label>

        <label className="learn-field">
          <span>만료일 (없으면 비움)</span>
          <input className="plan-input" type="date" value={draft.expires_on || ""} onChange={(event) => set("expires_on", event.target.value)} />
        </label>

        <label className="learn-field">
          <span>발급 기관</span>
          <input className="agent-input" value={draft.issuer} onChange={(event) => set("issuer", event.target.value)} />
        </label>

        <label className="learn-field prj-full">
          <span>메모</span>
          <input className="agent-input" placeholder="예: 영어회화 요건에 인정" value={draft.note} onChange={(event) => set("note", event.target.value)} />
        </label>
      </div>

      {badDates && <p className="agent-error">만료일이 취득일보다 빠를 수 없어요.</p>}

      <div className="ui-row">
        <Button
          writes
          disabled={working || !draft.name.trim() || badDates}
          onClick={() =>
            onSave({
              ...draft,
              name: draft.name.trim(),
              acquired_on: draft.acquired_on || null,
              expires_on: draft.expires_on || null
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

function CertificatesCard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [working, setWorking] = useState(false)
  const [editing, setEditing] = useState(null)

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)
      setData(await api.certificates.list())
    } catch (failure) {
      console.error("Failed to load certificates:", failure)
      setLoadError("자격증을 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const message = await action()
      await load(true)
      if (message) setNotice(message)
      return true
    } catch (failure) {
      console.error("Certificate action failed:", failure)
      setError(failure?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  const save = async (fields) => {
    const ok = await run(async () => {
      if (editing?.id === "new") {
        const created = await api.certificates.create(fields)
        return `'${created.name}' 을(를) 추가했어요.`
      }
      await api.certificates.update(editing.id, fields)
      return "저장했어요."
    }, "저장하지 못했습니다.")

    if (ok) setEditing(null)
  }

  if (loading) return <LoadingState label="자격증을 불러오는 중…" />
  if (!data) return <ErrorState message={loadError} onRetry={() => load()} />

  const { summary } = data

  return (
    <section className="card cert-card" data-section="certificates">
      <div className="evd-head">
        <div>
          <p className="card-label">자격증 · 어학</p>
          <p className="muted opp-meta">
            보유 {summary.held}개
            {summary.planned > 0 && ` · 준비 중 ${summary.planned}개`}
            {summary.expiring_soon > 0 && ` · 만료 임박 ${summary.expiring_soon}개`}
            {summary.expired > 0 && ` · 만료됨 ${summary.expired}개`}
          </p>
        </div>
        {editing?.id !== "new" && (
          <Button variant="secondary" writes onClick={() => setEditing({ id: "new", category: "language" })}>
            + 추가
          </Button>
        )}
      </div>

      <p className="muted form-hint">
        자격번호 · 수험번호는 넣지 않아요. 제출할 때는 원본 증빙 파일을 쓰세요. 여기 적은 것은
        기회 화면의 자격 경고 옆에 함께 보입니다.
      </p>

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

      {editing?.id === "new" && (
        <CertificateForm
          initial={{ category: editing.category }}
          working={working}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      )}

      <div className="cert-columns">
        {COLUMNS.map((column) => (
          <div className="cert-column" key={column.key}>
            <div className="cert-column-head">
              <strong>{column.title}</strong>
              <span className="muted">{column.hint}</span>
            </div>

            {data[column.key].length === 0 ? (
              <EmptyState
                title={column.empty}
                actions={[
                  {
                    label: column.add,
                    writes: true,
                    onClick: () => setEditing({ id: "new", category: column.key })
                  }
                ]}
              />
            ) : (
              <ul className="cert-list">
                {data[column.key].map((item) => (
                  <li key={item.id} className={item.status === "planned" ? "cert-item is-planned" : "cert-item"}>
                    {editing?.id === item.id ? (
                      <CertificateForm initial={item} working={working} onSave={save} onCancel={() => setEditing(null)} />
                    ) : (
                      <>
                        <div className="cert-item-head">
                          <strong className="cert-name">{item.name}</strong>
                          {item.score && <span className="cert-score">{item.score}</span>}
                          <ExpiryBadge item={item} />
                        </div>

                        {(item.detail || item.acquired_on || item.issuer) && (
                          <p className="cert-meta">
                            {[
                              item.detail,
                              item.acquired_on && `${dateText(item.acquired_on)} 취득`,
                              item.issuer
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        )}

                        {item.note && <p className="cert-note">{item.note}</p>}

                        <div className="ui-row">
                          <Button variant="quiet" writes onClick={() => setEditing({ id: item.id })}>
                            고치기
                          </Button>
                          <ConfirmButton
                            label="삭제"
                            confirmLabel="정말 삭제"
                            disabled={working}
                            onConfirm={() =>
                              run(async () => {
                                await api.certificates.remove(item.id)
                                return `'${item.name}' 을(를) 지웠어요.`
                              }, "지우지 못했습니다.")
                            }
                          />
                        </div>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export default CertificatesCard
