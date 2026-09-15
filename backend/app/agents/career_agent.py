import re
from ..scheduler import scheduler, automation_status
from ..automation import run_career_automation
from .tools import (
    get_learning_priority,
    get_active_projects,
    get_saved_resources,
    get_jobs,
)

from .. import models


class CareerAgent:

    def __init__(self):
        self.name = "Career Agent"

    def detect_intent(self, message: str):
        message = message.lower()

        if any(word in message for word in ["오늘", "today", "할 일", "뭐 해야"]):
            return "today"

        if any(word in message for word in ["공고", "채용", "job", "jobs", "회사"]):
            return "jobs"

        if any(word in message for word in ["공부", "학습", "skill", "스킬", "배워"]):
            return "learning"

        if any(word in message for word in ["프로젝트", "project", "진행률"]):
            return "projects"
        if (
            "자동화" in message
            and any(
                word in message
                for word in [
                    "상태",
                    "언제",
                    "다음",
                    "확인",
                ]
            )
        ):
            return "automation_status"

        if any(
            word in message
            for word in [
                "업데이트",
                "새로고침",
                "동기화",
                "자동화",
                "update",
                "refresh",
                "sync"
            ]
    ):
          return "automation"

        return "general"

    def extract_available_minutes(self, message: str):
        match = re.search(r"(\d+)\s*분", message)

        if match:
            return int(match.group(1))

        hour_match = re.search(r"(\d+)\s*시간", message)

        if hour_match:
            return int(hour_match.group(1)) * 60

        return None

    def analyze(self, message: str, db):
        intent = self.detect_intent(message)

        if intent == "jobs":
            return self.handle_jobs(message, db)

        if intent == "learning":
            return self.handle_learning(message, db)

        if intent == "projects":
            return self.handle_projects(message, db)

        if intent == "today":
            return self.handle_today(message, db)
        if intent == "automation_status":
            return self.handle_automation_status(message)

        if intent == "automation":
            return self.handle_automation(message, db)

        return self.handle_general(message)
    
    # --------------------
    # Jobs
    # --------------------

    def handle_jobs(self, message: str, db):
        jobs = get_jobs(db)

        return {
            "agent": self.name,
            "intent": "jobs",
            "message": message,
            "tool_used": "get_jobs",
            "result": jobs
        }

    # --------------------
    # Learning
    # --------------------

    def handle_learning(self, message: str, db):
        priorities = get_learning_priority(db)

        return {
            "agent": self.name,
            "intent": "learning",
            "message": message,
            "tool_used": "get_learning_priority",
            "result": priorities
        }
    
    # --------------------
    # Projects
    # --------------------

    def handle_projects(self, message: str, db):
        projects = get_active_projects(db)

        return {
            "agent": self.name,
            "intent": "projects",
            "message": message,
            "tool_used": "get_active_projects",
            "result": projects
        }

    # --------------------
    # Today
    # --------------------

    def handle_today(self, message: str, db):
        priorities = get_learning_priority(db)
        projects = get_active_projects(db)
        resources = get_saved_resources(db)

        available_minutes = self.extract_available_minutes(message)

        if not priorities:
            return {
                "agent": self.name,
                "intent": "today",
                "message": message,
                "result": {
                    "message": "No learning priorities available."
                }
            }

        top_skill = priorities[0]

        matched_resource = None

        for resource in resources:
            skill = db.query(models.Skill).filter(
                models.Skill.id == resource["skill_id"]
            ).first()

            if skill and skill.name == top_skill["skill"]:
                matched_resource = resource
                break

        matched_project = None

        for project_data in projects:
            project = db.query(models.Project).filter(
                models.Project.id == project_data["id"]
            ).first()

            if not project:
                continue

            skill_names = [
                skill.name
                for skill in project.skills
            ]

            if top_skill["skill"] in skill_names:
                matched_project = project_data
                break

        candidate_actions = []

        if matched_resource:
            candidate_actions.append({
                "type": "resource",
                "title": matched_resource["title"],
                "minutes": matched_resource["duration_minutes"],
                "url": matched_resource["url"]
            })

        if matched_project:
            candidate_actions.append({
                "type": "project",
                "title": matched_project["name"],
                "minutes": matched_project["daily_minutes"],
                "progress_percent":
                    matched_project["progress_percent"]
            })

        # 사용자가 시간을 말하지 않으면 기존 계획 그대로
        if available_minutes is None:
            actions = candidate_actions

        else:
            actions = []
            remaining_minutes = available_minutes

            for action in candidate_actions:
                if remaining_minutes <= 0:
                    break

                allocated_minutes = min(
                    action["minutes"],
                    remaining_minutes
                )

                adjusted_action = action.copy()
                adjusted_action["minutes"] = allocated_minutes

                actions.append(adjusted_action)

                remaining_minutes -= allocated_minutes

        total_minutes = sum(
            action["minutes"]
            for action in actions
        )

        return {
            "agent": self.name,
            "intent": "today",
            "message": message,
            "tools_used": [
                "get_learning_priority",
                "get_active_projects",
                "get_saved_resources"
            ],
            "result": {
                "focus_skill": top_skill["skill"],
                "priority_score":
                    top_skill["priority_score"],
                "available_minutes":
                    available_minutes,
                "actions": actions,
                "total_minutes": total_minutes
            }
        }

    # --------------------
    # General
    # --------------------

    def handle_general(self, message: str):
        return {
            "agent": self.name,
            "intent": "general",
            "message": message,
            "result": "I could not determine which Career OS action to run."
        }


    def handle_automation(self, message: str, db):
        result = run_career_automation(db)

        return {
            "agent": self.name,
            "intent": "automation",
            "message": message,
            "tool_used": "run_career_automation",
            "result": result
        }

    def handle_automation_status(self, message: str):
        job = scheduler.get_job("career_os_update")

        next_run_time = None

        if job and job.next_run_time:
            next_run_time = job.next_run_time.isoformat()

        return {
            "agent": self.name,
            "intent": "automation_status",
            "message": message,
            "tool_used": "scheduler_status",
            "result": {
                "scheduler_running": scheduler.running,
                "next_run_time": next_run_time,
                "last_run_at": automation_status["last_run_at"],
                "last_status": automation_status["last_status"],
                "last_error": automation_status["last_error"],
            }
        }