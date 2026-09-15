/* 해시 라우터.

   react-router 를 쓰지 않는 이유 둘.

   1. 런타임 의존성을 react · react-dom 둘로 유지한다. 이 앱의
      경로는 10여 개에 파라미터 하나뿐이라 라이브러리가 무겁다.
   2. 해시 라우팅은 서버 설정이 필요 없다. 정적 호스팅에 그대로
      올라가고, 새로고침해도 404 가 나지 않는다.

   대신 포기하는 것도 적는다 — 중첩 라우트, 로더, 스크롤 복원
   같은 건 없다. 그게 필요해지면 그때 react-router 로 간다.
*/

import { useCallback, useEffect, useState } from "react"

export function parseHash(hash) {
  const raw = (hash || "").replace(/^#/, "")
  const path = raw.startsWith("/") ? raw : `/${raw}`

  return path.split("/").filter(Boolean)
}

export function toHash(segments) {
  return `#/${segments.filter(Boolean).join("/")}`
}

/* 현재 경로를 조각 배열로 준다.

   #/learning/sessions/3  →  ["learning", "sessions", "3"]
   #/                     →  []
*/
export function useHashRoute() {
  const [segments, setSegments] = useState(() =>
    parseHash(window.location.hash)
  )

  useEffect(() => {
    const onChange = () => setSegments(parseHash(window.location.hash))

    window.addEventListener("hashchange", onChange)

    // 해시 없이 들어온 경우 홈으로 맞춰둔다.
    // 그래야 첫 화면에서 뒤로가기가 앱 밖으로 나가지 않는다.
    if (!window.location.hash) {
      window.history.replaceState(null, "", "#/")
    }

    return () => window.removeEventListener("hashchange", onChange)
  }, [])

  const navigate = useCallback((next, { replace = false } = {}) => {
    const target = toHash(Array.isArray(next) ? next : [next])

    if (target === window.location.hash) {
      return
    }

    if (replace) {
      window.history.replaceState(null, "", target)
      setSegments(parseHash(target))
      return
    }

    // hashchange 가 알아서 상태를 갱신한다.
    window.location.hash = target
  }, [])

  return { segments, navigate }
}
