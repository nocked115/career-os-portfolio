"""데모 데이터.

포트폴리오로 보여줄 배포본에 넣는다. 실사용 배포본에는 절대 넣지
않는다 — 실제 지원 내역과 섞이면 어느 쪽이 진짜인지 알 수 없다.

## 이 데이터가 지켜야 할 것

1. **가짜인 게 보여야 한다.** 조직명을 실존 기업으로 쓰지 않는다.
   보는 사람이 "이 사람이 여기 지원했구나" 로 오해하면 안 된다.

2. **판단이 보여야 한다.** 숫자가 그냥 채워져 있으면 화면이
   대시보드처럼 보인다. 스킬마다 시장 수요·격차·증거를 다르게
   줘서 우선순위가 실제로 갈리게 한다.

3. **빈 상태도 하나는 남긴다.** 전부 채우면 "데이터가 없을 때
   어떻게 보이나" 를 못 보여준다.

    python -m app.demo          # 비어 있을 때만 넣는다
    python -m app.demo --force  # 지우고 다시 넣는다
"""

from datetime import date, datetime, timedelta

from . import models
from .database import SessionLocal
from .services import opportunity as opportunity_service


def _has_data(db) -> bool:
    return db.query(models.Skill).count() > 0


def seed(db, force: bool = False) -> dict:
    if _has_data(db):
        if not force:
            return {"seeded": False, "reason": "이미 데이터가 있습니다"}

        _wipe(db)

    today = date.today()

    # --- 스킬 ---------------------------------------------------
    # 레벨을 다르게 줘서 격차가 갈리게 한다.
    skills = {}

    for name, category, level, aliases in [
        ("Python", "lang", 3, "파이썬"),
        ("SQL", "data", 3, ""),
        ("Machine Learning", "ai", 1, "머신러닝, ML"),
        ("Deep Learning", "ai", 0, "딥러닝, DL"),
        ("PyTorch", "ai", 0, "파이토치"),
        ("NLP", "ai", 0, "자연어 처리, 자연어처리"),
        ("AWS", "cloud", 2, ""),
        ("Docker", "infra", 1, "도커"),
    ]:
        skill = models.Skill(
            name=name, category=category, level=level, aliases=aliases
        )
        db.add(skill)
        skills[name] = skill

    db.flush()

    # --- 목표 직무 ------------------------------------------------
    target = models.TargetCareer(
        title="Data / AI Engineer",
        description="데이터와 모델로 제품을 만드는 직무",
        keywords="data, machine learning, python, ml engineer",
        is_active=True,
    )
    target.skills.extend(
        skills[n] for n in
        ["Python", "SQL", "Machine Learning", "Deep Learning", "PyTorch", "NLP"]
    )
    db.add(target)

    # --- 기회 ---------------------------------------------------
    # 조직명은 전부 가상이다. 실존 기업을 쓰면 보는 사람이
    # "여기 지원했구나" 로 오해한다.
    for kind, title, org, days, hours, text in [
        ("job", "ML Engineer 신입", "가상테크", 12, 40,
         "Python 과 PyTorch 로 모델을 학습하고 배포합니다. "
         "딥러닝 경험자 우대. Docker 기반 서빙."),
        ("job", "데이터 분석가", "샘플데이터랩", 25, 30,
         "SQL 과 Python 으로 지표를 설계하고 분석합니다. "
         "머신러닝을 활용한 예측 모델링 경험 우대."),
        ("competition", "AI 아이디어 공모전", "예시협회", 40, 60,
         "자연어 처리 또는 머신러닝을 활용한 서비스 아이디어. "
         "Python 구현 필수."),
        ("external_activity", "데이터 분석 서포터즈", "가상재단", 55, 20,
         "SQL 기반 공공데이터 분석과 리포트 작성."),
    ]:
        opportunity = models.Opportunity(
            opportunity_type=kind,
            title=title,
            organization=org,
            description=text,
            source="demo",
            status="interested",
            deadline=datetime.now() + timedelta(days=days),
            estimated_hours=hours,
        )
        db.add(opportunity)
        db.flush()
        opportunity_service.link_skills(db, opportunity)

    # --- 프로젝트 -------------------------------------------------
    # 증거의 세기를 단계별로 하나씩 둔다. 그래야 우선순위가
    # 왜 이렇게 나왔는지 화면에서 설명된다.
    for name, desc, status, progress, github, results, linked in [
        ("영화 추천 모델", "협업 필터링 기반 추천 시스템",
         "completed", 100, "https://github.com/example/movie-rec",
         "정확도 0.71 → 0.83", ["Python", "Machine Learning"]),
        ("리뷰 감성 분석", "한국어 리뷰 감성 분류",
         "in_progress", 60, "", "", ["Python", "NLP", "Deep Learning"]),
        ("사내 지표 대시보드", "SQL 기반 주간 지표 자동화",
         "completed", 100, "", "", ["SQL", "Python"]),
        ("컨테이너 배포 실습", "학습용 배포 파이프라인",
         "planned", 0, "", "", ["Docker", "AWS"]),
    ]:
        project = models.Project(
            name=name,
            description=desc,
            status=status,
            progress_percent=progress,
            career_related=True,
            github_url=github,
            results=results,
            daily_minutes=45,
            estimated_hours=20,
        )
        project.skills.extend(skills[n] for n in linked)
        db.add(project)

    db.flush()

    # --- 학습 경로 ------------------------------------------------
    path = models.LearningPath(
        title="딥러닝 기초 다지기",
        skill_id=skills["Deep Learning"].id,
        status="in_progress",
    )
    db.add(path)
    db.flush()

    for position, (step_title, status, minutes) in enumerate([
        ("신경망 기초", "completed", 60),
        ("역전파 이해하기", "completed", 90),
        ("PyTorch 로 첫 모델", "in_progress", 90),
        ("과적합 다루기", "not_started", 60),
    ]):
        db.add(models.LearningStep(
            learning_path_id=path.id,
            title=step_title,
            position=position,
            status=status,
            progress_percent=100 if status == "completed" else 0,
            estimated_minutes=minutes,
            completed_at=datetime.now() if status == "completed" else None,
        ))

    # --- 라이브러리 -----------------------------------------------
    # 지금 집중과 무관한 것도 섞는다. "안 봐도 되는 것" 을
    # 보여주는 게 이 제품의 핵심이라 그게 화면에 나와야 한다.
    for title, kind, minutes, ownership, skill_name, importance in [
        ("밑바닥부터 시작하는 딥러닝", "book", 0, "owned", "Deep Learning", "primary"),
        ("PyTorch 공식 튜토리얼", "official_doc", 25, "saved", "PyTorch", "primary"),
        ("역전파 시각화 영상", "video", 20, "saved", "Deep Learning", "primary"),
        ("CNN 구현 실습", "practice", 40, "saved", "Deep Learning", "supplementary"),
        ("Attention 논문", "paper", 60, "saved", "NLP", "deep_dive"),
        ("SQL 윈도우 함수 정리", "article", 15, "saved", "SQL", "primary"),
        ("Docker 입문 강의", "course", 120, "saved", "Docker", "primary"),
        ("AWS 아키텍처 백서", "paper", 90, "saved", "AWS", "deep_dive"),
        ("파이썬 클린 코드", "book", 0, "wishlist", "Python", "supplementary"),
    ]:
        resource = models.LearningResource(
            title=title,
            resource_type=kind,
            duration_minutes=minutes,
            ownership=ownership,
            importance=importance,
            skill_id=skills[skill_name].id,
            url=None if ownership == "owned" else "https://example.com",
        )
        db.add(resource)
        db.flush()

        # 책은 챕터로 나눈다 — "책 전체를 읽을 필요는 없습니다" 를
        # 보여주려면 조각이 있어야 한다.
        if title.startswith("밑바닥"):
            for index, (label, mins, done) in enumerate([
                ("1장 · 파이썬 입문", 20, True),
                ("3장 · 신경망", 35, True),
                ("5장 · 오차역전파법", 40, False),
                ("6장 · 학습 관련 기술들", 45, False),
            ]):
                db.add(models.LearningResourceSegment(
                    learning_resource_id=resource.id,
                    label=label,
                    position=index,
                    estimated_minutes=mins,
                    status="completed" if done else "not_started",
                    completed_at=datetime.now() if done else None,
                ))

    # --- 캘린더 -------------------------------------------------
    for title, kind, weekday, start, end in [
        ("데이터마이닝", "class", 0, 10 * 60, 12 * 60),
        ("알고리즘", "class", 1, 13 * 60, 15 * 60),
        ("데이터마이닝", "class", 2, 10 * 60, 12 * 60),
        ("연구실 미팅", "fixed", 3, 15 * 60, 17 * 60),
        ("과외", "work", 4, 18 * 60, 21 * 60),
    ]:
        db.add(models.CalendarBlock(
            title=title, kind=kind, weekday=weekday,
            start_minute=start, end_minute=end,
        ))

    # --- 경험 · 포트폴리오 -----------------------------------------
    done_project = (
        db.query(models.Project)
        .filter(models.Project.name == "영화 추천 모델")
        .first()
    )

    experience = models.Experience(
        experience_type="project",
        title="영화 추천 모델 개발",
        organization="개인 프로젝트",
        short_description="협업 필터링 기반 추천 시스템",
        problem="추천 품질이 낮아 사용자가 금방 이탈했습니다.",
        role="모델 설계와 학습 전체를 맡았습니다.",
        actions="협업 필터링을 구현하고 하이퍼파라미터를 조정했습니다.",
        results="정확도를 0.71 에서 0.83 으로 올렸습니다.",
        technologies="Python, PyTorch",
        metrics="accuracy 0.71 → 0.83",
        project_id=done_project.id if done_project else None,
    )
    experience.skills.extend(
        skills[n] for n in ["Python", "Machine Learning"]
    )
    db.add(experience)
    db.flush()

    db.add(models.PortfolioEntry(
        title="영화 추천 모델",
        short_description="협업 필터링 기반 추천 시스템",
        problem="추천 품질이 낮아 사용자가 금방 이탈했습니다.",
        role="모델 설계와 학습 전체를 맡았습니다.",
        actions="협업 필터링을 구현하고 하이퍼파라미터를 조정했습니다.",
        results="정확도를 0.71 에서 0.83 으로 올렸습니다.",
        technologies="Python, PyTorch",
        github_url="https://github.com/example/movie-rec",
        experience_id=experience.id,
        project_id=done_project.id if done_project else None,
    ))

    # --- 지원서 -------------------------------------------------
    first = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.title == "ML Engineer 신입")
        .first()
    )

    if first is not None:
        application = models.Application(
            opportunity_id=first.id,
            status="preparing",
            deadline=first.deadline,
        )
        db.add(application)
        db.flush()

        db.add(models.CoverLetterQuestion(
            application_id=application.id,
            question="지원 동기와 본인의 강점을 서술해주세요.",
            character_limit=800,
            position=0,
        ))

    # --- 프로필 -------------------------------------------------
    db.add(models.Profile(
        name="Demo",
        day_start_minute=9 * 60,
        day_end_minute=22 * 60,
        daily_cap_minutes=180,
    ))

    db.commit()

    return {
        "seeded": True,
        "skills": len(skills),
        "opportunities": db.query(models.Opportunity).count(),
        "projects": db.query(models.Project).count(),
        "resources": db.query(models.LearningResource).count(),
        "note": (
            "데모 데이터입니다. 조직명은 전부 가상이고 "
            "실제 지원 내역이 아닙니다."
        ),
    }


def _wipe(db) -> None:
    """--force 로 다시 넣을 때. 참조 순서를 지켜 지운다."""
    for model in (
        models.CoverLetterAnswer,
        models.CoverLetterQuestion,
        models.ApplicationExperienceMatch,
        models.Application,
        models.DailyPlanTask,
        models.PortfolioEntry,
        models.Experience,
        models.LearningResourceSegment,
        models.LearningResource,
        models.LearningStep,
        models.LearningPath,
        models.MarketSnapshot,
        models.Opportunity,
        models.Project,
        models.Job,
        models.TargetCareer,
        models.Skill,
        models.CalendarBlock,
        models.Profile,
    ):
        db.query(model).delete()

    db.commit()


def main() -> None:
    import sys

    force = "--force" in sys.argv

    db = SessionLocal()

    try:
        result = seed(db, force=force)
    finally:
        db.close()

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
