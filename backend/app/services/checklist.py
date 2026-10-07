"""학습 단계 체크리스트 — 저장 · 진행률 · 다음 항목.

진행률의 분모는 task 뿐이다. 설명(note)과 링크(link)는 세지 않는다.
체크를 모두 해도 단계를 저절로 끝내지 않는다 — 끝났다고 말하는 것은
사람이다. 대신 "모두 체크했어요" 를 알려 완료를 권한다.

이 모듈은 learning 서비스를 임포트하지 않는다 (learning 이 이쪽을 부른다).
경로 진행률 재계산은 라우터가 한다.
"""

from datetime import datetime

from .. import models


NEXT_COUNT = 3


def serialize_item(item) -> dict:
    return {
        "id": item.id,
        "position": item.position,
        "section": item.section,
        "kind": item.kind,
        "text": item.text,
        "url": item.url,
        "done": item.done,
        "done_at": item.done_at,
    }


def _ordered(step) -> list:
    return sorted(step.checklist, key=lambda item: (item.position, item.id))


def _tasks(step) -> list:
    return [item for item in _ordered(step) if item.kind == "task"]


def build_checklist(step) -> dict:
    sections: list[dict] = []
    by_title: dict[str, dict] = {}
    links = []

    for item in _ordered(step):
        if item.kind == "link":
            links.append(serialize_item(item))
            continue

        section = by_title.get(item.section)
        if section is None:
            section = {"title": item.section, "note": "", "items": []}
            by_title[item.section] = section
            sections.append(section)

        if item.kind == "note":
            section["note"] = f"{section['note']} {item.text}".strip()
        else:
            section["items"].append(serialize_item(item))

    for section in sections:
        section["done"] = sum(1 for item in section["items"] if item["done"])
        section["total"] = len(section["items"])

    tasks = _tasks(step)
    done = sum(1 for item in tasks if item.done)

    return {
        "sections": [s for s in sections if s["items"] or s["note"]],
        "links": links,
        "progress": {"done": done, "total": len(tasks)},
        "next": [
            {"id": item.id, "text": item.text, "section": item.section}
            for item in tasks
            if not item.done
        ][:NEXT_COUNT],
        "all_done": bool(tasks) and done == len(tasks),
    }


def today_slice(step, minutes: int | None = None, factor: float | None = None) -> dict | None:
    """오늘은 이 주차에서 **어디서부터 어디까지**.

    수현: "각 주차에서 무엇을 해야 한다 → 그 안에서 세부적으로 잘라서
    오늘은 여기서부터 여기까지 이게 나와야 할 것 같은데."

    주차 하나가 9시간이면 그걸 통째로 "오늘 할 일" 이라고 내밀 수 없다.
    오늘 쓸 시간만큼만 잘라서 몇 번째부터 몇 번째까지인지 말한다.

    항목마다 시간이 적혀 있지 않다 — 적게 하면 체크리스트를 만들 때마다
    숫자를 지어내야 한다. 대신 **주차 시간 ÷ 항목 수** 로 고르게 나눈다.
    고르지 않다는 건 알지만, 지어낸 숫자보다는 설명할 수 있다.

    minutes 를 안 주면 자르지 않고 남은 것 전부를 돌려준다.
    """
    tasks = _tasks(step)

    if not tasks:
        return None

    undone = [item for item in tasks if not item.done]

    if not undone:
        return None

    total = step.estimated_minutes or 0
    per_item = (total / len(tasks)) if total else 0

    # 보정 계수 — 지금까지 계획보다 1.4배 걸렸다면 한 항목도 1.4배로 본다.
    # 그러면 30분에 다섯 항목이 아니라 세 항목이 들어간다. 추정을 고치는
    # 대신 **자르는 자를** 고친다 — 원래 추정은 그대로 두고 설명할 수 있게.
    if factor:
        per_item *= factor

    if minutes and per_item > 0:
        # 적어도 한 항목은 준다. 0개를 "오늘 할 일" 이라고 내밀 수 없다.
        count = max(1, int(minutes // per_item))
    else:
        count = len(undone)

    chosen = undone[:count]

    return {
        # 사람이 세는 번호(1부터). position 은 0부터라 화면 숫자와 어긋난다.
        "from_number": tasks.index(chosen[0]) + 1,
        "to_number": tasks.index(chosen[-1]) + 1,
        "total_number": len(tasks),
        "count": len(chosen),
        "items": [item.text for item in chosen],
        # 화면이 테두리를 칠 대상. 글자로 맞추면 같은 문구가 두 번
        # 나오는 체크리스트에서 엉뚱한 줄에 쳐진다.
        "item_ids": [item.id for item in chosen],
        "minutes": round(per_item * len(chosen)) if per_item else None,
        # 보정을 썼는가. 화면이 "내 속도로 맞춤" 이라고 말할 수 있어야 한다.
        "adjusted": bool(factor and factor != 1),
        # 오늘 몫을 다 하면 이 주차가 끝나는가.
        "finishes_step": len(chosen) == len(undone),
    }


def summary(step, minutes: int | None = None, factor: float | None = None) -> dict | None:
    """오늘 계획 카드용. 체크리스트가 없으면 None."""
    tasks = _tasks(step)
    if not tasks:
        return None

    return {
        "done": sum(1 for item in tasks if item.done),
        "total": len(tasks),
        "next": [item.text for item in tasks if not item.done][:NEXT_COUNT],
        # 오늘 쓸 시간만큼 자른 몫. 주차 하나를 통째로 내밀지 않는다.
        "today": today_slice(step, minutes, factor=factor),
    }


def remaining(step) -> int:
    return sum(1 for item in _tasks(step) if not item.done)


def _next_position(step) -> int:
    return max((item.position for item in step.checklist), default=-1) + 1


def add_item(db, step, *, text, section="", kind="task", url="", done=False):
    item = models.LearningChecklistItem(
        learning_step_id=step.id,
        position=_next_position(step),
        section=section or "",
        kind=kind,
        text=text,
        url=url or "",
        done=bool(done) if kind == "task" else False,
        done_at=datetime.now() if done and kind == "task" else None,
    )
    db.add(item)
    step.checklist.append(item)
    return item


def import_structured(db, step, sections, links, replace: bool = False) -> int:
    """미리보기에서 고친 구조를 저장한다. 넣은 task 수를 돌려준다.

    replace 면 기존 항목을 모두 지운다 — 체크 기록도 함께 사라진다.
    화면은 누르기 전에 그 사실을 말해야 한다.
    """
    task_total = sum(len(section.items) for section in sections)
    if task_total == 0:
        raise ValueError("저장할 체크 항목이 없어요.")

    if replace:
        for item in list(step.checklist):
            step.checklist.remove(item)
            db.delete(item)
        db.flush()

    for section in sections:
        if section.note.strip():
            add_item(db, step, text=section.note.strip(), section=section.title, kind="note")
        for entry in section.items:
            add_item(db, step, text=entry.text, section=section.title, done=entry.done)

    for link in links:
        add_item(db, step, text=link.text or link.url, kind="link", url=link.url)

    return task_total


def set_done(step, item, done: bool) -> bool:
    """체크를 바꾼다. 단계가 시작 전이었으면 진행 중으로 올리고 True."""
    item.done = bool(done)
    item.done_at = datetime.now() if done else None

    tasks = _tasks(step)
    if step.status != "completed" and tasks:
        step.progress_percent = round(sum(1 for t in tasks if t.done) / len(tasks) * 100)

    if done and step.status == "not_started":
        step.status = "in_progress"
        return True

    return False
