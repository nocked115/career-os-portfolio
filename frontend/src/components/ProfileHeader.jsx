import { useCallback, useEffect, useState } from "react"
import * as api from "../api"

/* 화면 가운데 있어야 할 사람.

   DESIGN.md 3장 — 라벨은 카테고리고 이름은 사람이다.
   화면에서 사용자가 사라지면 그 순간 남의 대시보드가 된다.

   이번 주 누적은 새로 기록하지 않는다. 완료한 계획 항목을 더한 값이라
   계획 밖에서 한 공부는 잡히지 않는다 — 그렇다고 화면에 적는다. */

function greeting(hour) {
  if (hour < 5) return "늦은 밤이네요"
  if (hour < 11) return "좋은 아침이에요"
  if (hour < 17) return "안녕하세요"
  return "좋은 저녁이에요"
}

function formatWeek(week) {
  if (week.minutes === 0) {
    return "아직 없음"
  }

  if (week.hours === 0) {
    return `${week.remainder_minutes}분`
  }

  if (week.remainder_minutes === 0) {
    return `${week.hours}시간`
  }

  return `${week.hours}시간 ${week.remainder_minutes}분`
}

function ProfileHeader() {
  const [data, setData] = useState(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const [working, setWorking] = useState(false)

  const load = useCallback(async () => {
    try {
      setData(await api.profile.get())
    } catch (loadError) {
      // 이름을 못 읽어도 나머지 화면은 살아있어야 한다.
      console.error("Failed to load profile:", loadError)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const save = async () => {
    try {
      setWorking(true)
      setData(await api.profile.update(draft))
      setEditing(false)
    } catch (saveError) {
      console.error("Failed to save profile:", saveError)
    } finally {
      setWorking(false)
    }
  }

  if (!data) {
    return (
      <div>
        <p className="eyebrow">CAREER OS</p>
        <h1>Career OS</h1>
      </div>
    )
  }

  const hello = greeting(new Date().getHours())

  const startEditing = () => {
    setDraft(data.name)
    setEditing(true)
  }

  return (
    <div className="profile-header">
      <p className="eyebrow">CAREER OS</p>

      {editing ? (
        <div className="profile-edit">
          <input
            className="agent-input"
            placeholder="이름"
            maxLength={60}
            value={draft}
            autoFocus
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") save()
              if (event.key === "Escape") setEditing(false)
            }}
          />
          <button
            className="agent-button"
            disabled={working}
            onClick={save}
          >
            저장
          </button>
          <button
            className="ghost-button"
            onClick={() => setEditing(false)}
          >
            취소
          </button>
        </div>
      ) : (
        <h1>
          {data.has_name ? (
            <>
              {hello},{" "}
              <button className="profile-name" onClick={startEditing}>
                {data.name}
              </button>
              .
            </>
          ) : (
            <button className="profile-name" onClick={startEditing}>
              이름을 알려주세요
            </button>
          )}
        </h1>
      )}

      <p className="profile-line">
        {data.target_career ? (
          <>
            <strong>{data.target_career}</strong>
            {data.focus_skill && <> · 지금은 {data.focus_skill}</>}
          </>
        ) : (
          <span className="muted">
            목표 직무를 정하면 모든 판단의 기준이 됩니다.
          </span>
        )}
      </p>

      <div className="profile-week">
        <span className="profile-week-key">이번 주</span>
        <strong>{formatWeek(data.week)}</strong>
        <span className="muted">
          완료 {data.week.completed_tasks}개 · {data.week.active_days}일
        </span>
        <span className="profile-week-note">{data.week.note}</span>
      </div>
    </div>
  )
}

export default ProfileHeader
