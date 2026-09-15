/* 구경용 배포본이라는 사실을 말해준다.

   이 말이 없으면 버튼을 눌러도 아무 일이 없는 고장난 앱으로 보인다.
   포트폴리오로 여는 사람에게는 그 첫인상이 전부다. */

export default function DemoBanner({ readOnly }) {
  if (!readOnly) {
    return null
  }

  return (
    <div className="demo-banner" role="status">
      <span className="demo-banner-tag">데모</span>

      <span className="demo-banner-text">
        구경용 데이터입니다. 화면은 모두 볼 수 있지만 저장되지 않습니다.
      </span>
    </div>
  )
}
