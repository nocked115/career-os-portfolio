"""Application / Cover Letter API (SPEC 17~19장)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import application_board as board_service
from ..services import today as today_service
from ._common import apply_update, delete_instance, ensure_exists, get_or_404

router = APIRouter(tags=["applications"])


# --------------------------------
# Application
# --------------------------------

@router.post(
    "/applications",
    response_model=schemas.ApplicationResponse,
    status_code=201,
)
def create_application(
    payload: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
):
    ensure_exists(
        db,
        models.Opportunity,
        payload.opportunity_id,
        "Opportunity",
    )
    ensure_exists(db, models.Job, payload.legacy_job_id, "Job")

    application = models.Application(**payload.model_dump())

    db.add(application)
    db.commit()
    db.refresh(application)

    return application


@router.get(
    "/applications",
    response_model=list[schemas.ApplicationResponse],
)
def list_applications(
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Application)

    if status is not None:
        query = query.filter(models.Application.status == status)

    return query.order_by(models.Application.created_at.desc()).all()


# {application_id} 보다 먼저 둔다. 뒤에 두면 "board" 를 id 로 읽으려다 422 가 난다.
@router.get("/applications/board")
def application_board(db: Session = Depends(get_db)):
    """지원서마다 마감 · 매칭 · 자소서 진행 · 다음 행동, 그리고 맨 위 요약."""
    return board_service.build_board(db)


@router.get(
    "/applications/{application_id}",
    response_model=schemas.ApplicationResponse,
)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
):
    return get_or_404(
        db,
        models.Application,
        application_id,
        "Application",
    )


@router.patch(
    "/applications/{application_id}",
    response_model=schemas.ApplicationResponse,
)
def update_application(
    application_id: int,
    payload: schemas.ApplicationUpdate,
    db: Session = Depends(get_db),
):
    application = get_or_404(
        db,
        models.Application,
        application_id,
        "Application",
    )

    return apply_update(application, payload, db)


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
):
    application = get_or_404(
        db,
        models.Application,
        application_id,
        "Application",
    )

    # 이 지원서를 가리키던 계획 항목을 먼저 정리한다.
    # 안 하면 오늘 계획에 없는 지원서에 대한 "지원 준비" 가 남는다.
    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.application_id, application_id
    )

    result = delete_instance(application, db)
    result["plan_tasks"] = released

    return result


# --------------------------------
# Application <-> Experience 매칭
# --------------------------------

@router.put(
    "/applications/{application_id}/experiences/{experience_id}",
    response_model=schemas.ApplicationExperienceMatchResponse,
)
def upsert_experience_match(
    application_id: int,
    experience_id: int,
    payload: schemas.ApplicationExperienceMatchCreate,
    db: Session = Depends(get_db),
):
    if (
        payload.application_id != application_id
        or payload.experience_id != experience_id
    ):
        raise HTTPException(
            status_code=400,
            detail="path 와 body 의 id 가 일치하지 않습니다",
        )

    get_or_404(db, models.Application, application_id, "Application")
    get_or_404(db, models.Experience, experience_id, "Experience")

    match = db.get(
        models.ApplicationExperienceMatch,
        (application_id, experience_id),
    )

    if match is None:
        match = models.ApplicationExperienceMatch(
            application_id=application_id,
            experience_id=experience_id,
        )
        db.add(match)

    match.match_score = payload.match_score
    match.match_notes = payload.match_notes

    db.commit()
    db.refresh(match)

    return match


@router.get(
    "/applications/{application_id}/experiences",
    response_model=list[schemas.ApplicationExperienceMatchResponse],
)
def list_experience_matches(
    application_id: int,
    db: Session = Depends(get_db),
):
    application = get_or_404(
        db,
        models.Application,
        application_id,
        "Application",
    )

    return sorted(
        application.experience_matches,
        key=lambda m: (m.match_score is None, -(m.match_score or 0)),
    )


@router.delete(
    "/applications/{application_id}/experiences/{experience_id}"
)
def delete_experience_match(
    application_id: int,
    experience_id: int,
    db: Session = Depends(get_db),
):
    match = db.get(
        models.ApplicationExperienceMatch,
        (application_id, experience_id),
    )

    if match is None:
        raise HTTPException(
            status_code=404,
            detail="Experience match not found",
        )

    return delete_instance(match, db)


# --------------------------------
# Cover Letter
# --------------------------------

@router.post(
    "/cover-letter-questions",
    response_model=schemas.CoverLetterQuestionResponse,
    status_code=201,
)
def create_cover_letter_question(
    payload: schemas.CoverLetterQuestionCreate,
    db: Session = Depends(get_db),
):
    get_or_404(
        db,
        models.Application,
        payload.application_id,
        "Application",
    )

    duplicate = (
        db.query(models.CoverLetterQuestion)
        .filter(
            models.CoverLetterQuestion.application_id
            == payload.application_id,
            models.CoverLetterQuestion.position == payload.position,
        )
        .first()
    )

    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"position {payload.position} is already used "
                "in this application"
            ),
        )

    question = models.CoverLetterQuestion(**payload.model_dump())

    db.add(question)
    db.commit()
    db.refresh(question)

    return question


@router.get(
    "/cover-letter-questions",
    response_model=list[schemas.CoverLetterQuestionResponse],
)
def list_cover_letter_questions(
    application_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.CoverLetterQuestion)

    if application_id is not None:
        query = query.filter(
            models.CoverLetterQuestion.application_id == application_id
        )

    return query.order_by(models.CoverLetterQuestion.position).all()


@router.patch(
    "/cover-letter-questions/{question_id}",
    response_model=schemas.CoverLetterQuestionResponse,
)
def update_cover_letter_question(
    question_id: int,
    payload: schemas.CoverLetterQuestionUpdate,
    db: Session = Depends(get_db),
):
    question = get_or_404(
        db,
        models.CoverLetterQuestion,
        question_id,
        "Cover letter question",
    )

    return apply_update(question, payload, db)


@router.delete("/cover-letter-questions/{question_id}")
def delete_cover_letter_question(
    question_id: int,
    db: Session = Depends(get_db),
):
    question = get_or_404(
        db,
        models.CoverLetterQuestion,
        question_id,
        "Cover letter question",
    )

    return delete_instance(question, db)


@router.post(
    "/cover-letter-questions/{question_id}/answers",
    response_model=schemas.CoverLetterAnswerResponse,
    status_code=201,
)
def create_cover_letter_answer(
    question_id: int,
    payload: schemas.CoverLetterAnswerCreate,
    db: Session = Depends(get_db),
):
    """새 답변 버전을 만든다.

    version 은 서버가 정하고, 새 버전이 생기면 이전 버전의
    is_current 는 내려간다.
    """
    question = get_or_404(
        db,
        models.CoverLetterQuestion,
        question_id,
        "Cover letter question",
    )

    if question.character_limit is not None:
        if len(payload.draft) > question.character_limit:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"draft 가 {question.character_limit}자 제한을 넘습니다 "
                    f"(현재 {len(payload.draft)}자)"
                ),
            )

    next_version = max(
        (answer.version for answer in question.answers),
        default=0,
    ) + 1

    for answer in question.answers:
        answer.is_current = False

    answer = models.CoverLetterAnswer(
        question_id=question.id,
        draft=payload.draft,
        version=next_version,
        is_current=True,
    )

    db.add(answer)
    db.commit()
    db.refresh(answer)

    return answer


@router.get(
    "/cover-letter-questions/{question_id}/answers",
    response_model=list[schemas.CoverLetterAnswerResponse],
)
def list_cover_letter_answers(
    question_id: int,
    current_only: bool = False,
    db: Session = Depends(get_db),
):
    question = get_or_404(
        db,
        models.CoverLetterQuestion,
        question_id,
        "Cover letter question",
    )

    answers = question.answers

    if current_only:
        answers = [answer for answer in answers if answer.is_current]

    return answers
