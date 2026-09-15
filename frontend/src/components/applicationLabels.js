/* Applications · Workspace · 자소서가 같이 쓰는 말과 모양.

   화면마다 라벨을 따로 두면 한쪽은 "준비 중", 다른 쪽은 "preparing" 이
   된다. 실제로 Workspace 머리에 원시값이 떠 있었다. */

export const STATUS_LABELS = {
  interested: "관심",
  preparing: "준비 중",
  ready: "준비 완료",
  applied: "지원함",
  document_pass: "서류 통과",
  interview: "면접",
  accepted: "합격",
  rejected: "불합격",
  withdrawn: "철회"
}

// 상태 흐름. 합격·불합격은 한 칸("결과")에 모은다. 철회는 흐름 밖이다.
export const MAIN_STEPS = [
  { key: "interested", label: "관심" },
  { key: "preparing", label: "준비 중" },
  { key: "ready", label: "준비 완료" },
  { key: "applied", label: "지원함" },
  { key: "document_pass", label: "서류 통과" },
  { key: "interview", label: "면접" },
  { key: "result", label: "결과" }
]

export function statusLabel(status) {
  return STATUS_LABELS[status] ?? "알 수 없는 상태"
}

// 기관마다 타일 색을 고정한다. 목록에서 글자를 읽기 전에 모양으로 찾게.
const TILE_TONES = 6

export function tileTone(name = "") {
  let hash = 0

  for (const char of name) {
    hash = (hash * 31 + char.codePointAt(0)) >>> 0
  }

  return hash % TILE_TONES
}

export function initialOf(name = "") {
  const cleaned = name.replace(/^\s*(\(주\)|㈜|주식회사)\s*/, "").trim()
  return cleaned.slice(0, 1) || "?"
}

export function ddayText(days) {
  if (days == null) return "마감일 없음"
  if (days < 0) return "마감 지남"
  if (days === 0) return "오늘 마감"
  return `D-${days}`
}

export function ddayTone(days, urgentDays = 7) {
  if (days == null) return "none"
  if (days < 0) return "past"
  if (days <= urgentDays) return "soon"
  return "later"
}

// 마감은 사람이 적은 날짜다 — 시간대 없이 그대로 읽는다.
export function deadlineText(value) {
  if (!value) return ""

  const date = new Date(value)

  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`
}

// 저장 시각은 서버(SQLite CURRENT_TIMESTAMP)가 UTC 로 찍는다.
// 시간대 표시가 없으니 붙여서 읽는다. 안 붙이면 9시간 어긋난다.
function serverTime(value) {
  const hasZone = /(Z|[+-]\d\d:\d\d)$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

export function savedDate(value) {
  if (!value) return ""

  const date = serverTime(value)

  return `${date.getMonth() + 1}월 ${date.getDate()}일`
}

export function savedTime(value) {
  if (!value) return ""

  const date = serverTime(value)
  const hh = String(date.getHours()).padStart(2, "0")
  const mm = String(date.getMinutes()).padStart(2, "0")

  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${hh}:${mm}`
}

export function errorText(error, fallback) {
  return error?.detail || fallback
}
