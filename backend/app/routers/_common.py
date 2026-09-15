"""라우터 공용 헬퍼."""

from fastapi import HTTPException


def get_or_404(db, model, obj_id: int, label: str):
    """PK 로 하나 조회하고 없으면 404."""
    instance = db.get(model, obj_id)

    if instance is None:
        raise HTTPException(
            status_code=404,
            detail=f"{label} not found",
        )

    return instance


def ensure_exists(db, model, obj_id, label: str):
    """FK 로 넘어온 id 가 실제로 존재하는지 확인한다. None 이면 통과."""
    if obj_id is None:
        return None

    return get_or_404(db, model, obj_id, label)


def apply_update(instance, payload, db):
    """보낸 필드만 반영하고 커밋한다."""
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(instance, field, value)

    db.commit()
    db.refresh(instance)

    return instance


def delete_instance(instance, db):
    db.delete(instance)
    db.commit()

    return {"deleted": True}
