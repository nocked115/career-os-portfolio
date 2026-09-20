import { useState } from "react"
import * as api from "../api"
import { Button, Notice } from "./ui"
import { useReadOnly } from "../readOnly"

/* 한 달 스스로 평가.

   회고의 숫자는 전부 기록에서 센 것이다. "그래서 이번 달이 어땠나" 는 기록이
   말해주지 않는다 — 그건 사용자가 정한다. 앱은 적은 그대로 두고 계산하지 않는다.
   점수는 비워 둘 수 있다. 아직 오지 않은 달은 적을 수 없다. */

const SCALE = [
  { value: 1, label: "많이 아쉬움" },
  { value: 2, label: "아쉬움" },
  { value: 3, label: "보통" },
  { value: 4, label: "잘함" },
  { value: 5, label: "아주 잘함" }
]

const FIELDS = [
  { key: "went_well", label: "잘한 것", placeholder: "예: 코테를 거의 매일 풀었다" },
  { key: "to_improve", label: "아쉬운 것", placeholder: "예: Tave 발표 준비를 전날 몰아서 했다" },
  { key: "next_focus", label: "다음 달 초점", placeholder: "예: 캡스톤 MVP 먼저, 추천시스템은 주 2회" },
  // 할 게 너무 많다는 느낌은 대개 버린 것을 안 적어서 생긴다. 덜어낸 판단도 기록이다.
  {
    key: "dropped",
    label: "버린 것",
    placeholder: "예: 데이터 엔지니어링 책은 이번 학기에 안 본다, 공모전은 캡스톤 끝나고"
  }
]

function toForm(reflection) {
  return {
    rating: reflection?.rating ?? null,
    went_well: reflection?.went_well ?? "",
    to_improve: reflection?.to_improve ?? "",
    next_focus: reflection?.next_focus ?? "",
    dropped: reflection?.dropped ?? ""
  }
}

export default function ReflectionCard({ year, month, reflection, onSaved }) {
  const readOnly = useReadOnly()
  const [form, setForm] = useState(() => toForm(reflection))
  const [editing, setEditing] = useState(!reflection)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const save = async () => {
    try {
      setSaving(true)
      setError(null)
      const saved = await api.review.saveReflection(year, month, form)
      onSaved?.(saved)
      setEditing(false)
    } catch (failure) {
      setError(failure?.detail || "평가를 저장하지 못했습니다.")
    } finally {
      setSaving(false)
    }
  }

  const empty = !form.rating && FIELDS.every((field) => !form[field.key].trim())

  return (
    <section className="card rf" aria-labelledby="rf-title">
      <div className="materials-header">
        <p className="card-label" id="rf-title">
          {month}월 스스로 평가
        </p>
        {!editing && reflection && (
          <Button variant="quiet" writes onClick={() => setEditing(true)}>
            고치기
          </Button>
        )}
      </div>

      {error && (
        <Notice tone="bad" onClose={() => setError(null)}>
          {error}
        </Notice>
      )}

      {!editing && reflection ? (
        <div className="rf-view">
          <p className="rf-score">
            {reflection.rating ? (
              <>
                <strong>{reflection.rating}</strong> / 5 ·{" "}
                {SCALE.find((item) => item.value === reflection.rating)?.label}
              </>
            ) : (
              <span className="muted">점수 없이 적었어요</span>
            )}
          </p>
          <dl className="rf-lines">
            {FIELDS.filter((field) => reflection[field.key]).map((field) => (
              <div key={field.key}>
                <dt>{field.label}</dt>
                <dd>{reflection[field.key]}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : (
        <div className="rf-form">
          <p className="muted form-hint">
            위 기록을 보고 이번 달을 스스로 매겨 보세요. 앱은 계산하지 않고 적은 그대로 둬요.
          </p>

          <fieldset className="rf-scale" disabled={readOnly}>
            <legend>이번 달 점수</legend>
            {SCALE.map((item) => (
              <button
                type="button"
                key={item.value}
                className={form.rating === item.value ? "rf-dot rf-dot-on" : "rf-dot"}
                aria-pressed={form.rating === item.value}
                title={item.label}
                onClick={() =>
                  setForm({ ...form, rating: form.rating === item.value ? null : item.value })
                }
              >
                <span>{item.value}</span>
                <small>{item.label}</small>
              </button>
            ))}
          </fieldset>

          {FIELDS.map((field) => (
            <label className="learn-field" key={field.key}>
              <span>{field.label}</span>
              <textarea
                className="learn-textarea"
                rows={2}
                maxLength={2000}
                placeholder={field.placeholder}
                value={form[field.key]}
                disabled={readOnly}
                onChange={(event) => setForm({ ...form, [field.key]: event.target.value })}
              />
            </label>
          ))}

          <div className="ui-row">
            <Button writes disabled={saving || empty} onClick={save}>
              {saving ? "저장 중…" : "저장"}
            </Button>
            {reflection && (
              <Button
                variant="quiet"
                onClick={() => {
                  setForm(toForm(reflection))
                  setEditing(false)
                }}
              >
                취소
              </Button>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
