import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"
import { Button, EmptyState, ErrorState, LoadingState, Notice, ProgressBar, StatusBadge } from "./ui"
import { importanceLabel, minutesText, ownershipLabel, resourceTypeLabel } from "../format"
import { externalHref } from "../safeUrl"
import "../Library.css"

/* 내 자료 — 도서관을 그리는 것이 아니라, 자료를 서가처럼 정리한다.

   전에는 자료 46개가 세로로 길게 쌓여 있었다. 무엇을 보고 있고 무엇이
   다음인지 스크롤해야 알았다.

   이제 서가(언제 보는가)마다 가로 레일 하나 — 지금 학습 · 다음 학습 · 보류 ·
   분류 전 · 완료. 카드 모양은 자료 종류를 그대로 닮는다. 영상은 썸네일과
   재생 시간, 책은 세로 표지, 문서는 종이, 실습은 터미널.

   서가와 중요도는 다른 것이다. 서가는 언제, 중요도는 얼마나.
   사람이 정하지 않은 서가는 서버가 기록으로만 정하고 이유를 준다. */

const FILTERS = [
  { key: "all", label: "전체", types: null },
  { key: "book", label: "책", types: ["book"] },
  { key: "video", label: "영상", types: ["video", "youtube", "course"] },
  { key: "doc", label: "문서", types: ["official_doc", "documentation", "article", "paper"] },
  { key: "practice", label: "실습", types: ["practice", "problem", "dataset", "project_task"] }
]

const RAILS = [
  { key: "in_progress", title: "지금 학습", empty: "지금 학습 중인 자료가 없습니다." },
  { key: "queued", title: "다음 학습", empty: "다음에 볼 자료가 없습니다." },
  { key: "on_hold", title: "보류", empty: "보류한 자료가 없습니다." },
  { key: "saved", title: "분류 전", empty: null },
  { key: "completed", title: "완료", empty: null }
]

const BOOK_TONES = 6

function cardKind(type) {
  if (["video", "youtube", "course"].includes(type)) return "video"
  if (type === "book") return "book"
  if (["practice", "problem", "dataset", "project_task"].includes(type)) return "practice"
  return "document"
}

function toneOf(text = "") {
  let hash = 0
  for (const char of text) hash = (hash * 31 + char.codePointAt(0)) >>> 0
  return hash % BOOK_TONES
}

function youtubeId(url) {
  const match = String(url || "").match(
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([\w-]{11})/
  )
  return match?.[1] ?? null
}

// 영상 길이. 챕터를 초 단위로 쪼갠 영상은 정확한 초를 쓴다.
function clockText(item) {
  const seconds =
    item.unit_label === "초" && item.total_units
      ? item.total_units
      : (item.duration_minutes || 0) * 60

  if (!seconds) return null

  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const pad = (value) => String(value).padStart(2, "0")

  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

function metaText(item) {
  const kind = cardKind(item.resource_type)
  const percent = item.progress?.percent

  if (kind === "video") {
    return percent != null
      ? `${resourceTypeLabel(item.resource_type)} · 진행률 ${percent}%`
      : `${resourceTypeLabel(item.resource_type)} · ${item.duration_minutes ? minutesText(item.duration_minutes) : "길이 미정"}`
  }

  if (kind === "book") {
    return `책 · ${ownershipLabel(item.ownership)}${percent != null ? ` · ${percent}%` : ""}`
  }

  if (kind === "practice") {
    return `실습 · ${item.duration_minutes ? minutesText(item.duration_minutes) : "시간 미정"}${
      item.shelf === "completed" ? " · 완료" : ""
    }`
  }

  return `${resourceTypeLabel(item.resource_type)}${
    item.total_units ? ` · ${item.total_units}${item.unit_label}` : ""
  }${item.skill_name ? ` · ${item.skill_name}` : ""}`
}

function searchText(item) {
  return [
    item.title,
    resourceTypeLabel(item.resource_type),
    item.skill_name,
    item.url,
    ...(item.linked_steps ?? []).flatMap((step) => [step.title, step.path_title]),
    ...(item.segments ?? []).map((segment) => segment.label)
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
}

/* ---------- 카드 ---------- */

function ResourceCard({ item, hot, onOpen }) {
  const kind = cardKind(item.resource_type)
  const video = kind === "video" ? youtubeId(item.url) : null
  const clock = kind === "video" ? clockText(item) : null

  return (
    <button
      type="button"
      className={`rc rc-${kind}`}
      onClick={() => onOpen(item)}
      aria-label={`${item.title} · ${resourceTypeLabel(item.resource_type)} 자세히 보기`}
    >
      {hot && <span className={`rc-hot rc-hot-${hot.rank}`}>HOT {hot.rank}</span>}

      {kind === "video" && (
        <span className="rc-thumb">
          {video && <img src={`https://i.ytimg.com/vi/${video}/mqdefault.jpg`} alt="" loading="lazy" />}
          <span className="rc-play" aria-hidden="true">
            ▶
          </span>
          {clock && <span className="rc-clock">{clock}</span>}
        </span>
      )}

      {kind === "book" && (
        <span className={`rc-cover cover-${toneOf(item.title)}`}>
          <span className="rc-cover-title">{item.title}</span>
          <span className="rc-cover-foot">{item.skill_name}</span>
        </span>
      )}

      {kind === "document" && (
        <span className="rc-paper">
          <span className="rc-paper-tag">{item.resource_type === "paper" ? "논문" : "문서"}</span>
          <span className="rc-paper-title">{item.title}</span>
          <span className="rc-paper-lines" aria-hidden="true" />
        </span>
      )}

      {kind === "practice" && (
        <span className="rc-term">
          <span className="rc-term-bar" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="rc-term-prompt">&gt;_</span>
          <span className="rc-term-line">{item.title}</span>
        </span>
      )}

      <span className="rc-body">
        <strong className="rc-title">{item.title}</strong>
        <span className="rc-meta">{metaText(item)}</span>
        {item.progress?.percent != null && (
          <ProgressBar value={item.progress.percent} label={`${item.title} 진행률`} />
        )}
      </span>
    </button>
  )
}

/* ---------- 레일 ---------- */

function ResourceRail({ rail, items, hotById, expanded, onToggle, onOpen, emptyActions }) {
  const trackRef = useRef(null)

  if (items.length === 0 && !rail.empty) return null

  const scroll = (direction) => {
    const track = trackRef.current
    if (!track) return
    track.scrollBy({
      left: direction * track.clientWidth * 0.8,
      behavior: prefersReducedMotion() ? "auto" : "smooth"
    })
  }

  return (
    <section className="rail" id={`rail-${rail.key}`} aria-labelledby={`rail-title-${rail.key}`}>
      <div className="rail-head">
        <h2 className="rail-title" id={`rail-title-${rail.key}`}>
          {rail.title}
          <span className="rail-count">{items.length}</span>
        </h2>

        {items.length > 0 && (
          <div className="rail-tools">
            {!expanded && items.length > 3 && (
              <>
                <button type="button" className="rail-arrow" onClick={() => scroll(-1)} aria-label={`${rail.title} 앞으로`}>
                  ‹
                </button>
                <button type="button" className="rail-arrow" onClick={() => scroll(1)} aria-label={`${rail.title} 뒤로`}>
                  ›
                </button>
              </>
            )}
            {items.length > 3 && (
              <button type="button" className="rail-all" aria-expanded={expanded} onClick={onToggle}>
                {expanded ? "접기" : "전체 보기 →"}
              </button>
            )}
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <EmptyState title={rail.empty} actions={emptyActions ?? []} />
      ) : (
        <ul ref={trackRef} className={expanded ? "rail-track rail-grid" : "rail-track"}>
          {items.map((item) => (
            <li key={item.id} className="rail-item">
              <ResourceCard item={item} hot={hotById[item.id]} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/* ---------- 상세 서랍 (넓은 화면 오른쪽 · 좁은 화면 아래) ---------- */

function ResourceDrawer({ item, hot, working, onClose, onToPlan, onShelf }) {
  const closeRef = useRef(null)

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === "Escape") onClose()
    }

    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [onClose])

  useEffect(() => {
    closeRef.current?.focus()
  }, [item.id])

  const kind = cardKind(item.resource_type)
  const clock = kind === "video" ? clockText(item) : null
  const progress = item.progress ?? {}
  const href = externalHref(item.url)
  const segments = item.segments ?? []

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} aria-hidden="true" />

      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <div className="drawer-head">
          <div>
            <p className="card-label">
              {resourceTypeLabel(item.resource_type)} · {item.shelf_label}
            </p>
            <h2 id="drawer-title" className="drawer-title">
              {item.title}
            </h2>
          </div>
          <button ref={closeRef} type="button" className="drawer-close" onClick={onClose} aria-label="닫기">
            ×
          </button>
        </div>

        {hot && (
          <p className="drawer-hot">
            <span className={`rc-hot rc-hot-${hot.rank}`}>HOT {hot.rank}</span> {hot.reason}
          </p>
        )}

        <dl className="drawer-facts">
          <div>
            <dt>서가</dt>
            <dd>
              {item.shelf_label} <small>· {item.shelf_reason}</small>
            </dd>
          </div>
          <div>
            <dt>중요도</dt>
            <dd>{importanceLabel(item.importance)}</dd>
          </div>
          <div>
            <dt>진행률</dt>
            <dd>
              {progress.percent != null
                ? `${progress.percent}%${progress.total ? ` · 챕터 ${progress.done}/${progress.total}` : ""}`
                : "챕터가 없어 셀 수 없어요"}
            </dd>
          </div>
          {progress.next && (
            <div>
              <dt>다음 챕터</dt>
              <dd>{progress.next}</dd>
            </div>
          )}
          {(clock || item.total_units) && (
            <div>
              <dt>{kind === "video" ? "재생 시간" : "분량"}</dt>
              <dd>{clock ?? `${item.total_units}${item.unit_label}`}</dd>
            </div>
          )}
          <div>
            <dt>관련 스킬</dt>
            <dd>{item.skill_name || "없음"}</dd>
          </div>
          <div>
            <dt>학습 경로</dt>
            <dd>
              {item.linked_steps?.length
                ? item.linked_steps.map((step) => `${step.path_title} › ${step.title}`).join(", ")
                : "아직 어느 단계에도 연결되지 않았어요"}
            </dd>
          </div>
          <div>
            <dt>보유</dt>
            <dd>{ownershipLabel(item.ownership)}</dd>
          </div>
        </dl>

        {href && (
          <a className="ui-btn ui-btn-secondary" href={href} target="_blank" rel="noopener noreferrer">
            자료 열기 ↗
          </a>
        )}

        <div className="drawer-actions">
          <Button writes disabled={working || item.shelf === "completed"} onClick={onToPlan}>
            오늘 학습에 꺼내기
          </Button>
          {item.shelf !== "queued" && (
            <Button variant="secondary" writes disabled={working} onClick={() => onShelf("queued")}>
              다음 학습으로 보내기
            </Button>
          )}
          {item.shelf !== "in_progress" && item.shelf !== "completed" && (
            <Button variant="secondary" writes disabled={working} onClick={() => onShelf("in_progress")}>
              지금 학습으로
            </Button>
          )}
          {item.shelf !== "on_hold" && (
            <Button variant="quiet" writes disabled={working} onClick={() => onShelf("on_hold")}>
              보류로 이동
            </Button>
          )}
          {item.shelf !== "completed" && (
            <Button variant="quiet" writes disabled={working} onClick={() => onShelf("completed")}>
              완료로 표시
            </Button>
          )}
        </div>

        {segments.length > 0 && (
          <details className="drawer-chapters">
            <summary>챕터 {segments.length}개</summary>
            <ol>
              {segments.map((segment) => (
                <li key={segment.id} className={segment.status === "completed" ? "is-done" : undefined}>
                  <span aria-hidden="true">{segment.status === "completed" ? "✓" : "○"}</span>
                  <span>{segment.label}</span>
                  <small>{minutesText(segment.estimated_minutes)}</small>
                </li>
              ))}
            </ol>
            <p className="muted form-hint">챕터 체크와 추가는 아래 &lsquo;자료 등록 · 챕터 관리&rsquo;에서 해요.</p>
          </details>
        )}
      </aside>
    </>
  )
}

/* ---------- 화면 ---------- */

function LibraryShelf({ refreshKey, onChanged, onRegister }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [working, setWorking] = useState(false)

  const [query, setQuery] = useState("")
  const [filter, setFilter] = useState("all")
  const [openId, setOpenId] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [showCompleted, setShowCompleted] = useState(false)

  const load = useCallback(async (quiet = false) => {
    try {
      if (!quiet) setLoading(true)
      setLoadError(null)
      setData(await api.library.get())
    } catch (failure) {
      console.error("Failed to load library shelf:", failure)
      setLoadError("내 자료를 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(refreshKey > 0)
  }, [load, refreshKey])

  const closeDrawer = useCallback(() => setOpenId(null), [])

  const run = async (action, fallback) => {
    try {
      setWorking(true)
      setError(null)
      setNotice(null)
      const message = await action()
      await load(true)
      onChanged?.()
      if (message) setNotice(message)
    } catch (failure) {
      console.error("Library shelf action failed:", failure)
      setError(failure?.detail || fallback)
    } finally {
      setWorking(false)
    }
  }

  if (loading) {
    return <LoadingState label="내 자료를 불러오는 중…" />
  }

  if (!data) {
    return <ErrorState message={loadError} onRetry={() => load()} />
  }

  const hot = data.hot ?? []
  const hotById = Object.fromEntries(hot.map((row) => [row.resource_id, row]))
  const byId = Object.fromEntries(data.items.map((item) => [item.id, item]))

  const types = FILTERS.find((item) => item.key === filter)?.types
  const needle = query.trim().toLowerCase()

  const shown = data.items.filter(
    (item) =>
      (!types || types.includes(item.resource_type)) &&
      (!needle || searchText(item).includes(needle))
  )

  const onShelf = (key) =>
    shown
      .filter((item) => item.shelf === key)
      .sort((a, b) => (hotById[b.id]?.score ?? 0) - (hotById[a.id]?.score ?? 0))

  const opened = openId != null ? byId[openId] : null

  const toPlan = (item) =>
    run(async () => {
      const result = await api.library.addToPlan(item.id)

      return (
        <>
          {result.already_planned ? "이미 오늘 계획에 있어요" : "오늘 학습에 추가했어요"} — {result.task.title}.{" "}
          {result.session_step ? (
            <a className="td-link" href={`#/learning/sessions/${result.session_step.id}`}>
              학습 세션 열기 ({result.session_step.title}) →
            </a>
          ) : (
            <a className="td-link" href="#/today">
              오늘 계획 보기 →
            </a>
          )}
        </>
      )
    }, "오늘 학습에 추가하지 못했습니다.")

  const moveShelf = (item, shelf) =>
    run(async () => {
      const moved = await api.library.setShelf(item.id, shelf)
      return `'${item.title}' 을(를) ${moved.shelf_label}(으)로 옮겼어요.`
    }, "서가를 옮기지 못했습니다.")

  const scrollToRail = (key) =>
    document.getElementById(`rail-${key}`)?.scrollIntoView({ block: "start" })

  const railEmptyActions = {
    in_progress: [
      { label: "오늘 계획에서 추천받기", href: "#/today" },
      { label: "분류 전 자료 고르기", onClick: () => scrollToRail("saved") }
    ]
  }

  return (
    <div className="shelf">
      <section className="card shelf-head">
        <div className="evd-head">
          <div>
            <h2 className="shelf-title">내 학습 자료</h2>
            <p className="learn-sub">
              {data.summary.total}개 · 챕터 {data.summary.segments_done}/{data.summary.segments} 완료
            </p>
          </div>
          <Button variant="secondary" writes onClick={onRegister}>
            + 자료 등록
          </Button>
        </div>

        <label className="shelf-search">
          <span className="sr-only">자료 검색</span>
          <input
            type="search"
            className="agent-input"
            placeholder="제목 · 종류 · 스킬 · 학습 경로 · 챕터로 찾기"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>

        <div className="learn-tabs" role="tablist" aria-label="자료 종류">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              role="tab"
              aria-selected={filter === item.key}
              className={filter === item.key ? "chip chip-on" : "chip"}
              onClick={() => setFilter(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {hot.length > 0 ? (
          <div className="hot-strip">
            <p className="hot-strip-title">요즘 많이 다룬 자료</p>
            <ol className="hot-list">
              {hot.map((row) => (
                <li key={row.resource_id}>
                  <button type="button" className="hot-item" onClick={() => setOpenId(row.resource_id)}>
                    <span className={`hot-medal medal-${row.rank}`}>{row.rank}</span>
                    <span className="hot-body">
                      <strong>{byId[row.resource_id]?.title ?? "지워진 자료"}</strong>
                      <small>{row.reason}</small>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="muted form-hint">최근 30일 동안 챕터를 끝내거나 오늘 계획에서 자료를 완료하면 HOT 순위가 생겨요.</p>
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

      {shown.length === 0 ? (
        <section className="card">
          <EmptyState
            title="찾는 자료가 없습니다."
            body="다른 검색어를 쓰거나, 새 자료를 등록해 보세요."
            actions={[{ label: "자료 등록하기", onClick: onRegister, primary: true, writes: true }]}
          />
        </section>
      ) : (
        <section className="card shelf-rails">
          {RAILS.filter((rail) => rail.key !== "completed").map((rail) => (
            <ResourceRail
              key={rail.key}
              rail={rail}
              items={onShelf(rail.key)}
              hotById={hotById}
              expanded={Boolean(expanded[rail.key])}
              onToggle={() => setExpanded((current) => ({ ...current, [rail.key]: !current[rail.key] }))}
              onOpen={(item) => setOpenId(item.id)}
              emptyActions={railEmptyActions[rail.key]}
            />
          ))}

          {onShelf("completed").length > 0 && (
            <div className="rail-completed">
              <button type="button" className="rail-all" aria-expanded={showCompleted} onClick={() => setShowCompleted(!showCompleted)}>
                {showCompleted ? "완료한 자료 접기" : `완료한 자료 ${onShelf("completed").length}개 보기`}
              </button>
              {showCompleted && (
                <ResourceRail
                  rail={RAILS[4]}
                  items={onShelf("completed")}
                  hotById={hotById}
                  expanded={Boolean(expanded.completed)}
                  onToggle={() => setExpanded((current) => ({ ...current, completed: !current.completed }))}
                  onOpen={(item) => setOpenId(item.id)}
                />
              )}
            </div>
          )}

          <p className="muted form-hint shelf-legend">
            <StatusBadge>서가</StatusBadge> 언제 보는가 — 지금 · 다음 · 보류 · 완료.{" "}
            <StatusBadge tone="imp-primary">중요도</StatusBadge> 얼마나 중요한가 — 상세에서 확인해요.
          </p>
        </section>
      )}

      {opened && (
        <ResourceDrawer
          item={opened}
          hot={hotById[opened.id]}
          working={working}
          onClose={closeDrawer}
          onToPlan={() => toPlan(opened)}
          onShelf={(shelf) => moveShelf(opened, shelf)}
        />
      )}
    </div>
  )
}

export default LibraryShelf
