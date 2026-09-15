import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { externalHref } from "../safeUrl"
import OpportunityMap from "./OpportunityMap"
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  Notice,
  StatusBadge
} from "./ui"
import { ddayLabel } from "../format"
import { deadlineText, statusLabel } from "./applicationLabels"
import "../Learning.css"
import "../Evidence.css"
import "../Opportunity.css"
import "../Certificates.css"

/* 기회 — 많이 보여주는 곳이 아니라, 어떤 것을 고를지 돕는 곳.

   맨 위에 "지원할지 정할 것" 하나. 고른 기회는 다음 순서로 설명한다:
   고려할 이유 → 필요한 역량 → 자격 확인 → 준비 비용 · 마감 → 다음 행동.

   공고는 붙여넣어 가져온다. 앱은 공고 사이트를 열지 않는다(약관).
   붙여넣은 글에서 칸을 채운 미리보기를 보여주고, 사람이 고친 뒤 저장한다.

   "지금은 아닌 것" 은 사용자를 평가하는 말이 아니다. 집중을 지키려고
   아래로 내렸다는 뜻이다. 보류와 관심 없음은 사용자가 정한다. */

const TYPE_LABELS = {
  job: "채용 · 인턴",
  competition: "공모전",
  external_activity: "대외활동",
  job_event: "채용 행사"
}

const TABS = [
  { key: "all", label: "모든 종류" },
  { key: "job", label: "채용 · 인턴" },
  { key: "competition", label: "공모전" },
  { key: "external_activity", label: "대외활동" },
  { key: "job_event", label: "채용 행사" }
]

// 칸은 서버가 정한다 (match.lane). 지원서를 철회했거나 마감이 지난 기회가
// 검토 목록에 "지금 할 만해요" 로 남아 있던 것을 막는다.
const VIEWS = [
  { key: "review", label: "검토 중" },
  { key: "applied", label: "지원 중" },
  { key: "on_hold", label: "보류" },
  { key: "not_interested", label: "관심 없음" },
  { key: "archived", label: "보관함" },
  { key: "all", label: "전체" }
]

const VERDICT = {
  recommended: { label: "지금 할 만해요", tone: "ok" },
  consider: { label: "고려해 볼 만해요", tone: "action" },
  skip: { label: "지금은 아니에요", tone: "neutral" }
}

const DEADLINE_STATE = {
  comfortable: "여유 있음",
  workable: "할 만함",
  tight: "빠듯함",
  unrealistic: "지금 일정으로는 어려움",
  passed: "마감 지남",
  no_deadline: "마감일 없음"
}

// 서버 배점(services/opportunity.py WEIGHT_*)과 같아야 한다.
const BREAKDOWN = [
  ["relevance", "관련성 — 지금 우선순위 높은 스킬을 요구하는가", 40],
  ["readiness", "준비도 — 요구 스킬 중 이미 가진 비율", 30],
  ["portfolio_value", "포트폴리오 — 증거로 남는가", 15],
  ["deadline", "마감 — 일정이 현실적인가", 15]
]

const SOURCE_LABELS = {
  saramin: "사람인",
  worknet: "고용24"
}

const TREND_TEXT = {
  up: ["↑", "늘었음"],
  down: ["↓", "줄었음"],
  flat: ["→", "변화 없음"],
  unknown: ["·", "비교할 기록 없음"]
}

function ddayTone(days) {
  if (days == null || days < 0) return "neutral"
  return days <= 7 ? "warn" : "neutral"
}

/* 자격 경고 옆 "내 어학 · 자격". 충족 여부는 판단하지 않고 나란히 둔다. */
function MyCertificates({ groups }) {
  if (!groups?.length) return null

  return groups.map((group) => (
    <p className="opp-mine" key={group.flag_kind}>
      <strong>내 {group.category_label}</strong>
      {group.certificates.length > 0 ? (
        group.certificates
          .map(
            (item) =>
              `${item.name}${item.score ? ` ${item.score}` : ""}${
                item.expiry_state === "expired"
                  ? " (만료됨)"
                  : item.expiry_state === "soon"
                    ? ` (만료 ${item.days_to_expiry}일 전)`
                    : ""
              }`
          )
          .join(" · ")
      ) : (
        <>
          등록한 것이 없어요 —{" "}
          <a className="td-link" href="#/experience/certificates">
            추가하기
          </a>
        </>
      )}
    </p>
  ))
}

/* ---------- 공고 붙여넣기 ---------- */

function FoundBadge({ field }) {
  return field.found ? (
    <StatusBadge tone="ok">찾음</StatusBadge>
  ) : (
    <StatusBadge tone="warn">못 찾음</StatusBadge>
  )
}

function PasteImport({ working, onSave, onCancel, onError }) {
  const [text, setText] = useState("")
  const [url, setUrl] = useState("")
  const [preview, setPreview] = useState(null)
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)

  const analyze = async () => {
    try {
      setBusy(true)
      const result = await api.opportunities.parse(text, url)
      setPreview(result)
      setDraft({
        title: result.title.value,
        organization: result.organization.value,
        opportunity_type: result.opportunity_type.value,
        employment_type: result.employment_type.value,
        location: result.location.value,
        deadline_date: result.deadline.value ? result.deadline.value.slice(0, 10) : "",
        deadline_time: result.deadline.value ? result.deadline.value.slice(11, 16) : "23:59",
        estimated_hours: ""
      })
    } catch (failure) {
      console.error("Failed to parse posting:", failure)
      onError(failure?.detail || "공고 글을 분석하지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  const set = (key, value) => setDraft((current) => ({ ...current, [key]: value }))

  if (!preview) {
    return (
      <div className="opp-paste">
        <label className="learn-field">
          <span>공고 본문 붙여넣기</span>
          <textarea
            className="learn-textarea opp-paste-text"
            rows={10}
            placeholder="공고 페이지에서 본문을 전체 선택(⌘A)해 복사(⌘C)한 뒤 여기에 붙여넣으세요."
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>공고 링크 (선택)</span>
          <input
            className="agent-input"
            placeholder="https://…"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </label>

        <p className="muted form-hint">
          앱은 링크를 열지 않고 저장만 합니다. 채용 사이트 대부분이 자동 수집을 약관으로
          막기 때문에, 직접 읽은 글만 다룹니다.
        </p>

        <div className="ui-row">
          <Button disabled={busy || !text.trim()} onClick={analyze}>
            {busy ? "분석하는 중…" : "분석하기"}
          </Button>
          <Button variant="quiet" onClick={onCancel}>
            취소
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="opp-paste">
      <p className="opp-block-title">미리보기 — 틀린 칸은 고친 뒤 저장하세요</p>

      {preview.requirement_flags.length > 0 && (
        <div className="opp-flags" role="note">
          <p className="opp-block-title">⚠ 지원 자격을 먼저 확인하세요</p>
          <ul>
            {preview.requirement_flags.map((flag) => (
              <li key={`${flag.kind}-${flag.line}`}>
                <strong>{flag.label}</strong> {flag.line}
              </li>
            ))}
          </ul>
          <MyCertificates groups={preview.my_certificates} />
          <p className="form-hint">충족하는지는 앱이 판단하지 않아요. 내 조건과 비교해 주세요.</p>
        </div>
      )}

      <div className="prj-editor-grid">
        <label className="learn-field prj-wide">
          <span className="opp-field-head">
            제목 <FoundBadge field={preview.title} />
          </span>
          <input className="agent-input" value={draft.title} onChange={(event) => set("title", event.target.value)} />
        </label>

        <label className="learn-field">
          <span className="opp-field-head">
            기관 <FoundBadge field={preview.organization} />
          </span>
          <input
            className="agent-input"
            value={draft.organization}
            onChange={(event) => set("organization", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>종류</span>
          <select
            className="path-select"
            value={draft.opportunity_type}
            onChange={(event) => set("opportunity_type", event.target.value)}
          >
            {Object.entries(TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <label className="learn-field">
          <span>고용 형태</span>
          <input
            className="agent-input"
            value={draft.employment_type}
            onChange={(event) => set("employment_type", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>근무지</span>
          <input className="agent-input" value={draft.location} onChange={(event) => set("location", event.target.value)} />
        </label>

        <label className="learn-field">
          <span className="opp-field-head">
            마감일 <FoundBadge field={preview.deadline} />
          </span>
          <input
            className="plan-input"
            type="date"
            value={draft.deadline_date}
            onChange={(event) => set("deadline_date", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>마감 시각</span>
          <input
            className="plan-input"
            type="time"
            value={draft.deadline_time}
            onChange={(event) => set("deadline_time", event.target.value)}
          />
        </label>

        <label className="learn-field">
          <span>예상 준비 시간(시간)</span>
          <input
            className="plan-input"
            type="number"
            min="0"
            value={draft.estimated_hours}
            onChange={(event) => set("estimated_hours", event.target.value)}
          />
        </label>
      </div>

      {(preview.deadline.evidence || preview.deadline.note) && (
        <p className="opp-evidence">
          {preview.deadline.evidence && <>마감 근거: &ldquo;{preview.deadline.evidence}&rdquo; </>}
          {preview.deadline.note && <span>— {preview.deadline.note}</span>}
        </p>
      )}

      <div className="opp-block">
        <p className="opp-block-title">찾은 요구 스킬 {preview.skills.length}개</p>
        {preview.skills.length > 0 ? (
          <div className="prj-skills">
            {preview.skills.map((skill) => (
              <span className="lib-chip" key={skill.id}>
                {skill.name}
              </span>
            ))}
          </div>
        ) : (
          <p className="muted">등록된 스킬을 찾지 못했어요.</p>
        )}
      </div>

      {preview.qualifications.length > 0 && (
        <details className="opp-breakdown-box" open>
          <summary>찾은 지원 자격 {preview.qualifications.length}줄</summary>
          <ul>
            {preview.qualifications.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}

      {preview.warnings.length > 0 && (
        <ul className="opp-warnings">
          {preview.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="ui-row">
        <Button
          writes
          disabled={working || !draft.title.trim()}
          onClick={() =>
            onSave({
              opportunity_type: draft.opportunity_type,
              title: draft.title.trim(),
              organization: draft.organization.trim(),
              employment_type: draft.employment_type.trim(),
              location: draft.location.trim(),
              source: "manual",
              source_url: url.trim(),
              description: text,
              deadline: draft.deadline_date
                ? `${draft.deadline_date}T${draft.deadline_time || "23:59"}:00`
                : null,
              estimated_hours: draft.estimated_hours ? Number(draft.estimated_hours) : null
            })
          }
        >
          이대로 저장
        </Button>
        <Button variant="secondary" onClick={() => setPreview(null)}>
          본문 다시 고치기
        </Button>
        <Button variant="quiet" onClick={onCancel}>
          취소
        </Button>
      </div>
    </div>
  )
}

/* ---------- 목록 · 상세 ---------- */

function OpportunityRow({ match, selected, onSelect }) {
  const verdict = VERDICT[match.recommendation] ?? VERDICT.skip
  const archived = match.lane === "archived"

  return (
    <button
      className={`${selected ? "split-row split-row-on opp-row" : "split-row opp-row"} opp-type-${match.opportunity_type}`}
      aria-pressed={selected}
      onClick={onSelect}
    >
      <div className="split-row-body">
        {/* 종류를 색으로 먼저 구분한다 — "전체" 에서 채용 · 공모전 · 행사가 섞여도 한눈에. */}
        <span className={`opp-type-chip opp-type-chip-${match.opportunity_type}`}>
          {TYPE_LABELS[match.opportunity_type] ?? "기회"}
        </span>
        <strong>{match.title}</strong>
        <span className="muted">
          {match.organization || "기관 미상"} · {TYPE_LABELS[match.opportunity_type] ?? "기회"}
        </span>
        <span className="opp-row-badges">
          {match.application && (
            <StatusBadge tone="action">지원서 · {statusLabel(match.application.status)}</StatusBadge>
          )}
          {match.lane === "on_hold" && <StatusBadge tone="warn">보류</StatusBadge>}
          {match.lane === "not_interested" && <StatusBadge>관심 없음</StatusBadge>}
          {archived && <StatusBadge>보관 · {match.archive_reason}</StatusBadge>}
          {!archived && match.requirement_flags?.length > 0 && (
            <StatusBadge tone="warn">자격 확인</StatusBadge>
          )}
        </span>
      </div>

      <span className="opp-row-score" title={`매칭 점수 ${match.match_score} / 100 · ${verdict.label}`}>
        <strong className={archived ? "opp-num-neutral" : `opp-num-${verdict.tone}`}>
          {match.match_score}
        </strong>
        <small>/100</small>
      </span>

      {/* 끝난 기회에 "오늘 마감" 을 띄우면 아직 할 일처럼 읽힌다. */}
      {archived ? (
        <StatusBadge>{match.archive_reason}</StatusBadge>
      ) : (
        <StatusBadge tone={ddayTone(match.days_until_deadline)}>
          {ddayLabel(match.days_until_deadline)}
        </StatusBadge>
      )}
    </button>
  )
}

function OpportunityDetail({ match, working, onCreateApplication, onAddToPlan, onStatus, onRemove }) {
  const verdict = VERDICT[match.recommendation] ?? VERDICT.skip
  const href = externalHref(match.source_url)
  const parked = match.lane === "on_hold" || match.lane === "not_interested"
  const archived = match.lane === "archived"
  const flags = match.requirement_flags ?? []
  const [confirmRemove, setConfirmRemove] = useState(false)

  return (
    <section className="card opp-detail">
      <div className="opp-title-row">
        <div>
          <p className="card-label">{TYPE_LABELS[match.opportunity_type] ?? "기회"}</p>
          <strong className="opp-title">{match.title}</strong>
          <p className="muted opp-meta">
            {match.organization || "기관 미상"}
            {SOURCE_LABELS[match.source] && <> · 출처 {SOURCE_LABELS[match.source]}</>}
          </p>
        </div>

        <div className="opp-score-box">
          <strong>{match.match_score}</strong>
          <span>/ 100 매칭</span>
        </div>
      </div>

      <div className="ui-row">
        <StatusBadge tone={verdict.tone}>{verdict.label}</StatusBadge>
        {href && (
          <a className="ui-btn ui-btn-secondary" href={href} target="_blank" rel="noopener noreferrer">
            공고 원문 ↗
          </a>
        )}
      </div>

      <div className="opp-block">
        <p className="opp-block-title">이 기회를 고려할 이유</p>
        <ul className="opp-reasons">
          {match.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </div>

      <div className="opp-block">
        <p className="opp-block-title">필요한 역량 · 나와의 연결</p>
        {match.required_skills.length > 0 ? (
          <>
            <div className="prj-skills">
              {match.required_skills.map((name) => {
                const have = match.have_skills.includes(name)
                return (
                  <span className={have ? "lib-chip opp-have" : "lib-chip opp-gap"} key={name}>
                    {have ? "✓" : "!"} {name}
                  </span>
                )
              })}
            </div>
            <p className="muted form-hint">
              요구 스킬 {match.skills_required}개 중 {match.skills_i_have}개 보유 (레벨 1 이상). 공부 ·
              프로젝트 · 경험이 어디까지 찼는지는 아래 지도에 있어요.
            </p>
          </>
        ) : (
          <p className="muted">연결된 스킬이 없어 판단할 수 없어요. 아래 지도에서 스킬을 확인하세요.</p>
        )}
      </div>

      {flags.length > 0 && (
        <div className="opp-flags" role="note">
          <p className="opp-block-title">⚠ 지원 자격을 확인하세요</p>
          <ul>
            {flags.map((flag) => (
              <li key={`${flag.kind}-${flag.line}`}>
                <strong>{flag.label}</strong> {flag.line}
              </li>
            ))}
          </ul>
          <MyCertificates groups={match.my_certificates} />
          <p className="form-hint">충족하는지는 앱이 판단하지 않아요. 공고 원문과 내 조건을 비교해 주세요.</p>
        </div>
      )}

      <div className="opp-facts">
        <div>
          <span>예상 준비 비용</span>
          <strong>{match.estimated_hours != null ? `약 ${match.estimated_hours}시간` : "모름"}</strong>
          <small>
            {match.hours_per_day != null
              ? `마감까지 하루 ${match.hours_per_day}시간`
              : "예상 시간을 적으면 하루 몇 시간인지 계산해요"}
          </small>
        </div>
        <div>
          <span>마감</span>
          <strong>{ddayLabel(match.days_until_deadline)}</strong>
          <small>
            {DEADLINE_STATE[match.deadline_state] ?? ""}
            {match.deadline ? ` · ${deadlineText(match.deadline)}` : ""}
          </small>
        </div>
      </div>

      <details className="opp-breakdown-box">
        <summary>매칭 점수 구성 보기</summary>
        <ul>
          {BREAKDOWN.map(([key, label, max]) => (
            <li key={key}>
              {label} <strong>{match.breakdown[key]}</strong> / {max}
            </li>
          ))}
        </ul>
        <p className="form-hint">네 칸의 합이 매칭 점수예요. 70 이상이면 할 만함, 40 이상이면 고려.</p>
      </details>

      <div className="opp-block">
        <p className="opp-block-title">다음 행동</p>
        <div className="ui-row">
          {match.application ? (
            <a className="ui-btn ui-btn-primary" href={`#/applications/${match.application.id}`}>
              지원서 열기 · {statusLabel(match.application.status)}
            </a>
          ) : (
            <Button writes disabled={working} onClick={onCreateApplication}>
              지원서 만들기
            </Button>
          )}
          <Button variant="secondary" writes disabled={working} onClick={onAddToPlan}>
            오늘 계획에 준비 추가
          </Button>
        </div>
        <div className="ui-row">
          {archived ? (
            <>
              {/* 직접 닫은 것만 되돌릴 수 있다. 마감 지남 · 지원서 철회는 되돌려도 다시 보관함으로 온다. */}
              {match.archive_reason === "직접 닫음" && (
                <Button variant="secondary" writes disabled={working} onClick={() => onStatus("interested")}>
                  검토로 되돌리기
                </Button>
              )}
              {confirmRemove ? (
                <>
                  <Button
                    variant="quiet"
                    writes
                    disabled={working}
                    onClick={async () => {
                      await onRemove()
                      setConfirmRemove(false)
                    }}
                  >
                    정말 완전히 삭제
                  </Button>
                  <Button variant="quiet" onClick={() => setConfirmRemove(false)}>
                    취소
                  </Button>
                </>
              ) : (
                <Button variant="quiet" writes disabled={working} onClick={() => setConfirmRemove(true)}>
                  완전히 삭제
                </Button>
              )}
            </>
          ) : parked ? (
            <Button variant="secondary" writes disabled={working} onClick={() => onStatus("interested")}>
              다시 검토하기
            </Button>
          ) : (
            <>
              <Button variant="quiet" writes disabled={working} onClick={() => onStatus("on_hold")}>
                지금은 보류
              </Button>
              <Button variant="quiet" writes disabled={working} onClick={() => onStatus("not_interested")}>
                관심 없음
              </Button>
              <Button variant="quiet" writes disabled={working} onClick={() => onStatus("closed")}>
                보관함으로
              </Button>
            </>
          )}
        </div>
        <p className="muted form-hint">
          {archived
            ? match.application
              ? "지원서가 달린 기회는 지원 기록 때문에 삭제되지 않아요. 보관함에 남겨 두면 목록과 계획에는 나오지 않아요."
              : "완전히 삭제하면 되돌릴 수 없어요. 오늘 계획에 올라가 있던 할 일도 함께 치워요."
            : "보류 · 관심 없음 · 보관함으로 옮기면 오늘 마감 띠와 계획에서 빠지고, 이 목록의 해당 칸으로 갑니다."}
        </p>
      </div>
    </section>
  )
}

function OpportunitiesPage() {
  const [tab, setTab] = useState("all")
  const [view, setView] = useState("review")
  const [selectedId, setSelectedId] = useState(null)
  const [showImport, setShowImport] = useState(false)

  const [matches, setMatches] = useState([])
  const [signals, setSignals] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)

      const [scored, market] = await Promise.all([
        api.opportunities.matches(),
        api.marketSignals.get(6)
      ])

      setMatches(scored.matches)
      setSignals(market)
    } catch (failure) {
      console.error("Failed to load opportunities:", failure)
      setLoadError("기회를 불러오지 못했습니다.")
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
      console.error("Opportunity action failed:", failure)
      setError(failure?.detail || fallback)
      return false
    } finally {
      setWorking(false)
    }
  }

  const collect = () =>
    run(async () => {
      await api.opportunities.collect()
      return "연결된 수집원에서 가져왔어요."
    }, "수집하지 못했습니다.")

  const savePosting = (body) =>
    run(async () => {
      const created = await api.opportunities.create(body)
      setShowImport(false)
      setView("review")
      setTab("all")
      setSelectedId(created.id)

      return created.skills.length > 0
        ? `'${created.title}' 을(를) 저장했어요. 연결한 스킬 · ${created.skills.map((skill) => skill.name).join(" · ")}`
        : `'${created.title}' 을(를) 저장했어요. 등록된 스킬을 찾지 못해 수요 계산에서 분모만 늘어요 — 아래 지도에서 스킬을 확인하세요.`
    }, "공고를 저장하지 못했습니다.")

  const createApplication = (match) =>
    run(async () => {
      const application = await api.applications.create({
        opportunity_id: match.opportunity_id,
        deadline: match.deadline
      })
      return (
        <>
          지원서를 만들었어요.{" "}
          <a className="td-link" href={`#/applications/${application.id}`}>
            지원서 열기 →
          </a>
        </>
      )
    }, "지원서를 만들지 못했습니다.")

  const addToPlan = (match) =>
    run(async () => {
      const result = await api.opportunities.addToPlan(match.opportunity_id)
      if (result.already_planned) return "이미 오늘 계획에 있어요."
      return result.created_application
        ? `오늘 계획에 추가하고 지원서도 관심 상태로 만들었어요 — ${result.task.title}`
        : `오늘 계획에 추가했어요 — ${result.task.title}`
    }, "오늘 계획에 추가하지 못했습니다.")

  const setStatus = (match, status) =>
    run(async () => {
      await api.opportunities.setStatus(match.opportunity_id, status)
      if (status === "on_hold") return `'${match.title}' 을(를) 보류했어요. '보류' 칸에서 다시 볼 수 있어요.`
      if (status === "not_interested") return `'${match.title}' 을(를) 관심 없음으로 옮겼어요.`
      if (status === "closed") return `'${match.title}' 을(를) 보관함으로 옮겼어요.`
      return `'${match.title}' 을(를) 다시 검토 목록에 올렸어요.`
    }, "상태를 바꾸지 못했습니다.")

  const removeOpportunity = (match) =>
    run(async () => {
      await api.opportunities.remove(match.opportunity_id)
      setSelectedId(null)
      return `'${match.title}' 을(를) 완전히 삭제했어요.`
    }, "기회를 삭제하지 못했습니다.")

  if (loading) {
    return <LoadingState label="기회를 불러오는 중…" />
  }

  if (loadError) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const inView = (match) => view === "all" || match.lane === view

  const byType = tab === "all" ? matches : matches.filter((match) => match.opportunity_type === tab)
  const visible = byType.filter(inView)
  const worthDoing = visible.filter((match) => match.recommendation !== "skip")
  const notNow = visible.filter((match) => match.recommendation === "skip")

  const selected =
    visible.find((match) => match.opportunity_id === selectedId) ?? worthDoing[0] ?? visible[0] ?? null

  const viewCount = (key) =>
    byType.filter((match) => key === "all" || match.lane === key).length

  const candidates = matches
    .filter(
      (match) =>
        match.lane === "review" &&
        match.recommendation !== "skip" &&
        !match.application &&
        (match.days_until_deadline == null || match.days_until_deadline >= 0)
    )
    .sort(
      (a, b) =>
        (a.days_until_deadline ?? Infinity) - (b.days_until_deadline ?? Infinity) ||
        b.match_score - a.match_score
    )

  let hero

  if (matches.length === 0) {
    hero = (
      <EmptyState
        title="아직 모아둔 기회가 없어요."
        body="관심 있는 공고를 붙여넣으면 요구 스킬 · 마감 · 지원 자격을 채워 드려요."
        actions={[
          { label: "공고 붙여넣기", onClick: () => setShowImport(true), primary: true, writes: true },
          { label: "수집 실행", onClick: collect, writes: true }
        ]}
      />
    )
  } else if (candidates.length > 0) {
    const top = candidates[0]

    hero = (
      <NextActionCard
        eyebrow={`${TYPE_LABELS[top.opportunity_type] ?? "기회"} · ${ddayLabel(top.days_until_deadline)}`}
        icon="◇"
        title={`지원할지 정하기 — ${top.title}`}
        detail={`매칭 ${top.match_score}/100 · 요구 스킬 ${top.skills_required}개 중 ${top.skills_i_have}개 보유${
          top.requirement_flags?.length ? " · ⚠ 자격 확인 필요" : ""
        }`}
        meta={top.reasons[0]}
        action={
          <>
            <Button writes disabled={working} onClick={() => createApplication(top)}>
              지원서 만들기
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setView("review")
                setTab("all")
                setSelectedId(top.opportunity_id)
              }}
            >
              근거 보기
            </Button>
          </>
        }
      />
    )
  } else {
    hero = (
      <NextActionCard
        eyebrow="기회"
        tone="ok"
        icon="✓"
        title="지금 새로 판단할 기회가 없어요"
        meta="검토 중인 기회는 이미 지원서가 있거나, 우선순위가 낮거나, 마감이 지났어요."
        action={
          <Button variant="secondary" writes onClick={() => setShowImport(true)}>
            공고 붙여넣기
          </Button>
        }
      />
    )
  }

  return (
    <div className="opportunities-page learn evd">
      <section className="card learn-hero">
        <div className="evd-head">
          <div>
            <h1 className="learn-title">기회</h1>
            <p className="learn-sub">어떤 기회를 고를지 근거와 함께 판단합니다.</p>
          </div>

          <div className="ui-row">
            {!showImport && (
              <Button writes onClick={() => setShowImport(true)}>
                + 공고 붙여넣기
              </Button>
            )}
            <Button variant="secondary" writes disabled={working} onClick={collect}>
              수집 실행
            </Button>
          </div>
        </div>

        {showImport ? (
          <PasteImport
            working={working}
            onSave={savePosting}
            onCancel={() => setShowImport(false)}
            onError={setError}
          />
        ) : (
          hero
        )}
      </section>

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

      {matches.length > 0 && (
        <div className="opp-filters">
          <div className="learn-tabs" role="tablist" aria-label="검토 상태">
            {VIEWS.map((item) => (
              <button
                key={item.key}
                role="tab"
                aria-selected={view === item.key}
                className={view === item.key ? "chip chip-on" : "chip"}
                onClick={() => setView(item.key)}
              >
                {item.label} {viewCount(item.key)}
              </button>
            ))}
          </div>

          <div className="learn-tabs" role="tablist" aria-label="기회 종류">
            {TABS.map((item) => (
              <button
                key={item.key}
                role="tab"
                aria-selected={tab === item.key}
                className={tab === item.key ? "chip chip-on" : "chip"}
                onClick={() => setTab(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {matches.length > 0 &&
        (visible.length === 0 ? (
          <section className="card">
            <EmptyState
              title="이 칸에 해당하는 기회가 없어요."
              actions={[
                {
                  label: "검토 중 보기",
                  onClick: () => {
                    setView("review")
                    setTab("all")
                  },
                  primary: true
                }
              ]}
            />
          </section>
        ) : (
          <div className="split-grid">
            <div className="split-list">
              {worthDoing.map((match) => (
                <OpportunityRow
                  key={match.opportunity_id}
                  match={match}
                  selected={selected?.opportunity_id === match.opportunity_id}
                  onSelect={() => setSelectedId(match.opportunity_id)}
                />
              ))}

              {/* 치운 것을 숨기지 않는다. 판단은 사용자가 한다. */}
              {notNow.length > 0 && (
                <div className="split-aside">
                  <p className="split-aside-head">지금은 아닌 것 · {notNow.length}건</p>
                  <p className="muted form-hint">
                    우선순위가 낮거나 마감이 지나 아래로 내렸어요. 평가가 아니라 오늘의 집중을
                    지키기 위한 정리예요.
                  </p>

                  {notNow.map((match) => (
                    <OpportunityRow
                      key={match.opportunity_id}
                      match={match}
                      selected={selected?.opportunity_id === match.opportunity_id}
                      onSelect={() => setSelectedId(match.opportunity_id)}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="split-rail">
              {selected && (
                <OpportunityDetail
                  key={selected.opportunity_id}
                  match={selected}
                  working={working}
                  onCreateApplication={() => createApplication(selected)}
                  onAddToPlan={() => addToPlan(selected)}
                  onStatus={(status) => setStatus(selected, status)}
                  onRemove={() => removeOpportunity(selected)}
                />
              )}
            </div>
          </div>
        ))}

      {/* 지도는 네 칸짜리 표라 좁은 레일에 넣으면 스킬 이름이 잘린다. */}
      {selected && (
        <section className="card">
          <OpportunityMap opportunityId={selected.opportunity_id} />
        </section>
      )}

      {signals && (
        <section className="card">
          <p className="card-label">시장 신호 · 모아둔 기회 기준</p>

          {signals.signals.length === 0 ? (
            <p className="muted">아직 집계할 데이터가 없습니다.</p>
          ) : (
            <>
              <div className="signal-list">
                {signals.signals.map((signal) => {
                  const [mark, trendLabel] = TREND_TEXT[signal.trend] ?? TREND_TEXT.unknown

                  return (
                    <div className="signal-row" key={signal.skill_id}>
                      <span className="signal-name">{signal.skill}</span>
                      <div className="signal-bar">
                        <div className="signal-fill" style={{ width: `${signal.percentage}%` }} />
                      </div>
                      {/* 분모 없는 퍼센트는 근거가 아니다. */}
                      <span className="signal-value">
                        {signal.opportunity_count} / {signals.total_opportunities}건
                        <small>{signal.percentage}%</small>
                      </span>
                      <span className={`signal-trend trend-${signal.trend}`} aria-label={trendLabel} title={trendLabel}>
                        {mark}
                        {signal.change_points != null &&
                          signal.trend !== "unknown" &&
                          signal.trend !== "flat" && (
                            <span className="signal-delta">
                              {signal.change_points > 0 ? "+" : ""}
                              {signal.change_points}
                            </span>
                          )}
                      </span>
                    </div>
                  )
                })}
              </div>

              <p className="muted form-hint">
                기회 {signals.total_opportunities}건 · 소스 {signals.source_count}개 · 기록{" "}
                {signals.snapshot_count}행
                {!signals.has_trend_data && " — 비교할 과거 기록이 아직 없어 추세를 표시하지 않습니다."}
              </p>
            </>
          )}
        </section>
      )}
    </div>
  )
}

export default OpportunitiesPage
