import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingState,
  NextActionCard,
  Notice,
  ProgressBar,
  StatusBadge,
  WhyPanel
} from "./ui"
import { InlineCode } from "./ChecklistPanel"
import { areaLabel, ddayLabel, greeting, minutesText, todayText } from "../format"
import "../Today.css"
import "../Checklist.css"
import "../Routine.css"

// 밀린 것 중 먼저 보여줄 개수. 한꺼번에 들이밀면 읽지 않고 넘긴다.
const STALE_PREVIEW = 4

/* Today — 지금 무엇을 할지.

   맨 위에 세 가지만 둔다: 오늘 쓸 수 있는 시간, 핵심 초점, 가장 먼저
   할 일. 설정은 접어 둔다 — 매일 설정부터 만지게 하면 도구가 아니라 폼이다.

   항목마다 반드시 두 줄이 있다.
     선택 이유   이유를 못 쓰면 계획에 넣지 않는다 (DESIGN.md 원칙 1)
     완료하면    누르기 전에 무엇이 바뀌는지. 안 바뀌는 것은 안 바뀐다고.

   좁은 화면 순서: 요약 → 가장 먼저 할 일 → 작업 목록 → 근거. */

const PRESETS = [30, 60, 120, 180]

// 레일에는 결정에 직접 쓰인 것만. 아홉 개를 다 올리면 계산 설명 화면이 된다.
const RAIL_KEYS = ["market", "gap", "learning", "time"]

// 크게 보여줄 항목 수. 나머지는 지우지 않고 접는다.
const VISIBLE_TASKS = 3

/* 시작할 곳이 정해지지 않은 루틴 — 여기서 바로 정하고 시작한다.

   전에는 "캘린더에서 넣어 두세요" 한 줄만 떴다. 누른 사람 입장에선 아무 일도
   안 일어난 것과 같았다. 경로를 고르면 그 경로의 다음 단계를 바로 열고,
   주소를 넣으면 바로 열 수 있는 링크를 준다. */
function RoutineStart({ routine, working, onOpenStep, onSaved }) {
  const [paths, setPaths] = useState([])
  const [pathId, setPathId] = useState("")
  const [link, setLink] = useState("")
  const [savedLink, setSavedLink] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const panelRef = useRef(null)

  // 맨 위 "시작하기" 에서 눌렀으면 패널이 화면 밖에 뜬다. 뜨자마자 그 자리로 간다 —
  // 전에는 카드로 스크롤했는데 패널이 그려지기 전이라 엉뚱한 곳에 멈춰 아무 일도 안 난 것처럼 보였다.
  useEffect(() => {
    panelRef.current?.scrollIntoView({ block: "center" })
    panelRef.current?.querySelector("select")?.focus({ preventScroll: true })
  }, [])

  useEffect(() => {
    let cancelled = false
    api.learningPaths
      .list()
      .then((rows) => {
        if (!cancelled) setPaths(Array.isArray(rows) ? rows : rows?.paths ?? [])
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const connect = async () => {
    try {
      setBusy(true)
      setMessage(null)
      const saved = await api.routines.update(routine.id, { learning_path_id: Number(pathId) })
      onSaved?.()
      if (saved.next_step) return onOpenStep(saved.next_step.id)
      setMessage("연결했지만 그 경로에 남은 단계가 없어요. 학습 화면에서 단계를 추가하세요.")
    } catch (failure) {
      setMessage(failure?.detail || "연결하지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  const saveLink = async () => {
    try {
      setBusy(true)
      setMessage(null)
      const saved = await api.routines.update(routine.id, { link_url: link.trim() })
      setSavedLink(saved.link_url)
      onSaved?.()
    } catch (failure) {
      setMessage(failure?.detail ? "주소는 http 또는 https 로 시작해야 해요." : "저장하지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div ref={panelRef} className="td-howto" role="region" aria-label="시작할 곳 정하기">
      <strong className="td-howto-title">어디서 시작할지 아직 정해지지 않았어요</strong>
      {routine.note && <p className="td-howto-note">메모 · {routine.note}</p>}

      <div className="td-howto-row">
        <label className="learn-field">
          <span>학습 경로에 연결 — 체크리스트대로 오늘 할 문제가 보여요</span>
          <select className="path-select" value={pathId} onChange={(event) => setPathId(event.target.value)}>
            <option value="">경로 고르기</option>
            {paths.map((path) => (
              <option key={path.id} value={path.id}>
                {path.title}
              </option>
            ))}
          </select>
        </label>
        <Button writes disabled={working || busy || !pathId} onClick={connect}>
          연결하고 시작
        </Button>
      </div>

      <div className="td-howto-row">
        <label className="learn-field">
          <span>또는 문제 목록 주소</span>
          <input
            className="agent-input"
            maxLength={500}
            placeholder="https://school.programmers.co.kr/learn/challenges"
            value={link}
            onChange={(event) => setLink(event.target.value)}
          />
        </label>
        <Button variant="secondary" writes disabled={working || busy || !link.trim()} onClick={saveLink}>
          저장
        </Button>
      </div>

      {savedLink && (
        <p className="td-howto-note">
          저장했어요. 다음부터는 &lsquo;시작&rsquo;이 바로 엽니다 —{" "}
          <a className="td-link" href={savedLink} target="_blank" rel="noopener noreferrer">
            지금 열기
          </a>
        </p>
      )}
      {message && <p className="td-howto-note">{message}</p>}
    </div>
  )
}

/* 매일 하는 일 — 계획이 아니라 고정 칸.

   코테는 평일마다 하는 것이지 오늘 고른 것이 아니다. 계획 목록에 섞이면 매일 같은 줄이
   자리를 차지하고, 정작 오늘 정해야 할 일이 접힌 자리로 밀린다. 시간은 그대로 뗀다. */
function RoutineStrip({ routines, working, onOpenStep, onRecord, onUndo, onLearned }) {
  if (!routines?.length) return null

  const doneCount = routines.filter((row) => row.done).length

  return (
    <section className="card td-routines" aria-label="매일 하는 것">
      <div className="td-routines-head">
        <p className="card-label">매일 하는 것</p>
        <span className="td-routines-count">
          오늘 {doneCount}/{routines.length}
        </span>
      </div>

      <ul className="td-routine-list">
        {routines.map((routine) => (
          <RoutineRow
            key={routine.id}
            routine={routine}
            working={working}
            onOpenStep={onOpenStep}
            onRecord={onRecord}
            onUndo={onUndo}
            onLearned={onLearned}
          />
        ))}
      </ul>
    </section>
  )
}

function RoutineRow({ routine, working, onOpenStep, onRecord, onUndo, onLearned }) {
  const [count, setCount] = useState(routine.count ?? routine.target_count ?? "")
  /* 오늘 한 것 중 몰랐던 것. 개수를 적는 자리에서 같이 적는다 — 끝낸 직후가
     가장 잘 떠오른다. 끝낸 뒤에도 고칠 수 있게 열어 둔다. */
  const [learned, setLearned] = useState(routine.learned ?? "")
  const [editing, setEditing] = useState(false)
  const changed = (learned ?? "").trim() !== (routine.learned ?? "").trim()

  const start = () => {
    if (routine.next_step) return onOpenStep(routine.next_step.id)
    if (routine.link_url) {
      window.open(routine.link_url, "_blank", "noopener,noreferrer")
      return
    }
    // 갈 곳이 없으면 캘린더에서 정하게 한다 — 아무 화면으로나 보내지 않는다.
    window.location.hash = "#/calendar"
  }

  return (
    <li className={`td-routine td-routine-${routine.done ? "done" : "open"}`}>
      <div className="td-routine-main">
        <div className="td-routine-title">
          <strong>{routine.title}</strong>
          {/* 이번 주가 한눈에. 숫자만 쓰면 "1일 중 0일" 이 눈에 안 들어온다. */}
          {routine.week?.due > 0 && (
            <span
              className="td-routine-week"
              title={`이번 주 ${routine.week.due}일 중 ${routine.week.done}일 함`}
              aria-label={`이번 주 ${routine.week.due}일 중 ${routine.week.done}일 함`}
            >
              {Array.from({ length: routine.week.due }, (_, index) => (
                <i key={index} className={index < routine.week.done ? "on" : ""} />
              ))}
            </span>
          )}
        </div>
        <span className="muted">
          {routine.weekday_label} · {minutesText(routine.minutes)}
          {routine.target_text ? ` · 목표 ${routine.target_text}` : ""}
        </span>
        {routine.next_step && (
          <span className="muted">다음 단계 · {routine.next_step.title}</span>
        )}
      </div>

      {routine.done ? (
        <>
          {/* 오른쪽 칸에는 배지와 되돌리기만. 적는 칸까지 여기 두면
              왼쪽이 텅 빈 채 입력칸만 좁게 찌그러진다. */}
          <div className="td-routine-recorded">
            <div className="ui-row">
              <StatusBadge tone="ok">
                오늘 함{routine.count != null ? ` · ${routine.count}${routine.unit_label || "개"}` : ""}
              </StatusBadge>
              <Button variant="quiet" writes tryInDemo disabled={working} onClick={() => onUndo(routine)}>
                되돌리기
              </Button>
            </div>
          </div>

          {/* 적는 것은 아래 한 줄을 다 쓴다 — 문장을 쓰는 칸이라 폭이 필요하다. */}
          {routine.learned && !editing && (
            <p className="td-routine-learned">
              몰랐던 것 · {routine.learned}{" "}
              <button type="button" className="td-link" onClick={() => setEditing(true)}>
                고치기
              </button>
            </p>
          )}

          {(editing || !routine.learned) && (
            <div className="td-routine-learn">
              <label htmlFor={`learned-done-${routine.id}`}>오늘 한 것 중 몰랐던 것</label>
              <textarea
                id={`learned-done-${routine.id}`}
                className="plan-input"
                rows={2}
                maxLength={2000}
                placeholder="막힌 지점을 그대로. 예: 투 포인터에서 while 조건을 언제 끊는지 몰랐다"
                value={learned}
                onChange={(event) => setLearned(event.target.value)}
              />
              <Button
                variant="quiet"
                writes
                tryInDemo
                disabled={working || !changed}
                onClick={async () => {
                  await onLearned(routine, learned)
                  setEditing(false)
                }}
              >
                적어 두기
              </Button>
            </div>
          )}
        </>
      ) : (
        <div className="ui-row">
          {routine.target_count != null && (
            <label className="td-routine-count">
              한 개수
              <input
                className="plan-input"
                type="number"
                min="0"
                max="100"
                value={count}
                onChange={(event) => setCount(event.target.value)}
              />
              {routine.unit_label || "개"}
            </label>
          )}
          <Button onClick={start}>시작</Button>
          <Button
            variant="secondary"
            writes
            tryInDemo
            disabled={working}
            onClick={() =>
              onRecord(routine, count === "" ? undefined : Number(count), learned)
            }
          >
            했어요
          </Button>
        </div>
      )}

      {!routine.done && (
        <div className="td-routine-learn">
          <label htmlFor={`learned-${routine.id}`}>오늘 한 것 중 몰랐던 것 (선택)</label>
          <textarea
            id={`learned-${routine.id}`}
            className="plan-input"
            rows={2}
            maxLength={2000}
            placeholder="막힌 지점을 그대로. 예: 투 포인터에서 while 조건을 언제 끊는지 몰랐다"
            value={learned}
            onChange={(event) => setLearned(event.target.value)}
          />
        </div>
      )}
    </li>
  )
}

/* 오늘 계획에 직접 한 줄 넣기.

   앱이 고른 것만 할 수 있으면 "시간이 남아서 이걸 하고 싶다" 를 넣을 곳이 없다.
   계획은 제안이지 명령이 아니다. 대신 무엇을 가리키는지는 남긴다 — 완료했을 때
   진행률과 증거가 같이 움직여야 한다. */
function AddTask({ working, remainingMinutes, onAdded, onError }) {
  const [open, setOpen] = useState(false)
  const [kind, setKind] = useState("project")
  const [targetId, setTargetId] = useState("")
  const [title, setTitle] = useState("")
  const [minutes, setMinutes] = useState(30)
  const [options, setOptions] = useState({ project: [], learning_step: [], resource: [] })
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return undefined

    let cancelled = false

    Promise.all([
      api.projects.list().catch(() => []),
      api.learningPaths.list().catch(() => []),
      api.library.get().catch(() => ({ items: [] }))
    ])
      .then(async ([projects, paths, library]) => {
        const pathRows = Array.isArray(paths) ? paths : paths?.paths ?? []
        const steps = (
          await Promise.all(
            pathRows.map((path) =>
              api.learningSteps
                .list(path.id)
                .then((rows) => (Array.isArray(rows) ? rows : rows?.steps ?? []))
                .then((rows) =>
                  rows
                    .filter((step) => step.status !== "completed")
                    .map((step) => ({ id: step.id, label: `${path.title} — ${step.title}` }))
                )
                .catch(() => [])
            )
          )
        ).flat()

        if (cancelled) return

        setOptions({
          project: (Array.isArray(projects) ? projects : [])
            .filter((row) => row.status !== "completed" && row.purpose !== "hobby")
            .map((row) => ({ id: row.id, label: `${row.name} · ${row.progress_percent ?? 0}%` })),
          learning_step: steps,
          resource: (library.items ?? [])
            .filter((row) => row.status !== "completed")
            .map((row) => ({ id: row.id, label: row.title }))
        })
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [open])

  if (!open) {
    return (
      <div className="td-add-open">
        <Button variant="secondary" writes onClick={() => setOpen(true)}>
          + 오늘 계획에 직접 넣기
        </Button>
        {remainingMinutes > 0 && (
          <span className="muted">오늘 예산에서 {minutesText(remainingMinutes)} 남았어요</span>
        )}
      </div>
    )
  }

  const rows = options[kind] ?? []
  const ready = kind === "custom" ? title.trim().length > 0 : Boolean(targetId)

  const add = async () => {
    try {
      setBusy(true)
      const result = await api.todayPlan.addTask({
        kind,
        target_id: kind === "custom" ? null : Number(targetId),
        title: kind === "custom" ? title.trim() : "",
        minutes: Number(minutes) || 30
      })
      onAdded(result)
      setOpen(false)
      setTargetId("")
      setTitle("")
    } catch (failure) {
      onError(failure?.detail || "넣지 못했습니다.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="td-add">
      <div className="td-add-row">
        <label className="learn-field">
          <span>무엇을</span>
          <select
            className="path-select"
            value={kind}
            onChange={(event) => {
              setKind(event.target.value)
              setTargetId("")
            }}
          >
            <option value="project">프로젝트</option>
            <option value="learning_step">학습 단계</option>
            <option value="resource">내 자료</option>
            <option value="custom">직접 적기</option>
          </select>
        </label>

        {kind === "custom" ? (
          <label className="learn-field td-add-wide">
            <span>할 일</span>
            <input
              className="agent-input"
              maxLength={200}
              placeholder="예: 논문 초록 다시 읽기"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
        ) : (
          <label className="learn-field td-add-wide">
            <span>{rows.length > 0 ? "고르기" : "고를 것이 없어요"}</span>
            <select
              className="path-select"
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
            >
              <option value="">고르기</option>
              {rows.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.label}
                </option>
              ))}
            </select>
          </label>
        )}

        <label className="learn-field td-add-minutes">
          <span>분</span>
          <input
            className="plan-input"
            type="number"
            min="5"
            max="480"
            step="5"
            value={minutes}
            onChange={(event) => setMinutes(event.target.value)}
          />
        </label>
      </div>

      <div className="ui-row">
        <Button writes disabled={working || busy || !ready} onClick={add}>
          오늘 계획에 넣기
        </Button>
        <Button variant="quiet" onClick={() => setOpen(false)}>
          취소
        </Button>
        <span className="muted">
          계획은 제안이에요. 넣은 것도 완료하면 진행률 · 증거가 같이 움직여요.
        </span>
      </div>
    </div>
  )
}

/* 자료(책 · 강의)를 시작할 때 보이는 칸.

   전에는 "시작" 이 내 자료 **목록**으로 보냈다. 책 한 권을 펼쳐놓고
   "자 시작하세요" 하는 셈이라, 수현 말로 "아무것도 안 나온다" 였다.
   책 한 권은 오늘 할 일이 될 수 없다. 1장 45분은 될 수 있다.

   조각이 아직 없으면 범위를 지어내지 않는다 — 나누라고 말한다. */
function ResourceStart({ resource, working, onDone }) {
  const next = resource.next_segment
  const left = resource.segment_total - resource.segment_done

  /* 읽고 남길 한 줄. 끝낼 때 같이 적는다 — 그때가 가장 잘 떠오르고,
     나중에 다시 열 이유가 줄어든다 (루틴의 '몰랐던 것' 과 같은 판단). */
  const [note, setNote] = useState(next?.note ?? "")

  if (!next) {
    return (
      <div className="td-howto" role="region" aria-label="자료 시작">
        <strong className="td-howto-title">
          {resource.segment_total === 0
            ? "어디부터 어디까지 읽을지가 아직 안 나뉘어 있어요"
            : "이 자료는 다 끝냈어요"}
        </strong>
        <p className="td-howto-note">
          {resource.segment_total === 0
            ? "책 한 권은 오늘 할 일이 될 수 없어요. 장 · 회차로 나눠 두면 '시작' 이 오늘 읽을 데를 바로 보여줍니다."
            : `${resource.segment_total}개를 모두 마쳤습니다.`}
        </p>
        <div className="td-howto-row">
          <a className="ui-btn ui-btn-secondary" href="#/library">
            {resource.segment_total === 0 ? "내 자료에서 나누기 →" : "내 자료 보기 →"}
          </a>
          {resource.url && (
            <a
              className="ui-btn ui-btn-quiet"
              href={resource.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              자료 열기 ↗
            </a>
          )}
        </div>
      </div>
    )
  }

  // 페이지 · 회차가 적혀 있으면 그대로 보인다. 없으면 이름만.
  const range =
    next.start_ref != null && next.end_ref != null
      ? `${next.start_ref}–${next.end_ref}`
      : next.start_ref != null
        ? `${next.start_ref}부터`
        : null

  return (
    <div className="td-howto" role="region" aria-label="오늘 읽을 데">
      <strong className="td-howto-title">오늘은 여기 — {next.label}</strong>

      <p className="td-howto-note">
        {range && <>{range} · </>}
        {next.minutes > 0 ? minutesText(next.minutes) : "시간 미정"}
        {" · "}
        {resource.segment_total}개 중 {resource.segment_done + 1}번째
        {left > 1 && ` (뒤로 ${left - 1}개 남음)`}
      </p>

      {/* 지난번에 남긴 것. "뭐였더라" 가 화면에 있어야 다시 안 열어본다. */}
      {resource.last_note && (
        <p className="td-howto-note td-howto-last">
          지난번 · {resource.last_note.label} — {resource.last_note.note}
        </p>
      )}

      <label className="td-howto-field">
        <span>읽고 남길 한 줄 (안 적어도 됩니다)</span>
        <textarea
          className="agent-input td-howto-note-input"
          rows={2}
          maxLength={4000}
          placeholder="뭘 알게 됐는지 · 안 풀린 게 뭔지"
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      <div className="td-howto-row">
        {resource.url && (
          <a
            className="ui-btn ui-btn-primary"
            href={resource.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            자료 열기 ↗
          </a>
        )}
        <Button writes tryInDemo disabled={working} onClick={() => onDone(next, note)}>
          여기까지 읽었어요
        </Button>
      </div>

      <p className="td-howto-note">
        다 읽었으면 눌러 주세요. 다음에 &lsquo;시작&rsquo;을 누르면 그다음 장이 나옵니다.
      </p>
    </div>
  )
}


/* 이 일에 "시작" 이 열어 줄 곳이 있는가.

   손으로 적어 넣은 일에는 연결된 단계도 공고도 없다. 그런데도 시작을
   보여 주니, 누르면 갈 곳이 없어 학습 화면으로 떨어졌다. 적어 둔 일을
   하려다 엉뚱한 화면에서 길을 잃는다. 열 곳이 없으면 버튼을 숨긴다 —
   완료는 왼쪽 동그라미로 하므로 여기서 할 일이 막히지는 않는다. */
function hasDestination(task) {
  return Boolean(
    task.learning_step_id ||
    task.routine ||
    task.application_id ||
    task.opportunity_id ||
    task.project_id ||
    task.learning_resource_id
  )
}


function TaskCard({
  task,
  index,
  working,
  onComplete,
  onSkip,
  onPark,
  onEdit,
  onRemove,
  onSegmentDone,
  onStart,
  onReopen,
  onOpenStep,
  onSaved,
  showHow
}) {
  const planned = task.status === "planned"
  // 루틴에 목표 개수가 있으면 실제로 한 개수를 적고 끝낸다. 기본은 목표만큼.
  const target = task.routine?.target_count ?? null
  const [count, setCount] = useState(target ?? "")
  /* 실제로 걸린 시간. 비워 두면 안 보낸다 — 적어야만 끝낼 수 있게 하면
     적기 싫어서 안 끝내게 되고, 그러면 기록이 더 나빠진다. */
  const [actual, setActual] = useState("")
  const [skipReason, setSkipReason] = useState("")
  const [skipping, setSkipping] = useState(false)

  const finish = () =>
    onComplete(
      target != null && count !== "" ? Number(count) : undefined,
      actual !== "" ? Number(actual) : undefined
    )

  /* 고치는 칸은 접어 둔다. 늘 펴 두면 훑어보기가 어렵다. */
  const [editing, setEditing] = useState(false)
  const [draftTitle, setDraftTitle] = useState(task.title)
  const [draftMinutes, setDraftMinutes] = useState(task.minutes)

  return (
    <li id={`td-task-${task.id}`} className={`td-task td-task-${task.status}`}>
      <Button
        variant="check"
        writes
        tryInDemo
        className="td-check"
        disabled={working || !planned}
        onClick={finish}
        aria-label={`${task.title} 완료로 표시`}
      >
        {task.status === "done" ? "✓" : index + 1}
      </Button>

      <div className="td-task-body">
        <div className="td-task-top">
          <StatusBadge tone={`area-${task.task_type}`}>
            {areaLabel(task.task_type)}
          </StatusBadge>
          {task.carried_from && <StatusBadge tone="warn">이월</StatusBadge>}
          {task.status === "done" && <StatusBadge tone="ok">완료</StatusBadge>}
          {task.status === "skipped" && <StatusBadge>넘김</StatusBadge>}
          <span className="td-task-minutes">{minutesText(task.minutes)}</span>
        </div>

        {editing ? (
          <div className="td-task-edit">
            <input
              className="plan-input td-edit-title"
              value={draftTitle}
              maxLength={200}
              aria-label="할 일 이름"
              onChange={(event) => setDraftTitle(event.target.value)}
            />
            <label className="td-routine-count">
              걸리는 시간
              <input
                className="plan-input"
                type="number"
                min="5"
                max="480"
                step="5"
                value={draftMinutes}
                onChange={(event) => setDraftMinutes(event.target.value)}
              />
              분
            </label>
            <Button
              writes
              tryInDemo
              disabled={working || !draftTitle.trim()}
              onClick={() => {
                onEdit({ title: draftTitle.trim(), minutes: Number(draftMinutes) || task.minutes })
                setEditing(false)
              }}
            >
              저장
            </Button>
            <Button
              variant="quiet"
              disabled={working}
              onClick={() => {
                setDraftTitle(task.title)
                setDraftMinutes(task.minutes)
                setEditing(false)
              }}
            >
              그만두기
            </Button>
          </div>
        ) : (
          <strong className="td-task-title">{task.title}</strong>
        )}

        {/* 학습 단계는 하루에 안 끝난다. 오늘 실제로 할 줄을 보인다. */}
        {task.checklist && (
          <div className="td-task-line td-checklist">
            <span className="td-task-key">
              체크 {task.checklist.done}/{task.checklist.total}
            </span>

            {/* 할 일을 여기 **다 적지 않는다.** 오늘 카드는 "어디까지" 만
                말하고, 실제 항목은 '시작' 을 눌러 학습 화면에서 본다.
                거기서 오늘 몫에 테두리가 쳐진다. 같은 목록을 두 군데
                늘어놓으면 어느 쪽을 보고 체크해야 할지 알 수 없다. */}
            {task.checklist.today ? (
              <span className="td-slice-range">
                오늘은 {task.checklist.today.from_number}번부터{" "}
                {task.checklist.today.to_number}번까지
                <span className="muted">
                  {" "}— {task.checklist.today.count}개
                  {task.checklist.today.minutes != null &&
                    ` · ${minutesText(task.checklist.today.minutes)}`}
                  {task.checklist.today.adjusted && " · 내 속도로 맞췄어요"}
                  {task.checklist.today.finishes_step && " · 이걸로 이 주차가 끝나요"}
                </span>
              </span>
            ) : (
              <span>모두 체크했어요 — 끝났으면 완료로 표시하세요</span>
            )}
          </div>
        )}

        {task.reason && (
          <p className="td-task-line">
            <span className="td-task-key">선택 이유</span>
            <span>{task.reason}</span>
          </p>
        )}

        {planned && task.on_complete && (
          <p className="td-task-line">
            <span className="td-task-key">완료하면</span>
            <span>{task.on_complete}</span>
          </p>
        )}

        {planned && (
          <div className="ui-row td-task-actions">
            {/* 실제로 걸린 시간. 앱은 "30분" 이라고 적어 두고 한 번도 묻지
                않았다 — 그러니 추정이 영원히 안 맞는다. */}
            <label className="td-routine-count">
              실제
              <input
                className="plan-input"
                type="number"
                min="0"
                max="600"
                step="5"
                placeholder={String(task.minutes)}
                value={actual}
                onChange={(event) => setActual(event.target.value)}
              />
              분
            </label>
            {target != null && (
              <label className="td-routine-count">
                한 개수
                <input
                  className="plan-input"
                  type="number"
                  min="0"
                  max="100"
                  value={count}
                  onChange={(event) => setCount(event.target.value)}
                />
                {task.routine.unit_label || "개"} / 목표 {target}
              </label>
            )}
            {hasDestination(task) && <Button onClick={onStart}>시작</Button>}
            <Button
              variant="quiet"
              writes
              tryInDemo
              disabled={working}
              onClick={() => setSkipping(true)}
            >
              오늘은 넘기기
            </Button>
            {/* 넘기기는 그날로 끝나지만 이건 남는다. 기한 없이 빼두고 나중에 거기서 끝낸다. */}
            {onPark && (
              <Button variant="quiet" writes tryInDemo disabled={working} onClick={onPark}>
                나중에 →
              </Button>
            )}
            {/* 계획을 그 자리에서 바꾼다. 못 바꾸면 사람은 숫자를 무시하게 된다. */}
            {onEdit && !editing && (
              <Button variant="quiet" disabled={working} onClick={() => setEditing(true)}>
                고치기
              </Button>
            )}
            {onRemove && (
              <Button variant="quiet" writes tryInDemo disabled={working} onClick={onRemove}>
                지우기
              </Button>
            )}
          </div>
        )}

        {/* 잘못 누른 완료 · 넘김은 되돌린다. 완료가 남긴 기록도 같이 지워진다. */}
        {!planned && (
          <div className="ui-row td-task-actions">
            <Button variant="quiet" writes tryInDemo disabled={working} onClick={onReopen}>
              {task.status === "done" ? "완료 되돌리기" : "넘김 되돌리기"}
            </Button>
            {/* 넘긴 줄도 지울 수 있어야 한다 — 넘김은 자국을 남기지만
                잘못 넣은 줄은 자국까지 지우고 싶다. 끝낸 것은 두지 않는다:
                한 일을 지우면 그날 기록이 사실과 달라진다. */}
            {onRemove && task.status === "skipped" && (
              <Button variant="quiet" writes tryInDemo disabled={working} onClick={onRemove}>
                지우기
              </Button>
            )}
          </div>
        )}

        {/* 넘기는 까닭. 안 한 것도 기록이다 — 같은 까닭이 반복되면
            계획이 틀린 것이지 사람이 게으른 게 아니다. */}
        {skipping && planned && (
          <div className="td-howto" role="region" aria-label="넘기는 까닭">
            <label className="td-howto-field">
              <span>왜 오늘은 못 하나요 (안 적어도 됩니다)</span>
              <input
                className="agent-input"
                maxLength={200}
                placeholder="예: 캡스톤 발표 준비 · 시간이 모자랐다 · 생각보다 어렵다"
                value={skipReason}
                onChange={(event) => setSkipReason(event.target.value)}
              />
            </label>
            <div className="ui-row">
              <Button
                writes
                tryInDemo
                disabled={working}
                onClick={() => {
                  onSkip(skipReason.trim())
                  setSkipping(false)
                }}
              >
                넘기기
              </Button>
              <Button variant="quiet" disabled={working} onClick={() => setSkipping(false)}>
                그만두기
              </Button>
            </div>
          </div>
        )}

        {showHow && planned && task.routine && (
          <RoutineStart
            routine={task.routine}
            working={working}
            onOpenStep={onOpenStep}
            onSaved={onSaved}
          />
        )}

        {showHow && planned && !task.routine && task.resource && (
          <ResourceStart
            resource={task.resource}
            working={working}
            onDone={onSegmentDone}
          />
        )}
      </div>
    </li>
  )
}

function TodayPage({ onOpenStep, onWhy, onNavigate, onChanged }) {
  const [minutes, setMinutes] = useState(120)
  const [intensity, setIntensity] = useState("normal")
  const [intensities, setIntensities] = useState([])

  const [plan, setPlan] = useState(null)
  const [why, setWhy] = useState(null)
  const [calendar, setCalendar] = useState(null)
  // 즐겨찾기 공고. 마감이 멀어 계획에 안 올라오는 것을 눈에서 놓치지 않기 위한 배지.
  const [favorites, setFavorites] = useState([])
  const [loading, setLoading] = useState(true)
  const [working, setWorking] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [showSettings, setShowSettings] = useState(false)
  // 시작할 곳이 없는 루틴에서 "시작" 을 누른 카드
  const [howToId, setHowToId] = useState(null)
  // 밀린 것은 먼저 넷만 묻는다. 한꺼번에 들이밀면 읽지 않고 넘긴다.
  const [showAllStale, setShowAllStale] = useState(false)

  // quiet: 버튼을 누른 뒤 다시 읽을 때는 화면 전체를 "불러오는 중" 으로
  // 바꾸지 않는다. 방금 누른 자리가 사라지면 무엇이 됐는지 볼 수 없다.
  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setError(null)

      // 기본 예산은 캘린더가 정한다. 120 은 어디서 나온 숫자냐는
      // 질문에 답할 수 없는 값이었다.
      const day = await api.calendar.day()
      const budget = day.suggested_minutes

      const [options, current, reasoning, starred] = await Promise.all([
        api.todayPlan.intensities(),
        api.todayPlan.get(budget, "normal"),
        api.todayPlan.why(budget, "normal"),
        // 즐겨찾기는 없어도 화면이 돌아가야 한다 — 실패해도 빈 목록으로 둔다.
        api.opportunities.list().catch(() => [])
      ])

      setIntensities(options.intensities)
      setPlan(current)
      setWhy(reasoning)
      setCalendar(day)
      setMinutes(budget)
      /* 끝난 공고는 즐겨찾기에서 뺀다. 즐겨찾기는 "잊지 않게 여기 둬"
         라는 뜻인데, 마감이 지났거나 보관함에 들어간 공고는 잊을 일이
         없다. 지원하거나 치울 때는 서버가 표시를 내리지만, 그냥 마감만
         지난 것은 아무 일도 안 일어나므로 여기서 거른다. */
      const today = new Date().toISOString().slice(0, 10)

      setFavorites(
        (Array.isArray(starred) ? starred : []).filter((row) => {
          if (!row.favorite) return false
          if (row.blocked_reason) return false
          if (["closed", "archived", "not_interested"].includes(row.status)) return false
          if (row.deadline && String(row.deadline).slice(0, 10) < today) return false
          return true
        })
      )

      // 이미 만들어둔 계획이 있으면 그 설정으로 컨트롤을 맞춘다.
      if (current.total_tasks > 0) {
        setMinutes(current.available_minutes)
        setIntensity(current.intensity)
      }
    } catch (loadError) {
      console.error("Failed to load today:", loadError)
      setError("오늘 계획을 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const run = async (action, fallback = "요청을 처리하지 못했습니다.") => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const message = await action()
      await load(true)
      onChanged?.()
      if (message) setNotice(message)
    } catch (actionError) {
      console.error("Today action failed:", actionError)
      setError(actionError?.detail || fallback)
    } finally {
      setWorking(false)
    }
  }

  const createPlan = () =>
    run(async () => {
      const result = await api.todayPlan.create(minutes, intensity)

      /* 저절로 치운 것은 조용히 넘기지 않는다. 마감이 지났다는 건 사실이라
         묻지 않고 치우지만, 무엇이 왜 사라졌는지는 말해야 한다. */
      const cleared = result?.cleared ?? []

      if (cleared.length === 0) return "오늘 계획을 세웠어요."

      const why = [...new Set(cleared.map((row) => row.reason))].join(" · ")

      return `오늘 계획을 세웠어요. 답이 정해진 ${cleared.length}개는 묻지 않고 치웠습니다 — ${why}.`
    }, "계획을 세우지 못했습니다.")

  const complete = (task, count, actualMinutes) =>
    run(async () => {
      const body = {}
      if (count != null) body.count = count
      // 실제로 걸린 시간. 안 적어도 끝낼 수 있다.
      if (actualMinutes != null) body.actual_minutes = actualMinutes

      const result = await api.todayPlan.complete(
        task.id,
        Object.keys(body).length ? body : undefined
      )
      return result.effects?.length
        ? `완료했어요 — ${result.effects.join(" · ")}`
        : "완료했어요. 오늘 한 기록이 남았습니다."
    }, "완료로 표시하지 못했습니다.")

  const skip = (task, reason) =>
    run(async () => {
      await api.todayPlan.skip(task.id, reason)
      return reason
        ? `'${task.title}' 은(는) 오늘 넘겼어요 — ${reason}.`
        : `'${task.title}' 은(는) 오늘 넘겼어요.`
    }, "넘기지 못했습니다.")

  /* 기한 없이 빼둔다. 오늘 계획에서는 빠지지만 없어지지 않는다 —
     아래 "언젠가 할 일" 에 남고, 거기서 바로 끝낼 수 있다. */
  const park = (task) =>
    run(async () => {
      await api.todayPlan.park(task.id)
      return `'${task.title}' 은(는) 언젠가 할 일로 옮겼어요.`
    }, "옮기지 못했습니다.")

  const unpark = (task) =>
    run(async () => {
      await api.todayPlan.unpark(task.id)
      return `'${task.title}' 을(를) 오늘 할 일로 가져왔어요.`
    }, "가져오지 못했습니다.")

  /* 계획은 제안이지 명령이 아니다. 앱이 적어 둔 45분이 실제로는 20분이면
     그 숫자 위에서 세는 "남은 시간" 이 전부 틀린다. 그 자리에서 고친다. */
  /* 읽은 조각을 끝으로 표시한다. 다음에 '시작' 을 누르면 그다음 장이 나온다. */
  const finishSegment = (task, segment, note) =>
    run(async () => {
      await api.library.completeSegment(segment.id, note ?? "")
      const wrote = (note ?? "").trim() ? " 정리도 같이 남겼어요." : ""
      return `'${segment.label}' 까지 읽은 것으로 남겼어요.` + wrote
    }, "표시하지 못했습니다.")

  const editTask = (task, body) =>
    run(async () => {
      await api.todayPlan.editTask(task.id, body)
      return "고쳤어요."
    }, "고치지 못했습니다.")

  /* 넘기기 · 빼두기와 다르다. 저 둘은 "안 한다" 를 기록으로 남겨 자국이
     남지만, 잘못 넣은 줄은 안 한 일이 아니라 애초에 없던 일이다. */
  const removeTask = (task) =>
    run(async () => {
      const result = await api.todayPlan.removeTask(task.id)
      return result.was_generated
        ? `'${task.title}' 을(를) 지웠어요. 앱이 고른 일이라 다시 짜면 또 올라올 수 있어요 — 오늘 안 하기로 정한 거면 '오늘은 넘기기' 를 쓰세요.`
        : `'${task.title}' 을(를) 지웠어요.`
    }, "지우지 못했습니다.")

  /* 그 항목이 있는 실제 화면으로 데려간다.
     "시작" 이 아무 데도 데려가지 않으면 버튼이 아니라 장식이다. */
  const reopen = (task) =>
    run(async () => {
      const result = await api.todayPlan.reopen(task.id)
      return result.effects?.length
        ? `되돌렸어요 — ${result.effects.join(" · ")}`
        : "되돌렸어요. 다시 할 일로 돌아갔습니다."
    }, "되돌리지 못했습니다.")

  const recordRoutine = (routine, count, learned) =>
    run(async () => {
      const today = plan?.date ?? new Date().toISOString().slice(0, 10)
      await api.routines.log(routine.id, today, { done: true, count, learned })
      const wrote = (learned ?? "").trim() ? " 몰랐던 것도 적어 뒀어요." : ""
      return (
        (count != null
          ? `${routine.title} ${count}${routine.unit_label || "개"} 기록했어요.`
          : `${routine.title} 오늘 한 것으로 기록했어요.`) + wrote
      )
    }, "기록하지 못했습니다.")

  /* 이미 기록한 날의 메모만 고친다. count 를 안 보내면 서버가 그날 개수를
     그대로 둔다 — 메모를 고쳤다고 "2문제" 가 목표치로 올라가면 안 된다. */
  const recordLearned = (routine, learned) =>
    run(async () => {
      const today = plan?.date ?? new Date().toISOString().slice(0, 10)
      await api.routines.log(routine.id, today, { done: true, learned })
      return (learned ?? "").trim()
        ? `${routine.title} — 몰랐던 것을 적어 뒀어요.`
        : `${routine.title} — 적어 둔 것을 지웠어요.`
    }, "적어 두지 못했습니다.")

  const undoRoutine = (routine) =>
    run(async () => {
      const today = plan?.date ?? new Date().toISOString().slice(0, 10)
      await api.routines.log(routine.id, today, { done: false })
      return `${routine.title} 오늘 기록을 지웠어요.`
    }, "되돌리지 못했습니다.")

  const start = (task) => {
    // 계획을 세운 뒤 루틴에 경로를 연결했어도 바로 열린다 — 다음 단계는 지금 계산한 값.
    const stepId = task.learning_step_id ?? task.routine?.next_step?.id
    if (stepId) return onOpenStep(stepId)
    /* 루틴은 학습 화면으로 보내지 않는다 — 코테를 눌렀는데 늘 보던 학습 화면이
       나오면 시작한 게 아니다. 적어 둔 곳을 열거나, 없으면 그 자리에서 알려 준다. */
    if (task.routine) {
      if (task.routine.link_url) {
        window.open(task.routine.link_url, "_blank", "noopener,noreferrer")
        return
      }
      // 스크롤은 패널이 그려진 뒤 패널이 직접 한다 (RoutineStart).
      setHowToId(task.id)
      return
    }
    if (task.application_id) return onNavigate(["applications", String(task.application_id)])
    if (task.opportunity_id) return onNavigate("opportunities")
    if (task.project_id) return onNavigate("projects")
    /* 자료는 내 자료 **목록**으로 보내지 않는다. 책 한 권을 펼쳐놓고
       "시작하세요" 하는 것과 같아서, 눌러도 아무것도 안 나온 것처럼 보였다.
       오늘 읽을 데를 그 자리에서 보인다 (ResourceStart). */
    if (task.resource) {
      setHowToId(task.id)
      return
    }
    if (task.learning_resource_id) return onNavigate("library")
    /* 여기까지 왔다면 열 곳이 없는 일이다. 예전에는 학습 화면으로
       보냈지만 그건 시작이 아니라 길을 잃는 것이었다. 아무것도 안 한다 —
       hasDestination 이 애초에 버튼을 숨기므로 보통은 닿지 않는다. */
  }

  if (loading) {
    return <LoadingState label="오늘 계획을 불러오는 중…" />
  }

  if (!plan) {
    return <ErrorState message={error} onRetry={() => load()} />
  }

  const tasks = plan.tasks ?? []
  const active = tasks.filter((task) => task.status !== "skipped")
  const done = tasks.filter((task) => task.status === "done")
  const next = active.find((task) => task.status === "planned")

  // 넘긴 것은 목록에서 뺀다. 넘겼는데 계속 보이면 넘긴 게 아니다 —
  // 대신 접은 줄에 모아 두고, 마감이 가까운 것만 따로 묻는다.
  const skipped = tasks.filter((task) => task.status === "skipped")

  /* 공고 · 지원은 시간을 쓰는 일이 아니라 정할 일이다. 상한(VISIBLE_TASKS)에도 넣지 않고
     아래에 따로 둔다 — 안 그러면 공고 두 건이 들어온 날 공부가 접힌 줄로 밀린다. */
  const deciding = active.filter((task) => task.lane === "deciding")
  const work = active.filter((task) => task.lane !== "deciding")

  const visible = work.slice(0, VISIBLE_TASKS)
  const rest = work.slice(VISIBLE_TASKS)

  /* 갈래로 묶어 보인다. 무조건 하는 일(루틴)은 이미 맨 위에 따로 있다. */
  const laneOrder = ["course", "study", "project", "other"]
  const grouped = laneOrder
    .map((lane) => ({
      lane,
      label: visible.find((task) => task.lane === lane)?.lane_label || lane,
      items: visible.filter((task) => task.lane === lane)
    }))
    .filter((group) => group.items.length > 0)

  // 마감 3일 안인데 오늘 넘긴 것 — 조용히 묻어 두지 않는다.
  const urgentSkipped = skipped.filter((task) => {
    const deadline = (plan.deadlines ?? []).find(
      (row) =>
        (row.kind === "opportunity" && row.id === task.opportunity_id) ||
        (row.kind === "application" && row.id === task.application_id)
    )
    return deadline && deadline.days_left <= 3
  })

  const inputs = why?.inputs ?? []
  const market = inputs.find((cell) => cell.key === "market" && cell.available)
  const gap = inputs.find((cell) => cell.key === "gap")
  const rail = inputs.filter(
    (cell) => RAIL_KEYS.includes(cell.key) && cell.available
  )

  const conclusion = why?.focus_skill
    ? [why.headline, market?.detail].filter(Boolean).join(" ")
    : null

  let hero

  if (tasks.length === 0) {
    hero = (
      <NextActionCard
        eyebrow="가장 먼저 할 일"
        icon="+"
        title="아직 오늘 계획이 없어요"
        meta="우선순위 · 마감 · 어제 못 한 일을 보고 Career OS 가 골라 드려요."
        action={
          <Button writes disabled={working} onClick={createPlan}>
            계획 세우기
          </Button>
        }
      />
    )
  } else if (!next) {
    hero = (
      <NextActionCard
        eyebrow="오늘"
        tone="ok"
        icon="✓"
        title="오늘 계획을 모두 끝냈어요"
        detail={`${done.length}개 · ${minutesText(plan.done_minutes)}`}
        meta="한 일은 회고의 날마다 칸에 쌓입니다."
        action={
          <a className="ui-btn ui-btn-secondary" href="#/review">
            회고 보기
          </a>
        }
      />
    )
  } else {
    hero = (
      <NextActionCard
        eyebrow="가장 먼저 할 일"
        icon="▶"
        title={next.title}
        detail={`${areaLabel(next.task_type)} · ${minutesText(next.minutes)}`}
        meta={next.reason}
        action={<Button onClick={() => start(next)}>시작하기</Button>}
      />
    )
  }

  return (
    <div className="today-page td">
      {/* 즐겨찾기 공고 — 마감이 멀거나 없어서 오늘 계획에 안 올라오는 것들이다.
          매칭 점수가 가장 높은 공고가 정작 마감이 없어서 묻히는 일이 있었다.
          여기서 세어 주면 적어도 눈에서 사라지지는 않는다. */}
      {favorites.length > 0 && (
        <section className="card td-favorites" aria-label="즐겨찾기 공고">
          <p className="td-fav-head">
            즐겨찾기 {favorites.length}건
            <span className="td-fav-why">계획에 없어도 잊지 않게 여기 둡니다</span>
          </p>
          <div className="td-fav-rows">
            {favorites.slice(0, 5).map((row) => (
              <a className="td-fav-row" key={row.id} href="#/opportunities">
                <span className="td-fav-title">{row.title}</span>
                <span className="td-fav-meta">
                  {row.organization || "—"}
                  {row.match_score != null && ` · ${Math.round(row.match_score)}점`}
                  {row.deadline
                    ? ` · ${String(row.deadline).slice(0, 10)}`
                    : " · 마감 없음"}
                </span>
              </a>
            ))}
          </div>
          {favorites.length > 5 && (
            <p className="td-fav-more">
              그리고 {favorites.length - 5}건 더 —{" "}
              <a className="td-link" href="#/opportunities">기회 화면</a>
            </p>
          )}
        </section>
      )}

      {/* ---------- 요약 ---------- */}
      <section className="card td-hero">
        <p className="td-greet">
          {greeting()}
          <span className="td-date">{todayText()}</span>
        </p>

        <div className="td-facts">
          <div className="td-fact">
            <span className="td-fact-key">오늘 사용할 수 있는 시간</span>
            <strong className="td-fact-value">
              {minutesText(plan.available_minutes)}
            </strong>
            <span className="td-fact-hint">
              {calendar
                ? `일정을 빼고 빈 ${minutesText(calendar.free_minutes)} 중 하루 상한까지`
                : "캘린더를 읽지 못해 기본값을 썼어요"}
            </span>
          </div>

          <div className="td-fact">
            <span className="td-fact-key">오늘의 핵심 초점</span>
            <strong className="td-fact-value">{why?.focus_skill ?? "아직 없음"}</strong>
            <span className="td-fact-hint">
              {why?.focus_skill
                ? [
                    market && `시장 수요 ${market.value.split("·").pop().trim()}건`,
                    gap?.value
                  ]
                    .filter(Boolean)
                    .join(" · ")
                : "스킬과 공고가 쌓이면 정해져요"}
            </span>
          </div>

          <div className="td-fact">
            <span className="td-fact-key">오늘 진행</span>
            <strong className="td-fact-value">
              {done.length} / {active.length}
            </strong>
            <ProgressBar
              value={done.length}
              max={Math.max(1, active.length)}
              label="오늘 계획 진행"
            />
          </div>
        </div>

        {hero}
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

      {/* 매일 하는 일 — 계획 카드 **위**에 따로 둔다. 안에 넣으니 카드 안에 카드라 답답했다. */}
      <RoutineStrip
        routines={plan.routines}
        working={working}
        onOpenStep={onOpenStep}
        onRecord={recordRoutine}
        onUndo={undoRoutine}
        onLearned={recordLearned}
      />

      <div className="today-grid">
        {/* ---------- 작업 목록 ---------- */}
        <section className="card td-plan">
          <div className="td-plan-head">
            <div>
              <h2 className="td-plan-title">오늘 할 일</h2>
              <p className="td-plan-sub">
                {tasks.length > 0
                  ? `오늘 ${minutesText(plan.available_minutes)} 중 ${minutesText(plan.planned_minutes)}`
                    + (plan.routine_minutes
                        ? ` (매일 하는 일 ${minutesText(plan.routine_minutes)} 포함)`
                        : "")
                    + ` · 강도 ${plan.intensity_label}`
                    /* 실제로 적은 시간이 쌓이면 추정을 보정한다. 적을수록
                       오늘 몫이 내 속도에 맞춰 줄거나 늘어난다. */
                    + (plan.pace_factor
                        ? ` · 지금까지 계획의 ${plan.pace_factor.factor}배 걸렸어요 (${plan.pace_factor.samples}번 기록)`
                        : "")
                  : "아직 계획 전"}
              </p>
            </div>

            <Button
              variant="secondary"
              aria-expanded={showSettings}
              onClick={() => setShowSettings(!showSettings)}
            >
              {showSettings ? "설정 닫기" : "시간 · 강도 설정"}
            </Button>
          </div>

          {/* 계획은 세운 순간의 판단으로 저장된다. 그 뒤 공고가 들어와 1위가 바뀌면
              할 일의 "선택 이유" 와 아래 "왜 이 계획인가" 가 서로 다른 말을 한다. */}
          {plan?.outdated && (
            <Notice tone="warn">
              <strong>계획을 세운 뒤 바뀐 것이 있어요.</strong>{" "}
              {plan.outdated.reasons.join(" · ")}.{" "}
              <Button variant="secondary" writes disabled={working} onClick={createPlan}>
                지금 기준으로 다시 세우기
              </Button>
            </Notice>
          )}

          {showSettings && (
            <div className="plan-controls td-settings">
              <div className="plan-field">
                <span className="plan-key">사용 가능 시간</span>
                <div className="plan-minutes">
                  {PRESETS.map((preset) => (
                    <button
                      key={preset}
                      className={minutes === preset ? "chip chip-on" : "chip"}
                      aria-pressed={minutes === preset}
                      onClick={() => setMinutes(preset)}
                    >
                      {minutesText(preset)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="plan-field">
                <span className="plan-key">강도</span>
                <div className="plan-minutes">
                  {intensities.map((option) => (
                    <button
                      key={option.key}
                      className={intensity === option.key ? "chip chip-on" : "chip"}
                      aria-pressed={intensity === option.key}
                      title={`최대 ${option.max_tasks}개 · 한 덩어리 ${option.max_block}분까지`}
                      onClick={() => setIntensity(option.key)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>

              <Button writes disabled={working} onClick={createPlan}>
                이 설정으로 다시 세우기
              </Button>

              {/* 기본값이 어디서 나왔는지. 답할 수 없는 숫자를 기본값으로 두지 않는다. */}
              {calendar && (
                <p className="muted form-hint plan-source">
                  캘린더 기준 · 활동 시간대 {calendar.window_label} 중 일정{" "}
                  {minutesText(calendar.busy_minutes)}을 빼면{" "}
                  {minutesText(calendar.free_minutes)}이 비고, 하루 상한{" "}
                  {minutesText(calendar.daily_cap_minutes)}과 비교해{" "}
                  <strong>{minutesText(calendar.suggested_minutes)}</strong>을
                  제안했습니다. 일정을 바꾸면{" "}
                  <a className="td-link" href="#/calendar">
                    캘린더
                  </a>
                  에서 이 값이 바뀌고, 다시 세우면 계획에 반영됩니다.
                </p>
              )}
            </div>
          )}

          {plan.deadlines?.length > 0 && (
            <div className="td-deadlines" aria-label="다가오는 마감">
              {plan.deadlines.slice(0, 3).map((item) => (
                <StatusBadge
                  key={`${item.kind}-${item.id}`}
                  tone={item.days_left <= 3 ? "warn" : "neutral"}
                >
                  {ddayLabel(item.days_left)} · {item.title}
                </StatusBadge>
              ))}
            </div>
          )}

          {tasks.length === 0 ? (
            <EmptyState
              title="아직 오늘 계획이 없습니다."
              body="우선순위 · 마감 · 어제 못 한 일을 보고 오늘 할 일을 1~3개 고릅니다."
              actions={[
                { label: "계획 세우기", onClick: createPlan, primary: true, writes: true, disabled: working },
                { label: "캘린더에서 시간 확인", href: "#/calendar" }
              ]}
            />
          ) : (
            <>
              {/* 갈래로 묶는다. 한 갈래만 있으면 제목을 붙이지 않는다 — 한 줄짜리 목록에
                  제목을 달면 화면이 번잡해지기만 한다. */}
              {grouped.map((group) => (
                <section className="td-lane" key={group.lane}>
                  {grouped.length > 1 && (
                    <h3 className="td-lane-head">{group.label}</h3>
                  )}
                  <ol className="td-tasks">
                    {group.items.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={visible.indexOf(task)}
                        working={working}
                        onComplete={(count, actual) => complete(task, count, actual)}
                        onSkip={(reason) => skip(task, reason)}
                        onPark={() => park(task)}
                        onEdit={(body) => editTask(task, body)}
                        onRemove={() => removeTask(task)}
                        onSegmentDone={(segment, note) => finishSegment(task, segment, note)}
                        onStart={() => start(task)}
                        onReopen={() => reopen(task)}
                        onOpenStep={onOpenStep}
                        onSaved={() => load(true)}
                        showHow={howToId === task.id}
                      />
                    ))}
                  </ol>
                </section>
              ))}

              {/* 공고 · 지원은 아래에 목록으로만. 시간 예산과 자리를 먹지 않는다 —
                  마감은 놓치면 끝이라 보이기는 해야 한다. */}
              {deciding.length > 0 && (
                <section className="td-lane td-deciding" key="deciding">
                  <h3 className="td-lane-head">
                    공고 · 지원
                    <span className="td-lane-why">정할 일이라 시간에 넣지 않았어요</span>
                  </h3>
                  <ol className="td-tasks">
                    {deciding.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={-1}
                        working={working}
                        onComplete={(count, actual) => complete(task, count, actual)}
                        onSkip={(reason) => skip(task, reason)}
                        onPark={() => park(task)}
                        onEdit={(body) => editTask(task, body)}
                        onRemove={() => removeTask(task)}
                        onSegmentDone={(segment, note) => finishSegment(task, segment, note)}
                        onStart={() => start(task)}
                        onReopen={() => reopen(task)}
                        onOpenStep={onOpenStep}
                        onSaved={() => load(true)}
                        showHow={howToId === task.id}
                      />
                    ))}
                  </ol>
                </section>
              )}

              <AddTask
                working={working}
                remainingMinutes={plan.remaining_minutes}
                onAdded={(result) => {
                  load(true)
                  setNotice(
                    result.added
                      ? "오늘 계획에 넣었어요."
                      : result.reason || "이미 오늘 계획에 있어요."
                  )
                }}
                onError={setError}
              />

              {urgentSkipped.length > 0 && (
                <Notice tone="warn">
                  마감이 가까운데 오늘 넘긴 것이 있어요 —{" "}
                  {urgentSkipped.map((task) => task.title).join(" / ")}. 지원하지 않기로
                  했다면 기회 화면에서 보류하거나 치우면 다시 안 올라와요.
                </Notice>
              )}

              {skipped.length > 0 && (
                <details className="td-more">
                  <summary>오늘 넘긴 것 {skipped.length}개 — 되돌릴 수 있어요</summary>
                  <ol className="td-tasks">
                    {skipped.map((task, index) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={index}
                        working={working}
                        onComplete={(count, actual) => complete(task, count, actual)}
                        onSkip={(reason) => skip(task, reason)}
                        onPark={() => park(task)}
                        onEdit={(body) => editTask(task, body)}
                        onRemove={() => removeTask(task)}
                        onSegmentDone={(segment, note) => finishSegment(task, segment, note)}
                        onStart={() => start(task)}
                        onReopen={() => reopen(task)}
                        onOpenStep={onOpenStep}
                        onSaved={() => load(true)}
                        showHow={howToId === task.id}
                      />
                    ))}
                  </ol>
                </details>
              )}

              {/* "무엇을 하지 않아도 되는가" 를 말하지 않으면 고른 게 아니라 나열한 것이다. */}
              {/* 이 문장이 제품의 차별점이다. 접힌 버튼 안에 두면 열어야 발견한다. */}
              {rest.length > 0 && (
                <p className="td-enough">
                  오늘은 <strong>위의 {visible.length}개</strong>만 하세요. 나머지
                  {" "}{rest.length}개는 오늘 시간 {minutesText(plan.available_minutes)} 밖이라
                  내일 이후로 미뤘습니다.
                </p>
              )}

              {rest.length > 0 && (
                <details className="td-more">
                  <summary>미뤄 둔 {rest.length}개 보기</summary>
                  <ol className="td-tasks" start={VISIBLE_TASKS + 1}>
                    {rest.map((task, index) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        index={VISIBLE_TASKS + index}
                        working={working}
                        onComplete={(count, actual) => complete(task, count, actual)}
                        onSkip={(reason) => skip(task, reason)}
                        onPark={() => park(task)}
                        onEdit={(body) => editTask(task, body)}
                        onRemove={() => removeTask(task)}
                        onSegmentDone={(segment, note) => finishSegment(task, segment, note)}
                        onStart={() => start(task)}
                    onReopen={() => reopen(task)}
                    onOpenStep={onOpenStep}
                    onSaved={() => load(true)}
                    showHow={howToId === task.id}
                      />
                    ))}
                  </ol>
                </details>
              )}
            </>
          )}
        </section>

        {/* ---------- 근거 ---------- */}
        <section className="card today-why">
          {why?.focus_skill ? (
            <WhyPanel conclusion={conclusion}>
              {rail.length > 0 && (
                <dl className="today-why-list">
                  {rail.map((cell) => (
                    <div key={cell.key}>
                      <dt>{cell.ko}</dt>
                      <dd>{cell.value}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </WhyPanel>
          ) : (
            <EmptyState
              title="아직 판단할 데이터가 없어요."
              body="스킬과 공고가 있어야 무엇이 중요한지 고를 수 있어요."
              actions={[
                { label: "공고 모으기", href: "#/opportunities", primary: true },
                { label: "학습 경로 만들기", href: "#/learning" }
              ]}
            />
          )}

          {why && (
            <button className="today-why-more" onClick={onWhy}>
              계산 근거 전체 보기 →
              <span>
                쓰인 데이터 {why.used_count ?? 0} / {inputs.length}종
              </span>
            </button>
          )}
        </section>
      </div>

      {/* 기한 없이 빼둔 것. "오늘은 넘기기" 는 그날로 끝나지만 이건 남는다.
          날짜에 묶이지 않아 매일 보이고, 여기서 바로 끝낼 수 있다. */}
      {plan.parked?.length > 0 && (
        <section className="card parked-box">
          <p className="stale-head">
            언젠가 할 일
            <span className="stale-why">기한 없이 빼둔 것 — 오늘 계획을 밀어내지 않아요</span>
          </p>

          {plan.parked.map((item) => (
            <div className="stale-row" key={item.id}>
              <span className="stale-title">
                <span className="stale-name">{item.title}</span>
                <span className="stale-days">{item.minutes}분</span>
              </span>
              <Button
                writes
                tryInDemo
                disabled={working}
                onClick={() =>
                  run(async () => {
                    const result = await api.todayPlan.complete(item.id)
                    return result.effects?.length
                      ? `완료했어요 — ${result.effects.join(" · ")}`
                      : "완료했어요. 한 기록이 남았습니다."
                  }, "완료로 표시하지 못했습니다.")
                }
              >
                완료
              </Button>
              <Button
                variant="quiet"
                writes
                tryInDemo
                disabled={working}
                onClick={() => unpark(item)}
              >
                오늘 하기
              </Button>
            </div>
          ))}
        </section>
      )}

      {/* 사흘 넘게 밀린 것. 계획에서 빠졌다는 사실을 말해주지
          않으면 조용히 버린 것과 같다. 두 답이 다 가능해야 질문이다. */}
      {plan.stale?.length > 0 && (
        <section className="card stale-box">
          <p className="stale-head">
            이건 안 할 건가요?
            <span className="stale-why">
              사흘 넘게 미뤄서 오늘 계획에서 뺐습니다 · {plan.stale.length}개
            </span>
          </p>

          {/* 오래 밀린 것부터. 열한 줄을 한꺼번에 들이밀면 읽지 않고 넘긴다 —
              물어보려고 만든 칸이 거꾸로 안 보이게 된다. 먼저 넷만 묻는다. */}
          {(showAllStale ? plan.stale : plan.stale.slice(0, STALE_PREVIEW)).map((item) => (
            <div className="stale-row" key={item.task_id}>
              <span className="stale-title">
                <span className="stale-name">{item.title}</span>
                <span className="stale-days">{item.days_carried}일째</span>
              </span>
              <Button
                variant="quiet"
                writes
                disabled={working}
                onClick={() =>
                  run(async () => {
                    await api.todayPlan.revive(item.task_id)
                    return `'${item.title}' 을(를) 다시 계획 후보로 돌렸어요.`
                  })
                }
              >
                그래도 할래요
              </Button>
              <Button
                variant="quiet"
                writes
                disabled={working}
                onClick={() =>
                  run(async () => {
                    await api.todayPlan.skip(item.task_id)
                    return `'${item.title}' 을(를) 치웠어요.`
                  })
                }
              >
                치우기
              </Button>
            </div>
          ))}

          {plan.stale.length > STALE_PREVIEW && (
            <button
              className="stale-more"
              onClick={() => setShowAllStale((current) => !current)}
            >
              {showAllStale
                ? "접기"
                : `나머지 ${plan.stale.length - STALE_PREVIEW}개 더 보기`}
            </button>
          )}
        </section>
      )}
    </div>
  )
}

export default TodayPage
