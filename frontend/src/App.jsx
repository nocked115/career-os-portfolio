import { useEffect, useState } from "react"
import "./App.css"
import "./Universe.css"
import "./ui.css"
import * as api from "./api"
import { ReadOnlyContext } from "./readOnly"
import { useHashRoute } from "./router"
import LearningPage from "./components/LearningPage"
import LearningSession from "./components/LearningSession"
import TodayFocus from "./components/TodayFocus"
import TodayPage from "./components/TodayPage"
import WhyPlanPage from "./components/WhyPlanPage"
import OpportunitiesPage from "./components/OpportunitiesPage"
import CalendarPage from "./components/CalendarPage"
import CareerCompanion from "./components/CareerCompanion"
import DemoBanner from "./components/DemoBanner"
import OverviewPage from "./components/OverviewPage"
import ProfileHeader from "./components/ProfileHeader"
import ProjectsPage from "./components/ProjectsPage"
import Sidebar from "./components/Sidebar"
import Universe from "./components/Universe"
import ProofPage from "./components/ProofPage"
import ReviewPage from "./components/ReviewPage"
import ApplicationsPage from "./components/ApplicationsPage"

/* 경로 조각 → 화면.
   경로 이름은 사용자가 링크에서 보는 것이므로 화면 이름과 맞춘다. */
const ROUTES = {
  today: "dashboard",
  overview: "overview",
  calendar: "calendar",
  learning: "learning",
  library: "library",
  projects: "projects",
  opportunities: "opportunities",
  applications: "applications",
  experience: "proof",
  review: "review"
}

const PATHS = Object.fromEntries(
  Object.entries(ROUTES).map(([path, name]) => [name, path])
)


function App() {
  const [today, setToday] = useState(null)
  const [weeklyPlan, setWeeklyPlan] = useState(null)
  const [learningPriority, setLearningPriority] = useState(null)
  const [jobs, setJobs] = useState(null)
  const [projects, setProjects] = useState(null)
  const [readOnly, setReadOnly] = useState(false)

  // 화면은 URL 에서 나온다. 상태값으로 전환하면 뒤로가기도,
  // "이 화면 봐줘" 라고 링크를 보내는 것도 안 된다.
  const { segments, navigate } = useHashRoute()

  const view =
    segments[0] === "today" && segments[1] === "why"
      ? "why"
      : ROUTES[segments[0]] ?? "universe"
  const sessionStepId =
    segments[0] === "learning" && segments[1] === "sessions"
      ? Number(segments[2]) || null
      : null
  const applicationId =
    segments[0] === "applications" && segments[1]
      ? Number(segments[1]) || null
      : null

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const applyDashboard = (data) => {
    setToday(data.today)
    setWeeklyPlan(data.weeklyPlan)
    setLearningPriority(data.learningPriority)
    setJobs(data.jobs)
    setProjects(data.projects)
    setReadOnly(Boolean(data.config?.read_only))
  }

  // 학습 단계를 완료하면 우선순위와 Today 계획이 바뀌므로
  // 대시보드를 다시 읽어온다.
  const refreshDashboard = async () => {
    try {
      applyDashboard(await api.fetchDashboard())
    } catch (refreshError) {
      console.error("Failed to refresh dashboard:", refreshError)
    }
  }

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        setLoading(true)
        setError(null)

        applyDashboard(await api.fetchDashboard())
      } catch (error) {
        console.error("Failed to load Career OS:", error)

        setError("데이터를 불러오지 못했습니다.")
      } finally {
        setLoading(false)
      }
    }

    loadDashboard()
  }, [])

  if (loading) {
    return (
      <div className="app-gate" role="status" aria-live="polite">
        <div className="app-gate-box">
          <span className="ui-spinner" aria-hidden="true" />
          <p>Career OS 를 여는 중…</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-gate" role="alert">
        <div className="app-gate-box">
          <h2>Career OS 를 열지 못했어요</h2>
          <p>{error}</p>
          <p className="muted">
            잠시 뒤 다시 시도해 주세요. 계속되면 서버가 켜져 있는지 확인이 필요해요.
          </p>
          <button
            type="button"
            className="ui-btn ui-btn-primary"
            onClick={() => window.location.reload()}
          >
            다시 시도
          </button>
        </div>
      </div>
    )
  }

  if (
    !today ||
    !weeklyPlan ||
    !learningPriority ||
    !jobs ||
    !projects
  ) {
    return (
      <div className="app-gate">
        <div className="app-gate-box">
          <h2>아직 보여줄 데이터가 없어요</h2>
          <p className="muted">스킬이나 공고를 먼저 등록해 주세요.</p>
        </div>
      </div>
    )
  }

  // 홈은 우주. 작업 화면의 껍데기를 쓰지 않는다 —
  // 궤도 위에 사이드바와 카드가 겹치면 둘 다 죽는다.
  if (view === "universe") {
    return (
      <ReadOnlyContext.Provider value={readOnly}>
        <DemoBanner readOnly={readOnly} />

        <Universe
          onToday={() => navigate("today")}
          onEnter={(route, target) => {
            // 천체가 화면 안 특정 자리를 가리키면 그것도 경로에 담는다.
            navigate(target ? [PATHS[route], target] : [PATHS[route]])
          }}
        />
      </ReadOnlyContext.Provider>
    )
  }

  return (
    <ReadOnlyContext.Provider value={readOnly}>
    <div className="app">
      <DemoBanner readOnly={readOnly} />

      <Sidebar
        view={view}
        onNavigate={(next) => navigate(PATHS[next] ?? next)}
        onHome={() => navigate([])}
      />

      <div className="app-main">
        {/* 우주에서 내려온 자리. 띠가 있어야 텔레포트가 아니라
            이동으로 읽힌다. */}
        <div className="topbar-band">
          <header className="topbar">
            <ProfileHeader />
          </header>
        </div>

      {view === "why" && (
        <main className="dashboard">
          <WhyPlanPage onBack={() => navigate("today")} />
        </main>
      )}

      {view === "overview" && (
        <main className="dashboard">
          <OverviewPage weeklyPlan={weeklyPlan} />
        </main>
      )}

      {view === "calendar" && (
        <main className="dashboard">
          <CalendarPage />
        </main>
      )}

      {view === "projects" && (
        <main className="dashboard">
          <ProjectsPage onChanged={refreshDashboard} />
        </main>
      )}

      {view === "library" && (
        <main className="dashboard">
          <LearningPage
            onOpenSession={(id) =>
              navigate(["learning", "sessions", String(id)])
            }
            initialTab="library"
          />
        </main>
      )}

      {view === "applications" && (
        <main className="dashboard">
          <ApplicationsPage
            onChanged={refreshDashboard}
            openId={applicationId}
            onOpen={(id) => navigate(["applications", String(id)])}
            onClose={() => navigate("applications")}
          />
        </main>
      )}

      {view === "proof" && (
        <main className="dashboard">
          <ProofPage onChanged={refreshDashboard} focus={segments[1]} />
        </main>
      )}

      {view === "review" && (
        <main className="dashboard">
          <ReviewPage />
        </main>
      )}

      {view === "opportunities" && (
        <main className="dashboard">
          <OpportunitiesPage />
        </main>
      )}

      {view === "learning" && (
        <main className="dashboard">
          {sessionStepId ? (
            <LearningSession
              key={sessionStepId}
              stepId={sessionStepId}
              onBack={() => navigate("learning")}
              onCompleted={refreshDashboard}
              onOpenSession={(id) =>
                navigate(["learning", "sessions", String(id)])
              }
              onToday={() => navigate("today")}
            />
          ) : (
            <LearningPage
              onOpenSession={(id) =>
                navigate(["learning", "sessions", String(id)])
              }
              initialTab={segments[1] === "library" ? "library" : "paths"}
            />
          )}
        </main>
      )}

      <main
        className="dashboard"
        hidden={view !== "dashboard"}
      >
        {/* TODAY — 무엇에 집중할지, 그리고 왜 그것인지 */}

        {/* 계획이 먼저다. "오늘 뭘 하면 되지?" 의 답이고,
            아래 카드는 그 답의 근거다. 근거가 위에 있으면 답이
            접히는 선 아래로 내려간다 — 홈에서 TODAY 를 올린 것과
            같은 이유다 (DESIGN.md). */}
        <TodayPage
          onChanged={refreshDashboard}
          onNavigate={(next) => navigate(PATHS[next] ?? next)}
          onOpenStep={(stepId) =>
            navigate(["learning", "sessions", String(stepId)])
          }
          onWhy={() => navigate(["today", "why"])}
        />

        <TodayFocus
          today={today}
          onOpenStep={(stepId) =>
            navigate(["learning", "sessions", String(stepId)])
          }
        />

      </main>

      </div>

      {/* Agent 는 중심이 아니라 동반자다. 우하단에 작게,
          화면에 따라 역할이 바뀐다 (DESIGN.md 7장). */}
      <CareerCompanion view={view} onChanged={refreshDashboard} />
    </div>
    </ReadOnlyContext.Provider>
  )
}

export default App