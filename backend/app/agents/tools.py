from .. import models
from ..services import priority as priority_service


# --------------------------------
# Learning Priority Tool
# --------------------------------

def get_learning_priority(db):
    """API 와 동일한 계산을 쓴다.

    이전에는 이 함수가 evidence_weight 를 빼고 점수를 매겨서
    Agent 응답과 /analytics/learning-priority 응답이 서로 달랐다.
    """
    return priority_service.get_learning_priority(db)


# --------------------------------
# Project Tool
# --------------------------------

def get_active_projects(db):
    projects = db.query(models.Project).all()

    return [
        {
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "progress_percent": project.progress_percent,
            "estimated_hours": project.estimated_hours,
            "daily_minutes": project.daily_minutes,
        }
        for project in projects
        if project.status != "completed"
    ]


# --------------------------------
# Learning Resource Tool
# --------------------------------

def get_saved_resources(db):
    resources = db.query(
        models.LearningResource
    ).all()

    return [
        {
            "id": resource.id,
            "title": resource.title,
            "url": resource.url,
            "resource_type": resource.resource_type,
            "duration_minutes": resource.duration_minutes,
            "skill_id": resource.skill_id,
        }
        for resource in resources
        if resource.status == "saved"
    ]


# --------------------------------
# Job Tool
# --------------------------------

def get_jobs(db):
    jobs = db.query(models.Job).all()

    return [
        {
            "id": job.id,
            "company": job.company,
            "title": job.title,
            "employment_type": job.employment_type,
            "deadline": job.deadline,
            "status": job.status,
            "url": job.url,
        }
        for job in jobs
    ]