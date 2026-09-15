import { useEffect, useState } from "react"
import * as api from "../api"

/* Career Agent — 중심이 아니라 동반자.

   DESIGN.md 7장.

   화면 맨 위의 커다란 입력창은 ChatGPT 껍데기처럼 보인다.
   Career OS 의 가치는 대화창이 아니라 판단에 있다. 그래서 Agent 는
   우하단 작은 캡슐이고, 어느 화면이냐에 따라 역할이 바뀐다.

   중요한 제약이 하나 있고, 숨기지 않는다 —
   **이 Agent 에는 LLM 이 없다.** 키워드로 의도를 갈라 저장된 데이터를
   꺼내 보여줄 뿐이다. 그래서 "Learning Tutor" 라고 이름만 붙이고
   개념 설명을 해주는 척하면 안 된다. 화면마다 지금 실제로 답할 수
   있는 것과 없는 것을 같이 적는다. */

/* 이름은 실제로 할 수 있는 일에 맞춘다.

   전에는 "Learning Tutor" 라고 부르면서 "개념 설명은 못 합니다" 를
   같이 적었다. 정직하긴 한데 이름이 기능을 과장한다.
   사용자 입장에서는 "그러면 Tutor 가 아닌데?" 가 자연스러운 반응이다.

   지금 이 Agent 가 하는 일은 안내다 — 저장된 것 중에서 찾아주고,
   다음에 뭘 할지 가리킨다. 그래서 Guide 다.
   나중에 개념을 설명하고 이해 여부를 확인할 수 있게 되면
   그때 Tutor 로 올린다. 그게 제품 신뢰도를 높인다. */

// 작업 화면은 한국어로 부른다 (2026-09-15 결정). 이름은 할 수 있는 일에 맞춘다 —
// 저장된 것을 찾아 보여주는 안내이지, 설명하거나 판단하는 튜터가 아니다.
const ROLES = {
  dashboard: {
    role: "오늘 계획 안내",
    does: "오늘 계획 · 우선순위 · 진행 상황을 찾아 보여줘요",
    can: ["오늘 뭐 해야 돼?", "오늘 60분밖에 없어"]
  },
  why: {
    role: "오늘 계획 안내",
    does: "오늘 계획 · 우선순위 · 진행 상황을 찾아 보여줘요",
    can: ["오늘 뭐 해야 돼?", "오늘 60분밖에 없어"]
  },
  overview: {
    role: "상태 안내",
    does: "오늘 할 일 · 프로젝트 진행률을 찾아 보여줘요",
    can: ["오늘 뭐 해야 돼?", "프로젝트 진행률"]
  },
  calendar: {
    role: "시간 안내",
    does: "오늘 쓸 수 있는 시간으로 계획을 보여줘요",
    can: ["오늘 뭐 해야 돼?", "오늘 60분밖에 없어"]
  },
  learning: {
    role: "학습 안내",
    does: "다음 학습 단계 · 우선순위를 찾아 보여줘요",
    can: ["지금 어떤 공부를 먼저 해야 돼?", "프로젝트 진행률"]
  },
  library: {
    role: "학습 안내",
    does: "다음 학습 단계 · 우선순위를 찾아 보여줘요",
    can: ["지금 어떤 공부를 먼저 해야 돼?", "프로젝트 진행률"]
  },
  projects: {
    role: "프로젝트 안내",
    does: "진행 중인 것 · 남은 것을 찾아 보여줘요",
    can: ["프로젝트 진행률", "오늘 뭐 해야 돼?"]
  },
  opportunities: {
    role: "기회 안내",
    does: "저장된 공고를 찾아 보여줘요",
    can: ["채용공고 보여줘", "지금 어떤 공부를 먼저 해야 돼?"]
  },
  proof: {
    role: "경험 안내",
    does: "프로젝트 진행과 오늘 할 일을 찾아 보여줘요",
    can: ["프로젝트 진행률", "오늘 뭐 해야 돼?"]
  },
  applications: {
    role: "지원서 안내",
    does: "저장된 공고를 찾아 보여줘요",
    can: ["채용공고 보여줘"]
  },
  review: {
    role: "회고 안내",
    does: "프로젝트 진행률 · 오늘 할 일을 찾아 보여줘요",
    can: ["프로젝트 진행률", "오늘 뭐 해야 돼?"]
  }
}

const FALLBACK = ROLES.dashboard

function summarize(response) {
  /* 응답을 한 줄로 요약한다. 동반자는 작아야 하므로
     원본 데이터를 그대로 펼치지 않는다. */
  const result = response.result

  if (response.intent === "today" && result?.actions) {
    return {
      head: `집중 · ${result.focus_skill}`,
      lines: result.actions.map(
        (action) => `${action.title} — ${action.minutes}분`
      ),
      foot: `합계 ${result.total_minutes}분`
    }
  }

  if (response.intent === "learning" && Array.isArray(result)) {
    return {
      head: "학습 우선순위",
      lines: result
        .slice(0, 3)
        // 원시 점수(87점)는 무엇의 점수인지 말할 수 없어 보이지 않는다.
        .map((item, index) =>
          [
            `${index + 1}. ${item.skill}`,
            item.my_level != null && `레벨 ${item.my_level}/4`,
            item.total_demand > 0 && `기회 ${item.total_demand}건 중 ${item.demand_count}건`
          ]
            .filter(Boolean)
            .join(" · ")
        ),
      foot: null
    }
  }

  if (response.intent === "jobs" && Array.isArray(result)) {
    return {
      head: `공고 ${result.length}건`,
      lines: result
        .slice(0, 3)
        .map((job) => `${job.title} · ${job.company}`),
      foot: null
    }
  }

  if (response.intent === "projects" && Array.isArray(result)) {
    return {
      head: `진행 중 ${result.length}건`,
      lines: result
        .slice(0, 3)
        .map((item) => `${item.name} · ${item.progress_percent}%`),
      foot: null
    }
  }

  return {
    head: null,
    lines: [
      typeof result === "string"
        ? "어떤 동작을 실행할지 알아내지 못했습니다."
        : "결과를 받았습니다."
    ],
    foot: null
  }
}

function CareerCompanion({ view, onChanged }) {
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState("")
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const config = ROLES[view] ?? FALLBACK

  // 화면이 바뀌면 이전 답변을 지운다.
  // Career Planner 가 준 답이 Writing Assistant 라벨 아래 남아 있으면
  // 그 역할이 답한 것처럼 읽힌다.
  useEffect(() => {
    setResponse(null)
    setError(null)
    setMessage("")
  }, [view])

  // 열면 입력 칸으로, Esc 로 닫는다.
  useEffect(() => {
    if (!open) return undefined

    document.getElementById("companion-input")?.focus()

    const onKey = (event) => {
      if (event.key === "Escape") setOpen(false)
    }

    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open])

  const ask = async (text) => {
    const question = (text ?? message).trim()
    if (!question) return

    try {
      setLoading(true)
      setError(null)
      setResponse(null)

      const data = await api.sendAgentMessage(question)
      setResponse(data)

      if (data.intent === "automation") {
        onChanged?.()
      }
    } catch (askError) {
      console.error("Career Agent failed:", askError)
      setError("안내에 연결하지 못했어요. 잠시 뒤 다시 물어봐 주세요.")
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        className="companion-pill"
        onClick={() => setOpen(true)}
      >
        <span className="companion-spark" aria-hidden="true">✦</span>
        <span>{config.role}</span>
        <span className="companion-cta">물어보기</span>
      </button>
    )
  }

  const summary = response ? summarize(response) : null

  return (
    <div className="companion" role="dialog" aria-label={config.role}>
      <div className="companion-head">
        <span>
          <span className="companion-spark" aria-hidden="true">✦</span>
          {config.role}
        </span>
        <button
          className="companion-close"
          onClick={() => setOpen(false)}
          aria-label="닫기"
        >
          ✕
        </button>
      </div>

      <div className="companion-body">
        <div className="companion-suggestions">
          {config.can.map((question) => (
            <button
              key={question}
              disabled={loading}
              onClick={() => {
                setMessage(question)
                ask(question)
              }}
            >
              {question}
            </button>
          ))}
        </div>

        <div className="companion-input-row">
          <input
            id="companion-input"
            aria-label={`${config.role}에게 물어보기`}
            value={message}
            placeholder="물어보기"
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") ask()
            }}
          />
          <button disabled={loading} onClick={() => ask()}>
            {loading ? "..." : "→"}
          </button>
        </div>

        {error && <p className="companion-error">{error}</p>}

        {summary && (
          <div className="companion-answer">
            {summary.head && <strong>{summary.head}</strong>}
            <ul>
              {summary.lines.map((line, index) => (
                <li key={`${line}-${index}`}>{line}</li>
              ))}
            </ul>
            {summary.foot && (
              <p className="companion-foot">{summary.foot}</p>
            )}
          </div>
        )}

        {/* 이름이 이미 능력에 맞으므로 "못 합니다" 를 나열하지 않는다.
            대신 여기서 무엇을 할 수 있는지 한 줄로 적는다. */}
        <p className="companion-limit">{config.does}</p>
      </div>
    </div>
  )
}

export default CareerCompanion
