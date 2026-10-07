"""가고 싶은 회사.

매칭 점수에 얹는다 (services/opportunity.py). 이름만으로는 왜 가고 싶은지가 남지 않아서
note 를 같이 둔다 — 나중에 지원서를 쓸 때 그 문장이 재료가 된다.

기업 규모(대기업 · 중견 · 중소)는 여기 없다. 앱에 규모 데이터가 없어서다 —
공고에는 회사 이름 문자열만 있다. 사람인 API 가 승인되면 그때 공고 쪽에 붙인다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ._common import delete_instance, get_or_404

router = APIRouter(prefix="/preferred-companies", tags=["preferred company"])


@router.get("", response_model=list[schemas.PreferredCompanyResponse])
def list_preferred(db: Session = Depends(get_db)):
    return (
        db.query(models.PreferredCompany)
        .order_by(models.PreferredCompany.rank, models.PreferredCompany.name)
        .all()
    )


@router.post("", response_model=schemas.PreferredCompanyResponse, status_code=201)
def add_preferred(
    payload: schemas.PreferredCompanyCreate,
    db: Session = Depends(get_db),
):
    name = payload.name.strip()

    existing = (
        db.query(models.PreferredCompany)
        .filter(models.PreferredCompany.name == name)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"'{name}' 은(는) 이미 있어요.")

    company = models.PreferredCompany(
        name=name, note=payload.note.strip(), rank=payload.rank
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    return company


@router.patch("/{company_id}", response_model=schemas.PreferredCompanyResponse)
def update_preferred(
    company_id: int,
    payload: schemas.PreferredCompanyUpdate,
    db: Session = Depends(get_db),
):
    company = get_or_404(db, models.PreferredCompany, company_id, "Preferred company")

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "note" in changes:
        changes["note"] = changes["note"].strip()

    for field, value in changes.items():
        setattr(company, field, value)

    db.commit()
    db.refresh(company)

    return company


@router.delete("/{company_id}")
def remove_preferred(company_id: int, db: Session = Depends(get_db)):
    company = get_or_404(db, models.PreferredCompany, company_id, "Preferred company")
    return delete_instance(company, db)
