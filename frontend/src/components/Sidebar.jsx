/* 좌측 네비게이션.

   상단 탭은 항목이 늘어날수록 가로로 밀린다. Projects 와 My Library 가
   독립하면서 8개가 됐고, 그때부터 탭은 더 이상 맞지 않는다.

   Career Agent 는 목록의 한 항목이 아니라 맨 아래 따로 있다.
   가는 곳이 아니라 어디에 있든 옆에 있는 것이기 때문이다
   (DESIGN.md 7장). */

// 작업 화면은 한국어로 부른다 (2026-09-15 결정). 홈의 행성 이름만 영어를 함께 쓴다.
const ITEMS = [
  { key: "overview", label: "한눈에 보기", glyph: "▦" },
  { key: "dashboard", label: "오늘", glyph: "◎" },
  { key: "calendar", label: "캘린더", glyph: "◷" },
  { key: "learning", label: "학습", glyph: "◈" },
  { key: "projects", label: "프로젝트", glyph: "▲" },
  { key: "opportunities", label: "기회", glyph: "◇" },
  { key: "library", label: "내 자료", glyph: "▤" },
  { key: "applications", label: "지원서", glyph: "✉" },
  { key: "proof", label: "경험", glyph: "★" },
  { key: "review", label: "회고", glyph: "◑" }
]

// Why this plan? 은 Today 의 하위 화면이라 Today 를 켠 채 둔다.
const PARENT = { why: "dashboard" }

function Sidebar({ view, onNavigate, onHome }) {
  const active = PARENT[view] ?? view

  return (
    <aside className="sidebar">
      <button className="sidebar-brand" onClick={onHome}>
        <span className="sidebar-mark" aria-hidden="true">◉</span>
        Career OS
      </button>

      <nav className="sidebar-nav">
        {ITEMS.map((item) => (
          <button
            key={item.key}
            className={
              active === item.key
                ? "sidebar-item sidebar-item-on"
                : "sidebar-item"
            }
            aria-current={active === item.key ? "page" : undefined}
            onClick={() => onNavigate(item.key)}
          >
            <span className="sidebar-glyph" aria-hidden="true">
              {item.glyph}
            </span>
            {item.label}
          </button>
        ))}
      </nav>

      <button className="sidebar-home" onClick={onHome}>
        ← 우주 홈
      </button>
    </aside>
  )
}

export default Sidebar
