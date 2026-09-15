/* 화면마다 따로 쓰던 표기를 한곳에 모은다.

   Today 는 "2h 30m", Calendar 는 "2시간 30분" 이었다. 같은 앱에서
   같은 양을 두 가지로 쓰면 다른 것을 세는 것처럼 읽힌다. */

export function minutesText(minutes) {
  const value = Math.max(0, Math.round(minutes || 0))

  if (value < 60) return `${value}분`

  const hours = Math.floor(value / 60)
  const rest = value % 60

  return rest === 0 ? `${hours}시간` : `${hours}시간 ${rest}분`
}

// 계획 항목의 영역. 서버 원시값(learning_step)을 그대로 보이지 않는다.
// "opportunity" 가 빠져 있어서 화면에 영어로 떴었다.
export const TASK_AREAS = {
  routine: "루틴",
  learning_step: "학습",
  resource: "자료",
  project: "프로젝트",
  application: "지원",
  opportunity: "기회"
}

export function areaLabel(type) {
  return TASK_AREAS[type] ?? "할 일"
}

// 자료 중요도. PRIMARY 같은 영어 대신, 무엇을 뜻하는지까지 함께.
export const IMPORTANCE_LABELS = {
  primary: "핵심",
  supplementary: "보조",
  deep_dive: "깊이 파기"
}

export const IMPORTANCE_HINTS = {
  primary: "이번 단계에 꼭 볼 것",
  supplementary: "막히면 펼쳐 볼 것",
  deep_dive: "여유가 있을 때 더 볼 것"
}

export function importanceLabel(key) {
  return IMPORTANCE_LABELS[key] ?? "중요도 미정"
}

export const RESOURCE_TYPES = [
  { key: "book", label: "책", unit: "쪽" },
  { key: "video", label: "영상", unit: "분" },
  { key: "youtube", label: "영상", unit: "분" },
  { key: "course", label: "강의", unit: "분" },
  { key: "official_doc", label: "공식 문서", unit: "" },
  { key: "documentation", label: "문서", unit: "" },
  { key: "article", label: "글", unit: "" },
  { key: "paper", label: "논문", unit: "쪽" },
  { key: "practice", label: "실습", unit: "" },
  { key: "problem", label: "코딩 문제", unit: "" },
  { key: "dataset", label: "데이터셋", unit: "" },
  { key: "project_task", label: "프로젝트 과제", unit: "" }
]

export function resourceTypeLabel(key) {
  return RESOURCE_TYPES.find((type) => type.key === key)?.label ?? "기타 자료"
}

export const OWNERSHIP_LABELS = {
  owned: "가지고 있음",
  saved: "저장해 둠",
  wishlist: "사고 싶음"
}

export function ownershipLabel(key) {
  return OWNERSHIP_LABELS[key] ?? "보유 미정"
}

export const STEP_STATUS_LABELS = {
  not_started: "시작 전",
  in_progress: "진행 중",
  completed: "완료",
  review_needed: "복습 필요"
}

export function stepStatusLabel(key) {
  return STEP_STATUS_LABELS[key] ?? "상태 모름"
}

export const STEP_STATUS_TONES = {
  not_started: "neutral",
  in_progress: "action",
  completed: "ok",
  review_needed: "warn"
}

export const PROJECT_STATUS_LABELS = {
  planned: "계획",
  in_progress: "진행 중",
  completed: "완료",
  paused: "멈춤"
}

export const EXPERIENCE_TYPES = [
  { key: "project", label: "프로젝트" },
  { key: "research", label: "연구" },
  { key: "competition", label: "대회" },
  { key: "internship", label: "인턴 · 실무" },
  { key: "activity", label: "활동" }
]

export function experienceTypeLabel(key) {
  return EXPERIENCE_TYPES.find((type) => type.key === key)?.label ?? "경험"
}

export const PORTFOLIO_STATUS_LABELS = {
  draft: "초안",
  ready: "준비됨",
  published: "공개"
}

// 사람이 적은 날짜(2026-10-01). 시간대 없이 그대로 읽는다.
export function dateText(value) {
  if (!value) return ""

  const date = new Date(`${String(value).slice(0, 10)}T00:00:00`)

  if (Number.isNaN(date.getTime())) return String(value)

  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`
}

export function greeting(now = new Date()) {
  const hour = now.getHours()

  if (hour < 5) return "늦은 밤이에요"
  if (hour < 12) return "좋은 아침입니다"
  if (hour < 18) return "좋은 오후입니다"
  return "좋은 저녁입니다"
}

export function todayText(now = new Date()) {
  const days = ["일", "월", "화", "수", "목", "금", "토"]
  return `${now.getMonth() + 1}월 ${now.getDate()}일 ${days[now.getDay()]}요일`
}

export function ddayLabel(days) {
  if (days == null) return "마감일 없음"
  if (days < 0) return "마감 지남"
  if (days === 0) return "오늘 마감"
  return `D-${days}`
}
