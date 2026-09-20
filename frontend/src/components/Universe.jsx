import { useCallback, useEffect, useRef, useState } from "react"
import * as api from "../api"

/* Career Universe — 홈.

   DESIGN.md 1~4d 장.

   가운데는 나. 궤도의 천체는 커리어를 이루는 영역.
   Today 는 행성이 아니다 — 모든 영역이 모이는 중심이라 가운데에 붙는다.

   천체를 고르면 바로 들어가지 않는다. 아래 요약 패널이 열린다.
   클릭 즉시 이동이면 그냥 메뉴다. 요약을 한 번 거치면 선택이 된다.

   우주지 우주 게임이 아니다. 궤도는 어디로 갈지 정하는 곳이고,
   실제로 학습하고 지원서를 쓰는 화면은 밝고 차분해야 한다. */

const FRONT = Math.PI / 2
const TICKS = 36

/* 천체마다 궤도 반경과 크기를 달리 준다.

   전부 같은 타원 위에 균등 배치하면 메뉴 바가 휜 것처럼 보인다.
   제각각 떨어져 있어야 "영역들이 모인 하나의 계" 로 읽힌다.

   난수가 아니라 고정값이다 — 다시 그릴 때마다 자리가 바뀌면
   어디에 무엇이 있는지 외울 수가 없다. */
const SPREAD = [
  { rx: 1.0, ry: 1.0, scale: 1.0 },
  { rx: 0.83, ry: 1.16, scale: 0.88 },
  { rx: 1.08, ry: 0.87, scale: 1.06 },
  { rx: 0.91, ry: 1.09, scale: 0.94 },
  { rx: 1.05, ry: 0.93, scale: 1.0 },
  { rx: 0.86, ry: 1.13, scale: 0.9 }
]

// 근거의 세기. 영어 대문자 HIGH/MID/LOW 대신 읽히는 말로.
const LEVELS = { high: "높음", mid: "보통", low: "낮음" }

function spread(index) {
  return SPREAD[index % SPREAD.length]
}

function Universe({ onEnter, onToday }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [current, setCurrent] = useState(0)

  const areaRef = useRef(null)
  const angleRef = useRef(FRONT)
  const targetRef = useRef(FRONT)
  const rafRef = useRef(null)
  const dragRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      setData(await api.universe.get())
    } catch (loadError) {
      console.error("Failed to load universe:", loadError)
      setError("Career Universe 를 불러오지 못했습니다.")
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const planets = data?.planets ?? []
  const count = planets.length

  /* 궤도 배치. 라이브러리 없이 sin/cos 로 타원을 그린다. */
  const layout = useCallback(() => {
    const area = areaRef.current
    if (!area || count === 0) return

    const width = area.clientWidth
    const height = area.clientHeight
    const cx = width / 2
    const cy = height / 2
    // 폭이 아직 0 일 때(숨겨진 채 마운트되는 순간) 음수가 되면
    // SVG 가 rx="-80" 을 거부하고 콘솔에 에러를 남긴다.
    const rx = Math.max(40, Math.min(360, width / 2 - 80))
    const ry = Math.max(80, Math.min(148, height / 2 - 78))
    const step = (Math.PI * 2) / count
    const angle = angleRef.current

    const svg = area.querySelector(".orbit-svg")
    if (svg) {
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`)

      svg.querySelectorAll("ellipse").forEach((ring) => {
        const factor = Number(ring.dataset.factor ?? 1)

        ring.setAttribute("cx", cx)
        ring.setAttribute("cy", cy)
        ring.setAttribute("rx", rx * factor)
        ring.setAttribute("ry", ry * factor)
      })
    }

    // 표식은 천체 라벨 아래로 내린다.
    // 천체는 점이 링 위에 뜨고 이름이 링을 가로질러 내려오므로,
    // 링 바로 아래에 표식을 두면 이름과 겹친다 (DESIGN.md 겹침 금지).
    const marker = area.querySelector(".orbit-marker")
    if (marker) marker.style.top = `${cy + ry + 52}px`

    const tickStep = (Math.PI * 2) / TICKS
    area.querySelectorAll(".orbit-tick").forEach((tick, index) => {
      const a = angle + index * tickStep
      const sin = Math.sin(a)
      const depth = (sin + 1) / 2

      tick.style.transform =
        `translate(${cx + rx * Math.cos(a)}px, ${cy + ry * sin}px) ` +
        `scale(${(0.55 + depth * 0.75).toFixed(3)})`
      tick.style.opacity = (0.18 + depth * 0.82).toFixed(3)
    })

    area.querySelectorAll(".planet").forEach((node, index) => {
      const a = angle + index * step
      const sin = Math.sin(a)
      const depth = (sin + 1) / 2
      const own = spread(index)

      node.style.transform =
        `translate(${cx + rx * own.rx * Math.cos(a)}px, ` +
        `${cy + ry * own.ry * sin}px) ` +
        `scale(${((0.74 + depth * 0.34) * own.scale).toFixed(3)})`
      node.style.opacity = (0.6 + depth * 0.4).toFixed(3)
      node.style.zIndex = String(Math.round(depth * 200) + 60)
    })
  }, [count])

  const animate = useCallback(() => {
    const diff = targetRef.current - angleRef.current

    if (Math.abs(diff) < 0.0006) {
      angleRef.current = targetRef.current
      layout()
      rafRef.current = null
      return
    }

    angleRef.current += diff * 0.14
    layout()
    rafRef.current = requestAnimationFrame(animate)
  }, [layout])

  const run = useCallback(() => {
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(animate)
    }
  }, [animate])

  const select = useCallback(
    (index) => {
      if (count === 0) return

      const step = (Math.PI * 2) / count
      let delta = (((index - current) % count) + count) % count
      if (delta > count / 2) delta -= count

      setCurrent((((index % count) + count) % count))
      targetRef.current -= delta * step
      run()
    },
    [count, current, run]
  )

  useEffect(() => {
    layout()

    const onResize = () => layout()
    window.addEventListener("resize", onResize)

    return () => {
      window.removeEventListener("resize", onResize)
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [layout])

  // 화살표는 궤도에 초점이 있을 때만 링을 돌린다. window 에 걸면
  // 입력 칸이나 다른 곳에서 누른 화살표까지 가로챈다.
  const onOrbitKey = (event) => {
    if (event.key === "ArrowRight") {
      select(current + 1)
      event.preventDefault()
    }
    if (event.key === "ArrowLeft") {
      select(current - 1)
      event.preventDefault()
    }
  }

  if (error) {
    return (
      <div className="universe">
        <div className="universe-error" role="alert">
          <p>{error}</p>
          <button type="button" className="orbit-enter" onClick={load}>
            다시 시도
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="universe">
        <p className="universe-loading" role="status">Career Universe 를 여는 중…</p>
      </div>
    )
  }

  const me = data.me
  const readiness = data.readiness
  const planet = planets[current]

  /* 배경의 별은 쌓인 증거의 실제 개수다. 장식이 아니다. */
  const stars = Array.from({ length: data.evidence.total }, (_, index) => ({
    left: ((index * 4409) % 9973) / 9973,
    top: ((index * 2683) % 7919) / 7919
  }))

  const onPointerDown = (event) => {
    if (event.target.closest(".core")) return

    dragRef.current = {
      x: event.clientX,
      angle: targetRef.current,
      moved: false
    }
  }

  const onPointerMove = (event) => {
    const drag = dragRef.current
    if (!drag) return

    const dx = event.clientX - drag.x
    if (Math.abs(dx) <= 4) return

    // 캡처는 실제로 끌기 시작한 뒤에 건다.
    // 누르자마자 캡처하면 천체 버튼의 click 이 삼켜져서
    // 링은 돌아가는데 클릭 선택이 안 된다.
    if (!drag.moved) {
      drag.moved = true
      event.currentTarget.setPointerCapture(event.pointerId)
    }

    targetRef.current = drag.angle + dx * 0.0052
    angleRef.current = targetRef.current
    layout()
  }

  const onPointerUp = () => {
    const drag = dragRef.current
    if (!drag) return

    dragRef.current = null
    if (!drag.moved || count === 0) return

    // 손을 떼면 가장 앞에 온 천체로 맞춘다.
    const step = (Math.PI * 2) / count
    let best = 0
    let bestSin = -2

    for (let index = 0; index < count; index += 1) {
      const sin = Math.sin(targetRef.current + index * step)
      if (sin > bestSin) {
        bestSin = sin
        best = index
      }
    }

    const turns = Math.round(
      (FRONT - (targetRef.current + best * step)) / (Math.PI * 2)
    )

    setCurrent(best)
    targetRef.current = FRONT - best * step + turns * Math.PI * 2
    run()
  }

  return (
    <div className="universe">
      {/* 첫 화면에서 제품이 무엇을 해 주는지 한 줄로. 이게 없으면 궤도와 영역 여섯 개가
          먼저 읽혀 "기능 많은 커리어 대시보드" 가 된다. */}
      <p className="universe-line">
        지금 가진 시간과 쌓인 근거로 <strong>오늘 할 일 몇 가지</strong>를 골라 드려요.
      </p>

      <div className="universe-stars" aria-hidden="true">
        {stars.map((star, index) => (
          <span
            key={index}
            className="evidence-star"
            style={{
              left: `${star.left * 100}%`,
              top: `${star.top * 62}%`
            }}
          />
        ))}
      </div>

      <div
        className="orbit-area"
        ref={areaRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={onOrbitKey}
        role="group"
        aria-label="커리어 영역 궤도 — 좌우 화살표로 돌리기"
      >
        <svg className="orbit-svg" aria-hidden="true">
          <defs>
            <linearGradient id="orbitRing" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2A3547" stopOpacity="0.55" />
              <stop offset="45%" stopColor="#4A6DA8" stopOpacity="0.75" />
              <stop offset="100%" stopColor="#7FA6F5" stopOpacity="1" />
            </linearGradient>
            <linearGradient id="orbitGlow" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5B8DEF" stopOpacity="0" />
              <stop offset="100%" stopColor="#5B8DEF" stopOpacity="0.28" />
            </linearGradient>
          </defs>
          <ellipse
            data-factor="0.84"
            fill="none"
            stroke="#2a3547"
            strokeOpacity="0.5"
            strokeWidth="1"
          />
          <ellipse
            data-factor="1.14"
            fill="none"
            stroke="#2a3547"
            strokeOpacity="0.4"
            strokeWidth="1"
          />
          <ellipse
            data-factor="1"
            fill="none"
            stroke="url(#orbitGlow)"
            strokeWidth="12"
          />
          <ellipse
            data-factor="1"
            fill="none"
            stroke="url(#orbitRing)"
            strokeWidth="3"
          />
        </svg>

        {Array.from({ length: TICKS }, (_, index) => (
          <span
            key={index}
            className="orbit-tick"
            data-major={index % 6 === 0 ? "true" : "false"}
            aria-hidden="true"
          />
        ))}

        <span className="orbit-marker" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0c.7 6.2 5.1 10.6 12 12-6.9 1.4-11.3 5.8-12 12-.7-6.2-5.1-10.6-12-12C6.9 10.6 11.3 6.2 12 0z" />
          </svg>
        </span>

        <button
          className="core"
          type="button"
          onClick={onToday}
          aria-label={`오늘 계획 보기 — ${readiness.detail}`}
        >
          {/* 준비도 링. 퍼센트 하나만 띄우면 무엇의 퍼센트인지
              알 수 없어서, 아래에 근거를 반드시 같이 쓴다. */}
          <svg className="core-ring" viewBox="0 0 100 100" aria-hidden="true">
            <circle
              cx="50"
              cy="50"
              r="47"
              fill="none"
              stroke="#22304a"
              strokeWidth="2"
            />
            <circle
              cx="50"
              cy="50"
              r="47"
              fill="none"
              stroke="#5b8def"
              strokeWidth="2"
              strokeLinecap="round"
              strokeDasharray={`${(readiness.percent / 100) * 295} 295`}
              transform="rotate(-90 50 50)"
            />
          </svg>

          <span className="core-me">
            {me.has_name ? me.name : "MY CAREER"}
          </span>
          <span className="core-dir">
            {me.target_career ?? "목표 미설정"}
          </span>

          <span className="core-percent">{readiness.percent}%</span>
          <span className="core-note">스킬 레벨 평균 · 커리어 진척도가 아니에요</span>
          <span className="core-basis">
            {readiness.skill_count > 0
              ? `${readiness.basis} ${readiness.skill_count}개 평균 숙련도`
              : readiness.basis}
          </span>

          <span className="core-rule" />

          <span className="core-focus" title={me.focus_skill ?? undefined}>
            {me.focus_skill ? `집중 · ${me.focus_skill}` : "집중 스킬 없음"}
          </span>
        </button>

        {planets.map((item, index) => (
          <button
            key={item.key}
            className="planet"
            type="button"
            data-front={index === current ? "true" : "false"}
            onClick={() => select(index)}
            aria-label={`${item.ko} (${item.name}) — ${item.badge}`}
            aria-pressed={index === current}
          >
            <span className="planet-dot" />
            <span className="planet-name">{item.name}</span>
            <span className="planet-ko">{item.ko.split(" · ")[0]}</span>
            <span className="planet-badge">{item.badge}</span>
          </button>
        ))}
      </div>

      {/* 북극성. 궤도 바로 아래, 접히는 선 위에 둔다 —
          "오늘 뭘 하면 되지?" 가 스크롤 뒤에 있으면 안 된다. */}
      <div className="orbit-today">
        <button className="orbit-card orbit-card-today" onClick={onToday}>
          <span className="orbit-card-key">오늘 할 일 보기</span>
          {/* 개수만 보여서는 질문에 답이 안 된다. 첫 할 일을 바로 보인다. */}
          <strong>
            {data.today.first_task
              ? `먼저 · ${data.today.first_task.title}`
              : data.today.total_tasks > 0
                ? "오늘 계획을 모두 끝냈어요"
                : "오늘 뭘 하면 될까요?"}
          </strong>
          <span className="orbit-card-sub">
            {data.today.first_task
              ? `${data.today.first_task.area} · ${data.today.first_task.minutes}분 · 전체 ${data.today.done_tasks}/${data.today.total_tasks} 끝냄`
              : data.today.total_tasks > 0
                ? `${data.today.total_tasks}개 모두 끝냄`
                : "아직 계획이 없어요 — 눌러서 세우기"}
          </span>
          <span className="orbit-card-arrow" aria-hidden="true">→</span>
        </button>
      </div>

      {/* 들어가기 전 요약 — DESIGN.md 4d */}
      {planet && (
        <div className="orbit-panel">
          <div className="orbit-panel-head">
            <h2>{planet.name}</h2>
            <span>{planet.ko}</span>
          </div>

          <div className="orbit-panel-grid">
            <div>
              <p className="orbit-key">지금 볼 이유</p>
              <dl className="orbit-why">
                {planet.why.map((row) => (
                  <div className="orbit-why-row" key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>
                      <span className={`orbit-level orbit-${row.level}`}>
                        {LEVELS[row.level] ?? row.level}
                      </span>
                      <span className="orbit-detail">{row.detail}</span>
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div className="orbit-stats">
              {planet.stats.map((stat) => (
                <div key={stat.key}>
                  <p className="orbit-key">{stat.key}</p>
                  <p className="orbit-stat-value">
                    {stat.value}
                    {stat.sub && <small>{stat.sub}</small>}
                  </p>
                </div>
              ))}
            </div>

            <button
              className="orbit-enter"
              onClick={() => onEnter(planet.route, planet.section)}
            >
              들어가기 <span aria-hidden="true">→</span>
            </button>
          </div>
        </div>
      )}

      <div className="orbit-foot">
        <a className="orbit-card orbit-card-flat" href="#/overview">
          <span className="orbit-card-key">한눈에 보기</span>
          <strong>지금 상태를 한 장으로</strong>
          <span className="orbit-card-sub">
            준비도 · 이번 주 실행 · 영역별 요약
          </span>
          <span className="orbit-card-spark" aria-hidden="true">→</span>
        </a>
      </div>

      <p className="orbit-hint">
        <span className="orbit-key-cap">← →</span> 궤도를 누른 뒤 돌리기
        <span className="orbit-dot">·</span> 드래그 또는 천체 누르기
      </p>
    </div>
  )
}

export default Universe
