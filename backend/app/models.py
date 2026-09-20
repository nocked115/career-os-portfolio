from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Boolean,
    Text,
    Table,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


# --------------------------------
# Profile
#
# Career OS 는 1인용이다. 로그인도 사용자 목록도 없다.
# 이 테이블은 항상 한 줄만 갖는다.
#
# 그런데 이 한 줄이 없으면 화면에서 사람이 사라진다.
# 목표도 우선순위도 다 남의 데이터처럼 읽힌다 (DESIGN.md 3장).
# --------------------------------

class Certificate(Base):
    """자격증 · 어학 점수 한 건.

    번호(자격번호 · 수험번호 · 등록번호)를 담는 칸이 없다. 개인정보이고,
    제출할 때는 어차피 원본 증빙 파일을 쓴다. 앱이 이걸 가진 이유는
    공고의 자격 경고 옆에 "내가 가진 것" 을 보여주고 만료를 미리 말하기 위해서다.
    """

    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)

    # language(어학) · job(직무 자격)
    category = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)

    # "900" · "IH" · "95" 처럼 시험마다 모양이 달라 문자열로 둔다.
    score = Column(String, default="", server_default="", nullable=False)
    detail = Column(String, default="", server_default="", nullable=False)
    issuer = Column(String, default="", server_default="", nullable=False)

    # held(보유) · planned(준비 중)
    status = Column(String, default="held", server_default="held", nullable=False)

    acquired_on = Column(Date, nullable=True)
    expires_on = Column(Date, nullable=True)
    note = Column(Text, default="", server_default="", nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)

    # 화면 가운데 놓일 이름. 비어 있으면 이름 없이 인사한다.
    name = Column(String, default="", nullable=False)

    # 하루 중 커리어에 쓸 수 있는 시간대. 자정 기준 분.
    # 09:00~22:00 이 기본값이다.
    day_start_minute = Column(
        Integer, default=540, server_default="540", nullable=False
    )
    day_end_minute = Column(
        Integer, default=1320, server_default="1320", nullable=False
    )

    # 하루 상한. "빈 시간 = 공부할 시간" 이 아니기 때문에 필요하다.
    # 9시간이 비어도 9시간 공부하지 않는다.
    daily_cap_minutes = Column(
        Integer, default=180, server_default="180", nullable=False
    )

    # 내 GitHub · 블로그. Evidence 화면 머리에 "보러 가기" 로 붙는다.
    github_url = Column(String, default="", server_default="", nullable=False)
    blog_url = Column(String, default="", server_default="", nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --------------------------------
# Calendar
#
# 학교 시간표를 가져오지 않는다. 직접 넣는다.
#
# 반복(수업·알바)과 일회성(면접·약속)을 한 테이블에 둔다.
# 화면에서 둘을 나란히 봐야 "오늘 실제로 몇 분 비었나" 가 나온다.
#
# 시각은 자정 기준 분으로 저장한다. 문자열 시간을 파싱하는 대신
# 빼기만 하면 되고, 겹침 판정도 정수 비교로 끝난다.
# --------------------------------

class CalendarBlock(Base):
    __tablename__ = "calendar_blocks"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)

    # class · work · personal · fixed
    kind = Column(String, default="class", nullable=False, index=True)

    # 매주 반복이면 weekday(0=월 ~ 6=일), 하루짜리면 date.
    # 둘 중 정확히 하나만 채운다 — 스키마에서 검증한다.
    weekday = Column(Integer, nullable=True, index=True)
    date = Column(Date, nullable=True, index=True)

    start_minute = Column(Integer, nullable=False)
    end_minute = Column(Integer, nullable=False)

    # 종일 일정과 마감은 시간을 먹지 않는다. 시각은 00:00–24:00 로 둔다.
    all_day = Column(Boolean, default=False, server_default="0", nullable=False)

    note = Column(Text, default="", server_default="", nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --------------------------------
# Project <-> Skill 중간 테이블
# --------------------------------

project_skills = Table(
    "project_skills",
    Base.metadata,
    Column(
        "project_id",
        ForeignKey("projects.id"),
        primary_key=True
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True
    )
)


# --------------------------------
# Job <-> Skill 중간 테이블
# --------------------------------

job_skills = Table(
    "job_skills",
    Base.metadata,
    Column(
        "job_id",
        ForeignKey("jobs.id"),
        primary_key=True
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True
    )
)


# --------------------------------
# Mission 021 association tables
# --------------------------------

# 경로 하나가 여러 스킬을 키운다. Tave 논문 스터디는 PyTorch 와 Computer Vision 을 같이 키운다.
# 대표 스킬(learning_paths.skill_id)은 남겨 둔다 — 화면이 "이 경로의 스킬" 한 줄을 쓸 때 필요하다.
learning_path_skills = Table(
    "learning_path_skills",
    Base.metadata,
    Column(
        "learning_path_id",
        ForeignKey("learning_paths.id"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True,
    ),
)


learning_step_resources = Table(
    "learning_step_resources",
    Base.metadata,
    Column(
        "learning_step_id",
        ForeignKey("learning_steps.id"),
        primary_key=True,
    ),
    Column(
        "learning_resource_id",
        ForeignKey("learning_resources.id"),
        primary_key=True,
    ),
)


target_career_skills = Table(
    "target_career_skills",
    Base.metadata,
    Column(
        "target_career_id",
        ForeignKey("target_careers.id"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True,
    ),
)


opportunity_skills = Table(
    "opportunity_skills",
    Base.metadata,
    Column(
        "opportunity_id",
        ForeignKey("opportunities.id"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True,
    ),
)


experience_skills = Table(
    "experience_skills",
    Base.metadata,
    Column(
        "experience_id",
        ForeignKey("experiences.id"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id"),
        primary_key=True,
    ),
)


# --------------------------------
# Target Career (Phase 1)
#
# 모든 우선순위 계산의 기준점.
# 이게 없으면 "무엇이 중요한가" 를 전체 공고 기준으로밖에 못 정한다.
# --------------------------------

class TargetCareer(Base):
    __tablename__ = "target_careers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")

    # 공고 제목·설명에서 이 직무를 알아보기 위한 단서.
    # 쉼표로 구분한 자유 문자열.
    keywords = Column(Text, default="")

    target_date = Column(Date, nullable=True)

    # 활성은 한 번에 하나. 바꿔도 이전 목표를 지우지 않는다.
    is_active = Column(Boolean, default=False, nullable=False, index=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    skills = relationship(
        "Skill",
        secondary=target_career_skills,
        back_populates="target_careers",
    )


# --------------------------------
# Skill
# --------------------------------

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )
    category = Column(String, nullable=False)
    level = Column(Integer, default=0)
    status = Column(String, default="not_started")

    # 같은 스킬을 부르는 다른 이름들. 쉼표로 구분한다.
    #
    # 추출기는 이름을 글자 그대로 찾는다. 그래서 한글 공고에
    # "Machine Learning" 은 안 걸리고, 영문 공고에 "머신러닝" 은
    # 안 걸린다. 한국 공고를 다루려면 이게 없으면 매번 터진다.
    aliases = Column(String, default="", server_default="", nullable=False)

    level_events = relationship(
        "SkillLevelEvent",
        back_populates="skill",
        order_by="SkillLevelEvent.changed_at",
        cascade="all, delete-orphan",
    )

    projects = relationship(
        "Project",
        secondary=project_skills,
        back_populates="skills"
    )

    jobs = relationship(
        "Job",
        secondary=job_skills,
        back_populates="skills"
    )

    resources = relationship(
        "LearningResource",
        back_populates="skill"
    )

    learning_paths = relationship(
        "LearningPath",
        back_populates="skill"
    )

    # 여러 스킬을 키우는 경로들 (learning_path_skills).
    linked_paths = relationship(
        "LearningPath",
        secondary=learning_path_skills,
        back_populates="skills",
    )

    @property
    def growing_paths(self) -> list:
        """이 스킬을 키우는 경로 전부.

        대표 스킬로만 이어진 옛 경로와 여러 스킬 연결을 함께 본다. 한쪽만 보면
        "Tave 는 PyTorch 도 키운다" 를 넣어도 학습 진행이 0 으로 남는다.
        """
        paths = {path.id: path for path in self.linked_paths}

        for path in self.learning_paths:
            paths.setdefault(path.id, path)

        return list(paths.values())

    experiences = relationship(
        "Experience",
        secondary=experience_skills,
        back_populates="skills"
    )

    opportunities = relationship(
        "Opportunity",
        secondary=opportunity_skills,
        back_populates="skills"
    )

    market_snapshots = relationship(
        "MarketSnapshot",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    target_careers = relationship(
        "TargetCareer",
        secondary=target_career_skills,
        back_populates="skills"
    )




# --------------------------------
# Project
# --------------------------------

class SkillLevelEvent(Base):
    """레벨이 언제 얼마에서 얼마로 바뀌었는가.

    skills 테이블에는 시각이 없다. 그래서 "9월에 Machine Learning 이
    0에서 2가 되었다" 를 셀 수 없었고, 회고에 그 자리가 비어 있었다.

    현재 값만 들고 있으면 쌓인 것을 보여줄 수 없다. 변화를 남긴다.
    """

    __tablename__ = "skill_level_events"

    id = Column(Integer, primary_key=True, index=True)

    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False,
        index=True,
    )

    from_level = Column(Integer, nullable=False)
    to_level = Column(Integer, nullable=False)

    # 무엇 때문에 바뀌었는가. 지금은 사람이 직접 고치는 것뿐이지만,
    # 나중에 증거로부터 자동으로 올릴 때 구분이 필요하다.
    source = Column(
        String, default="manual", server_default="manual", nullable=False
    )

    note = Column(String, default="", server_default="", nullable=False)

    changed_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    skill = relationship("Skill", back_populates="level_events")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String,
        unique=True,
        nullable=False
    )
    description = Column(Text, default="")
    status = Column(String, default="planned")
    career_related = Column(Boolean, default=True)
    estimated_hours = Column(Integer, default=0)
    progress_percent = Column(Integer, default=0)
    daily_minutes = Column(Integer, default=0)
    target_date = Column(String, default="")

    # Phase 4: 프로젝트가 증거가 되려면 보여줄 것이 있어야 한다.
    github_url = Column(String, default="", server_default="", nullable=False)
    demo_url = Column(String, default="", server_default="", nullable=False)
    results = Column(Text, default="", server_default="")

    skills = relationship(
        "Skill",
        secondary=project_skills,
        back_populates="projects"
    )


# --------------------------------
# Job
# --------------------------------

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company = Column(String, nullable=False)
    title = Column(String, nullable=False)
    role = Column(String, nullable=False)
    employment_type = Column(
        String,
        default="intern"
    )
    url = Column(String, default="")
    deadline = Column(String, default="")
    description = Column(Text, default="")
    status = Column(String, default="discovered")

    skills = relationship(
        "Skill",
        secondary=job_skills,
        back_populates="jobs"
    )

class LearningResource(Base):
    """내 학습 자료 한 건.

    Phase 2 부터 이것이 곧 My Learning Library 의 항목이다.
    별도 모델을 만들지 않은 이유는, 라이브러리 항목이 학습 단계에
    연결되면 그게 곧 "오늘의 자료" 이기 때문이다.
    둘을 나누면 "내 것 중에서 고른다" 는 제품 논지가 깨진다.
    """

    __tablename__ = "learning_resources"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String, nullable=False)

    # 내가 가진 종이책에는 URL 이 없다.
    url = Column(String, nullable=True)

    resource_type = Column(String, default="video")
    duration_minutes = Column(Integer, default=0)

    # owned(가지고 있음) · saved(저장해둠) · wishlist(사고 싶음)
    #
    # "내가 이미 가진 것" 과 "누가 추천한 것" 을 구분하지 못하면
    # 라이브러리에서 고른다는 개념이 성립하지 않는다.
    ownership = Column(
        String,
        default="saved",
        server_default="saved",
        nullable=False,
        index=True,
    )

    # 책이면 페이지 수, 영상이면 총 길이(분) 같은 전체 분량.
    total_units = Column(Integer, nullable=True)
    unit_label = Column(String, default="", server_default="", nullable=False)

    # Mission 022: 지금 필요한 자료를 먼저 보여주기 위한 중요도.
    # primary / supplementary / deep_dive
    importance = Column(
        String,
        default="primary",
        server_default="primary",
        nullable=False,
    )

    status = Column(String, default="saved")

    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False
    )

    skill = relationship(
        "Skill",
        back_populates="resources"
    )

    learning_steps = relationship(
        "LearningStep",
        secondary=learning_step_resources,
        back_populates="resources"
    )

    segments = relationship(
        "LearningResourceSegment",
        back_populates="resource",
        order_by="LearningResourceSegment.position",
        cascade="all, delete-orphan",
    )


class LearningResourceSegment(Base):
    """자료 안의 한 조각. 오늘 실제로 소비하는 단위.

    "책 한 권을 읽으세요" 가 아니라 "3장을 15분 읽으세요" 여야 한다.
    이게 없으면 Career OS 의 핵심 문장이 성립하지 않는다.
    """

    __tablename__ = "learning_resource_segments"
    __table_args__ = (
        UniqueConstraint(
            "learning_resource_id",
            "position",
            name="uq_segment_resource_position",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    learning_resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id"),
        nullable=False,
        index=True,
    )

    position = Column(Integer, nullable=False)
    label = Column(String, nullable=False)

    # 페이지 범위 또는 타임스탬프(초). 단위는 자료의 unit_label 을 따른다.
    start_ref = Column(Integer, nullable=True)
    end_ref = Column(Integer, nullable=True)

    estimated_minutes = Column(Integer, default=0, nullable=False)

    status = Column(String, default="not_started", nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    resource = relationship("LearningResource", back_populates="segments")


# --------------------------------
# Learning paths
# --------------------------------

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    status = Column(String, default="not_started", nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    target_date = Column(Date, nullable=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    skill = relationship("Skill", back_populates="learning_paths")
    # 이 경로가 키우는 스킬 전부 (대표 스킬 포함). 학습 진행이 이 스킬들의 증거가 된다.
    skills = relationship(
        "Skill",
        secondary=learning_path_skills,
        back_populates="linked_paths",
    )
    steps = relationship(
        "LearningStep",
        back_populates="learning_path",
        order_by="LearningStep.position",
        cascade="all, delete-orphan",
    )


class LearningStep(Base):
    __tablename__ = "learning_steps"
    __table_args__ = (
        UniqueConstraint(
            "learning_path_id",
            "position",
            name="uq_learning_step_path_position",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    learning_path_id = Column(
        Integer,
        ForeignKey("learning_paths.id"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    position = Column(Integer, nullable=False)
    status = Column(String, default="not_started", nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    estimated_minutes = Column(Integer, default=0, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # 이 단계를 끝내야 하는 날 (예: Tave 발표일). 있으면 우선순위 1위 스킬이
    # 아니어도 오늘 계획에 오른다.
    due_date = Column(Date, nullable=True)

    learning_path = relationship("LearningPath", back_populates="steps")
    resources = relationship(
        "LearningResource",
        secondary=learning_step_resources,
        back_populates="learning_steps",
    )
    checklist = relationship(
        "LearningChecklistItem",
        back_populates="learning_step",
        order_by="LearningChecklistItem.position",
        cascade="all, delete-orphan",
    )
    outputs = relationship(
        "LearningStepOutput",
        back_populates="learning_step",
        order_by="LearningStepOutput.id",
        cascade="all, delete-orphan",
    )


class LearningChecklistItem(Base):
    """학습 단계 안에서 실제로 체크하는 한 줄.

    단계("2주차 — 인기 기반 추천")는 하루에 끝나지 않는다. 오늘 하는 일은
    그 아래 항목("movie_stats 생성") 단위라서 여기에 둔다. 전에는 단계 설명의
    줄을 목표로 보여주고 체크는 브라우저에만 남겼다.

    kind
      task  체크하는 항목. 진행률의 분모
      note  묶음 설명 ("완성 코드 대신 받지 않는 구간"). 세지 않는다
      link  자료 링크. 세지 않는다. http(s) 만
    """

    __tablename__ = "learning_checklist_items"

    id = Column(Integer, primary_key=True, index=True)
    learning_step_id = Column(
        Integer,
        ForeignKey("learning_steps.id"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False)
    section = Column(String, default="", nullable=False)
    kind = Column(String, default="task", nullable=False)
    text = Column(Text, nullable=False)
    url = Column(String, default="", nullable=False)
    done = Column(Boolean, default=False, nullable=False)
    done_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    learning_step = relationship("LearningStep", back_populates="checklist")


class LearningStepOutput(Base):
    """이 단계에서 **내가 만든 것** — 요약 노트 · 발표 자료 · 코드.

    체크 항목은 "했다" 를 세고, 이건 "남은 것" 을 가리킨다. 공부한 흔적이
    앱 밖에만 있으면 나중에 경험으로 꺼낼 수 없다.

    파일은 저장하지 않는다. 서버에 디스크가 없고, 파일을 받기 시작하면
    백업 · 용량 · 공개 범위가 전부 딸려온다. 주소(노션 · 깃허브 · 드라이브)만 둔다.
    """

    __tablename__ = "learning_step_outputs"

    id = Column(Integer, primary_key=True, index=True)
    learning_step_id = Column(
        Integer,
        ForeignKey("learning_steps.id"),
        nullable=False,
        index=True,
    )
    title = Column(String, nullable=False)
    url = Column(String, default="", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    learning_step = relationship("LearningStep", back_populates="outputs")


# --------------------------------
# Source-independent opportunities
# --------------------------------

class DismissedPosting(Base):
    """사람이 휴지통으로 지운 수집 공고의 번호.

    지운 공고는 목록 어디에도 남기지 않는다. 그런데 번호까지 잊으면 다음 날 아침 수집이
    같은 공고를 다시 들인다 — 지워도 돌아오는 휴지통이 된다. 그래서 출처와 번호만 남긴다.
    제목 · 회사 · 설명은 남기지 않는다.
    """

    __tablename__ = "dismissed_postings"
    __table_args__ = (
        UniqueConstraint("source", "source_external_id", name="uq_dismissed_posting"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    source_external_id = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Opportunity(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_external_id",
            name="uq_opportunity_source_external_id",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    opportunity_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    organization = Column(String, default="", nullable=False)
    role = Column(String, default="", nullable=False)
    description = Column(Text, default="")
    source = Column(String, nullable=False, index=True)
    source_external_id = Column(String, nullable=True)
    source_url = Column(String, default="", nullable=False)
    location = Column(String, default="", nullable=False)
    employment_type = Column(String, default="", nullable=False)
    deadline = Column(DateTime, nullable=True)
    status = Column(String, default="discovered", nullable=False)
    raw_payload = Column(Text, default="")
    legacy_job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=True,
        unique=True,
    )
    collected_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Phase 3: 이걸 하는 데 대략 몇 시간이 드는가.
    # 마감까지 남은 날짜만으로는 "할 수 있는가" 를 판단할 수 없다.
    # 40시간짜리를 5일 안에 끝내는 것과 4시간짜리를 5일 안에 끝내는 것은 다르다.
    estimated_hours = Column(Integer, nullable=True)

    # 직무가 맞지 않아 자동으로 뺀 이유 (services/job_fit.py). 비어 있으면 뺀 게 아니다.
    # 뺀 기회는 보관함으로 가고, 스킬 수요에 세지 않는다.
    filtered_reason = Column(String, default="", server_default="", nullable=False)
    # 사람이 "그래도 검토" 로 되살렸다. 다시 자동으로 빼지 않는다.
    keep_anyway = Column(Boolean, default=False, server_default="0", nullable=False)

    # Mission 023: 매칭 점수. 계산은 services/opportunity.py 가 한다.
    match_score = Column(Float, nullable=True)
    match_recommendation = Column(String, nullable=True)
    scored_at = Column(DateTime, nullable=True)

    legacy_job = relationship("Job")
    applications = relationship("Application", back_populates="opportunity")
    skills = relationship(
        "Skill",
        secondary=opportunity_skills,
        back_populates="opportunities",
    )


# --------------------------------
# Today Plan (Phase 1)
#
# 계획을 저장하는 이유는 두 가지다.
#   1. 완료 체크를 하려면 어딘가 기록이 있어야 한다
#   2. 미완료 이월은 어제 무엇이 남았는지 알아야 가능하다
# 매번 새로 계산해서 버리면 둘 다 못 한다.
# --------------------------------

class DailyPlanTask(Base):
    __tablename__ = "daily_plan_tasks"

    id = Column(Integer, primary_key=True, index=True)
    plan_date = Column(Date, nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)

    # learning_step · project · resource · application
    task_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    minutes = Column(Integer, default=0, nullable=False)

    # 왜 이게 오늘 계획에 있는지. 설명할 수 없으면 넣지 않는다.
    reason = Column(Text, default="")

    # planned · done · skipped
    status = Column(String, default="planned", nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)

    # 이월된 경우 원래 날짜
    carried_from = Column(Date, nullable=True)

    # 이 계획을 만들 때 쓴 설정.
    # 저장하지 않으면 나중에 "몇 분 남았는지" 를 조회 파라미터로
    # 다시 받아야 하고, 실제와 다른 숫자가 화면에 나온다.
    plan_available_minutes = Column(Integer, nullable=True)
    plan_intensity = Column(String, nullable=True)

    # 이 계획을 세울 때 우선순위 1위였던 스킬. 지금 1위와 다르면 계획이 낡은 것이다 —
    # 세운 뒤 공고가 들어와 1위가 바뀌었는데, 할 일의 이유는 옛 1위를 말하고 있었다.
    plan_focus_skill = Column(String, nullable=True)

    learning_step_id = Column(
        Integer, ForeignKey("learning_steps.id"), nullable=True
    )
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    learning_resource_id = Column(
        Integer, ForeignKey("learning_resources.id"), nullable=True
    )
    application_id = Column(
        Integer, ForeignKey("applications.id"), nullable=True
    )

    # 아직 지원서를 만들지 않은 기회. 마감이 임박했는데 지원할지
    # 아직 안 정한 것을 오늘 계획에 올리려면 이 연결이 필요하다.
    opportunity_id = Column(
        Integer, ForeignKey("opportunities.id"), nullable=True
    )

    # 매일 하는 일(코테 등). 이월하지 않는다.
    routine_id = Column(Integer, ForeignKey("routines.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    learning_step = relationship("LearningStep")
    project = relationship("Project")
    learning_resource = relationship("LearningResource")
    application = relationship("Application")
    opportunity = relationship("Opportunity")
    routine = relationship("Routine")


# --------------------------------
# 루틴 — 매일(정한 요일마다) 하는 일
# --------------------------------

class Routine(Base):
    """코테 30분처럼 정해진 요일마다 하는 일.

    오늘 계획이 시간을 **먼저 떼어 둔다.** 강도의 칸 수는 쓰지 않는다 —
    코테가 하루 세 칸 중 한 칸을 차지하면 학습이 밀려난다.
    이월하지 않는다. 어제 못 푼 3문제를 오늘 6문제로 만들지 않는다.

    weekdays       "0123456" (월=0, 캘린더와 같다)
    target_count   하루 목표 개수 ("3"). 없으면 시간만 채우는 루틴
    unit_label     "문제"
    learning_path  coding rehab 처럼 경로가 있으면 그 경로의 다음 단계를 연다
    """

    __tablename__ = "routines"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    minutes = Column(Integer, default=30, nullable=False)
    weekdays = Column(String, default="0123456", nullable=False)
    target_count = Column(Integer, nullable=True)
    unit_label = Column(String, default="", nullable=False)
    learning_path_id = Column(
        Integer, ForeignKey("learning_paths.id"), nullable=True
    )
    active = Column(Boolean, default=True, nullable=False)

    # 시작하는 곳 (예: 프로그래머스 문제 목록). 오늘 계획에서 "시작" 을 누르면 여기로 연다.
    # 없으면 학습 화면으로 보내지 않고, 적어 둔 메모로 시작하는 방법을 보여준다.
    link_url = Column(String, default="", server_default="", nullable=False)
    note = Column(Text, default="", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    learning_path = relationship("LearningPath")
    logs = relationship(
        "RoutineLog",
        back_populates="routine",
        order_by="RoutineLog.log_date",
        cascade="all, delete-orphan",
    )


class MonthlyReflection(Base):
    """한 달 스스로 평가. 앱이 계산하지 않는다 — 사람이 적은 그대로 둔다.

    회고 화면의 숫자는 전부 기록에서 센 것이다. 그런데 "그래서 이번 달이 어땠나" 는
    기록이 말해주지 않는다. 그 판단을 한 달에 한 번 남긴다.
    """

    __tablename__ = "monthly_reflections"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_reflection_month"),
    )

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    rating = Column(Integer, nullable=True)          # 1~5, 비워 둘 수 있다
    went_well = Column(Text, default="", nullable=False)
    to_improve = Column(Text, default="", nullable=False)
    next_focus = Column(Text, default="", nullable=False)
    # 이번 달에 **안 하기로** 한 것. 할 게 많다는 느낌은 대개 버린 것을 안 적어서 생긴다.
    # 한 일과 못 한 일만 세면, 덜어낸 판단은 아무 데도 안 남는다.
    dropped = Column(Text, default="", server_default="", nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RoutineLog(Base):
    """루틴을 한 날. 하루에 한 줄 — 몇 개 했는지까지."""

    __tablename__ = "routine_logs"
    __table_args__ = (
        UniqueConstraint("routine_id", "log_date", name="uq_routine_log_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    routine_id = Column(
        Integer, ForeignKey("routines.id"), nullable=False, index=True
    )
    log_date = Column(Date, nullable=False, index=True)
    count = Column(Integer, nullable=True)
    minutes = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    routine = relationship("Routine", back_populates="logs")


# --------------------------------
# Market snapshots (Mission 023)
#
# 추세(상승/하락)를 계산하려면 시점별 값이 있어야 한다.
# 수집이 끝날 때마다 스킬별 수요를 한 줄씩 남긴다.
# --------------------------------

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False,
        index=True,
    )
    opportunity_count = Column(Integer, default=0, nullable=False)
    total_opportunities = Column(Integer, default=0, nullable=False)
    percentage = Column(Integer, default=0, nullable=False)
    captured_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    skill = relationship("Skill", back_populates="market_snapshots")


# --------------------------------
# Experience Bank and portfolio
# --------------------------------

class Experience(Base):
    __tablename__ = "experiences"

    id = Column(Integer, primary_key=True, index=True)
    experience_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    organization = Column(String, default="", nullable=False)
    short_description = Column(Text, default="")
    problem = Column(Text, default="")
    role = Column(Text, default="")
    actions = Column(Text, default="")
    results = Column(Text, default="")
    technologies = Column(Text, default="")
    metrics = Column(Text, default="")
    tags = Column(Text, default="")
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    github_url = Column(String, default="", nullable=False)
    # 이 경험을 풀어쓴 글 (Velog 등).
    blog_url = Column(String, default="", server_default="", nullable=False)
    demo_url = Column(String, default="", nullable=False)
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=True,
        unique=True,
    )
    # 이 경험이 어느 학습 단계에서 나왔는가. 같은 단계를 두 번 보내지 않는다.
    learning_step_id = Column(
        Integer,
        ForeignKey("learning_steps.id"),
        nullable=True,
        unique=True,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project")
    skills = relationship(
        "Skill",
        secondary=experience_skills,
        back_populates="experiences",
    )
    portfolio_entries = relationship(
        "PortfolioEntry",
        back_populates="experience",
    )
    application_matches = relationship(
        "ApplicationExperienceMatch",
        back_populates="experience",
    )


class PortfolioEntry(Base):
    __tablename__ = "portfolio_entries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    short_description = Column(Text, default="")
    problem = Column(Text, default="")
    role = Column(Text, default="")
    actions = Column(Text, default="")
    results = Column(Text, default="")
    technologies = Column(Text, default="")
    github_url = Column(String, default="", nullable=False)
    demo_url = Column(String, default="", nullable=False)

    # Phase 4: 이력서에 그대로 넣을 수 있는 한 줄.
    # 저장된 내용에서만 만든다. 없는 성과를 지어내지 않는다.
    resume_bullet = Column(Text, default="", server_default="")

    status = Column(String, default="draft", nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    experience_id = Column(
        Integer,
        ForeignKey("experiences.id"),
        nullable=True,
        index=True,
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    experience = relationship("Experience", back_populates="portfolio_entries")
    project = relationship("Project")


# --------------------------------
# Applications and cover letters
# --------------------------------

class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(
        Integer,
        ForeignKey("opportunities.id"),
        nullable=True,
        index=True,
    )
    legacy_job_id = Column(
        Integer,
        ForeignKey("jobs.id"),
        nullable=True,
        index=True,
    )
    status = Column(String, default="interested", nullable=False, index=True)
    deadline = Column(DateTime, nullable=True)
    job_analysis = Column(Text, default="")
    notes = Column(Text, default="")
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    opportunity = relationship("Opportunity", back_populates="applications")
    legacy_job = relationship("Job")
    experience_matches = relationship(
        "ApplicationExperienceMatch",
        back_populates="application",
        cascade="all, delete-orphan",
    )
    cover_letter_questions = relationship(
        "CoverLetterQuestion",
        back_populates="application",
        cascade="all, delete-orphan",
    )


class ApplicationExperienceMatch(Base):
    __tablename__ = "application_experience_matches"

    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        primary_key=True,
    )
    experience_id = Column(
        Integer,
        ForeignKey("experiences.id"),
        primary_key=True,
    )
    match_score = Column(Float, nullable=True)
    match_notes = Column(Text, default="")

    application = relationship(
        "Application",
        back_populates="experience_matches",
    )
    experience = relationship(
        "Experience",
        back_populates="application_matches",
    )


class CoverLetterQuestion(Base):
    __tablename__ = "cover_letter_questions"
    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "position",
            name="uq_cover_letter_question_application_position",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(
        Integer,
        ForeignKey("applications.id"),
        nullable=False,
        index=True,
    )
    question = Column(Text, nullable=False)
    character_limit = Column(Integer, nullable=True)
    position = Column(Integer, default=0, nullable=False)

    application = relationship(
        "Application",
        back_populates="cover_letter_questions",
    )
    answers = relationship(
        "CoverLetterAnswer",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="CoverLetterAnswer.version",
    )


class CoverLetterAnswer(Base):
    __tablename__ = "cover_letter_answers"
    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "version",
            name="uq_cover_letter_answer_question_version",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer,
        ForeignKey("cover_letter_questions.id"),
        nullable=False,
        index=True,
    )
    draft = Column(Text, default="", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    question = relationship("CoverLetterQuestion", back_populates="answers")
