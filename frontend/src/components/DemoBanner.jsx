import { STATIC_DEMO, STATIC_DEMO_DATE } from "../api"

/* 구경용 배포본이라는 사실을 말해준다.

   이 말이 없으면 버튼을 눌러도 아무 일이 없는 고장난 앱으로 보인다.
   포트폴리오로 여는 사람에게는 그 첫인상이 전부다.

   정적 데모(GitHub Pages)는 만든 날의 응답을 그대로 보여준다. "D-3" 이나 "오늘" 이
   그날 기준이라는 걸 말하지 않으면 날짜가 틀린 앱으로 보인다. */

export default function DemoBanner({ readOnly }) {
  if (!readOnly && !STATIC_DEMO) {
    return null
  }

  return (
    <div className="demo-banner" role="status">
      <span className="demo-banner-tag">데모</span>

      <span className="demo-banner-text">
        {STATIC_DEMO
          ? `가상 데이터로 만든 정적 데모예요${STATIC_DEMO_DATE ? ` (${STATIC_DEMO_DATE} 기준 — 날짜와 D-day 도 그날 기준)` : ""}. 모든 화면을 둘러볼 수 있지만 저장되지 않아요.`
          : "구경용 데이터입니다. 화면은 모두 볼 수 있지만 저장되지 않습니다."}
      </span>
    </div>
  )
}
