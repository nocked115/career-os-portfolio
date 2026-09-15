/* 사용자가 직접 넣은 주소를 링크로 만들기 전에 거른다.

   javascript: 같은 것을 그대로 href 에 넣으면 누르는 순간 그 코드가
   이 페이지에서 돈다. http/https 만 통과시킨다.

   한곳에 둔 이유: 보안 검사를 복사하면 한쪽이 언젠가 어긋난다. */

export function externalHref(url) {
  if (!url) {
    return null
  }

  try {
    const parsed = new URL(url)

    return parsed.protocol === "https:" || parsed.protocol === "http:"
      ? parsed.href
      : null
  } catch {
    return null
  }
}
