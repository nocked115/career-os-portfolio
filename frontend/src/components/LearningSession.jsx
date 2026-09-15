import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import ChecklistPanel from "./ChecklistPanel"
import {
  Button,
  ErrorState,
  LoadingState,
  Notice,
  StatusBadge
} from "./ui"
import {
  IMPORTANCE_HINTS,
  STEP_STATUS_TONES,
  importanceLabel,
  minutesText,
  ownershipLabel,
  resourceTypeLabel,
  stepStatusLabel
} from "../format"
import { useReadOnly } from "../readOnly"
import "../Learning.css"
import "../Routine.css"

/* Learning Session — 실제로 학습을 시작하고 끝내는 화면.

   위에서부터: 무엇을 · 왜 지금 · 체크리스트 · 이번 세션 자료 · 시작/완료.
   끝내면 무엇이 바뀌었는지 보여주고 다음 단계로 잇는다.

   전에는 단계 설명의 줄을 "오늘의 목표" 로 보여주고 체크는 브라우저에만
   남겼다. 이제 체크리스트가 서버에 남는다. 예전 목표 줄은 체크리스트로
   옮기는 버튼이 있다. */

function LearningSession({ stepId, onBack, onCompleted, onOpenSession, onToday }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [working, setWorking] = useState(false)
  const [result, setResult] = useState(null)

  const [skillResources, setSkillResources] = useState([])
  const [linkId, setLinkId] = useState("")
  const readOnly = useReadOnly()
  // 클립보드가 막히면(권한 · 브라우저) 텍스트를 직접 보여주고 골라 복사하게 한다.
  const [handoffText, setHandoffText] = useState(null)

  const copyHandoff = async () => {
    try {
      setError(null)
      const { text } = await api.learningSteps.handoff(stepId)
      try {
        await navigator.clipboard.writeText(text)
        setHandoffText(null)
        setNotice("다른 세션에 붙여넣을 프롬프트를 복사했어요. 결과 아티팩트는 아래 체크리스트에 붙여넣으면 돼요.")
      } catch {
        setHandoffText(text)
      }
    } catch (failure) {
      setError(failure?.detail || "프롬프트를 만들지 못했습니다.")
    }
  }

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)
      setSession(await api.learningSteps.session(stepId))
    } catch (failure) {
      console.error("Failed to load learning session:", failure)
      setLoadError("학습 세션을 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [stepId])

  useEffect(() => {
    load()
  }, [load])

  const skillId = session?.skill?.id ?? null

  // 이 단계에 연결할 수 있는 자료 — 같은 스킬로 등록한 것.
  useEffect(() => {
    if (!skillId) return undefined

    let cancelled = false

    api.library
      .get()
      .then((library) => {
        if (!cancelled) {
          setSkillResources(library.items.filter((item) => item.skill_id === skillId))
        }
      })
      .catch((failure) => console.error("Failed to load library:", failure))

    return () => {
      cancelled = true
    }
  }, [skillId])

  const run = async (action, success, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      await action()
      await load(true)
      onCompleted?.()
      if (success) setNotice(success)
    } catch (failure) {
      console.error("Learning session action failed:", failure)
      setError(failure?.detail || fallback)
    } finally {
      setWorking(false)
    }
  }

  const completeStep = () =>
    run(
      async () => {
        setResult(await api.learningSteps.complete(stepId))
        // 결과 카드는 맨 위에 뜬다. 체크리스트 아래에서 눌렀으면 안 보인다.
        window.scrollTo({ top: 0, behavior: "smooth" })
      },
      null,
      "완료로 표시하지 못했습니다."
    )

  if (loading) {
    return <LoadingState label="학습 세션을 불러오는 중…" />
  }

  if (!session) {
    return (
      <div className="session">
        <button className="ghost-button back-link" onClick={onBack}>
          ← 학습
        </button>
        <ErrorState message={loadError} onRetry={() => load()} />
      </div>
    )
  }

  const { step, learning_path: path, skill, why_now: why } = session
  const selection = session.selection
  const goals = session.goals ?? []
  const isCompleted = step.status === "completed"

  const selectedIds = new Set((selection?.selected ?? []).map((item) => item.resource_id))
  const linkable = skillResources.filter(
    (item) => !selectedIds.has(item.id) && !item.linked_steps?.some((linked) => linked.id === step.id)
  )

  return (
    <div className="session learn">
      <button className="ghost-button back-link" onClick={onBack}>
        ← 학습
      </button>

      {/* ---------- 무엇을 ---------- */}
      <section className="card session-header">
        <div>
          <p className="card-label">
            {skill ? skill.name : "학습"}
            {path ? ` · ${path.title} ${path.progress_percent}%` : ""}
          </p>
          <h2>{step.title}</h2>
          <StatusBadge tone={STEP_STATUS_TONES[step.status]}>
            {stepStatusLabel(step.status)}
          </StatusBadge>

          {/* 마감이 14일 안에 들어오면 우선순위 1위 스킬이 아니어도 오늘 계획에 오른다. */}
          <label className="learn-due">
            마감
            <input
              key={`due-${step.due_date ?? ""}`}
              className="plan-input"
              type="date"
              defaultValue={step.due_date ?? ""}
              disabled={readOnly || working}
              onBlur={(event) => {
                const value = event.target.value || null
                if (value === (step.due_date ?? null)) return
                run(
                  () => api.learningSteps.update(step.id, { due_date: value }),
                  value
                    ? `마감을 ${value} 로 정했어요. 14일 안이면 오늘 계획이 먼저 챙겨요.`
                    : "마감을 지웠어요.",
                  "마감을 저장하지 못했습니다."
                )
              }}
            />
          </label>
        </div>

        <div className="session-time">
          <strong>{step.estimated_minutes ? minutesText(step.estimated_minutes) : "시간 미정"}</strong>
          <span>예상</span>
        </div>
      </section>

      {/* 체크리스트는 다른 Claude 세션이 만들고, 기록은 여기서 한다. 둘을 잇는 텍스트. */}
      <div className="ui-row learn-handoff">
        <Button variant="secondary" onClick={copyHandoff}>
          다른 세션에 넘길 프롬프트 복사
        </Button>
        <span className="muted form-hint">
          트랙 설명 · 이번 단계 · 마감 · 체크 진행 · 붙여넣기 형식이 함께 들어가요.
        </span>
      </div>

      {handoffText && (
        <section className="card">
          <p className="card-label">복사가 막혀서 텍스트로 보여 드려요 — 전부 선택해 복사하세요</p>
          <textarea
            className="learn-textarea"
            rows={14}
            readOnly
            value={handoffText}
            onFocus={(event) => event.target.select()}
          />
          <Button variant="quiet" onClick={() => setHandoffText(null)}>
            닫기
          </Button>
        </section>
      )}

      {/* ---------- 끝낸 결과 ---------- */}
      {result && (
        <section className="card learn-result" role="status" aria-live="polite">
          <p className="learn-result-title">✓ 학습 세션 완료</p>

          {result.effects.length > 0 ? (
            <ul className="learn-result-list">
              {result.effects.map((effect) => (
                <li key={effect}>{effect}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">이미 끝낸 단계라 새로 바뀐 것은 없습니다.</p>
          )}

          <div className="ui-row">
            {result.next_step ? (
              <Button onClick={() => onOpenSession(result.next_step.id)}>
                다음 단계 보기 · {result.next_step.title}
              </Button>
            ) : (
              <span className="muted">이 경로의 마지막 단계였어요.</span>
            )}
            <Button variant="secondary" onClick={onToday}>
              오늘 계획으로
            </Button>
          </div>
        </section>
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

      {/* ---------- 왜 지금 ---------- */}
      {why && (
        <section className="card">
          <p className="card-label">왜 지금인가</p>

          <ul className="why-list">
            {why.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>

          <div className="ui-row learn-why-meta">
            <StatusBadge tone="action">우선순위 {why.priority_rank}위</StatusBadge>
            <StatusBadge>
              {why.total_demand > 0
                ? `기회 ${why.total_demand}건 중 ${why.demand_requiring}건이 요구`
                : "모아둔 기회 없음"}
            </StatusBadge>
            <StatusBadge>레벨 {why.my_level}/4</StatusBadge>
          </div>
        </section>
      )}

      {/* ---------- 체크리스트 ---------- */}
      <ChecklistPanel
        stepId={step.id}
        checklist={session.checklist}
        goals={goals}
        isCompleted={isCompleted}
        onUpdated={(checklist) => setSession((current) => ({ ...current, checklist }))}
        onStarted={() => {
          // 첫 체크로 단계가 진행 중이 됐다. 상태 표시와 경로 진행률을 다시 읽는다.
          load(true)
          onCompleted?.()
        }}
        onComplete={completeStep}
      />

      {/* ---------- 이번 세션 자료 ---------- */}
      <section className="card">
        <div className="materials-header">
          <p className="card-label">이번 세션 자료</p>
          {selection && (
            <span className="muted">
              {minutesText(selection.selected_minutes)} / 예산 {minutesText(selection.available_minutes)}
            </span>
          )}
        </div>

        {!selection || selection.selected.length === 0 ? (
          <p className="muted">이 단계에 연결된 자료 중 지금 볼 수 있는 것이 없습니다. 아래에서 연결하세요.</p>
        ) : (
          <>
            <p className="learn-enough">
              이번 세션에는 아래 {selection.selected.length}개면 충분합니다.
            </p>
            <div className="pick-list">
              {selection.selected.map((item) => (
                <div className="pick-item" key={`${item.kind}-${item.segment_id ?? item.resource_id}`}>
                  <StatusBadge tone={`imp-${item.importance}`}>
                    {importanceLabel(item.importance)}
                  </StatusBadge>

                  <div className="pick-body">
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noreferrer">
                        <strong>{item.title}</strong>
                      </a>
                    ) : (
                      <strong>{item.title}</strong>
                    )}

                    <span className="material-type">
                      {resourceTypeLabel(item.resource_type)} · {ownershipLabel(item.ownership)}
                      {!item.url && " · 오프라인"}
                      {IMPORTANCE_HINTS[item.importance] && ` · ${IMPORTANCE_HINTS[item.importance]}`}
                    </span>
                  </div>

                  <span className="pick-minutes">{minutesText(item.minutes)}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {selection?.skipped?.length > 0 && (
          <details className="put-away">
            <summary className="put-away-head">
              지금 안 해도 되는 자료 {selection.skipped.length}개 — {selection.skipped_message}
            </summary>
            <ul>
              {selection.skipped.map((item) => (
                <li key={`s-${item.kind}-${item.segment_id ?? item.resource_id}`}>
                  {item.title}
                  <span className="muted"> — {item.skip_reason}</span>
                </li>
              ))}
            </ul>
          </details>
        )}

        <div className="learn-link">
          {linkable.length > 0 ? (
            <>
              <label className="learn-field">
                <span>{skill ? `${skill.name} 자료를 이 단계에 연결` : "자료를 이 단계에 연결"}</span>
                <select
                  className="path-select"
                  value={linkId}
                  onChange={(event) => setLinkId(event.target.value)}
                >
                  <option value="">자료 고르기</option>
                  {linkable.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.title} · {resourceTypeLabel(item.resource_type)}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                variant="secondary"
                writes
                disabled={working || !linkId}
                onClick={() =>
                  run(
                    async () => {
                      await api.learningSteps.linkResource(step.id, Number(linkId))
                      setLinkId("")
                    },
                    "자료를 이 단계에 연결했어요.",
                    "자료를 연결하지 못했습니다."
                  )
                }
              >
                연결
              </Button>
            </>
          ) : (
            <p className="muted form-hint">
              {skill ? `${skill.name} 로 등록한 자료 중 더 연결할 것이 없어요.` : "스킬이 없는 경로라 연결할 자료를 고를 수 없어요."}{" "}
              <a className="td-link" href="#/library">
                내 자료에서 등록하기
              </a>
            </p>
          )}
        </div>
      </section>

      {/* ---------- 시작 · 완료 ---------- */}
      <div className="session-actions learn-actions">
        {step.status === "not_started" && (
          <Button
            variant="secondary"
            writes
            disabled={working}
            onClick={() =>
              run(
                () => api.learningSteps.start(stepId),
                "학습을 시작했어요. 진행 중으로 표시했습니다.",
                "학습을 시작하지 못했습니다."
              )
            }
          >
            학습 시작
          </Button>
        )}

        <Button writes disabled={working || isCompleted} onClick={completeStep}>
          {isCompleted ? "완료한 단계" : "이 단계 완료로 표시"}
        </Button>
      </div>

      {isCompleted && !result && (
        <p className="muted session-note">
          이미 끝낸 단계입니다. 진행률과 우선순위에 반영되어 있어요.
        </p>
      )}
    </div>
  )
}

export default LearningSession
