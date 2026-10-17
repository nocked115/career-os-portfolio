/* 적어 둔 생각 — 고민 · 아이디어 · 메모.
 *
 * 수현: "요즘 생각 고민이나 이런 거, 대학원을 갈지 말지 고민하는 거
 * 얘는 모르잖아."
 *
 * 적어 두는 것만으로는 메모장과 다르지 않다. 이 앱이 더하는 건 **이미
 * 가진 데이터를 그 질문 옆에 놓는 것**이다 — 대학원 고민에는 석박사
 * 요건에 막힌 공고가 몇 건인지를 붙인다.
 */
import { useCallback, useEffect, useState } from "react"

import * as api from "../api"
import { Button, LoadingState } from "./ui"
import "../Thought.css"

const KINDS = [
  { key: "question", label: "아직 못 정한 것" },
  { key: "idea", label: "해 볼 만한 것" },
  { key: "note", label: "적어 둘 것" }
]

function Evidence({ evidence }) {
  if (!evidence) return null

  return (
    <div className="thought-evidence">
      <p className="thought-evidence-head">
        앱이 아는 것 — {evidence.label} <strong>{evidence.postings}건</strong>
        {evidence.organizations.length > 0 &&
          ` · ${evidence.organizations.join(" · ")}`}
      </p>

      {evidence.degree_lines.length > 0 && (
        <ul className="thought-evidence-lines">
          {evidence.degree_lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      {evidence.top_skills.length > 0 && (
        <p className="muted form-hint">
          그 자리들이 요구하는 것 — {evidence.top_skills.join(" · ")}.{" "}
          자세한 것은 {evidence.where}에 있어요.
        </p>
      )}
    </div>
  )
}

function Row({ thought, working, onDecide, onRemove }) {
  const [deciding, setDeciding] = useState(false)
  const [decision, setDecision] = useState("")

  return (
    <li className={`thought-row thought-${thought.status}`}>
      <p className="thought-body">
        <span className="thought-kind">{thought.kind_label}</span>
        {thought.body}
      </p>

      <p className="muted thought-meta">
        {thought.source && `${thought.source} · `}
        {thought.status === "open"
          ? thought.open_days > 0
            ? `${thought.open_days}일째 열려 있어요`
            : "오늘 적었어요"
          : `정함 — ${thought.decision}`}
      </p>

      <Evidence evidence={thought.evidence} />

      {thought.status === "open" ? (
        deciding ? (
          <div className="thought-decide">
            <input
              className="plan-input"
              type="text"
              placeholder="무엇으로 정했나요"
              value={decision}
              onChange={(event) => setDecision(event.target.value)}
            />
            <Button
              writes
              disabled={working || !decision.trim()}
              onClick={() => onDecide(thought, decision.trim())}
            >
              정함으로 남기기
            </Button>
            <Button variant="quiet" onClick={() => setDeciding(false)}>
              취소
            </Button>
          </div>
        ) : (
          <div className="ui-row">
            <Button variant="secondary" onClick={() => setDeciding(true)}>
              정했어요
            </Button>
            <Button variant="quiet" writes disabled={working}
              onClick={() => onRemove(thought)}>
              지우기
            </Button>
          </div>
        )
      ) : (
        <Button variant="quiet" writes disabled={working}
          onClick={() => onDecide(thought, "")}>
          다시 열기
        </Button>
      )}
    </li>
  )
}

export function ThoughtBox() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [kind, setKind] = useState("question")
  const [body, setBody] = useState("")
  const [source, setSource] = useState("")

  const load = useCallback(async () => {
    try {
      setData(await api.thoughts.list())
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action) => {
    try {
      setWorking(true)
      await action()
      await load()
    } finally {
      setWorking(false)
    }
  }

  const add = () => {
    const text = body.trim()
    if (!text) return

    return run(async () => {
      await api.thoughts.create({ kind, body: text, source: source.trim() })
      setBody("")
      setSource("")
    })
  }

  if (loading) return <LoadingState label="적어 둔 것을 불러오는 중…" />

  const thoughts = data?.thoughts ?? []

  return (
    <section className="card thought-box">
      <p className="card-label">생각 · 고민 · 아이디어</p>

      <p className="muted opp-meta">
        세션마다 흩어지는 것을 여기 적어 둬요. 아직 못 정한 것은 닫을
        때까지 남아 있고, 앱이 아는 것 중 닿는 게 있으면 같이 보여줍니다.
      </p>

      <div className="thought-new">
        <div className="plan-minutes">
          {KINDS.map((item) => (
            <button
              key={item.key}
              className={kind === item.key ? "chip chip-on" : "chip"}
              aria-pressed={kind === item.key}
              onClick={() => setKind(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <textarea
          className="plan-input thought-input"
          rows={2}
          placeholder={
            kind === "question"
              ? "예: 대학원을 갈지 말지"
              : kind === "idea"
                ? "예: 장기 취향과 현재 의도를 나눠 보기"
                : "적어 둘 것"
          }
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />

        <div className="ui-row">
          <input
            className="plan-input thought-source"
            type="text"
            placeholder="어디서 나온 생각인가요 (예: 추천시스템 수업)"
            value={source}
            onChange={(event) => setSource(event.target.value)}
          />
          <Button writes disabled={working || !body.trim()} onClick={add}>
            적어 두기
          </Button>
        </div>
      </div>

      {thoughts.length === 0 ? (
        <p className="muted form-hint">아직 적어 둔 것이 없어요.</p>
      ) : (
        <ul className="thought-list">
          {thoughts.map((thought) => (
            <Row
              key={thought.id}
              thought={thought}
              working={working}
              onDecide={(row, decision) =>
                run(() => api.thoughts.decide(row.id, decision))
              }
              onRemove={(row) => run(() => api.thoughts.remove(row.id))}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

export default ThoughtBox
