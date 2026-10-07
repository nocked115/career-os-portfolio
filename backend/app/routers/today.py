"""Today Plan API (Phase 1).

기존 `GET /today` 는 main.py 에 그대로 두고 건드리지 않는다.
계획을 만들고 체크하는 것은 여기서 한다.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import today as today_service
from ..services import why as why_service
from ._common import get_or_404

router = APIRouter(prefix="/today", tags=["today"])


@router.get("/plan")
def get_today_plan(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 저장된 계획. 아직 만들지 않았으면 빈 목록."""
    return today_service.build_plan(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.post("/plan")
def create_today_plan(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 계획을 만든다. 다시 부르면 아직 안 한 것만 새로 짠다.

    이미 끝낸 일은 지우지 않는다.
    """
    if intensity not in today_service.INTENSITY:
        raise HTTPException(
            status_code=422,
            detail=(
                "intensity 는 "
                + " / ".join(today_service.INTENSITY)
                + " 중 하나여야 합니다"
            ),
        )

    return today_service.generate_plan(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.get("/why")
def get_today_why(
    available_minutes: int = Query(
        today_service.DEFAULT_AVAILABLE_MINUTES, ge=0, le=1440
    ),
    intensity: str = today_service.DEFAULT_INTENSITY,
    db: Session = Depends(get_db),
):
    """오늘 계획이 왜 이렇게 나왔는지.

    새로 계산하지 않는다. 각 서비스가 이미 내놓는 값을 모은다.
    데이터가 없는 입력은 available=false 로 표시해서
    무엇을 못 봤는지도 같이 보여준다.
    """
    return why_service.build_why(
        db,
        available_minutes=available_minutes,
        intensity_name=intensity,
    )


@router.get("/intensities")
def list_intensities():
    """선택할 수 있는 강도와 그 의미."""
    return {
        "intensities": [
            {
                "key": key,
                "label": value["label"],
                "max_tasks": value["max_tasks"],
                "min_block": value["min_block"],
                "max_block": value["max_block"],
            }
            for key, value in today_service.INTENSITY.items()
        ]
    }


@router.get("/deadlines")
def get_deadlines(db: Session = Depends(get_db)):
    """다가오는 마감. 지난 것은 빼고 가까운 순으로."""
    return {"deadlines": today_service.collect_deadlines(db)}


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    body: schemas.TaskCompleteRequest | None = None,
    db: Session = Depends(get_db),
):
    """완료 처리. 학습 단계라면 실제 진행도까지, 루틴이면 그날 기록까지 남긴다."""
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    return today_service.complete_task(
        db, task,
        count=body.count if body else None,
        actual_minutes=body.actual_minutes if body else None,
    )


@router.post("/tasks")
def add_task(body: schemas.PlanTaskAdd, db: Session = Depends(get_db)):
    """오늘 계획에 직접 한 줄 넣기 — 시간이 남아 하고 싶은 것을 넣을 자리.

    계획은 제안이지 명령이 아니다. 대신 무엇을 가리키는지는 남긴다 — 완료했을 때
    진행률과 증거가 같이 움직여야 한다.
    """
    try:
        return today_service.add_task(
            db, body.kind, body.target_id, body.title, body.minutes
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: int, db: Session = Depends(get_db)):
    """완료 · 넘김 되돌리기. 완료가 남긴 기록(루틴 그날 기록 등)도 같이 되돌린다."""
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    if task.status == "planned":
        raise HTTPException(status_code=400, detail="아직 하지 않은 일이라 되돌릴 게 없어요.")

    return today_service.reopen_task(db, task)


@router.post("/tasks/{task_id}/revive")
def revive_task(task_id: int, db: Session = Depends(get_db)):
    """사흘 넘게 밀린 일을 "그래도 하겠다" 고 되살린다.

    "이건 안 할 건가요?" 는 두 답이 다 가능해야 질문이다. 치우는
    길만 있으면 그건 묻는 게 아니라 버리는 것이다.

    나이를 오늘로 되돌린다. 그러면 다시 이월 후보가 되고, 또 사흘을
    미루면 다시 물어본다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    task.carried_from = date.today()

    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.post("/tasks/{task_id}/skip")
def skip_task(
    task_id: int,
    body: schemas.TaskSkipRequest | None = None,
    db: Session = Depends(get_db),
):
    """오늘은 넘긴다. 이월되지 않고 여기서 끝난다.

    까닭을 적을 수 있다 — 안 한 것도 기록이다. 같은 까닭이 반복되면
    계획이 틀린 것이지 사람이 게으른 게 아니다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    if body is not None and body.reason.strip():
        task.skip_reason = body.reason.strip()

    task.status = "skipped"
    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.post("/tasks/{task_id}/park")
def park_task(task_id: int, db: Session = Depends(get_db)):
    """기한 없이 빼둔다 — "언젠가 할 일" 로 옮긴다.

    치우기(skip)와 다르다. 치운 것은 그날로 끝나지만 이건 남는다.
    날짜에 묶이지 않아서 매일 보이고, 거기서 바로 완료할 수 있다.
    오늘 계획은 밀어내지 않는다 — 이월도 다시 짜기도 `planned` 만 보기 때문이다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    if task.status == "done":
        raise HTTPException(status_code=409, detail="이미 끝낸 일이에요.")

    task.status = today_service.PARKED
    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.post("/tasks/{task_id}/unpark")
def unpark_task(task_id: int, db: Session = Depends(get_db)):
    """빼둔 것을 오늘 계획으로 되돌린다.

    plan_date 를 오늘로 옮긴다. 안 옮기면 빼둔 날의 계획에 들어가
    오늘 화면에 안 보인다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    if task.status != today_service.PARKED:
        raise HTTPException(status_code=409, detail="빼둔 일이 아니에요.")

    task.status = "planned"
    task.plan_date = date.today()
    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.patch("/tasks/{task_id}")
def edit_task(
    task_id: int,
    body: schemas.PlanTaskEdit,
    db: Session = Depends(get_db),
):
    """한 줄의 제목 · 걸리는 시간을 고친다.

    계획은 제안이지 명령이다. 앱이 "45분" 이라고 적어 둔 것이 실제로는
    20분이면, 그 숫자 위에서 세는 "남은 시간" 이 전부 틀린다. 고칠 자리가
    없으면 사람은 그냥 숫자를 무시하게 되고, 그러면 계획 자체가 장식이 된다.

    끝낸 일은 고치지 않는다 — 이미 센 시간이라 되돌아가 숫자를 바꾸면
    그날의 기록이 사실과 달라진다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    if task.status == "done":
        raise HTTPException(status_code=409, detail="이미 끝낸 일이에요. 되돌린 뒤에 고쳐 주세요.")

    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="무엇을 할지 적어 주세요.")
        task.title = title[:200]

    if body.minutes is not None:
        task.minutes = body.minutes

    db.commit()
    db.refresh(task)

    return today_service.serialize_task(task)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """한 줄을 아주 지운다.

    넘기기 · 빼두기와 다르다. 둘은 "안 한다" 를 **기록으로 남기는** 것이라
    화면에 자국이 남는다. 직접 넣었다가 잘못 넣은 줄은 자국도 남기고 싶지
    않다 — 안 한 일이 아니라 애초에 없던 일이기 때문이다.

    앱이 고른 줄도 지울 수 있지만, 다시 짜면 같은 근거로 또 올라온다.
    그건 지우기가 고장난 게 아니라 그 일이 아직 할 일이라는 뜻이다.
    오늘 안 하기로 **정한** 것이면 넘기기를, 나중에 할 것이면 빼두기를 쓴다.
    """
    task = get_or_404(db, models.DailyPlanTask, task_id, "Task")

    # 직접 넣은 줄은 reason 이 "직접 넣었습니다" 로 시작한다 (add_task).
    was_generated = not (task.reason or "").startswith("직접 넣었습니다")

    db.delete(task)
    db.commit()

    return {
        "deleted": True,
        "was_generated": was_generated,
        "plan": today_service.build_plan(db, date.today()),
    }
