"""자격증 · 어학 API.

번호 칸이 없다. 자격번호 · 수험번호는 앱에 담지 않는다.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import certificates as certificate_service
from ._common import delete_instance, get_or_404

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("")
def list_certificates(db: Session = Depends(get_db)):
    """어학 · 직무 자격으로 나눈 목록과 만료 요약."""
    return certificate_service.build_list(db)


@router.post("", status_code=201)
def create_certificate(
    payload: schemas.CertificateCreate,
    db: Session = Depends(get_db),
):
    certificate = models.Certificate(**payload.model_dump())

    db.add(certificate)
    db.commit()
    db.refresh(certificate)

    return certificate_service.serialize(certificate)


@router.patch("/{certificate_id}")
def update_certificate(
    certificate_id: int,
    payload: schemas.CertificateUpdate,
    db: Session = Depends(get_db),
):
    certificate = get_or_404(db, models.Certificate, certificate_id, "Certificate")

    changes = payload.model_dump(exclude_unset=True)

    # 한쪽 날짜만 보내도 저장된 다른 쪽과 맞는지 본다.
    acquired = changes.get("acquired_on", certificate.acquired_on)
    expires = changes.get("expires_on", certificate.expires_on)

    if acquired and expires and expires < acquired:
        raise HTTPException(
            status_code=422, detail="만료일이 취득일보다 빠를 수 없습니다."
        )

    for field, value in changes.items():
        setattr(certificate, field, value)

    db.commit()
    db.refresh(certificate)

    return certificate_service.serialize(certificate)


@router.delete("/{certificate_id}")
def delete_certificate(certificate_id: int, db: Session = Depends(get_db)):
    certificate = get_or_404(db, models.Certificate, certificate_id, "Certificate")

    return delete_instance(certificate, db)
