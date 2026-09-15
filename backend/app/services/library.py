"""My Learning Library — Phase 2.

Career OS 는 새 자료를 추천하지 않는다.

    ❌ "AWS 공부하려면 이런 유튜브가 있습니다."
    ✅ "이미 가진 책 3장과 저장해둔 영상 하나면 오늘 45분은 충분합니다."

그래서 Learning 의 핵심은 추천 엔진이 아니라 **선별**이다.
쌓아둔 것 중에서 지금 필요한 것만 꺼내고, **나머지는 치운다.**

치운 것을 보여주는 것까지가 선별이다.
"나머지 4개는 지금 볼 필요 없음" 을 빼면 그냥 목록이 된다.
"""

from datetime import date, datetime, time, timedelta

from .. import models


OWNERSHIP_ORDER = ("owned", "saved", "wishlist")

IMPORTANCE_ORDER = ("primary", "supplementary", "deep_dive")

COMPLETED = "completed"


# --------------------------------
# 라이브러리 조회
# --------------------------------

def summarize(db) -> dict:
    """라이브러리 전체 요약. 종류별로 몇 개인지."""
    resources = db.query(models.LearningResource).all()

    by_type: dict[str, int] = {}
    by_ownership: dict[str, int] = {}

    for resource in resources:
        by_type[resource.resource_type] = by_type.get(resource.resource_type, 0) + 1
        by_ownership[resource.ownership] = by_ownership.get(resource.ownership, 0) + 1

    segments = db.query(models.LearningResourceSegment).all()

    return {
        "total": len(resources),
        "by_type": by_type,
        "by_ownership": by_ownership,
        "segments": len(segments),
        "segments_done": sum(1 for s in segments if s.status == COMPLETED),
    }


def serialize_segment(segment) -> dict:
    return {
        "id": segment.id,
        "learning_resource_id": segment.learning_resource_id,
        "position": segment.position,
        "label": segment.label,
        "start_ref": segment.start_ref,
        "end_ref": segment.end_ref,
        "estimated_minutes": segment.estimated_minutes,
        "status": segment.status,
        "completed_at": segment.completed_at,
    }


# --------------------------------
# 서가 — 자료가 언제 학습되는가
#
# 중요도(primary · supplementary · deep_dive)는 "얼마나 중요한가" 이고,
# 서가는 "언제 보는가" 다. 둘을 섞지 않는다.
#
# 사람이 직접 정한 서가가 있으면 그것을 따른다. 없으면(saved) 기록으로만
# 정하고, 그렇게 정한 이유를 함께 준다. 기록이 없으면 "분류 전" 이다.
# --------------------------------

SHELVES = ("in_progress", "queued", "on_hold", "completed")

SHELF_LABELS = {
    "in_progress": "지금 학습",
    "queued": "다음 학습",
    "on_hold": "보류",
    "completed": "완료",
    "saved": "분류 전",
}


def _ordered_segments(resource):
    return sorted(resource.segments, key=lambda item: (item.position, item.id))


def shelf_of(resource) -> tuple[str, str]:
    if resource.status in SHELVES:
        return resource.status, "직접 정한 서가"

    segments = resource.segments
    done = sum(1 for segment in segments if segment.status == COMPLETED)

    if segments and done == len(segments):
        return "completed", "챕터를 모두 끝내서"

    if done:
        return "in_progress", f"챕터 {done}개를 끝내서"

    steps = resource.learning_steps

    if any(step.status == "in_progress" for step in steps):
        return "in_progress", "진행 중인 학습 단계에 연결돼 있어서"

    if any(step.status != COMPLETED for step in steps):
        return "queued", "아직 안 끝낸 학습 단계에 연결돼 있어서"

    return "saved", "아직 정하지 않았어요"


def progress_of(resource) -> dict:
    """챕터로 셀 수 있을 때만 진행률을 준다. 없으면 모른다고 한다."""
    segments = _ordered_segments(resource)

    if not segments:
        return {
            "percent": 100 if resource.status == COMPLETED else None,
            "done": 0,
            "total": 0,
            "next": None,
        }

    done = [segment for segment in segments if segment.status == COMPLETED]
    total_minutes = sum(segment.estimated_minutes or 0 for segment in segments)
    done_minutes = sum(segment.estimated_minutes or 0 for segment in done)

    percent = (
        round(done_minutes / total_minutes * 100)
        if total_minutes
        else round(len(done) / len(segments) * 100)
    )

    upcoming = next(
        (segment for segment in segments if segment.status != COMPLETED), None
    )

    return {
        "percent": percent,
        "done": len(done),
        "total": len(segments),
        "next": upcoming.label if upcoming else None,
    }


def serialize_resource(resource, include_segments: bool = True) -> dict:
    data = {
        "id": resource.id,
        "title": resource.title,
        "url": resource.url,
        "resource_type": resource.resource_type,
        "duration_minutes": resource.duration_minutes,
        "importance": resource.importance,
        "ownership": resource.ownership,
        "total_units": resource.total_units,
        "unit_label": resource.unit_label,
        "status": resource.status,
        "skill_id": resource.skill_id,
        # 이 자료를 쓰는 학습 단계. 없으면 등록만 해두고 아무 단계에서도
        # 안 쓰는 자료라는 뜻이다 — 화면이 그 사실을 보여줄 수 있어야 한다.
        "linked_steps": [
            {
                "id": step.id,
                "title": step.title,
                "path_title": step.learning_path.title if step.learning_path else "",
            }
            for step in resource.learning_steps
        ],
    }

    if include_segments:
        segments = resource.segments

        data["segments"] = [serialize_segment(s) for s in segments]
        data["segments_total"] = len(segments)
        data["segments_done"] = sum(
            1 for s in segments if s.status == COMPLETED
        )

    shelf, reason = shelf_of(resource)

    data["skill_name"] = resource.skill.name if resource.skill else ""
    data["shelf"] = shelf
    data["shelf_label"] = SHELF_LABELS[shelf]
    data["shelf_reason"] = reason
    data["progress"] = progress_of(resource)

    return data


def set_shelf(db, resource, shelf: str):
    """사람이 서가를 정한다. 기록으로 정한 것보다 앞선다."""
    resource.status = shelf
    db.commit()
    db.refresh(resource)

    return serialize_resource(resource)


# --------------------------------
# HOT — 요즘 많이 다룬 자료
#
# 재미 요소지만 숫자는 기록에서만 나온다. 최근 30일 동안 끝낸 챕터와
# 오늘 계획에서 완료한 자료 작업을 센다. 기록이 없는 자료는 순위에
# 넣지 않는다 — 1위를 지어내지 않는다.
# --------------------------------

HOT_WINDOW_DAYS = 30
HOT_LIMIT = 3


def build_hot(db, today: date | None = None, limit: int = HOT_LIMIT) -> list[dict]:
    today = today or date.today()
    since = datetime.combine(today - timedelta(days=HOT_WINDOW_DAYS), time.min)

    counts: dict[int, dict] = {}

    def bucket(resource_id):
        return counts.setdefault(resource_id, {"chapters": 0, "tasks": 0})

    segments = (
        db.query(models.LearningResourceSegment)
        .filter(models.LearningResourceSegment.status == COMPLETED)
        .filter(models.LearningResourceSegment.completed_at >= since)
        .all()
    )

    for segment in segments:
        bucket(segment.learning_resource_id)["chapters"] += 1

    tasks = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.learning_resource_id.isnot(None))
        .filter(models.DailyPlanTask.status == "done")
        .filter(models.DailyPlanTask.completed_at >= since)
        .all()
    )

    for task in tasks:
        bucket(task.learning_resource_id)["tasks"] += 1

    rows = []

    for resource_id, count in counts.items():
        parts = []
        if count["chapters"]:
            parts.append(f"챕터 {count['chapters']}개 끝냄")
        if count["tasks"]:
            parts.append(f"오늘 계획에서 {count['tasks']}번 완료")

        rows.append({
            "resource_id": resource_id,
            "score": count["chapters"] * 2 + count["tasks"],
            "chapters": count["chapters"],
            "tasks": count["tasks"],
            "reason": f"최근 {HOT_WINDOW_DAYS}일 · " + " · ".join(parts),
        })

    rows.sort(key=lambda row: (-row["score"], row["resource_id"]))

    for rank, row in enumerate(rows[:limit], start=1):
        row["rank"] = rank

    return rows[:limit]


# --------------------------------
# 오늘 학습에 꺼내기
#
# 서가 상태만 바꾸고 끝나면 "꺼냈다" 가 아니다. 오늘 계획에 실제 작업을
# 올리고, 이 자료를 쓰는 학습 단계가 있으면 그 세션으로 가는 길을 준다.
# --------------------------------

def add_to_plan(db, resource, minutes: int | None = None) -> dict:
    from . import today as today_service

    today = date.today()

    existing = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.plan_date == today,
            models.DailyPlanTask.learning_resource_id == resource.id,
            models.DailyPlanTask.status == "planned",
        )
        .first()
    )

    session_step = next(
        (
            step
            for step in sorted(
                resource.learning_steps, key=lambda item: (item.position, item.id)
            )
            if step.status != COMPLETED
        ),
        None,
    )

    step_payload = (
        {"id": session_step.id, "title": session_step.title} if session_step else None
    )

    if existing is not None:
        return {
            "already_planned": True,
            "task": today_service.serialize_task(existing),
            "session_step": step_payload,
            "resource": serialize_resource(resource),
        }

    upcoming = next(
        (s for s in _ordered_segments(resource) if s.status != COMPLETED), None
    )

    title = f"{resource.title} — {upcoming.label}" if upcoming else resource.title

    wanted = minutes or (
        (upcoming.estimated_minutes if upcoming else 0)
        or resource.duration_minutes
        or 30
    )

    position = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date == today)
        .count()
    )

    task = models.DailyPlanTask(
        plan_date=today,
        position=position,
        task_type="resource",
        title=title,
        minutes=min(wanted, 180),
        reason="내 자료에서 직접 꺼냈습니다.",
        status="planned",
        learning_resource_id=resource.id,
    )

    db.add(task)

    if resource.status != COMPLETED:
        resource.status = "in_progress"

    db.commit()
    db.refresh(task)
    db.refresh(resource)

    return {
        "already_planned": False,
        "task": today_service.serialize_task(task),
        "session_step": step_payload,
        "resource": serialize_resource(resource),
    }


def list_library(db, resource_type=None, ownership=None, skill_id=None):
    query = db.query(models.LearningResource)

    if resource_type:
        query = query.filter(
            models.LearningResource.resource_type == resource_type
        )

    if ownership:
        query = query.filter(models.LearningResource.ownership == ownership)

    if skill_id is not None:
        query = query.filter(models.LearningResource.skill_id == skill_id)

    return [serialize_resource(r) for r in query.all()]


# --------------------------------
# Resource Selector
#
# 오늘 필요한 것만 고른다. 나머지는 명시적으로 치운다.
# --------------------------------

def _consumable_units(resource) -> list[dict]:
    """이 자료에서 오늘 소비할 수 있는 조각들.

    조각(Segment)이 있으면 미완료 조각만 쓴다.
    없으면 자료 전체를 한 덩어리로 본다.
    """
    if resource.segments:
        return [
            {
                "kind": "segment",
                "segment_id": segment.id,
                "resource_id": resource.id,
                "title": f"{resource.title} · {segment.label}",
                "minutes": segment.estimated_minutes or 0,
                "importance": resource.importance,
                "ownership": resource.ownership,
                "resource_type": resource.resource_type,
                "url": resource.url,
            }
            for segment in resource.segments
            if segment.status != COMPLETED
        ]

    if resource.status == COMPLETED:
        return []

    return [{
        "kind": "resource",
        "segment_id": None,
        "resource_id": resource.id,
        "title": resource.title,
        "minutes": resource.duration_minutes or 0,
        "importance": resource.importance,
        "ownership": resource.ownership,
        "resource_type": resource.resource_type,
        "url": resource.url,
    }]


def _sort_key(item):
    """중요도 우선, 같으면 내가 가진 것 우선.

    이미 가진 것을 두고 저장만 해둔 것을 먼저 보라고 하면
    이 제품의 논지에 어긋난다.
    """
    importance = (
        IMPORTANCE_ORDER.index(item["importance"])
        if item["importance"] in IMPORTANCE_ORDER
        else len(IMPORTANCE_ORDER)
    )
    ownership = (
        OWNERSHIP_ORDER.index(item["ownership"])
        if item["ownership"] in OWNERSHIP_ORDER
        else len(OWNERSHIP_ORDER)
    )

    return (importance, ownership, item["minutes"])


def select_for_step(db, step, available_minutes: int) -> dict:
    """이 학습 단계에 대해 오늘 볼 것만 고른다.

    고른 것과 **치운 것을 함께** 돌려준다.
    치운 것을 숨기면 선별했다는 증거가 사라진다.
    """
    candidates = []

    for resource in step.resources:
        candidates.extend(_consumable_units(resource))

    candidates.sort(key=_sort_key)

    chosen = []
    skipped = []
    remaining = max(0, available_minutes)

    for item in candidates:
        minutes = item["minutes"] or 0

        if minutes == 0:
            # 시간을 모르는 자료는 오늘 계획에 넣지 않는다.
            # 얼마나 걸릴지 모르는 걸 넣으면 계획이 거짓이 된다.
            skipped.append({**item, "skip_reason": "예상 시간이 없습니다"})
            continue

        if minutes > remaining:
            skipped.append({
                **item,
                "skip_reason": f"오늘 남은 시간({remaining}분)으로는 부족합니다",
            })
            continue

        chosen.append(item)
        remaining -= minutes

    return {
        "available_minutes": available_minutes,
        "selected_minutes": sum(i["minutes"] for i in chosen),
        "remaining_minutes": remaining,
        "selected": chosen,
        "skipped": skipped,
        "skipped_count": len(skipped),
        "skipped_message": (
            f"나머지 자료 {len(skipped)}개 → 지금은 볼 필요 없음"
            if skipped
            else None
        ),
    }


# --------------------------------
# 라이브러리 전체 선별
#
# select_for_step 은 학습 단계 하나만 본다. 그래서 "이 단계 자료 중
# 오늘 볼 것" 까지만 답할 수 있다.
#
# 사용자가 실제로 안고 있는 부담은 그게 아니다. 쌓아둔 것이 63개인데
# 뭘 봐야 할지 모르는 상태다. 그래서 라이브러리 **전체**를 놓고
# 골라야 하고, 치운 것의 개수를 밝혀야 한다.
#
#   "영상 43개 · 책 11권 — 지금은 볼 필요 없습니다"
#
# 이 문장이 이 제품에서 가장 중요한 문장이다 (DESIGN.md 원칙 2).
# --------------------------------

# 지금 필요한 것으로 인정하는 근거. 위일수록 강하다.
RELEVANCE_STEP = 0      # 지금 학습 단계가 직접 요구
RELEVANCE_FOCUS = 1     # 집중 스킬 자료
RELEVANCE_OTHER = 2     # 그 밖 — 오늘은 아니다


def _relevance(item, step_resource_ids, focus_skill):
    """왜 이게 지금 필요한가(또는 아닌가)."""
    if item["resource_id"] in step_resource_ids:
        return RELEVANCE_STEP, "지금 학습 단계가 요구하는 내용입니다"

    if focus_skill is not None and item["skill_id"] == focus_skill.id:
        return RELEVANCE_FOCUS, f"집중 스킬 {focus_skill.name} 자료입니다"

    if focus_skill is None:
        return RELEVANCE_OTHER, "지금 집중할 스킬이 정해지지 않았습니다"

    return (
        RELEVANCE_OTHER,
        f"지금 집중하는 {focus_skill.name} 와(과) 관련이 없습니다",
    )


def _type_counts(items) -> list[dict]:
    """치운 것을 종류별로 센다.

    "63개" 보다 "영상 43개 · 책 11권" 이 부담을 더 덜어준다.
    무엇을 안 봐도 되는지가 눈에 들어오기 때문이다.
    """
    counts = {}

    for item in items:
        counts[item["resource_type"]] = (
            counts.get(item["resource_type"], 0) + 1
        )

    return [
        {"resource_type": kind, "count": count}
        for kind, count in sorted(
            counts.items(), key=lambda pair: (-pair[1], pair[0])
        )
    ]


def _set_aside_message(picked: int, aside: int, focus_skill) -> str | None:
    if aside == 0:
        return None

    if picked == 0:
        if focus_skill is None:
            return (
                "집중할 스킬이 정해지지 않아 무엇을 고를지 판단할 수 "
                "없습니다. 자료는 그대로 있습니다."
            )

        return (
            f"지금 집중하는 {focus_skill.name} 와(과) 바로 이어지는 자료가 "
            "없습니다. 자료를 연결하거나 예상 시간을 넣어주세요."
        )

    return (
        f"오늘은 위 {picked}개면 충분합니다. "
        "나머지는 지금 집중하는 것과 직접 관련이 없어 보류했습니다."
    )


def select_for_today(db, available_minutes: int) -> dict:
    """라이브러리 전체에서 오늘 필요한 것만 고른다.

    새로 계산하지 않는다. 집중 스킬과 다음 학습 단계는 이미 각
    서비스가 정해 놓은 것을 그대로 쓴다.
    """
    # 순환 임포트를 피하려고 지역에서 가져온다.
    from . import learning as learning_service
    from . import priority as priority_service

    entries = priority_service.build_skill_priorities(db)
    focus_skill = entries[0]["skill"] if entries else None

    step = (
        learning_service.find_next_step(focus_skill)
        if focus_skill is not None
        else None
    )
    step_resource_ids = (
        {resource.id for resource in step.resources} if step else set()
    )

    candidates = []
    done = []

    for resource in db.query(models.LearningResource).all():
        units = _consumable_units(resource)

        if not units:
            # 다 본 자료. 치운 것으로 세지 않는다 —
            # 끝낸 것을 "안 봐도 됨" 으로 묶으면 성과가 지워진다.
            done.append(resource)
            continue

        for unit in units:
            candidates.append({**unit, "skill_id": resource.skill_id})

    selected = []
    set_aside = []
    remaining = max(0, available_minutes)

    scored = []
    for item in candidates:
        rank, note = _relevance(item, step_resource_ids, focus_skill)
        scored.append({**item, "relevance": rank, "why": note})

    scored.sort(key=lambda item: (item["relevance"], _sort_key(item)))

    for item in scored:
        minutes = item["minutes"] or 0

        if item["relevance"] == RELEVANCE_OTHER:
            set_aside.append({**item, "skip_reason": item["why"]})
            continue

        if minutes == 0:
            # 얼마나 걸릴지 모르는 것을 오늘에 넣으면 계획이 거짓이 된다.
            set_aside.append({
                **item,
                "skip_reason": "예상 시간이 없습니다",
            })
            continue

        if minutes > remaining:
            set_aside.append({
                **item,
                "skip_reason": (
                    f"오늘 남은 시간({remaining}분)으로는 부족합니다"
                ),
            })
            continue

        selected.append(item)
        remaining -= minutes

    return {
        "focus_skill": focus_skill.name if focus_skill is not None else None,
        "current_step": step.title if step is not None else None,
        "available_minutes": available_minutes,
        "selected_minutes": sum(item["minutes"] for item in selected),
        "remaining_minutes": remaining,
        "selected": selected,
        "set_aside": set_aside,
        "set_aside_count": len(set_aside),
        "set_aside_by_type": _type_counts(set_aside),
        "completed_count": len(done),
        # 심판처럼 말하지 않는다. "필요 없음" 은 쌓아둔 것을 평가하는
        # 말이고, 사용자를 불안하게 만든다. 주의력을 지켜주는 쪽으로 쓴다.
        #
        # 고른 게 없을 때 "0개면 충분합니다" 라고 쓰면 틀린 문장이 된다.
        "message": _set_aside_message(
            len(selected), len(set_aside), focus_skill
        ),
    }


# --------------------------------
# 진행
# --------------------------------

def complete_segment(db, segment):
    """조각 하나를 끝냈다고 표시한다.

    자료의 모든 조각이 끝나면 자료 자체도 완료로 올린다.
    """
    segment.status = COMPLETED
    segment.completed_at = datetime.now()

    resource = segment.resource

    if resource.segments and all(
        s.status == COMPLETED for s in resource.segments
    ):
        resource.status = COMPLETED

    db.commit()
    db.refresh(segment)

    return {
        "segment": serialize_segment(segment),
        "resource_status": resource.status,
    }
