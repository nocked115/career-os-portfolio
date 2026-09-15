import { createContext, useContext } from "react"

// 공개 데모(읽기 전용)면 쓰기 버튼을 미리 끈다.
// 전에는 눌러 보고 나서야 403 으로 막혔다.
//
// 컴포넌트 파일(ui.jsx)과 나눠 둔다 — 한 파일에 컴포넌트가 아닌 것이
// 섞이면 개발 중 화면 갱신(fast refresh)이 통째로 새로고침된다.
export const ReadOnlyContext = createContext(false)

export function useReadOnly() {
  return useContext(ReadOnlyContext)
}

export const READ_ONLY_HINT = "구경용 데모라 저장되지 않아요."
