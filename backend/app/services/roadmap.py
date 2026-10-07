"""로드맵 한 장을 통째로 들여온다 — 경로 + 단계 전부 + 마지막 프로젝트.

체크리스트 붙여넣기(checklist_parser)는 **한 주차**를 만든다. 그래서 경로
하나를 세우려면 단계를 하나씩 손으로 넣어야 했고, 그 일을 사람이 하다 보니
경로가 "주제 목록" 에서 멈췄다.

로드맵은 **프로젝트로 끝나야 한다.** 주제만 늘어놓으면 다 하고 나서도
포트폴리오에 쓸 게 없다. 그래서 마지막 블록을 읽어 실제 Project 행을
만들고 스킬을 잇는다 — 그 순간부터 기존 증거 판단(services/proof.py)이
그 프로젝트를 맡는다: 결과 기록 · GitHub · 데모 · 경험 · 포트폴리오 ·
이력서 문장 중 무엇이 남았는지 세어 준다. **판단하는 쪽을 새로 만들지
않고 이미 있는 데로 꽂는다.**

규칙 기반이다. LLM 은 앱에 넣지 않는다 (DECISIONS 17장) — 내용은 Claude
세션이 만들고, 앱은 구조 · 진행률 · 증거를 맡는다 (DECISIONS 30장).
"""

import re
from datetime import date, datetime

from .. import models
from . import checklist as checklist_service
from . import learning as learning_service


class RoadmapError(ValueError):
    """읽을 수 없는 로드맵. 무엇이 모자란지 말해 준다."""


# 머리말 — "# 경로: 제목" 또는 그냥 "# 제목"
PATH_HEAD = re.compile(r"^#\s*(?:경로\s*[:：]\s*)?(.+)$")

# 단계 — "## 1주차 · 제목 (180분)" · "## 2단계 — 제목 (3시간)"
STEP_HEAD = re.compile(r"^##\s+(?!최종\s*프로젝트)(.+)$")

# 마지막 프로젝트 — "## 최종 프로젝트: 제목"
PROJECT_HEAD = re.compile(r"^##\s*최종\s*프로젝트\s*[:：]?\s*(.*)$")

# 머리말 안의 "목표일: 2026-12-20"
META = re.compile(r"^(목표일|목표|설명|증명|남길\s*것)\s*[:：]\s*(.*)$")

BULLET = re.compile(r"^(?:[-*+•·]|\d+[.)])\s+(.+)$")

# "(180분)" · "(3시간)" · "(1시간 30분)"
MINUTES = re.compile(r"[（(]\s*(?:(\d+)\s*시간)?\s*(?:(\d+)\s*분)?\s*[)）]\s*$")

DATE = re.compile(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})")


def _minutes_from(title: str) -> tuple[str, int]:
    """제목 끝의 (시간)을 떼어내 분으로. 없으면 0."""
    found = MINUTES.search(title)

    if not found:
        return title.strip(), 0

    hours = int(found.group(1) or 0)
    minutes = int(found.group(2) or 0)

    return MINUTES.sub("", title).strip(), hours * 60 + minutes


def _date_from(text: str):
    found = DATE.search(text or "")

    if not found:
        return None

    try:
        return date(int(found.group(1)), int(found.group(2)), int(found.group(3)))
    except ValueError:
        return None


def parse(text: str) -> dict:
    """로드맵 글 → {title, description, target_date, steps[], project}.

    저장하지 않는다. 화면이 먼저 보여주고 사람이 확인한 뒤 넣는다.
    """
    title = ""
    description_lines = []
    target_date = None

    steps = []
    project = None

    current = None   # 지금 모으고 있는 단계
    in_project = False

    for raw in (text or "").splitlines():
        line = raw.strip()

        if not line:
            continue

        # 마지막 프로젝트 블록
        found = PROJECT_HEAD.match(line)
        if found:
            project = {
                "name": _strip(found.group(1)),
                "description": "",
                "skills": [],
                "outputs": [],
            }
            current = None
            in_project = True
            continue

        found = STEP_HEAD.match(line)
        if found:
            name, minutes = _minutes_from(_strip(found.group(1)))
            current = {
                "title": name,
                "minutes": minutes,
                "due_date": _date_from(name),
                "items": [],
            }
            steps.append(current)
            in_project = False
            continue

        found = PATH_HEAD.match(line)
        if found and not title:
            title = _strip(found.group(1))
            continue

        meta = META.match(line)
        if meta:
            key, value = meta.group(1), _strip(meta.group(2))

            if key == "목표일":
                target_date = _date_from(value)
            elif in_project and key == "증명":
                project["skills"] = _split_list(value)
            elif in_project and key.startswith("남길"):
                project["outputs"] = _split_list(value)
            elif in_project:
                project["description"] = value
            else:
                description_lines.append(value)
            continue

        bullet = BULLET.match(line)
        if bullet:
            content = _strip(bullet.group(1))

            if in_project:
                project["description"] += ("\n" if project["description"] else "") + content
            elif current is not None:
                current["items"].append(content)
            else:
                description_lines.append(content)
            continue

        # 그냥 줄글
        if in_project:
            project["description"] += ("\n" if project["description"] else "") + line
        elif current is None:
            description_lines.append(line)

    if not title:
        raise RoadmapError(
            "경로 이름을 못 찾았어요. 첫 줄을 '# 경로: 이름' 으로 적어 주세요."
        )

    if not steps:
        raise RoadmapError(
            "단계를 못 찾았어요. '## 1주차 · 제목 (180분)' 처럼 ## 로 적어 주세요."
        )

    total = sum(step["minutes"] for step in steps)

    return {
        "title": title,
        "description": "\n".join(description_lines),
        "target_date": target_date,
        "steps": steps,
        "project": project,
        "total_minutes": total,
        # 프로젝트가 없으면 화면이 그 말을 해야 한다. 주제만 늘어놓은
        # 로드맵은 다 해도 포트폴리오에 쓸 게 안 남는다.
        "warnings": (
            [] if project else
            ["마지막 프로젝트가 없어요. 다 끝내도 포트폴리오에 쓸 것이 안 남습니다."]
        ) + (
            [] if total else
            ["걸리는 시간이 안 적혀 있어요. '(180분)' 처럼 단계 제목 끝에 넣으면 "
             "오늘 할 몫을 계산할 수 있습니다."]
        ),
    }


def _strip(text: str) -> str:
    return (text or "").replace("**", "").replace("__", "").strip(" ·—-:：")


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,·、]", value or "") if part.strip()]


# --------------------------------
# 저장
# --------------------------------

def apply(db, parsed: dict, *, skill_id: int | None = None) -> dict:
    """읽은 로드맵을 실제 행으로 만든다.

    경로 · 단계 · 체크 항목 · 마지막 프로젝트까지 한 번에. 프로젝트는
    `purpose="evidence"` 로 둔다 — 증거로 남기려고 하는 것이기 때문이고,
    그래야 proof.py 가 "무엇이 남았는지" 를 세기 시작한다.
    """
    path = models.LearningPath(
        title=parsed["title"],
        description=parsed["description"],
        target_date=parsed["target_date"],
        skill_id=skill_id,
        kind="self",
        status="not_started",
    )
    db.add(path)
    db.flush()

    for position, step in enumerate(parsed["steps"]):
        row = models.LearningStep(
            learning_path_id=path.id,
            title=step["title"],
            position=position,
            estimated_minutes=step["minutes"],
            due_date=step["due_date"],
            status="not_started",
        )
        db.add(row)
        db.flush()

        for item in step["items"]:
            checklist_service.add_item(db, row, text=item)

    project_id = None

    if parsed["project"]:
        spec = parsed["project"]

        project = models.Project(
            name=spec["name"] or f"{parsed['title']} — 최종 프로젝트",
            description=spec["description"],
            # 증거로 남기려고 하는 것이다. 취미가 아니다.
            purpose="evidence",
            status="planned",
            progress_percent=0,
            target_date=parsed["target_date"],
        )

        # 증명할 스킬을 잇는다. 없는 이름은 만들지 않는다 — 오타와
        # 비슷한 이름이 쌓이는 걸 막는다 (vocabulary.py 와 같은 판단).
        for name in spec["skills"]:
            found = (
                db.query(models.Skill)
                .filter(models.Skill.name.ilike(name))
                .first()
            )
            if found is not None:
                project.skills.append(found)

        db.add(project)
        db.flush()
        project_id = project.id

    db.commit()
    db.refresh(path)

    learning_service.recalculate_path_progress(db, path)

    return {
        "learning_path_id": path.id,
        "title": path.title,
        "steps": len(parsed["steps"]),
        "checklist_items": sum(len(s["items"]) for s in parsed["steps"]),
        "project_id": project_id,
        "total_minutes": parsed["total_minutes"],
        # 스킬을 안 걸면 그 경로에서는 자료를 고를 수 없다 (자료가 스킬로
        # 묶여 있다). 화면이 그 말을 할 수 있게 돌려준다.
        "skill_id": skill_id,
    }


# --------------------------------
# 오늘 할 몫
# --------------------------------

def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    return value


def _next_segment(steps, today: date) -> dict | None:
    """다음 마감까지 — 거기까지 남은 시간과 하루 몫.

    마감이 붙은 **아직 안 끝난** 단계 중 가장 이른 것을 찾고, 거기까지의
    안 끝난 단계 시간을 모두 더한다. 중간에 마감 없는 단계가 있어도
    그것들은 그 마감 안에 들어가는 일이다.
    """
    milestone = None

    for step in steps:
        if step.status == "completed":
            continue

        due = _as_date(step.due_date)

        if due is not None:
            milestone = step
            break

    if milestone is None:
        return None

    due = _as_date(milestone.due_date)

    minutes = 0
    for step in steps:
        if step.status == "completed":
            continue
        minutes += step.estimated_minutes or 0
        if step.id == milestone.id:
            break

    days = (due - today).days

    return {
        "title": milestone.title,
        "due_date": due.isoformat(),
        "days_left": days,
        "left_minutes": minutes,
        "minutes_per_day": round(minutes / max(1, days)) if minutes else 0,
        # 마감이 이미 지났다. 숫자를 내밀기 전에 그 말을 먼저 해야 한다.
        "overdue": days < 0,
    }


def pace(path, today: date | None = None) -> dict:
    """전체에서 오늘 얼마나 해야 하는가.

    수현: "시간당 나눴을 때 오늘은 전체 주차에서 이만큼 하겠다가 있어야
    하는 거 아닌가."

    맞다. 로드맵에 24시간이라고 적혀 있어도, 그게 오늘 몇 분인지 안 나오면
    계획이 안 된다. **남은 시간 ÷ 남은 날** 이 그 답이다.

    목표일이 없으면 계산하지 않는다. 지어낸 날짜로 나누면 그 숫자가
    어디서 왔는지 설명할 수 없다.
    """
    today = today or date.today()

    steps = sorted(path.steps, key=lambda s: (s.position, s.id))

    total = sum(s.estimated_minutes or 0 for s in steps)
    done = sum(
        s.estimated_minutes or 0 for s in steps if s.status == "completed"
    )
    left = max(0, total - done)

    target = _as_date(path.target_date)

    days_left = (target - today).days if target else None

    # 오늘까지가 마감이면 남은 날은 1 로 본다 (0 으로 나누지 않는다).
    per_day = None
    if days_left is not None and left > 0:
        per_day = round(left / max(1, days_left))

    # **구간별 속도.** 전체를 목표일까지 고르게 나누면 실제 계획과 다르다.
    #
    # 수현의 로드맵에는 마감이 셋 있다 — 12/10 ML Core · 1/31 프로젝트 ·
    # 2/28 1회전. 161시간을 2/28 까지로 고르게 나누면 하루 1시간 7분이
    # 나오는데, 정작 12/10 까지 끝내야 할 57시간은 하루 53분이다.
    # **지금 달려야 할 속도는 다음 마감까지의 것이다.**
    segment = _next_segment(steps, today)

    return {
        "total_minutes": total,
        "done_minutes": done,
        "left_minutes": left,
        "target_date": target.isoformat() if target else None,
        "days_left": days_left,
        "minutes_per_day": per_day,
        "total_steps": len(steps),
        "done_steps": sum(1 for s in steps if s.status == "completed"),
        # 지금 할 차례. 끝내지 않은 것 중 첫 번째다.
        "current_step": next(
            (
                {
                    "id": s.id,
                    "title": s.title,
                    "position": s.position,
                    "minutes": s.estimated_minutes or 0,
                }
                for s in steps
                if s.status != "completed"
            ),
            None,
        ),
        # 다음 마감까지의 몫. 마감이 없으면 None — 전체 속도만 쓴다.
        "segment": segment,
        "behind": (
            days_left is not None
            and per_day is not None
            and days_left >= 0
            and per_day > 0
            and total > 0
            # 남은 몫이 하루 3시간을 넘기면 일정이 빡빡하다는 뜻이다.
            and per_day > 180
        ),
    }
