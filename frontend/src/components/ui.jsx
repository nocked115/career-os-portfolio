import { useState } from "react"
import { READ_ONLY_HINT, useReadOnly } from "../readOnly"

/* 모든 작업 화면이 같이 쓰는 모양.

   화면마다 "불러오는 중...", 오류 문구, 빈 상태를 따로 만들다 보니
   어떤 화면은 다시 시도할 길이 없고, 어떤 화면은 오류가 나면 통째로
   깨졌다. 여기 모아서 같은 상황은 같은 모양으로 보이게 한다.

   색과 크기는 ui.css. 앱의 기존 토큰(App.css :root) 위에 의미 있는
   색만 더한다 — 행동=파랑, 주의=호박, 완료=초록, 부족=빨강. */

export function Button({
  variant = "primary",
  writes = false,
  disabled = false,
  className = "",
  title,
  children,
  ...props
}) {
  const readOnly = useReadOnly()
  const blocked = writes && readOnly

  return (
    <button
      type="button"
      className={`ui-btn ui-btn-${variant} ${className}`.trim()}
      disabled={disabled || blocked}
      title={blocked ? READ_ONLY_HINT : title}
      {...props}
    >
      {children}
    </button>
  )
}

function ActionItem({ label, href, onClick, primary, writes, disabled }) {
  if (href) {
    return (
      <a
        className={primary ? "ui-btn ui-btn-primary" : "ui-btn ui-btn-secondary"}
        href={href}
      >
        {label}
      </a>
    )
  }

  return (
    <Button
      variant={primary ? "primary" : "secondary"}
      writes={writes}
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </Button>
  )
}

export function LoadingState({ label = "불러오는 중…" }) {
  return (
    <section className="card ui-state" role="status" aria-live="polite">
      <span className="ui-spinner" aria-hidden="true" />
      <span>{label}</span>
    </section>
  )
}

export function ErrorState({ message, onRetry }) {
  return (
    <section className="card ui-state ui-state-error" role="alert">
      <strong>{message}</strong>
      <span className="ui-state-hint">
        잠시 뒤 다시 시도해 주세요. 계속되면 서버가 켜져 있는지 확인이 필요해요.
      </span>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          다시 불러오기
        </Button>
      )}
    </section>
  )
}

// 빈 상태는 안내문으로 끝내지 않는다. 다음에 누를 것을 함께 준다.
export function EmptyState({ title, body, actions = [] }) {
  return (
    <div className="ui-empty">
      <strong>{title}</strong>
      {body && <p>{body}</p>}
      {actions.length > 0 && (
        <div className="ui-row">
          {actions.map((action) => (
            <ActionItem key={action.label} {...action} />
          ))}
        </div>
      )}
    </div>
  )
}

export function ProgressBar({ value, max = 100, label }) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0

  return (
    <span
      className="ui-progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-label={label}
    >
      <span style={{ width: `${percent}%` }} />
    </span>
  )
}

export function StatusBadge({ tone = "neutral", children }) {
  return <span className={`ui-badge ui-badge-${tone}`}>{children}</span>
}

// 현재 상태 → 다음에 할 일 → 버튼. 화면마다 맨 위에 하나.
export function NextActionCard({
  eyebrow = "다음 행동",
  title,
  detail,
  meta,
  action,
  icon = "→",
  tone = "action"
}) {
  return (
    <div className={`ui-next ui-next-${tone}`}>
      <span className="ui-next-icon" aria-hidden="true">
        {icon}
      </span>

      <div className="ui-next-body">
        <span className="ui-next-eyebrow">{eyebrow}</span>
        <strong className="ui-next-title">{title}</strong>
        {detail && <span className="ui-next-detail">{detail}</span>}
        {meta && <span className="ui-next-meta">{meta}</span>}
      </div>

      {action && <div className="ui-next-actions">{action}</div>}
    </div>
  )
}

// 결론 문장이 먼저, 숫자는 접어 둔다.
export function WhyPanel({
  title = "왜 이 계획인가?",
  conclusion,
  detailLabel = "근거 숫자 보기",
  children
}) {
  return (
    <div className="ui-why">
      <p className="ui-why-title">{title}</p>
      {conclusion && <p className="ui-why-conclusion">{conclusion}</p>}
      {children && (
        <details className="ui-why-details">
          <summary>{detailLabel}</summary>
          <div className="ui-why-body">{children}</div>
        </details>
      )}
    </div>
  )
}

// 되돌리기 어려운 일은 두 번 누른다.
export function ConfirmButton({
  label,
  confirmLabel = "정말 할까요?",
  onConfirm,
  writes = true,
  disabled = false
}) {
  const [asking, setAsking] = useState(false)

  if (!asking) {
    return (
      <Button
        variant="quiet"
        writes={writes}
        disabled={disabled}
        onClick={() => setAsking(true)}
      >
        {label}
      </Button>
    )
  }

  return (
    <span className="ui-row">
      <Button
        variant="danger"
        writes={writes}
        disabled={disabled}
        onClick={() => {
          setAsking(false)
          onConfirm()
        }}
      >
        {confirmLabel}
      </Button>
      <Button variant="quiet" onClick={() => setAsking(false)}>
        취소
      </Button>
    </span>
  )
}

export function Notice({ tone = "ok", children, onClose }) {
  return (
    <p className={`ui-notice ui-notice-${tone}`} role="status" aria-live="polite">
      <span>{children}</span>
      {onClose && (
        <button
          type="button"
          className="ui-notice-close"
          onClick={onClose}
          aria-label="알림 닫기"
        >
          ×
        </button>
      )}
    </p>
  )
}
