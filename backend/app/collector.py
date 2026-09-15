from . import models, schemas, collector
import os 
from dotenv import load_dotenv
from . import models

load_dotenv() #.env 파일 읽기 

SARAMIN_API_KEY = os.getenv("SARAMIN_API_KEY")

def normalize_job_data(raw_job: dict) -> dict:
    return {
        "company": raw_job.get("company", ""),
        "title": raw_job.get("title", ""),
        "role": raw_job.get("role", ""),
        "employment_type": raw_job.get("employment_type", "intern"),
        "url": raw_job.get("url", ""),
        "deadline": raw_job.get("deadline", ""),
        "description": raw_job.get("description", ""),
        "status": raw_job.get("status", "discovered"),
    }

def save_job(db, raw_job: dict):
    job_data = normalize_job_data(raw_job)

    existing_job = None

    if job_data["url"]:
        existing_job = db.query(models.Job).filter(
            models.Job.url == job_data["url"]
        ).first()

    if existing_job:
        return existing_job, False

    job = models.Job(
        company=job_data["company"],
        title=job_data["title"],
        role=job_data["role"],
        employment_type=job_data["employment_type"],
        url=job_data["url"],
        deadline=job_data["deadline"],
        description=job_data["description"],
        status=job_data["status"],
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    link_skills_from_description(db, job)

    return job, True


def link_skills_from_description(db, job):
    skills = db.query(models.Skill).all()

    description = job.description.lower()

    matched_skills = []

    for skill in skills:
        if skill.name.lower() in description:
            job.skills.append(skill)
            matched_skills.append(skill.name)

    db.commit()

    return matched_skills

def fetch_jobs():
    if not SARAMIN_API_KEY:
        return [
            {
                "company": "Mock Data Company",
                "title": "Data Scientist Intern",
                "role": "data_scientist",
                "employment_type": "intern",
                "url": "https://example.com/mock-job",
                "deadline": "2026-09-30",
                "description": (
                    "Python, SQL, Statistics and "
                    "Machine Learning experience preferred."
                ),
                "status": "discovered",
            }
        ]

    # 사람인 API 승인 후 여기에 실제 API 호출 코드를 넣을 예정
    return []