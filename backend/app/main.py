import os

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import SessionLocal, get_db
from . import models, schemas,collector
from .services import priority as priority_service
from .services import learning as learning_service
from .services import opportunity as opportunity_service
from .routers import (
    applications as applications_router,
    calendar as calendar_router,
    evidence as evidence_router,
    experiences as experiences_router,
    learning as learning_router,
    library as library_router,
    market as market_router,
    opportunities as opportunities_router,
    proof as proof_router,
    profile as profile_router,
    target_careers as target_careers_router,
    review as review_router,
    today as today_router,
    transfer as transfer_router,
    universe as universe_router,
    workspace as workspace_router,
)

from math import ceil
from pathlib import Path
from datetime import date, timedelta

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth
from .auth import BasicAuthMiddleware, ReadOnlyMiddleware, check_startup
from .agents.career_agent import CareerAgent
from . import automation

from contextlib import asynccontextmanager
from .scheduler import (
    start_scheduler,
    scheduler,
    automation_status,
)

career_agent = CareerAgent()

# 빌드된 화면이 옆에 있으면 이 서비스가 그것도 낸다 (배포).
# 없으면 API 만 낸다 (로컬 개발 — Vite 가 따로 뜬다).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "static"
HAS_FRONTEND = FRONTEND_DIR.is_dir()

# 스키마는 Alembic 이 관리한다. 서버 기동 전에 `alembic upgrade head` 를 실행할 것.
# create_all 은 기존 테이블을 변경하지 못해 마이그레이션과 충돌하므로 사용하지 않는다.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 배포인데 자격 증명이 없으면 여기서 멈춘다.
    # 기본 비밀번호를 두는 것보다 안 뜨는 편이 낫다.
    check_startup()

    # 어떤 모드로 떴는지 로그에 남긴다.
    #
    # 공개 데모 변수가 실사용 서비스에 잘못 들어가면 진짜 경력
    # 기록이 인증 없이 열린다. 배포 로그 한 줄만 보고도 알아챌 수
    # 있어야 한다.
    if auth.is_public_demo():
        print(
            "[Career OS] 공개 데모 모드 — 인증 없음, 쓰기 차단. "
            "실사용 배포라면 지금 CAREER_OS_PUBLIC_DEMO 를 지울 것."
        )
    elif auth.is_read_only():
        print("[Career OS] 읽기 전용 모드 — 인증 필요, 쓰기 차단.")
    elif auth.credentials():
        print("[Career OS] 인증 켜짐 — 쓰기 가능.")

    # 데모 배포용. 비어 있을 때만 채운다.
    #
    # 이게 있으면 데모는 영속 볼륨이 필요 없다 — 컨테이너가 다시
    # 떠도 같은 데이터가 다시 생긴다. 볼륨은 대부분의 호스트에서
    # 유료라, 이 한 줄이 데모를 무료 티어에 올릴 수 있게 한다.
    #
    # 실사용 배포에는 절대 켜지 않는다. 실제 지원 내역과 섞인다.
    if os.getenv("CAREER_OS_SEED_DEMO") == "1":
        from .demo import seed

        session = SessionLocal()

        try:
            print("[Career OS]", seed(session))
        finally:
            session.close()

    start_scheduler()

    yield

    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

# 배포에서는 프런트를 같은 서비스가 서빙하므로 교차 출처가 없다.
# 개발에서만 Vite 개발 서버를 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 읽기 전용은 인증 안쪽이다. 인증부터 통과해야 401 과 403 이
# 섞이지 않는다.
app.add_middleware(ReadOnlyMiddleware)

# 인증은 가장 바깥이어야 한다. CORS 보다 안쪽에 두면
# preflight 응답으로 경로 존재 여부가 새어 나간다.
app.add_middleware(BasicAuthMiddleware)


@app.get("/healthz")
def healthz():
    """로드밸런서용. 인증 없이 연다 (auth.PUBLIC_PATHS)."""
    return {"status": "ok"}


@app.get("/config")
def config():
    """화면이 배포본의 성격을 알아야 하는 것들.

    읽기 전용인데 그 말을 안 해주면, 버튼을 눌러도 아무 일이
    없는 고장난 앱으로 보인다.
    """
    return {"read_only": auth.is_read_only()}

# Mission 021 신규 리소스는 라우터로 분리한다.
# 기존 엔드포인트는 main.py 에 그대로 두고 건드리지 않는다.
app.include_router(learning_router.router)
app.include_router(library_router.router)
app.include_router(opportunities_router.router)
app.include_router(experiences_router.router)
app.include_router(applications_router.router)
app.include_router(market_router.router)
app.include_router(evidence_router.router)
app.include_router(proof_router.router)
app.include_router(target_careers_router.router)
app.include_router(today_router.router)
app.include_router(profile_router.router)
app.include_router(universe_router.router)
app.include_router(calendar_router.router)
app.include_router(workspace_router.router)
app.include_router(transfer_router.router)
app.include_router(review_router.router)

from .routers import certificates as certificates_router  # noqa: E402

app.include_router(certificates_router.router)

from .routers import overview as overview_router  # noqa: E402

app.include_router(overview_router.router)

from .routers import checklist as checklist_router  # noqa: E402

app.include_router(checklist_router.router)

from .routers import routines as routines_router  # noqa: E402

app.include_router(routines_router.router)


# --------------------
# Root
# --------------------

if not HAS_FRONTEND:
    # 화면이 있으면 "/" 는 화면이 가진다. 이 인사말이 먼저 등록되면
    # 배포본 첫 화면이 JSON 한 줄이 된다.
    @app.get("/")
    def root():
        return {
            "message": "Career OS API is running"
        }


# --------------------
# Skills
# --------------------

@app.post("/skills", response_model=schemas.SkillResponse)
def create_skill(
    skill: schemas.SkillCreate,
    db: Session = Depends(get_db)
):
    # 같은 스킬을 두 번 만들면 수요와 레벨이 둘로 쪼개진다.
    # 대소문자 · 띄어쓰기만 다른 이름("machine learning")도 같은 스킬로 본다.
    wanted = "".join(skill.name.split()).lower()
    if not wanted:
        raise HTTPException(status_code=422, detail="스킬 이름을 적어 주세요.")

    for existing in db.query(models.Skill).all():
        if "".join(existing.name.split()).lower() == wanted:
            raise HTTPException(
                status_code=409,
                detail=f"'{existing.name}' 스킬이 이미 있어요. 레벨이나 별칭을 고쳐 주세요.",
            )

    db_skill = models.Skill(**{**skill.model_dump(), "name": skill.name.strip()})

    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)

    return db_skill


@app.patch("/skills/{skill_id}", response_model=schemas.SkillResponse)
def update_skill(
    skill_id: int,
    payload: schemas.SkillUpdate,
    db: Session = Depends(get_db),
):
    """스킬을 고친다. 레벨이 바뀌면 그 변화를 기록으로 남긴다.

    전에는 이 엔드포인트가 아예 없었다. 스킬은 만들 때 정한 레벨에
    영원히 머물렀고, 9장을 다 읽어도 Machine Learning 은 레벨 0 ·
    400점 그대로였다. 점수가 시장수요 x 격차 x 증거인데 격차가
    안 움직이니, 배운 것이 우선순위에 하나도 반영되지 않았다.

    레벨 변화는 skill_level_events 에 남긴다. 현재 값만 들고 있으면
    "이번 달에 무엇이 늘었나" 를 셀 수 없다.
    """
    skill = db.get(models.Skill, skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    fields = payload.model_dump(exclude_unset=True)

    before = skill.level or 0

    for key, value in fields.items():
        setattr(skill, key, value)

    after = skill.level or 0

    # 같은 값으로 다시 저장한 것은 변화가 아니다.
    if "level" in fields and after != before:
        db.add(models.SkillLevelEvent(
            skill_id=skill.id,
            from_level=before,
            to_level=after,
            source="manual",
        ))

    db.commit()
    db.refresh(skill)

    return skill


@app.get(
    "/skills/{skill_id}/level-events",
    response_model=list[schemas.SkillLevelEventResponse],
)
def list_skill_level_events(
    skill_id: int,
    db: Session = Depends(get_db),
):
    """이 스킬의 레벨이 어떻게 움직였는가."""
    skill = db.get(models.Skill, skill_id)

    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    return skill.level_events


@app.get("/skills", response_model=list[schemas.SkillResponse])
def get_skills(
    db: Session = Depends(get_db)
):
    return db.query(models.Skill).all()


# --------------------
# Projects
# --------------------

@app.post("/projects", response_model=schemas.ProjectResponse)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(get_db)
):
    db_project = models.Project(**project.model_dump())

    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project


@app.get("/projects", response_model=list[schemas.ProjectResponse])
def get_projects(
    db: Session = Depends(get_db)
):
    return db.query(models.Project).all()


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """프로젝트를 지운다. 스킬은 지우지 않는다.

    - 아직 안 한 오늘 계획 항목은 치우고, 끝낸 기록은 남긴다.
    - 이 프로젝트에서 나온 경험 · 포트폴리오는 지우지 않고 연결만 끊는다.
      증거는 프로젝트가 사라져도 따로 지울지 사람이 정한다.
    """
    from .services import today as today_service

    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    released = today_service.release_plan_tasks(
        db, models.DailyPlanTask.project_id, project_id
    )

    unlinked = 0
    for model in (models.Experience, models.PortfolioEntry):
        for row in db.query(model).filter(model.project_id == project_id).all():
            row.project_id = None
            unlinked += 1

    project.skills.clear()
    db.delete(project)
    db.commit()

    return {"deleted": True, "plan_tasks": released, "unlinked_evidence": unlinked}


# --------------------
# Jobs
# --------------------

@app.post("/jobs", response_model=schemas.JobResponse)
def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db)
):
    db_job = models.Job(**job.model_dump())

    db.add(db_job)
    db.flush()

    # 수요 집계의 모수는 Opportunity 하나다.
    # Job 으로 들어온 것도 거기 있어야 두 화면이 같은 수를 말한다.
    opportunity_service.bridge_from_legacy_job(db, db_job)

    db.commit()
    db.refresh(db_job)

    return db_job


@app.get("/jobs", response_model=list[schemas.JobResponse])
def get_jobs(
    db: Session = Depends(get_db)
):
    return db.query(models.Job).all()

from fastapi import HTTPException


# --------------------------------
# Project <-> Skill
# --------------------------------

@app.post("/projects/{project_id}/skills/{skill_id}")
def add_skill_to_project(
    project_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    skill = db.query(models.Skill).filter(
        models.Skill.id == skill_id
    ).first()

    if skill is None:
        raise HTTPException(
            status_code=404,
            detail="Skill not found"
        )

    if skill not in project.skills:
        project.skills.append(skill)
        db.commit()

    return {
        "message": f"{skill.name} linked to {project.name}"
    }


@app.get(
    "/projects/{project_id}/skills",
    response_model=list[schemas.SkillResponse]
)
def get_project_skills(
    project_id: int,
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return project.skills


# --------------------------------
# Job <-> Skill
# --------------------------------

@app.post("/jobs/{job_id}/skills/{skill_id}")
def add_skill_to_job(
    job_id: int,
    skill_id: int,
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(
        models.Job.id == job_id
    ).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    skill = db.query(models.Skill).filter(
        models.Skill.id == skill_id
    ).first()

    if skill is None:
        raise HTTPException(
            status_code=404,
            detail="Skill not found"
        )

    if skill not in job.skills:
        job.skills.append(skill)

    # 연결된 Opportunity 에도 같은 스킬을 붙인다.
    # 한쪽만 붙이면 수요 집계가 다시 갈라진다.
    opportunity_service.bridge_from_legacy_job(db, job)

    db.commit()

    return {
        "message": f"{skill.name} linked to {job.title}"
    }


@app.get(
    "/jobs/{job_id}/skills",
    response_model=list[schemas.SkillResponse]
)
def get_job_skills(
    job_id: int,
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(
        models.Job.id == job_id
    ).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job.skills


# --------------------------------
# Job Match Analysis
# --------------------------------

@app.get("/jobs/{job_id}/match")
def analyze_job_match(
    job_id: int,
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(
        models.Job.id == job_id
    ).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    required_skills = job.skills

    if len(required_skills) == 0:
        return {
            "job_id": job.id,
            "company": job.company,
            "title": job.title,
            "match_score": 0,
            "message": "No skills are linked to this job yet."
        }

    matched_skills = []
    missing_skills = []
    skill_details = []

    for skill in required_skills:

        # 현재 V0 기준:
        # level > 0 이면 어느 정도 보유/학습 중이라고 판단
        has_skill = skill.level > 0

        if has_skill:
            matched_skills.append(skill.name)
        else:
            missing_skills.append(skill.name)

        # 이 Skill을 증명할 수 있는 Career Project 찾기
        evidence_projects = [
            project.name
            for project in skill.projects
            if project.career_related
        ]

        skill_details.append({
            "skill": skill.name,
            "level": skill.level,
            "status": skill.status,
            "matched": has_skill,
            "evidence_projects": evidence_projects
        })

    match_score = round(
        len(matched_skills) / len(required_skills) * 100
    )

    return {
        "job_id": job.id,
        "company": job.company,
        "title": job.title,
        "match_score": match_score,
        "required_skills": [
            skill.name for skill in required_skills
        ],
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_details": skill_details
    }

# --------------------------------
# Skill Market Statistics
# --------------------------------

@app.get("/analytics/skills")
def get_skill_statistics(
    db: Session = Depends(get_db)
):
    # 계산은 한 곳에만 둔다. 여기는 우선순위 서비스가 낸 값을
    # 이 엔드포인트의 모양으로 다시 담기만 한다.
    entries = priority_service.build_skill_priorities(db)

    skill_stats = [
        {
            "skill": entry["skill_name"],
            "demand_count": entry["demand_count"],
            "demand_percentage": entry["market_percentage"],
            "my_level": entry["my_level"],
            "my_status": entry["skill"].status,
        }
        for entry in entries
    ]

    skill_stats.sort(
        key=lambda item: item["demand_count"],
        reverse=True
    )

    return {
        "total_demand": entries[0]["total_demand"] if entries else 0,
        "skills": skill_stats
    }

# --------------------------------
# Learning Priority
# --------------------------------

@app.get("/analytics/learning-priority")
def get_learning_priority(
    db: Session = Depends(get_db)
):
    return {
        "total_demand": db.query(models.Opportunity).count(),
        "learning_priority": priority_service.get_learning_priority(
            db,
            include_resources=True,
        ),
    }


# --------------------------------
# Job Collector
# --------------------------------

@app.post("/collector/jobs", response_model=schemas.JobResponse)
def collect_job(
    job: schemas.JobCreate,
    db: Session = Depends(get_db)
):
    raw_job = job.model_dump()

    saved_job = collector.save_job(
        db=db,
        raw_job=raw_job
    )

    return saved_job

# --------------------------------
# Fetch Jobs
# --------------------------------

@app.post("/collector/fetch")
def fetch_and_save_jobs(
    db: Session = Depends(get_db)
):
    raw_jobs = collector.fetch_jobs()

    created_count = 0
    skipped_count = 0
    jobs = []

    for raw_job in raw_jobs:
        saved_job, created = collector.save_job(
            db=db,
            raw_job=raw_job
        )

        if created:
            created_count += 1
        else:
            skipped_count += 1

        jobs.append({
            "id": saved_job.id,
            "company": saved_job.company,
            "title": saved_job.title,
            "created": created
        })

    return {
        "fetched_count": len(raw_jobs),
        "created_count": created_count,
        "skipped_count": skipped_count,
        "jobs": jobs
    }

# --------------------------------
# Learning Resources
# --------------------------------

@app.post(
    "/resources",
    response_model=schemas.LearningResourceResponse
)
def create_resource(
    resource: schemas.LearningResourceCreate,
    db: Session = Depends(get_db)
):
    # 필드를 하나씩 나열하면 스키마에 새 필드가 생겼을 때 조용히 누락된다.
    # 같은 버그가 세 번 났다: importance · estimated_hours · results.
    # 새 엔드포인트도 반드시 model_dump() 를 쓸 것.
    db_resource = models.LearningResource(**resource.model_dump())

    db.add(db_resource)
    db.commit()
    db.refresh(db_resource)

    return db_resource


@app.get(
    "/resources",
    response_model=list[schemas.LearningResourceResponse]
)
def get_resources(
    db: Session = Depends(get_db)
):
    return db.query(models.LearningResource).all()


@app.get(
    "/skills/{skill_id}/resources",
    response_model=list[schemas.LearningResourceResponse]
)
def get_skill_resources(
    skill_id: int,
    db: Session = Depends(get_db)
):
    return (
        db.query(models.LearningResource)
        .filter(models.LearningResource.skill_id == skill_id)
        .all()
    )


@app.get("/today")
def get_today_plan(
    db: Session = Depends(get_db)
):
    priorities = priority_service.build_skill_priorities(db)

    if not priorities:
        return {
            "message": "No skills available."
        }

    top_priority = priorities[0]
    top_skill = top_priority["skill"]

    # 3. 추천 학습자료 찾기
    recommended_resource = None

    if top_skill.resources:
        resource = top_skill.resources[0]

        recommended_resource = {
            "id": resource.id,
            "title": resource.title,
            "url": resource.url,
            "resource_type": resource.resource_type,
            "duration_minutes": resource.duration_minutes
        }

    # 4. 연결된 프로젝트 찾기
    related_project = None

    for project in top_skill.projects:
        if (
            project.career_related
            and project.status != "completed"
        ):
            related_project = project
            break

    project_plan = None

    # 5. 프로젝트 ETA 계산
    if related_project:
        remaining_ratio = (
            100 - related_project.progress_percent
        ) / 100

        remaining_hours = (
            related_project.estimated_hours
            * remaining_ratio
        )

        days_needed = None
        finish_date = None

        if related_project.daily_minutes > 0:
            remaining_minutes = remaining_hours * 60

            days_needed = ceil(
                remaining_minutes
                / related_project.daily_minutes
            )

            finish_date = (
                date.today()
                + timedelta(days=days_needed)
            ).isoformat()

        project_plan = {
            "id": related_project.id,
            "name": related_project.name,
            "progress_percent":
                related_project.progress_percent,
            "estimated_hours":
                related_project.estimated_hours,
            "remaining_hours":
                round(remaining_hours, 1),
            "daily_minutes":
                related_project.daily_minutes,
            "days_needed":
                days_needed,
            "estimated_finish_date":
                finish_date
        }

    # 6. 오늘 행동 만들기
    if recommended_resource and recommended_resource["duration_minutes"] > 0:
        today_action = (
            f"{recommended_resource['title']} — "
            f"{recommended_resource['duration_minutes']}분"
        )
    elif recommended_resource:
        # 자료를 쪼개뒀으면 그 조각이 오늘의 단위다.
        next_segment = next(
            (
                item
                for item in db.get(
                    models.LearningResource, recommended_resource["id"]
                ).segments
                if item.status != "completed"
            ),
            None,
        )

        if next_segment is not None:
            today_action = (
                f"{recommended_resource['title']} — {next_segment.label}"
                f" · {next_segment.estimated_minutes}분"
            )
        else:
            # 분량도 모르고 쪼개지도 않은 자료다. 종이책을 넣으면
            # 여기로 온다.
            #
            # 전에는 그대로 "for 0 minutes" 라고 말했다. 0분
            # 공부하라는 말은 아무 뜻이 없다. 모르면 모른다고 하고,
            # 무엇을 채우면 되는지 말한다.
            today_action = (
                f"{recommended_resource['title']} — "
                "장으로 나누면 오늘 어디까지 할지 정해집니다"
            )
    elif related_project and related_project.daily_minutes > 0:
        today_action = (
            f"{related_project.name} — {related_project.daily_minutes}분"
        )
    else:
        # 수요는 있는데 가진 자료가 없다. 빈칸을 감추지 않는다 —
        # 이 앱은 새 자료를 추천하지 않기로 했으므로(README 의
        # "하지 않는 것"), 대신 구멍이 어디인지는 정확히 말한다.
        today_action = (
            f"{top_skill.name} 자료가 라이브러리에 없습니다. "
            "하나 넣으면 오늘 계획에 올라옵니다"
        )

    # Mission 022: 학습 경로가 있으면 다음 스텝을 가리킨다.
    # 화면에서 Today -> Learning Session 으로 넘어가는 진입점이다.
    next_step = learning_service.summarize_step_for_plan(
        learning_service.find_next_step(top_skill)
    )

    return {
        "focus_skill": top_skill.name,
        "priority_score": top_priority["priority_score"],
        "reason": {
            "market_percentage":
                top_priority["market_percentage"],
            # 분모를 같이 보낸다. 화면은 "100%" 가 아니라
            # "공고 1건 중 1건" 으로 쓴다 (DESIGN.md 원칙 1).
            "demand_count": top_priority["demand_count"],
            "total_demand": top_priority["total_demand"],
            "my_level": top_skill.level,
            "skill_gap": top_priority["skill_gap"],
            "learning_progress":
                top_priority["learning_progress"],
            "has_project_evidence":
                top_priority["has_project_evidence"],
            "career_projects": [
                project.name
                for project in top_priority["career_projects"]
            ]
        },
        "recommended_resource": recommended_resource,
        "next_learning_step": next_step,
        "project_plan": project_plan,
        "today_action": today_action
    }


@app.get("/projects/{project_id}/eta")
def get_project_eta(
    project_id: int,
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id
    ).first()

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    if project.daily_minutes <= 0:
        return {
            "project": project.name,
            "message": "daily_minutes must be greater than 0"
        }

    remaining_ratio = (100 - project.progress_percent) / 100

    remaining_hours = project.estimated_hours * remaining_ratio

    remaining_minutes = remaining_hours * 60

    days_needed = ceil(
        remaining_minutes / project.daily_minutes
    )

    estimated_finish_date = date.today() + timedelta(
        days=days_needed
    )

    return {
        "project": project.name,
        "estimated_hours": project.estimated_hours,
        "progress_percent": project.progress_percent,
        "daily_minutes": project.daily_minutes,
        "remaining_hours": round(remaining_hours, 1),
        "days_needed": days_needed,
        "estimated_finish_date": estimated_finish_date.isoformat()
    }


@app.get("/weekly-plan")
def get_weekly_plan(
    daily_available_minutes: int = 120,
    db: Session = Depends(get_db)
):
    projects = (
        db.query(models.Project)
        .filter(
            models.Project.career_related == True,
            models.Project.status != "completed"
        )
        .all()
    )

    skill_priorities = priority_service.build_skill_priorities(db)

    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    ]

    weekly_plan = []

    used_resource_ids = set()
    used_resource_titles = set()


    # -----------------------------
    # 하루 단위 계획 생성
    # -----------------------------
    for day in days:
        remaining_minutes = daily_available_minutes
        tasks = []

        resource_added_today = False

        # 1. Project 먼저 배정
        for project in projects:
            if remaining_minutes <= 0:
                break

            if project.daily_minutes <= 0:
                continue

            allocated_minutes = min(
                project.daily_minutes,
                remaining_minutes
            )

            tasks.append({
                "type": "project",
                "project_id": project.id,
                "title": project.name,
                "minutes": allocated_minutes,
                "progress_percent":
                    project.progress_percent
            })

            remaining_minutes -= allocated_minutes

        # 2. 남는 시간에 Learning Resource 배정
        resource_added_today = False

        for item in skill_priorities:
            if remaining_minutes <= 0:
                break

            if resource_added_today:
                break

            skill = item["skill"]

            for resource in skill.resources:
                if remaining_minutes <= 0:
                    break

                if resource.status == "completed":
                    continue

                   # 이미 이번 주에 사용한 리소스면 건너뛰기
                if resource.id in used_resource_ids:
                    continue

                # 제목이 같은 중복 리소스도 건너뛰기
                if resource.title in used_resource_titles:
                    continue

                resource_minutes = (
                    resource.duration_minutes
                    if resource.duration_minutes > 0
                    else 30
                )

                allocated_minutes = min(
                    resource_minutes,
                    remaining_minutes
                )

                tasks.append({
                    "type": "resource",
                    "resource_id": resource.id,
                    "skill": skill.name,
                    "title": resource.title,
                    "url": resource.url,
                    "minutes": allocated_minutes,
                    "priority_score":
                        item["priority_score"]
                })

                used_resource_ids.add(resource.id)
                used_resource_titles.add(resource.title)

                remaining_minutes -= allocated_minutes

                resource_added_today = True

                break

        weekly_plan.append({
            "day": day,
            "planned_minutes":
                daily_available_minutes
                - remaining_minutes,
            "remaining_minutes": remaining_minutes,
            "tasks": tasks
        })

    return {
        "daily_available_minutes":
            daily_available_minutes,
        "weekly_plan": weekly_plan
    }

@app.post("/agent")
def run_agent(
    request: schemas.AgentRequest,
    db: Session = Depends(get_db)
):
    return career_agent.analyze(
        message=request.message,
        db=db
    )

@app.post("/automation/run")
def run_automation(
    db: Session = Depends(get_db)
):
    return automation.run_career_automation(db)


@app.get("/automation/status")
def get_automation_status():
    job = scheduler.get_job("career_os_update")

    next_run_time = None

    if job and job.next_run_time:
        next_run_time = job.next_run_time.isoformat()

    return {
        "scheduler_running": scheduler.running,
        "next_run_time": next_run_time,
        "last_run_at": automation_status["last_run_at"],
        "last_status": automation_status["last_status"],
        "last_error": automation_status["last_error"],
    }


# --------------------------------
# 프런트엔드
#
# 배포에서는 한 서비스가 API 와 화면을 같이 낸다. 둘로 나누면
# CORS, 두 개의 URL, 두 번의 배포가 생기는데 1인용 앱에 그럴
# 이유가 없다.
#
# 이 마운트는 **모든 API 라우트를 등록한 뒤** 와야 한다.
# 먼저 두면 정적 파일 핸들러가 /today 같은 경로를 먼저 삼킨다.
# --------------------------------

if HAS_FRONTEND:
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """해시 라우팅이라 경로는 항상 하나다.

        그래도 /favicon.ico 같은 실제 파일은 그대로 내보낸다.
        """
        candidate = FRONTEND_DIR / full_path

        if full_path and candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(FRONTEND_DIR / "index.html")
