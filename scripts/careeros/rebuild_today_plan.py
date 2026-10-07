"""오늘 계획을 다시 세우고, 전/후를 보여준다.

resequence_recsys_steps.py 가 POST 응답을 확인하지 않아서 정말 다시 세워졌는지 알 수 없었다.
이 스크립트는 HTTP 상태를 찍고, 전/후 목록을 나란히 보여준다.

  python3 rebuild_today_plan.py          # 지금 계획만 보여준다 (읽기 전용)
  python3 rebuild_today_plan.py --apply  # 다시 세운다

다시 세우면 `planned` 줄만 지우고 새로 짠다 — 끝낸 것 · 건너뛴 것은 그대로 둔다
(today.py generate_plan). 가용 시간과 강도는 지금 저장된 값을 그대로 쓴다.
"""

import sys

from career_api import Api


def show(plan, label):
    print(f"\n{label} — 할 일 {plan.get('total_tasks')}개 · "
          f"계획 {plan.get('planned_minutes')}분 / 예산 {plan.get('available_minutes')}분 "
          f"· 강도 {plan.get('intensity')}")
    for t in plan.get("tasks", []):
        mark = {"done": "✅", "skipped": "⏭ ", "planned": "  "}.get(t.get("status"), "▶ ")
        print(f"{mark} {(t.get('title') or '')[:52]:54} {t.get('minutes')}분 · {t.get('status')}")
        if t.get("reason"):
            print(f"      {t['reason'][:70]}")


def main():
    apply = "--apply" in sys.argv
    api = Api()

    before = api.get("/today/plan")
    show(before, "지금")

    if not apply:
        print("\n지금은 보여주기만 했어요. 다시 세우려면 --apply 를 붙이세요.")
        return

    minutes = before.get("available_minutes") or 120
    intensity = before.get("intensity") or "normal"
    status, body = api.call("POST", f"/today/plan?available_minutes={minutes}"
                                    f"&intensity={intensity}")
    print(f"\nPOST /today/plan?available_minutes={minutes}&intensity={intensity}  →  HTTP {status}")
    if status not in (200, 201):
        sys.exit(f"다시 세우지 못했어요: {body}")

    after = api.get("/today/plan")
    show(after, "다시 세운 뒤")

    ids_before = [t.get("title") for t in before.get("tasks", [])]
    ids_after = [t.get("title") for t in after.get("tasks", [])]
    if ids_before == ids_after:
        print("\n⚠ 목록이 그대로예요. 마감을 바꿨는데도 안 바뀌면 후보 규칙을 더 봐야 합니다.")


if __name__ == "__main__":
    main()
