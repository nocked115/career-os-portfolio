import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import ApplicationWorkspace from "./ApplicationWorkspace"
import {
  ddayText,
  ddayTone,
  initialOf,
  savedDate,
  statusLabel,
  tileTone
} from "./applicationLabels"
import "../Applications.css"

/* Applications — "그래서 지금 무엇을 해야 하지?"

   전에는 상태 칩과 "열기" 뿐이라, 무엇을 할지는 지원서를 하나씩 열어
   봐야 알았다. 이제 맨 위에 가장 먼저 할 일 하나를 두고, 목록의 줄마다
   마감 · 매칭 · 자소서 진행 · 다음 행동을 보인다.

   무엇을 할지는 서버(/applications/board)가 정한다. 상태 전이 규칙과
   같은 곳이어야 목록과 Workspace 가 다른 말을 하지 않는다. */

const BEFORE = ["interested", "preparing", "ready"]
const AFTER = ["applied", "document_pass", "interview"]

const FILTERS = [
  { key: "active", label: "진행 중", test: (card) => !card.is_terminal },
  { key: "before", label: "지원 전", test: (card) => BEFORE.includes(card.status) },
  { key: "after", label: "지원 후", test: (card) => AFTER.includes(card.status) },
  { key: "closed", label: "끝남", test: (card) => card.is_terminal },
  { key: "all", label: "전체", test: () => true }
]

const ACTION_ICONS = {
  write: "✎",
  revise: "✎",
  add_questions: "+",
  move: "→",
  submit: "↗",
  overdue: "!",
  wait: "…",
  interview: "◎"
}

function NextAction({ next, cards, beforeApplying, onOpen }) {
  if (!next) {
    let body = "지원서를 열어 마감일과 자기소개서 문항을 등록하세요."

    if (cards.length === 0) {
      body = "Opportunities 에서 공고를 고르고 지원서를 만드세요."
    } else if (beforeApplying === 0) {
      body = "지원 전인 지원서가 없습니다. 결과가 나오면 상태를 바꾸세요."
    }

    return (
      <div className="apl-next apl-next-empty">
        <span className="apl-next-icon" aria-hidden="true">
          ?
        </span>
        <span className="apl-next-body">
          <span className="apl-next-key">다음 행동</span>
          <strong>아직 다음 행동을 정할 정보가 부족합니다.</strong>
          <span className="apl-next-meta">{body}</span>
          {cards.length === 0 && (
            <a className="apl-link" href="#/opportunities">
              공고 보러 가기 →
            </a>
          )}
        </span>
      </div>
    )
  }

  return (
    <button className="apl-next" onClick={() => onOpen(next.application_id)}>
      <span className={`apl-next-icon kind-${next.kind}`} aria-hidden="true">
        {ACTION_ICONS[next.kind] ?? "→"}
      </span>

      <span className="apl-next-body">
        <span className="apl-next-key">다음 행동</span>
        <strong>{next.label}</strong>
        <span className="apl-next-meta">
          {next.title}
          {next.organization && ` · ${next.organization}`}
          {next.days_left != null && ` · ${ddayText(next.days_left)}`}
        </span>
      </span>

      <span className="apl-next-go" aria-hidden="true">
        →
      </span>
    </button>
  )
}

function ApplicationRow({ card, urgentDays, onOpen }) {
  const { letter, match } = card
  const name = card.organization || card.title
  const percent = letter.total
    ? Math.round((letter.answered / letter.total) * 100)
    : 0

  return (
    <button
      className={card.is_terminal ? "apl-row apl-row-closed" : "apl-row"}
      onClick={() => onOpen(card.id)}
    >
      <span className={`apl-tile tile-${tileTone(name)}`} aria-hidden="true">
        {initialOf(name)}
      </span>

      <span className="apl-row-main">
        <strong className="apl-row-title">{card.title}</strong>
        <span className="apl-row-org">
          {card.organization || "기관 미상"}
          {card.target === "legacy_job" && " · 예전 방식(Job)"}
        </span>
      </span>

      <span className="apl-row-badges">
        <span className={`apl-dday dday-${ddayTone(card.days_left, urgentDays)}`}>
          {ddayText(card.days_left)}
        </span>
        <span className={`apl-status st-${card.status}`}>
          {statusLabel(card.status)}
        </span>
      </span>

      <span className="apl-row-metrics">
        <span
          className="apl-metric"
          title={
            match.available
              ? `요구 역량 ${match.total}개 중 ${match.have}개 보유`
              : match.reason
          }
        >
          <span className="apl-metric-key">매칭</span>
          {match.available ? (
            <strong>
              {match.have}/{match.total}
            </strong>
          ) : (
            <span className="apl-metric-none">분석 불가</span>
          )}
        </span>

        <span className="apl-metric">
          <span className="apl-metric-key">자소서</span>
          {letter.total ? (
            <>
              <strong>
                {letter.answered}/{letter.total}
              </strong>
              <span className="apl-bar" aria-hidden="true">
                <span style={{ width: `${percent}%` }} />
              </span>
            </>
          ) : (
            <span className="apl-metric-none">문항 없음</span>
          )}
        </span>
      </span>

      <span className="apl-row-next">
        {card.next_action ? (
          <>
            <span className="apl-row-next-key">다음 행동</span>
            <span className="apl-row-next-label">{card.next_action.label}</span>
          </>
        ) : (
          <span className="apl-row-next-label apl-quiet">끝난 지원서</span>
        )}
      </span>

      <span className="apl-row-updated">수정 {savedDate(card.updated_at)}</span>
    </button>
  )
}

function ApplicationsPage({ onChanged, openId, onOpen, onClose }) {
  const [board, setBoard] = useState(null)
  const [opportunities, setOpportunities] = useState([])
  const [filter, setFilter] = useState("active")
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setError(null)

      const [boardData, opportunityList] = await Promise.all([
        api.applications.board(),
        api.opportunities.list()
      ])

      setBoard(boardData)
      setOpportunities(opportunityList)
    } catch (loadError) {
      console.error("Failed to load applications:", loadError)
      setError("지원서를 불러오지 못했습니다. 잠시 뒤 다시 열어 주세요.")
    } finally {
      setLoading(false)
    }
  }, [])

  // Workspace 에서 돌아오면 다시 읽는다. 거기서 쓴 글이 목록에 반영돼야 한다.
  useEffect(() => {
    if (!openId) load()
  }, [load, openId])

  const createFor = async (opportunityId) => {
    try {
      setWorking(true)
      setError(null)
      await api.applications.create({ opportunity_id: Number(opportunityId) })
      await load()
      onChanged?.()
    } catch (createError) {
      console.error("Failed to create application:", createError)
      setError("지원서를 만들지 못했습니다. 잠시 뒤 다시 시도해 주세요.")
    } finally {
      setWorking(false)
    }
  }

  if (openId) {
    return (
      <ApplicationWorkspace
        applicationId={openId}
        onBack={onClose}
        onChanged={onChanged}
      />
    )
  }

  if (loading) {
    return (
      <div className="card">
        <p className="muted">지원서를 불러오는 중…</p>
      </div>
    )
  }

  if (!board) {
    return (
      <div className="card">
        <p className="agent-error">{error}</p>
        <button className="chip" onClick={load}>
          다시 불러오기
        </button>
      </div>
    )
  }

  const cards = board.applications
  const { summary } = board

  const linked = new Set(cards.map((card) => card.opportunity_id))
  const available = opportunities.filter((item) => !linked.has(item.id))

  const active = FILTERS.find((item) => item.key === filter)
  const visible = cards.filter(active.test)

  return (
    <div className="applications-page apl">
      <section className="card apl-summary">
        <div className="apl-summary-intro">
          <p className="card-label">이번 주 지원 준비</p>
          <h2 className="apl-title">
            {summary.before_applying > 0
              ? `지원 전인 지원서 ${summary.before_applying}건을 준비하고 있어요`
              : "지금 준비 중인 지원서가 없어요"}
          </h2>
        </div>

        <div className="apl-stats">
          <div className="apl-stat">
            <span className="apl-stat-key">마감 임박</span>
            <strong className="apl-num apl-num-amber">
              {summary.urgent}
              <small>건</small>
            </strong>
            <span className="apl-stat-hint">{board.urgent_days}일 안에 마감</span>
          </div>

          <div className="apl-stat">
            <span className="apl-stat-key">작성 중</span>
            <strong className="apl-num apl-num-blue">
              {summary.writing}
              <small>건</small>
            </strong>
            <span className="apl-stat-hint">문항 일부만 씀</span>
          </div>
        </div>

        <NextAction
          next={summary.next}
          cards={cards}
          beforeApplying={summary.before_applying}
          onOpen={onOpen}
        />
      </section>

      <section className="card apl-listcard">
        <div className="apl-list-head">
          <div className="apl-list-title">
            <p className="card-label">지원서</p>
            <span className="apl-count">{cards.length}</span>
          </div>

          {available.length > 0 && (
            <label className="apl-create">
              <span className="sr-only">공고를 골라 지원서 만들기</span>
              <select
                className="path-select"
                defaultValue=""
                disabled={working}
                onChange={(event) => {
                  if (event.target.value) createFor(event.target.value)
                  event.target.value = ""
                }}
              >
                <option value="">+ 공고를 골라 지원서 만들기</option>
                {available.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                    {item.organization ? ` · ${item.organization}` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <div className="apl-filters" role="tablist" aria-label="지원서 거르기">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={filter === item.key}
              className={filter === item.key ? "chip chip-on" : "chip"}
              onClick={() => setFilter(item.key)}
            >
              {item.label} {cards.filter(item.test).length}
            </button>
          ))}
        </div>

        {error && <p className="agent-error">{error}</p>}

        {visible.length === 0 ? (
          <div className="apl-empty">
            {cards.length === 0 ? (
              <>
                <strong>아직 지원서가 없습니다.</strong>
                <span>
                  Opportunities 에서 공고를 계획에 추가하거나, 위에서 공고를
                  골라 바로 만드세요.
                </span>
                <a className="apl-cta" href="#/opportunities">
                  공고 보러 가기
                </a>
              </>
            ) : (
              <>
                <strong>이 조건에 맞는 지원서가 없습니다.</strong>
                <button className="chip" onClick={() => setFilter("all")}>
                  전체 보기
                </button>
              </>
            )}
          </div>
        ) : (
          <ul className="apl-list">
            {visible.map((card) => (
              <li key={card.id}>
                <ApplicationRow
                  card={card}
                  urgentDays={board.urgent_days}
                  onOpen={onOpen}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

export default ApplicationsPage
