import { useCallback, useEffect, useState } from "react"
import * as api from "../api"
import { ErrorState, LoadingState, NextActionCard, ProgressBar, StatusBadge } from "./ui"
import { areaLabel, ddayLabel, minutesText } from "../format"
import "../Learning.css"
import "../Overview.css"

/* 한눈에 보기 — 지금 상태를 이해하는 곳. 행동은 Today 에서 한다.

   전에는 옛 대시보드 데이터(주간 계획 · 원시 우선순위 점수 · 공고 목록)가
   영어 라벨로 늘어서 있었고 누를 곳이 없었다. 이제 영역마다 한 칸 —
   숫자는 분모와 함께, 칸마다 들어가는 길 하나. 세부는 각 화면이 맡는다. */

const DAY_NAMES = {
  Monday: "월요일",
  Tuesday: "화요일",
  Wednesday: "수요일",
  Thursday: "목요일",
  Friday: "금요일",
  Saturday: "토요일",
  Sunday: "일요일"
}

function Tile({ label, value, sub, href, cta, children }) {
  return (
    <section className="card ov-tile">
      <p className="ov-label">{label}</p>
      <strong className="ov-value">{value}</strong>
      {sub && <p className="ov-sub">{sub}</p>}
      {children}
      {href && (
        <a className="ov-link" href={href}>
          {cta} →
        </a>
      )}
    </section>
  )
}

function OverviewPage({ weeklyPlan }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      setData(await api.overview.get())
    } catch (failure) {
      console.error("Failed to load overview:", failure)
      setError("한눈에 보기를 불러오지 못했습니다.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <LoadingState label="지금 상태를 모으는 중…" />
  if (!data) return <ErrorState message={error} onRetry={load} />

  const { readiness, week, learning, projects, evidence, applications, deadlines, certificates } = data
  const action = data.next_action

  return (
    <div className="learn ov">
      <section className="card learn-hero">
        <div>
          <h1 className="learn-title">한눈에 보기</h1>
          <p className="learn-sub">지금 상태를 이해하는 곳이에요. 행동은 오늘 화면에서 합니다.</p>
        </div>

        {action ? (
          <NextActionCard
            eyebrow={`오늘 가장 먼저 할 일 · ${data.plan.done}/${data.plan.total} 끝냄`}
            icon="▶"
            title={action.title}
            detail={`${action.area || areaLabel()} · ${minutesText(action.minutes)}`}
            meta={action.reason}
            action={
              <a className="ui-btn ui-btn-primary" href="#/today">
                오늘 화면으로
              </a>
            }
          />
        ) : (
          <NextActionCard
            eyebrow="오늘"
            icon="+"
            title={data.plan.total > 0 ? "오늘 계획을 모두 끝냈어요" : "오늘 계획이 아직 없어요"}
            meta={data.plan.total > 0 ? "한 일은 회고에 쌓여요." : "오늘 화면에서 계획을 세우면 할 일을 1~3개 골라 드려요."}
            tone={data.plan.total > 0 ? "ok" : "action"}
            action={
              <a className="ui-btn ui-btn-primary" href={data.plan.total > 0 ? "#/review" : "#/today"}>
                {data.plan.total > 0 ? "회고 보기" : "계획 세우러 가기"}
              </a>
            }
          />
        )}
      </section>

      <div className="ov-grid">
        <Tile
          label="목표 · 준비도"
          value={data.target.title ?? "목표 직무 미설정"}
          sub={
            readiness.skill_count > 0
              ? `${readiness.percent}% — ${readiness.basis} ${readiness.skill_count}개의 평균 숙련도`
              : readiness.detail
          }
          href="#/learning"
          cta="스킬 레벨 확인"
        >
          <ProgressBar value={readiness.percent} label="준비도" />
          {data.target.focus_skill && <p className="ov-sub">핵심 초점 · {data.target.focus_skill}</p>}
        </Tile>

        <Tile
          label="이번 주 실행"
          value={week.rate != null ? `${week.done} / ${week.decided}` : "기록 없음"}
          sub={
            week.rate != null
              ? `지난 날까지 계획한 할 일 중 ${week.rate}% 끝냄 · 넘김 ${week.skipped} · 못 함 ${week.missed}`
              : "이번 주에 끝난 날의 계획 기록이 아직 없어요"
          }
          href="#/review"
          cta="회고 보기"
        >
          {week.rate != null && <ProgressBar value={week.done} max={week.decided} label="이번 주 실행" />}
          {week.pending_today > 0 && <p className="ov-sub">오늘 남은 할 일 {week.pending_today}개 (분모에 넣지 않음)</p>}
        </Tile>

        <Tile
          label="학습"
          value={learning.steps_total ? `${learning.steps_done} / ${learning.steps_total} 단계` : "경로 없음"}
          sub={
            learning.next_step
              ? `다음 · ${learning.next_step.title} (${learning.next_step.path})`
              : learning.paths
                ? "남은 단계가 없어요"
                : "학습 경로를 만들면 다음 단계가 오늘 계획에 들어가요"
          }
          href={learning.next_step ? `#/learning/sessions/${learning.next_step.id}` : "#/learning"}
          cta={learning.next_step ? "다음 단계 열기" : "학습으로"}
        >
          {learning.steps_total > 0 && (
            <ProgressBar value={learning.steps_done} max={learning.steps_total} label="학습 단계" />
          )}
        </Tile>

        <Tile
          label="프로젝트"
          value={`진행 중 ${projects.active}개`}
          sub={
            projects.average_progress != null
              ? `진행 중인 것의 평균 진행률 ${projects.average_progress}% · 완료 ${projects.completed}개`
              : `완료 ${projects.completed}개`
          }
          href="#/projects"
          cta="프로젝트로"
        >
          {projects.unproven > 0 && (
            <StatusBadge tone="warn">증거로 안 남긴 완료 {projects.unproven}개</StatusBadge>
          )}
        </Tile>

        <Tile
          label="쌓인 증거"
          value={`★ ${evidence.total}`}
          sub={evidence.breakdown
            .filter((item) => item.count > 0)
            .map((item) => `${item.label} ${item.count}`)
            .join(" · ") || "아직 쌓인 증거가 없어요"}
          href="#/experience"
          cta="경험으로"
        />

        <Tile
          label="지원서"
          value={`진행 중 ${applications.active}건`}
          sub={`지원 전 ${applications.before_applying} · ${deadlines.within_days}일 안 마감 ${applications.urgent} · 작성 중 ${applications.writing}`}
          href="#/applications"
          cta="지원서로"
        >
          {applications.next && <p className="ov-sub">다음 · {applications.next.label} — {applications.next.title}</p>}
        </Tile>

        <Tile
          label={`${deadlines.within_days}일 안 마감`}
          value={`${deadlines.count}건`}
          sub={
            deadlines.nearest
              ? `가장 가까운 것 · ${ddayLabel(deadlines.nearest.days_left)} ${deadlines.nearest.title}`
              : "이번 주 안에 마감되는 것이 없어요"
          }
          href="#/opportunities"
          cta="기회로"
        />

        <Tile
          label="자격 · 어학"
          value={`보유 ${certificates.held}개`}
          sub={
            certificates.expired > 0
              ? `만료됨 ${certificates.expired}개`
              : certificates.expiring_soon > 0
                ? `180일 안 만료 ${certificates.expiring_soon}개`
                : "만료 임박 없음"
          }
          href="#/experience/certificates"
          cta="자격증 보기"
        >
          {(certificates.expiring_soon > 0 || certificates.expired > 0) && (
            <StatusBadge tone="warn">갱신 · 재응시 확인</StatusBadge>
          )}
        </Tile>
      </div>

      {weeklyPlan?.weekly_plan?.length > 0 && (
        <details className="card lib-manage">
          <summary>예전 주간 계획 (참고용)</summary>
          <p className="muted form-hint">
            오늘 계획과 계산 방식이 달라요 — 프로젝트를 먼저 놓고 하루 2시간으로 가정합니다.
            실제 할 일은 오늘 화면을 따르세요.
          </p>
          <div className="ov-week">
            {weeklyPlan.weekly_plan.map((day) => (
              <div className="ov-week-day" key={day.day}>
                <strong>{DAY_NAMES[day.day] ?? day.day}</strong>
                {day.tasks.length === 0 ? (
                  <span className="muted">할 일 없음</span>
                ) : (
                  day.tasks.map((task, index) => (
                    <span key={`${day.day}-${index}`}>
                      {task.title} · {minutesText(task.minutes)}
                    </span>
                  ))
                )}
                <small className="muted">남는 시간 {minutesText(day.remaining_minutes)}</small>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

export default OverviewPage
