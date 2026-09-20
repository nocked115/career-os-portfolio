"""단계에서 내가 만든 것, 그리고 그것을 경험으로 넘기기.

체크는 "했다" 를 센다. 이 모듈은 "남은 것" 을 다룬다 — 요약 노트 · 발표
자료 · 코드의 주소. 공부한 흔적이 앱 밖에만 있으면 나중에 지원서를 쓸 때
꺼낼 수 없다.

경험은 **지어내지 않는다.** 초안에 들어가는 문장은 전부 이미 앱에 있는 것뿐이다
— 단계 이름 · 경로 설명 · 체크한 항목 · 만든 것의 제목과 주소. 상황 · 역할처럼
사람만 아는 칸은 비워 두고 경험 화면에서 채우게 한다.
"""

from .. import models


# 깃허브 주소는 경험의 GitHub 칸으로, 나머지는 글 칸으로 간다.
GITHUB_HOSTS = ("github.com", "gitlab.com")

MAX_ACTIONS = 12


def serialize(output) -> dict:
    return {
        "id": output.id,
        "title": output.title,
        "url": output.url,
        "created_at": output.created_at,
    }


def add(db, step, title: str, url: str):
    output = models.LearningStepOutput(
        learning_step_id=step.id,
        title=title.strip()[:200],
        url=url.strip(),
    )
    db.add(output)
    db.commit()
    db.refresh(output)
    return output


def _is_code(url: str) -> bool:
    return any(host in url for host in GITHUB_HOSTS)


def _done_items(step) -> list[str]:
    return [item.text for item in step.checklist if item.done and item.kind == "task"]


def experience_of(db, step):
    """이 단계로 이미 만든 경험. 같은 단계를 두 번 보내지 않는다."""
    return (
        db.query(models.Experience)
        .filter(models.Experience.learning_step_id == step.id)
        .first()
    )


def build_draft(step) -> dict:
    """경험 초안. 앱에 있는 것만 옮긴다."""
    path = step.learning_path
    outputs = list(step.outputs)

    code = next((item for item in outputs if _is_code(item.url)), None)
    writing = next((item for item in outputs if not _is_code(item.url)), None)

    done = _done_items(step)
    actions = "\n".join(f"- {text}" for text in done[:MAX_ACTIONS])
    results = "\n".join(f"- {item.title} ({item.url})" for item in outputs)

    skills = list(getattr(path, "skills", []) or []) if path else []
    ended = step.completed_at.date() if step.completed_at else step.due_date

    return {
        # 학습에서 나온 것은 대개 연구 · 활동이다. 프로젝트인지는 사람이 고른다.
        "experience_type": "research",
        "title": f"{path.title} — {step.title}" if path else step.title,
        "organization": "",
        "short_description": (step.description or (path.description if path else ""))[:2000],
        "problem": "",
        "role": "",
        "actions": actions,
        "results": results,
        "technologies": ", ".join(skill.name for skill in skills),
        "metrics": "",
        "tags": "",
        "start_date": None,
        "end_date": ended,
        "github_url": code.url if code else "",
        "blog_url": writing.url if writing else "",
        "demo_url": "",
        "learning_step_id": step.id,
    }


def to_experience(db, step):
    """단계를 경험 초안으로 넘긴다. 만든 것이 하나도 없으면 만들지 않는다."""
    experience = models.Experience(**build_draft(step))
    db.add(experience)
    db.commit()
    db.refresh(experience)
    return experience


def session_summary(db, step) -> dict:
    existing = experience_of(db, step)
    return {
        "outputs": [serialize(output) for output in step.outputs],
        "experience": (
            {"id": existing.id, "title": existing.title} if existing else None
        ),
    }
