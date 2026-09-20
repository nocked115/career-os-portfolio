// Career OS API 접근을 한곳에 모은다.
// 이전에는 App.jsx 안에 http://127.0.0.1:8000 이 11군데 하드코딩돼 있어서
// 배포하거나 포트를 바꾸려면 전부 찾아 고쳐야 했다.

import { handleDemoWrite } from "./demoWrites"

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"

// 정적 데모 (GitHub Pages). 서버 없이, 데모 데이터로 미리 받아 둔 응답 묶음을 읽는다.
// 저장은 되지 않는다 — 쓰기 요청은 이유를 말하는 오류로 돌려준다.
export const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "1"
export const STATIC_DEMO_DATE = import.meta.env.VITE_DEMO_DATE ?? ""

let demoBundle = null

async function loadDemoBundle() {
  if (!demoBundle) {
    const response = await fetch(`${import.meta.env.BASE_URL}demo-data.json`)
    demoBundle = await response.json()
  }
  return demoBundle
}

async function staticRequest(path, options) {
  const method = options?.method ?? "GET"
  const bundle = await loadDemoBundle()

  if (method !== "GET") {
    // 몇 가지는 브라우저 안에서 흉내 낸다 — 체크 하나가 계획을 바꾸는 것이
    // 이 제품의 핵심인데, 버튼이 전부 잠긴 데모에서는 그게 증명되지 않는다.
    const body = options?.body ? JSON.parse(options.body) : null
    const simulated = handleDemoWrite(path, method, body, bundle)

    if (simulated) return structuredClone(simulated)

    const error = new Error(`Static demo is read-only: ${method} ${path}`)
    error.status = 403
    error.detail = "데모에서는 오늘 계획 체크만 눌러 볼 수 있어요. 나머지는 저장되지 않아요."
    throw error
  }

  // 같은 주소를 먼저, 없으면 조건(?…)을 뗀 주소를 쓴다 — 날짜 · 분 같은 조건이 달라도 화면이 빈다.
  const bare = path.split("?")[0]
  const hit = bundle.responses[path] ?? bundle.responses[bare]

  if (hit === undefined) {
    const error = new Error(`Static demo has no data for ${path}`)
    error.status = 404
    error.detail = "데모 데이터에 없는 화면이에요."
    throw error
  }

  return structuredClone(hit)
}

async function request(path, options) {
  if (STATIC_DEMO) {
    return staticRequest(path, options)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    const error = new Error(
      `API request failed: ${options?.method ?? "GET"} ${path} ` +
        `(${response.status})`
    )

    // 서버가 막힌 이유를 문장으로 주는 경우가 있다 (상태 전이 409 등).
    // 메시지는 그대로 두고 따로 붙인다 — 다른 화면의 오류 처리를 바꾸지 않는다.
    error.status = response.status

    try {
      const body = await response.json()
      error.detail = typeof body?.detail === "string" ? body.detail : null
    } catch {
      error.detail = null
    }

    throw error
  }

  return response.json()
}

export function get(path) {
  return request(path)
}

export function post(path, body) {
  return request(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  })
}

export function del(path) {
  return request(path, { method: "DELETE" })
}

export function patch(path, body) {
  return request(path, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  })
}

export function put(path, body) {
  return request(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body ?? {})
  })
}

// --------------------
// 대시보드
// --------------------

export const DEFAULT_DAILY_MINUTES = 120

export async function fetchDashboard(
  dailyMinutes = DEFAULT_DAILY_MINUTES
) {
  const [today, weeklyPlan, learningPriority, jobs, projects, config] =
    await Promise.all([
      get("/today"),
      get(`/weekly-plan?daily_available_minutes=${dailyMinutes}`),
      get("/analytics/learning-priority"),
      get("/jobs"),
      get("/projects"),
      // 구경용 배포본인지. 이걸 모르면 버튼이 먹통인 고장난 앱으로
      // 보인다. 서버가 오래된 버전이면 없을 수 있으니 기본값을 둔다.
      get("/config").catch(() => ({ read_only: false }))
    ])

  return { today, weeklyPlan, learningPriority, jobs, projects, config }
}

// --------------------
// Career Agent
// --------------------

export function sendAgentMessage(message) {
  return post("/agent", { message })
}

// --------------------
// Mission 021 리소스
// --------------------

export const learningPaths = {
  list: (params = "") => get(`/learning-paths${params}`),
  get: (id) => get(`/learning-paths/${id}`),
  create: (body) => post("/learning-paths", body),
  update: (id, body) => patch(`/learning-paths/${id}`, body),
  remove: (id) => del(`/learning-paths/${id}`),
  progress: (id) => get(`/learning-paths/${id}/progress`)
}

export const learningSteps = {
  list: (pathId) => get(`/learning-steps?learning_path_id=${pathId}`),
  create: (body) => post("/learning-steps", body),
  update: (id, body) => patch(`/learning-steps/${id}`, body),
  remove: (id) => del(`/learning-steps/${id}`),

  // Mission 022
  session: (id) => get(`/learning-steps/${id}/session`),
  start: (id) => post(`/learning-steps/${id}/start`),
  complete: (id) => post(`/learning-steps/${id}/complete`),
  // 다른 세션에 붙여넣을 텍스트 { text }
  handoff: (id) => get(`/learning-steps/${id}/handoff`),
  // 이 단계에서 내가 만든 것 — 노트 · 자료 · 코드의 주소
  addOutput: (id, body) => post(`/learning-steps/${id}/outputs`, body),
  removeOutput: (outputId) => del(`/step-outputs/${outputId}`),
  toExperience: (id) => post(`/learning-steps/${id}/experience`),
  linkResource: (id, resourceId) =>
    post(`/learning-steps/${id}/resources/${resourceId}`),
  unlinkResource: (id, resourceId) =>
    del(`/learning-steps/${id}/resources/${resourceId}`)
}

// --------------------
// Today Plan (Phase 1)
// --------------------

export const todayPlan = {
  get: (minutes, intensity) =>
    get(`/today/plan?available_minutes=${minutes}&intensity=${intensity}`),
  create: (minutes, intensity) =>
    post(`/today/plan?available_minutes=${minutes}&intensity=${intensity}`),
  why: (minutes, intensity) =>
    get(`/today/why?available_minutes=${minutes}&intensity=${intensity}`),
  intensities: () => get("/today/intensities"),
  deadlines: () => get("/today/deadlines"),
  // 루틴이면 body 에 { count } — 실제로 푼 개수. 비우면 목표만큼 한 것으로 본다.
  complete: (taskId, body) => post(`/today/tasks/${taskId}/complete`, body),
  skip: (taskId) => post(`/today/tasks/${taskId}/skip`),
  // 잘못 누른 완료 · 넘김 되돌리기. 루틴이면 그날 기록도 지운다.
  reopen: (taskId) => post(`/today/tasks/${taskId}/reopen`),
  revive: (taskId) => post(`/today/tasks/${taskId}/revive`)
}

// --------------------
// My Learning Library (Phase 2)
// --------------------

export const library = {
  get: (params = "") => get(`/library${params}`),
  segments: (resourceId) => get(`/resources/${resourceId}/segments`),
  addSegment: (resourceId, body) =>
    post(`/resources/${resourceId}/segments`, body),
  updateSegment: (id, body) => patch(`/segments/${id}`, body),
  removeSegment: (id) => del(`/segments/${id}`),
  completeSegment: (id) => post(`/segments/${id}/complete`),
  setShelf: (resourceId, shelf) => post(`/resources/${resourceId}/shelf?to=${shelf}`),
  addToPlan: (resourceId) => post(`/resources/${resourceId}/add-to-plan`),
  selection: (stepId, minutes) =>
    get(`/learning-steps/${stepId}/selection?available_minutes=${minutes}`),

  // 라이브러리 전체에서 오늘 필요한 것만 (Phase 7)
  todaySelection: (minutes) =>
    get(`/library/selection?available_minutes=${minutes}`)
}

export const calendar = {
  blocks: (weekday) =>
    get(`/calendar/blocks${weekday != null ? `?weekday=${weekday}` : ""}`),
  addBlock: (body) => post("/calendar/blocks", body),
  updateBlock: (id, body) => patch(`/calendar/blocks/${id}`, body),
  removeBlock: (id) => del(`/calendar/blocks/${id}`),
  day: (date) => get(`/calendar/day${date ? `?date=${date}` : ""}`),
  week: () => get("/calendar/week"),
  month: (year, month) => get(`/calendar/month?year=${year}&month=${month}`),
  settings: (body) => patch("/calendar/settings", body)
}

export const universe = {
  get: (minutes = 120) => get(`/universe?available_minutes=${minutes}`)
}

// 루틴 — 정한 요일마다 하는 일과 그날 기록.
export const routines = {
  list: () => get("/routines"),
  create: (body) => post("/routines", body),
  update: (id, body) => patch(`/routines/${id}`, body),
  remove: (id) => del(`/routines/${id}`),
  log: (id, isoDate, body) => put(`/routines/${id}/logs/${isoDate}`, body)
}

// 학습 단계 체크리스트. parse 는 저장하지 않고 링크도 열지 않는다.
export const checklists = {
  parse: (text) => post("/checklists/parse", { text }),
  get: (stepId) => get(`/learning-steps/${stepId}/checklist`),
  importTo: (stepId, body) => post(`/learning-steps/${stepId}/checklist/import`, body),
  createStep: (pathId, body) => post(`/learning-paths/${pathId}/checklist-steps`, body),
  add: (stepId, body) => post(`/learning-steps/${stepId}/checklist`, body),
  update: (itemId, body) => patch(`/checklist-items/${itemId}`, body),
  remove: (itemId) => del(`/checklist-items/${itemId}`)
}

export const overview = {
  get: () => get("/overview")
}

export const certificates = {
  list: () => get("/certificates"),
  create: (body) => post("/certificates", body),
  update: (id, body) => patch(`/certificates/${id}`, body),
  remove: (id) => del(`/certificates/${id}`)
}

export const profile = {
  get: () => get("/profile"),
  // 문자열이면 이름만, 객체면 보낸 칸만 바꾼다.
  update: (fields) =>
    patch("/profile", typeof fields === "string" ? { name: fields } : fields)
}

export const targetCareers = {
  active: () => get("/target-careers/active"),
  list: () => get("/target-careers"),
  create: (body) => post("/target-careers", body),
  activate: (id) => post(`/target-careers/${id}/activate`),
  linkSkill: (id, skillId) => post(`/target-careers/${id}/skills/${skillId}`)
}

export const analytics = {
  learningPriority: () => get("/analytics/learning-priority")
}

export const skills = {
  list: () => get("/skills"),
  // 같은 이름(대소문자 · 띄어쓰기 무시)이 있으면 409 로 거절한다.
  create: (body) => post("/skills", body),
  setLevel: (skillId, level) => patch(`/skills/${skillId}`, { level }),
  levelEvents: (skillId) => get(`/skills/${skillId}/level-events`)
}

export const opportunityMap = (opportunityId) =>
  get(`/opportunities/${opportunityId}/map`)

export const activity = {
  get: (year, month) => get(`/analytics/activity?year=${year}&month=${month}`)
}

export const review = {
  get: (year, month) =>
    get(`/analytics/review?year=${year}&month=${month}`),
  trend: (months = 6) => get(`/analytics/review/trend?months=${months}`),
  // 그 달의 스스로 평가 — { rating(1~5|null), went_well, to_improve, next_focus }
  saveReflection: (year, month, body) =>
    put(`/analytics/review/reflection?year=${year}&month=${month}`, body)
}

export const evidence = {
  get: () => get("/analytics/evidence")
}

export const resources = {
  list: () => get("/resources"),
  create: (body) => post("/resources", body),
  update: (id, body) => patch(`/resources/${id}`, body),
  remove: (id) => del(`/resources/${id}`)
}

// Learning 화면이 필요한 것을 한 번에 가져온다.
export async function fetchLearning() {
  const [paths, skills, allResources] = await Promise.all([
    get("/learning-paths"),
    get("/skills"),
    get("/resources")
  ])

  const withSteps = await Promise.all(
    paths.map(async (path) => ({
      ...path,
      steps: await get(`/learning-steps?learning_path_id=${path.id}`)
    }))
  )

  return { paths: withSteps, skills, resources: allResources }
}

export const opportunities = {
  list: (params = "") => get(`/opportunities${params}`),
  create: (body) => post("/opportunities", body),
  update: (id, body) => patch(`/opportunities/${id}`, body),

  // Phase 3
  matches: () => get("/opportunities/matches"),
  recommended: (limit = 3) =>
    get(`/opportunities/recommended?limit=${limit}`),
  collect: () => post("/opportunities/collect"),
  parse: (text, url = "") => post("/opportunities/parse", { text, url }),
  // 알림 메일 하나에 든 여러 건을 공고 단위로 자른다. 하나뿐이면 count 0.
  split: (text) => post("/opportunities/split", { text }),
  // 공고 주소 한 건 가져오기. robots 가 막으면 422 와 이유가 온다 — 그때는 붙여넣기로.
  fetchUrl: (url) => post("/opportunities/fetch-url", { url }),
  setStatus: (id, status) => patch(`/opportunities/${id}`, { status }),
  // 지원서가 달린 기회는 서버가 409 로 거절한다 (지원 기록은 지우지 않는다).
  remove: (id) => del(`/opportunities/${id}`),
  // 직무가 달라 자동으로 뺀 공고를 되살린다. 다시 자동으로 빼지 않는다.
  keep: (id) => post(`/opportunities/${id}/keep`),
  addToPlan: (id, minutes = 30) =>
    post(`/opportunities/${id}/add-to-plan?minutes=${minutes}`)
}

export const marketSignals = {
  get: (limit) => get(`/analytics/market-signals${limit ? `?limit=${limit}` : ""}`),
  snapshot: () => post("/analytics/market-snapshots")
}

export const experiences = {
  list: () => get("/experiences"),
  create: (body) => post("/experiences", body),
  update: (id, body) => patch(`/experiences/${id}`, body),
  usage: () => get("/experiences/usage"),
  promoteToPortfolio: (id) => post(`/experiences/${id}/portfolio-entry`)
}

// --------------------
// PROVE (Phase 4)
// --------------------

export const projects = {
  list: () => get("/projects"),
  create: (body) => post("/projects", body),
  update: (id, body) => patch(`/projects/${id}`, body),
  evidence: (id) => get(`/projects/${id}/evidence`),
  eta: (id) => get(`/projects/${id}/eta`),
  linkSkill: (id, skillId) => post(`/projects/${id}/skills/${skillId}`),
  toExperience: (id) => post(`/projects/${id}/to-experience`)
}

export const portfolio = {
  list: () => get("/portfolio-entries"),
  update: (id, body) => patch(`/portfolio-entries/${id}`, body),
  resumeBullet: (id) => post(`/portfolio-entries/${id}/resume-bullet`)
}

// PROVE 화면이 필요한 것을 한 번에
export async function fetchProof() {
  const [projectList, experienceList, portfolioList, stars, me, usage] =
    await Promise.all([
      get("/projects"),
      get("/experiences"),
      get("/portfolio-entries"),
      get("/analytics/evidence"),
      get("/profile"),
      get("/experiences/usage")
    ])

  const evidence = await Promise.all(
    projectList.map((p) => get(`/projects/${p.id}/evidence`))
  )

  return {
    projects: projectList,
    evidence,
    experiences: experienceList,
    portfolio: portfolioList,
    stars,
    usage,
    links: { github_url: me.github_url, blog_url: me.blog_url }
  }
}

export const applications = {
  list: (params = "") => get(`/applications${params}`),
  board: () => get("/applications/board"),
  create: (body) => post("/applications", body),
  update: (id, body) => patch(`/applications/${id}`, body),

  // Phase 5 — Workspace
  analysis: (id) => get(`/applications/${id}/analysis`),
  autoMatch: (id) => post(`/applications/${id}/auto-match`),
  transitions: (id) => get(`/applications/${id}/transitions`),
  move: (id, status, force = false) =>
    post(`/applications/${id}/move?status=${status}&force=${force}`),
  experiences: (id) => get(`/applications/${id}/experiences`)
}

export const coverLetter = {
  questions: (applicationId) =>
    get(`/cover-letter-questions?application_id=${applicationId}`),
  addQuestion: (body) => post("/cover-letter-questions", body),
  outline: (questionId) =>
    get(`/cover-letter-questions/${questionId}/outline`),
  answers: (questionId) =>
    get(`/cover-letter-questions/${questionId}/answers`),
  saveAnswer: (questionId, draft) =>
    post(`/cover-letter-questions/${questionId}/answers`, { question_id: questionId, draft }),
  review: (questionId, draft) =>
    post(`/cover-letter-questions/${questionId}/review?draft=${encodeURIComponent(draft)}`)
}
