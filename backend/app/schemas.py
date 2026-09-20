from datetime import date, datetime

# CalendarBlock 의 필드 이름이 date 라서, 그 클래스 안에서는
# `date` 가 타입이 아니라 자기 필드를 가리킨다. 별칭으로 갈라둔다.
from datetime import date as DateValue
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


LearningStatus = Literal[
    "not_started",
    "in_progress",
    "completed",
    "review_needed",
]
OpportunityType = Literal["job", "competition", "external_activity", "job_event"]

# 자료 종류. Mission 022 이전에는 자유 문자열이었고 기본값이 "youtube" 였다.
ResourceType = Literal[
    "official_doc",
    "documentation",
    "book",
    "course",
    "video",
    "article",
    "paper",
    "practice",
    "problem",
    "dataset",
    "project_task",
]

# 자료 중요도. 사용자에게 자료를 쏟아붓지 않기 위한 장치.
ResourceImportance = Literal["primary", "supplementary", "deep_dive"]

# 내가 가진 것인지, 저장만 해둔 것인지, 아직 없는 것인지.
# 이 구분이 없으면 "내 라이브러리에서 고른다" 가 성립하지 않는다.
ResourceOwnership = Literal["owned", "saved", "wishlist"]
ApplicationStatus = Literal[
    "interested",
    "preparing",
    "ready",
    "applied",
    "document_pass",
    "interview",
    "rejected",
    "accepted",
    "withdrawn",
]


# --------------------
# Skill
# --------------------

class SkillCreate(BaseModel):
    name: str
    category: str
    level: int = 0
    status: str = "not_started"

    # 같은 스킬을 부르는 다른 이름. 쉼표로 구분.
    # "머신러닝, ML" 처럼 두면 한글 공고에서도 찾는다.
    aliases: str = ""


class SkillUpdate(BaseModel):
    """부분 수정. 준 것만 바꾼다.

    level 은 상한이 있다 — priority.MAX_SKILL_LEVEL 을 넘으면
    skill_gap 이 음수가 되어 점수가 뒤집힌다.
    """

    name: str | None = None
    category: str | None = None
    level: int | None = Field(default=None, ge=0, le=4)
    status: str | None = None
    aliases: str | None = None


class SkillLevelEventResponse(BaseModel):
    id: int
    skill_id: int
    from_level: int
    to_level: int
    source: str
    note: str
    changed_at: datetime

    class Config:
        from_attributes = True


class SkillResponse(SkillCreate):
    id: int

    class Config:
        from_attributes = True


# --------------------
# Project
# --------------------

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    status: str = "planned"
    career_related: bool = True

    estimated_hours: int = 0
    progress_percent: int = 0
    daily_minutes: int = 0
    target_date: str = ""

    # Phase 4: 증거가 되려면 보여줄 것이 있어야 한다
    github_url: str = ""
    demo_url: str = ""
    results: str = ""


class ProjectSkillRef(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class ProjectResponse(ProjectCreate):
    id: int

    # 프로젝트가 무엇으로 만들어졌는지가 곧 그 프로젝트가 증명하는 것이다.
    # 목록에서 이게 빠지면 화면이 기술 태그를 그릴 수 없다.
    skills: list[ProjectSkillRef] = []

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    career_related: bool | None = None
    estimated_hours: int | None = Field(default=None, ge=0)
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    daily_minutes: int | None = Field(default=None, ge=0)
    target_date: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    results: str | None = None

# --------------------
# Job
# --------------------

class JobCreate(BaseModel):
    company: str
    title: str
    role: str
    employment_type: str = "intern"
    url: str = ""
    deadline: str = ""
    description: str = ""
    status: str = "discovered"


class JobResponse(JobCreate):
    id: int

    class Config:
        from_attributes = True


# --------------------
# Learning Resource
# --------------------

class LearningResourceCreate(BaseModel):
    title: str
    # 내가 가진 종이책에는 URL 이 없다.
    url: str | None = None
    resource_type: ResourceType = "video"
    duration_minutes: int = Field(default=0, ge=0)
    importance: ResourceImportance = "primary"
    ownership: ResourceOwnership = "saved"
    total_units: int | None = Field(default=None, ge=0)
    unit_label: str = ""
    status: str = "saved"
    skill_id: int


class LearningResourceResponse(BaseModel):
    """응답에서는 종류/중요도를 str 로 둔다.

    Literal 로 두면 예전 데이터에 예상 밖의 값이 하나라도 있을 때
    조회가 500 으로 죽는다. 검증은 입력에서만 한다.
    """

    id: int
    title: str
    url: str | None = None
    resource_type: str
    duration_minutes: int
    importance: str
    ownership: str
    total_units: int | None = None
    unit_label: str = ""
    status: str
    skill_id: int

    class Config:
        from_attributes = True


class LearningResourceUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    resource_type: ResourceType | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    importance: ResourceImportance | None = None
    ownership: ResourceOwnership | None = None
    total_units: int | None = Field(default=None, ge=0)
    unit_label: str | None = None
    status: str | None = None


# --------------------
# Library Segment (Phase 2)
#
# "책 한 권" 이 아니라 "3장 15분" 이 오늘 소비하는 단위다.
# --------------------

class SegmentCreate(BaseModel):
    label: str
    position: int = Field(default=0, ge=0)
    start_ref: int | None = Field(default=None, ge=0)
    end_ref: int | None = Field(default=None, ge=0)
    estimated_minutes: int = Field(default=0, ge=0)
    status: LearningStatus = "not_started"


class SegmentResponse(SegmentCreate):
    id: int
    learning_resource_id: int
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class SegmentUpdate(BaseModel):
    label: str | None = None
    position: int | None = Field(default=None, ge=0)
    start_ref: int | None = Field(default=None, ge=0)
    end_ref: int | None = Field(default=None, ge=0)
    estimated_minutes: int | None = Field(default=None, ge=0)
    status: LearningStatus | None = None

# --------------------
# Agent
# --------------------

class AgentRequest(BaseModel):
    message: str


# --------------------
# Mission 021 foundation
# --------------------

class LearningPathCreate(BaseModel):
    title: str
    description: str = ""
    status: LearningStatus = "not_started"
    progress_percent: int = Field(default=0, ge=0, le=100)
    target_date: date | None = None
    # 대표 스킬. skill_ids 를 주면 그 첫 번째로 맞춘다.
    skill_id: int | None = None
    # 이 경로가 키우는 스킬 전부. 한 경로가 PyTorch 와 Computer Vision 을 같이 키울 수 있다.
    skill_ids: list[int] | None = Field(default=None, max_length=10)


class LearningPathResponse(LearningPathCreate):
    id: int
    skills: list[SkillResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LearningStepCreate(BaseModel):
    learning_path_id: int
    title: str
    description: str = ""
    position: int = Field(ge=0)
    status: LearningStatus = "not_started"
    progress_percent: int = Field(default=0, ge=0, le=100)
    estimated_minutes: int = Field(default=0, ge=0)
    completed_at: datetime | None = None
    due_date: date | None = None


class LearningStepResponse(LearningStepCreate):
    id: int

    class Config:
        from_attributes = True


class OpportunityCreate(BaseModel):
    opportunity_type: OpportunityType
    title: str
    organization: str = ""
    role: str = ""
    description: str = ""
    source: str
    source_external_id: str | None = None
    source_url: str = ""
    location: str = ""
    employment_type: str = ""
    deadline: datetime | None = None
    status: str = "discovered"
    raw_payload: str = ""
    legacy_job_id: int | None = None
    # 이걸 하는 데 대략 몇 시간이 드는가 (Phase 3)
    estimated_hours: int | None = Field(default=None, ge=0)


class OpportunityResponse(OpportunityCreate):
    id: int
    collected_at: datetime
    updated_at: datetime

    # 어떤 스킬을 요구하는지가 곧 수요 집계의 재료다.
    # 응답에서 빠지면 화면이 "무엇을 찾았는지" 를 보여줄 수 없다.
    skills: list[ProjectSkillRef] = []

    # Mission 023: 매칭 결과. 서버가 계산해서 채운다.
    match_score: float | None = None
    match_recommendation: str | None = None
    scored_at: datetime | None = None

    class Config:
        from_attributes = True


class ExperienceCreate(BaseModel):
    experience_type: str
    title: str
    organization: str = ""
    short_description: str = ""
    problem: str = ""
    role: str = ""
    actions: str = ""
    results: str = ""
    technologies: str = ""
    metrics: str = ""
    tags: str = ""
    start_date: date | None = None
    end_date: date | None = None
    github_url: str = ""
    blog_url: str = ""
    demo_url: str = ""
    project_id: int | None = None


class ExperienceResponse(ExperienceCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PortfolioEntryCreate(BaseModel):
    title: str
    short_description: str = ""
    problem: str = ""
    role: str = ""
    actions: str = ""
    results: str = ""
    technologies: str = ""
    github_url: str = ""
    demo_url: str = ""
    resume_bullet: str = ""
    status: str = "draft"
    display_order: int = Field(default=0, ge=0)
    experience_id: int | None = None
    project_id: int | None = None


class PortfolioEntryResponse(PortfolioEntryCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    opportunity_id: int | None = None
    legacy_job_id: int | None = None
    status: ApplicationStatus = "interested"
    deadline: datetime | None = None
    job_analysis: str = ""
    notes: str = ""
    applied_at: datetime | None = None

    @model_validator(mode="after")
    def require_target(self):
        if self.opportunity_id is None and self.legacy_job_id is None:
            raise ValueError(
                "opportunity_id or legacy_job_id is required"
            )
        return self


class ApplicationResponse(ApplicationCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationExperienceMatchCreate(BaseModel):
    application_id: int
    experience_id: int
    match_score: float | None = Field(default=None, ge=0, le=100)
    match_notes: str = ""


class ApplicationExperienceMatchResponse(ApplicationExperienceMatchCreate):

    class Config:
        from_attributes = True


class CoverLetterQuestionCreate(BaseModel):
    application_id: int
    question: str
    character_limit: int | None = Field(default=None, gt=0)
    position: int = Field(default=0, ge=0)


class CoverLetterQuestionResponse(CoverLetterQuestionCreate):
    id: int

    class Config:
        from_attributes = True


class CoverLetterAnswerCreate(BaseModel):
    question_id: int
    draft: str = ""
    version: int = Field(default=1, ge=1)
    is_current: bool = True


class CoverLetterAnswerResponse(CoverLetterAnswerCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --------------------
# Mission 021 부분 수정(PATCH) 스키마
#
# 전부 Optional 이고, 라우터는 exclude_unset 으로 실제로 보낸 필드만 반영한다.
# --------------------

class LearningPathUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: LearningStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    target_date: date | None = None
    skill_id: int | None = None
    # 빈 목록을 주면 연결을 모두 끊는다.
    skill_ids: list[int] | None = Field(default=None, max_length=10)


class LearningStepUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    position: int | None = Field(default=None, ge=0)
    status: LearningStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    estimated_minutes: int | None = Field(default=None, ge=0)
    completed_at: datetime | None = None
    due_date: date | None = None


# --------------------------------
# 학습 단계 체크리스트
#
# 링크는 http(s) 만 받는다. 저장된 링크는 화면에서 눌리므로
# javascript: 같은 주소가 들어오면 안 된다.
# --------------------------------

ChecklistKind = Literal["task", "note", "link"]
SAFE_URL_PATTERN = r"^https?://\S+$"


class PostingUrlRequest(BaseModel):
    """공고 주소 한 건. 앱이 목록을 훑지 않는다 — 사람이 고른 주소만."""

    url: str = Field(pattern=r"^https?://\S+$", max_length=2000)


class ChecklistParseRequest(BaseModel):
    text: str = Field(max_length=500_000)


class ChecklistEntry(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class ChecklistSection(BaseModel):
    title: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=300)
    items: list[ChecklistEntry] = Field(default_factory=list, max_length=200)


class ChecklistLink(BaseModel):
    text: str = Field(default="", max_length=300)
    url: str = Field(pattern=SAFE_URL_PATTERN, max_length=2000)


class ChecklistImport(BaseModel):
    sections: list[ChecklistSection] = Field(max_length=50)
    links: list[ChecklistLink] = Field(default_factory=list, max_length=30)
    replace: bool = False


class ChecklistStepCreate(BaseModel):
    title: str = Field(max_length=200)
    estimated_minutes: int = Field(default=0, ge=0)
    due_date: date | None = None
    sections: list[ChecklistSection] = Field(max_length=50)
    links: list[ChecklistLink] = Field(default_factory=list, max_length=30)


class ChecklistItemCreate(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    section: str = Field(default="", max_length=120)
    kind: ChecklistKind = "task"
    url: str = Field(default="", pattern=r"^(https?://\S+)?$", max_length=2000)


class StepOutputCreate(BaseModel):
    """단계에서 내가 만든 것. 파일은 안 받는다 — 열 수 있는 주소만."""

    title: str = Field(min_length=1, max_length=200)
    url: str = Field(pattern=r"^https?://\S+$", max_length=2000)


class ChecklistItemUpdate(BaseModel):
    done: bool | None = None
    text: str | None = Field(default=None, min_length=1, max_length=300)


# --------------------------------
# 한 달 스스로 평가
# --------------------------------

class ReflectionUpdate(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    went_well: str = Field(default="", max_length=2000)
    to_improve: str = Field(default="", max_length=2000)
    next_focus: str = Field(default="", max_length=2000)
    dropped: str = Field(default="", max_length=2000)


# --------------------------------
# 루틴
# --------------------------------

class RoutineCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    minutes: int = Field(default=30, ge=5, le=600)
    # 월=0 … 일=6. 범위 검사는 서비스가 한국어로 알려준다.
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], max_length=7)
    target_count: int | None = Field(default=None, ge=1, le=100)
    unit_label: str = Field(default="", max_length=20)
    learning_path_id: int | None = None
    # 시작하는 곳. http(s) 만 — 화면에서 눌리는 주소다.
    link_url: str = Field(default="", pattern=r"^(https?://\S+)?$", max_length=500)
    note: str = Field(default="", max_length=500)


class RoutineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    minutes: int | None = Field(default=None, ge=5, le=600)
    weekdays: list[int] | None = Field(default=None, max_length=7)
    target_count: int | None = Field(default=None, ge=1, le=100)
    unit_label: str | None = Field(default=None, max_length=20)
    learning_path_id: int | None = None
    active: bool | None = None
    link_url: str | None = Field(default=None, pattern=r"^(https?://\S+)?$", max_length=500)
    note: str | None = Field(default=None, max_length=500)


class RoutineLogUpdate(BaseModel):
    done: bool = True
    count: int | None = Field(default=None, ge=0, le=100)


class TaskCompleteRequest(BaseModel):
    # 루틴이면 실제로 한 개수 (예: 코테 2문제). 비우면 목표만큼 한 것으로 본다.
    count: int | None = Field(default=None, ge=0, le=100)


# --------------------------------
# 자격증 · 어학
#
# 번호 칸이 없다 — 자격번호 · 수험번호는 앱에 담지 않는다.
# 모르는 칸(예: number)을 보내도 저장되지 않는다.
# --------------------------------

CertificateCategory = Literal["language", "job"]
CertificateStatus = Literal["held", "planned"]


class CertificateCreate(BaseModel):
    category: CertificateCategory
    name: str = Field(min_length=1, max_length=80)
    score: str = Field(default="", max_length=40)
    detail: str = Field(default="", max_length=120)
    issuer: str = Field(default="", max_length=80)
    status: CertificateStatus = "held"
    acquired_on: DateValue | None = None
    expires_on: DateValue | None = None
    note: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def check_dates(self):
        if self.acquired_on and self.expires_on and self.expires_on < self.acquired_on:
            raise ValueError("만료일이 취득일보다 빠를 수 없습니다")
        return self


class CertificateUpdate(BaseModel):
    category: CertificateCategory | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)
    score: str | None = Field(default=None, max_length=40)
    detail: str | None = Field(default=None, max_length=120)
    issuer: str | None = Field(default=None, max_length=80)
    status: CertificateStatus | None = None
    acquired_on: DateValue | None = None
    expires_on: DateValue | None = None
    note: str | None = Field(default=None, max_length=500)


class PostingParseRequest(BaseModel):
    """붙여넣은 공고 글. 여기서는 링크를 열지 않는다 — 주소로 가져오기는 /fetch-url."""

    text: str = Field(min_length=1, max_length=50000)
    url: str = ""


class OpportunityUpdate(BaseModel):
    opportunity_type: OpportunityType | None = None
    title: str | None = None
    organization: str | None = None
    role: str | None = None
    description: str | None = None
    source_url: str | None = None
    location: str | None = None
    employment_type: str | None = None
    deadline: datetime | None = None
    status: str | None = None
    estimated_hours: int | None = Field(default=None, ge=0)


class ExperienceUpdate(BaseModel):
    experience_type: str | None = None
    title: str | None = None
    organization: str | None = None
    short_description: str | None = None
    problem: str | None = None
    role: str | None = None
    actions: str | None = None
    results: str | None = None
    technologies: str | None = None
    metrics: str | None = None
    tags: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    github_url: str | None = None
    blog_url: str | None = None
    demo_url: str | None = None
    project_id: int | None = None


class PortfolioEntryUpdate(BaseModel):
    title: str | None = None
    short_description: str | None = None
    problem: str | None = None
    role: str | None = None
    actions: str | None = None
    results: str | None = None
    technologies: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    resume_bullet: str | None = None
    status: str | None = None
    display_order: int | None = Field(default=None, ge=0)
    experience_id: int | None = None
    project_id: int | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    deadline: datetime | None = None
    job_analysis: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class CoverLetterQuestionUpdate(BaseModel):
    question: str | None = None
    character_limit: int | None = Field(default=None, gt=0)
    position: int | None = Field(default=None, ge=0)


class CoverLetterAnswerUpdate(BaseModel):
    draft: str | None = None
    is_current: bool | None = None


# --------------------
# Target Career (Phase 1)
# --------------------

class TargetCareerCreate(BaseModel):
    title: str
    description: str = ""
    keywords: str = ""
    target_date: date | None = None
    is_active: bool = False


class TargetCareerResponse(TargetCareerCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetCareerUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    keywords: str | None = None
    target_date: date | None = None


# --------------------------------
# Profile
#
# 1인용이라 사용자 목록이 없다. 이름만 받는다.
# --------------------------------

class ProfileUpdate(BaseModel):
    """보낸 칸만 바꾼다.

    전에는 name 하나뿐이라, 링크만 보내면 이름이 빈칸으로 지워졌을
    것이다. 라우터가 exclude_unset 으로 받는다.
    """

    name: str | None = Field(default=None, max_length=60)
    github_url: str | None = Field(default=None, max_length=300)
    blog_url: str | None = Field(default=None, max_length=300)

    @field_validator("github_url", "blog_url")
    @classmethod
    def only_web_links(cls, value):
        # 화면이 이 값을 href 에 넣는다. javascript: 등은 받지 않는다.
        if value is None:
            return value

        value = value.strip()

        if value and not value.startswith(("https://", "http://")):
            raise ValueError("http:// 또는 https:// 로 시작하는 주소만 받습니다")

        return value


# --------------------------------
# Calendar (Phase 5.6)
#
# 학교 시간표를 가져오지 않는다. 직접 넣는다.
# 시각은 자정 기준 분이다 — 09:30 은 570.
# --------------------------------

# deadline 은 시간을 먹지 않는다 — 그날까지의 선이다.
CalendarKind = Literal["class", "work", "personal", "fixed", "deadline"]


class CalendarBlockCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    kind: CalendarKind = "class"

    # 매주 반복이면 weekday, 하루짜리면 date. 정확히 하나만.
    weekday: int | None = Field(default=None, ge=0, le=6)
    date: DateValue | None = None

    # 종일이면 시각을 비워도 된다. 마감도 시각 없이 넣으면 종일이 된다.
    start_minute: int | None = Field(default=None, ge=0, le=1439)
    end_minute: int | None = Field(default=None, ge=1, le=1440)
    all_day: bool = False

    note: str = ""

    @model_validator(mode="after")
    def check(self):
        if (self.weekday is None) == (self.date is None):
            raise ValueError(
                "weekday(매주 반복) 와 date(하루짜리) 중 "
                "정확히 하나만 지정해야 합니다"
            )

        # 매주 돌아오는 마감은 없다. 매주 종일 막힌 요일이면 활동
        # 시간대를 줄이는 게 맞다.
        if (self.all_day or self.kind == "deadline") and self.date is None:
            raise ValueError("마감과 종일 일정은 날짜 하나에만 걸 수 있습니다")

        if self.kind == "deadline" and self.start_minute is None:
            self.all_day = True

        if self.all_day:
            self.start_minute = 0
            self.end_minute = 1440
            return self

        if self.start_minute is None or self.end_minute is None:
            raise ValueError("시작과 끝 시각이 필요합니다")

        if self.end_minute <= self.start_minute:
            raise ValueError("끝나는 시각이 시작보다 뒤여야 합니다")

        return self


class CalendarBlockUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    kind: CalendarKind | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    date: DateValue | None = None
    start_minute: int | None = Field(default=None, ge=0, le=1439)
    end_minute: int | None = Field(default=None, ge=1, le=1440)
    all_day: bool | None = None
    note: str | None = None


class CalendarSettingsUpdate(BaseModel):
    """활동 시간대와 하루 상한.

    상한이 있어야 하는 이유는 "빈 시간 = 공부할 시간" 이 아니기
    때문이다. 9시간이 비어도 9시간 공부하지 않는다.
    """

    day_start_minute: int | None = Field(default=None, ge=0, le=1439)
    day_end_minute: int | None = Field(default=None, ge=1, le=1440)
    daily_cap_minutes: int | None = Field(default=None, ge=0, le=1440)

    @model_validator(mode="after")
    def check(self):
        if (
            self.day_start_minute is not None
            and self.day_end_minute is not None
            and self.day_end_minute <= self.day_start_minute
        ):
            raise ValueError("활동 시간대의 끝이 시작보다 뒤여야 합니다")

        return self
