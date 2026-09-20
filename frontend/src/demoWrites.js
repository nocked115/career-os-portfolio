/* 정적 데모에서 "한 번 눌러 보기".

   데모는 녹화된 응답 묶음이라 원래 쓰기가 전부 막혀 있었다. 그런데 Career OS 의 핵심은
   **체크 하나가 다음 계획을 바꾼다**는 닫힌 고리라서, 버튼이 전부 잠긴 데모에서는 그 핵심이
   증명되지 않는다. 처음 보는 사람은 "계산한다고 쓰여 있네" 까지만 읽고 끝난다.

   그래서 몇 가지 쓰기만 **브라우저 안에서** 흉내 낸다.
     - 서버로 나가지 않는다. 새로고침하면 처음으로 돌아온다.
     - 흉내 낼 수 없는 것(우선순위 재계산 같은 서버 계산)은 지어내지 않는다.
       바뀌는 값만 바꾸고, 나머지는 "실제 앱에서는 …" 이라고 말로 돌려준다.
     - 목록에 없는 쓰기는 그대로 막는다.
*/

const DEMO_NOTE = "데모라 이 화면에만 반영돼요. 새로고침하면 처음으로 돌아갑니다."

// 녹화된 응답은 주소마다 따로 들어 있다. 같은 계획이 여러 주소에 있으므로 전부 고친다.
function planResponses(bundle) {
  return Object.keys(bundle.responses).filter(
    (key) => key.split("?")[0] === "/today/plan" && bundle.responses[key]?.tasks
  )
}

function recount(plan) {
  const tasks = plan.tasks ?? []
  const done = tasks.filter((task) => task.status === "done")

  plan.done_tasks = done.length
  plan.done_minutes = done.reduce((sum, task) => sum + (task.minutes ?? 0), 0)
  plan.remaining_minutes = Math.max(
    0,
    (plan.planned_minutes ?? 0) - plan.done_minutes
  )
}

function eachTask(bundle, taskId, change) {
  let touched = null

  for (const key of planResponses(bundle)) {
    const plan = bundle.responses[key]

    for (const task of plan.tasks) {
      if (task.id === taskId) {
        change(task)
        touched = task
      }
    }

    recount(plan)
  }

  return touched
}

/* 학습 단계 체크 한 줄. 오늘 카드의 "체크 2/12" 와 세션 화면이 같은 값을 쓴다. */
function eachChecklistItem(bundle, itemId, change) {
  let touched = null

  for (const [key, value] of Object.entries(bundle.responses)) {
    if (!key.startsWith("/learning-steps/")) continue

    // 세션 응답은 { checklist: {...} }, 체크리스트 응답은 그 자체다.
    const checklist = value?.checklist?.sections ? value.checklist : value?.sections ? value : null
    if (!checklist) continue

    for (const section of checklist.sections) {
      for (const item of section.items ?? []) {
        if (item.id === itemId) {
          change(item)
          touched = { item, checklist }
        }
      }
    }

    const items = checklist.sections.flatMap((section) => section.items ?? [])
    const tasks = items.filter((row) => row.kind !== "note" && row.kind !== "link")
    checklist.done = tasks.filter((row) => row.done).length
    checklist.total = tasks.length
    if (checklist.progress) {
      checklist.progress = { done: checklist.done, total: checklist.total }
    }
  }

  return touched
}

export function handleDemoWrite(path, method, body, bundle) {
  const complete = path.match(/^\/today\/tasks\/(\d+)\/complete$/)
  if (complete && method === "POST") {
    const task = eachTask(bundle, Number(complete[1]), (row) => {
      row.status = "done"
    })

    if (!task) return null

    // 실제 앱은 여기서 학습 진행률 · 증거 · 우선순위까지 다시 센다.
    // 데모는 그 계산을 할 수 없으므로 했다고 하지 않는다.
    return {
      task,
      effects: [
        `실제 앱에서는 ${task.title} 의 진행률과 스킬 우선순위가 여기서 다시 계산돼요`,
        DEMO_NOTE,
      ],
    }
  }

  const skip = path.match(/^\/today\/tasks\/(\d+)\/skip$/)
  if (skip && method === "POST") {
    const task = eachTask(bundle, Number(skip[1]), (row) => {
      row.status = "skipped"
    })
    return task ? { ...task } : null
  }

  const reopen = path.match(/^\/today\/tasks\/(\d+)\/reopen$/)
  if (reopen && method === "POST") {
    const task = eachTask(bundle, Number(reopen[1]), (row) => {
      row.status = "planned"
    })
    return task ? { task, effects: [DEMO_NOTE] } : null
  }

  const check = path.match(/^\/checklist-items\/(\d+)$/)
  if (check && method === "PATCH" && typeof body?.done === "boolean") {
    const hit = eachChecklistItem(bundle, Number(check[1]), (item) => {
      item.done = body.done
    })
    return hit ? { checklist: hit.checklist, started: false } : null
  }

  return null
}

export { DEMO_NOTE }
