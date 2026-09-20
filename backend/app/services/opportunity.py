"""Opportunity 수집과 매칭 - Mission 023.

수집기가 만드는 것은 이제 Opportunity 다.
레거시 `Job` 은 대시보드와 기존 매칭이 쓰고 있어 그대로 두고,
`legacy_job_id` 로 이어서 양쪽이 함께 동작하게 한다.
"""

from datetime import date, datetime

from .. import collectors, models
from . import certificates as certificate_service
from . import posting_parser
from . import priority as priority_service


# --------------------------------
# 점수 구성 - 합계 100
#
# 각 요소가 왜 그 배점인지는 build_match() 의 주석 참고.
# --------------------------------

WEIGHT_RELEVANCE = 40      # 지금 배워야 할 스킬을 요구하는가
WEIGHT_READINESS = 30      # 지금 지원/도전할 만한 준비가 됐는가
WEIGHT_PORTFOLIO = 15      # 포트폴리오 증거가 되는가
WEIGHT_DEADLINE = 15       # 마감까지 현실적인가

# 공고에서 스킬을 못 찾았을 때 관련성 · 준비도. 모르는 것을 0 으로 치지 않는다.
UNKNOWN_SKILL_VALUE = 0.5

RECOMMEND_THRESHOLD = 70
CONSIDER_THRESHOLD = 40

# 마감이 이보다 적게 남으면 촉박하다고 본다.
TIGHT_DEADLINE_DAYS = 7
COMFORTABLE_DEADLINE_DAYS = 30

# 필요 시간을 아는 경우, 하루에 몇 시간을 써야 하는지로 판단한다 (Phase 3).
#
# 남은 날짜만 보면 "40시간짜리를 5일 안에" 와
# "4시간짜리를 5일 안에" 를 구분하지 못한다.
HOURS_PER_DAY_COMFORTABLE = 1
HOURS_PER_DAY_WORKABLE = 2
HOURS_PER_DAY_TIGHT = 4


# --------------------------------
# 수집
# --------------------------------

def link_skills(db, opportunity) -> list:
    """설명과 제목에서 스킬을 찾아 연결한다.

    단어 경계를 지키는 jd.extract_skills 를 쓴다. 전에는 단순
    부분 문자열 비교라 "Go" 가 "Google" 에, "C" 가 "CSS" 에 걸렸다.

    스킬이 연결되지 않은 기회는 분모만 늘리고 어느 스킬의 분자에도
    들어가지 않는다. 즉 넣을수록 모든 스킬의 비율이 내려간다.
    그래서 이 연결은 선택이 아니라 필수다.
    """
    from . import jd as jd_service

    text = f"{opportunity.title}\n{opportunity.description or ''}"

    linked = []

    for found in jd_service.extract_skills(db, text):
        skill = db.get(models.Skill, found["skill_id"])

        if skill is None:
            continue

        if skill not in opportunity.skills:
            opportunity.skills.append(skill)

        linked.append(skill)

    return linked


def _bridge_to_legacy_job(db, opportunity):
    """type 이 job 인 기회는 레거시 Job 으로도 남긴다.

    대시보드와 /jobs/{id}/match, 학습 우선순위가 아직 Job 을 본다.
    Opportunity 로 넘어가는 동안 양쪽을 함께 유지하기 위한 다리다.
    """
    if opportunity.opportunity_type != "job":
        return None

    if opportunity.legacy_job is not None:
        return opportunity.legacy_job

    existing = None

    if opportunity.source_url:
        existing = (
            db.query(models.Job)
            .filter(models.Job.url == opportunity.source_url)
            .first()
        )

    if existing is None:
        existing = models.Job(
            company=opportunity.organization,
            title=opportunity.title,
            role=opportunity.role,
            employment_type=opportunity.employment_type or "intern",
            url=opportunity.source_url,
            deadline=(
                opportunity.deadline.date().isoformat()
                if opportunity.deadline
                else ""
            ),
            description=opportunity.description,
            status="discovered",
        )
        db.add(existing)
        db.flush()

    # 레거시 Job 쪽 스킬 연결도 맞춰준다
    for skill in opportunity.skills:
        if skill not in existing.skills:
            existing.skills.append(skill)

    opportunity.legacy_job_id = existing.id

    return existing


def bridge_from_legacy_job(db, job):
    """레거시 Job 을 Opportunity 로도 남긴다.

    `_bridge_to_legacy_job` 의 반대 방향이다. 그쪽은 job 타입 기회만
    Job 으로 넘겼기 때문에, 공모전·대외활동은 Job 이 되지 않았다.
    그 결과 같은 "수요" 를 두 테이블이 서로 다른 모수로 세고 있었다 —
    AWS 가 한쪽에서는 1/1, 다른 쪽에서는 0/3 이었다.

    모수를 Opportunity 하나로 모으려면 Job 쪽에서 들어온 것도
    Opportunity 에 있어야 한다.
    """
    existing = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.legacy_job_id == job.id)
        .first()
    )

    if existing is None:
        existing = models.Opportunity(
            opportunity_type="job",
            title=job.title,
            organization=job.company or "",
            role=job.role or "",
            description=job.description or "",
            source="legacy_job",
            source_url=job.url or "",
            employment_type=job.employment_type or "",
            status="discovered",
            legacy_job_id=job.id,
        )
        db.add(existing)
        db.flush()

    # 스킬 연결을 맞춘다. 이게 곧 수요 집계의 재료다.
    for skill in job.skills:
        if skill not in existing.skills:
            existing.skills.append(skill)

    return existing


def save_opportunity(db, normalized: dict):
    """정규화된 기회를 저장한다. 이미 있으면 갱신한다.

    (source, source_external_id) 로 같은 것인지 판단한다.
    반환: (opportunity, created)
    """
    existing = None

    if normalized.get("source_external_id"):
        existing = (
            db.query(models.Opportunity)
            .filter(
                models.Opportunity.source == normalized["source"],
                models.Opportunity.source_external_id
                == normalized["source_external_id"],
            )
            .first()
        )

    created = existing is None

    if existing is None:
        opportunity = models.Opportunity(**normalized)
        db.add(opportunity)
    else:
        opportunity = existing

        # 마감일이나 설명이 바뀌었을 수 있으니 갱신한다.
        # status 는 사용자가 바꿨을 수 있으므로 건드리지 않는다.
        for field in (
            "title",
            "organization",
            "role",
            "description",
            "source_url",
            "location",
            "employment_type",
            "deadline",
            "raw_payload",
        ):
            setattr(opportunity, field, normalized[field])

    db.flush()

    link_skills(db, opportunity)
    _bridge_to_legacy_job(db, opportunity)

    db.commit()
    db.refresh(opportunity)

    return opportunity, created


def is_dismissed(db, source, external_id) -> bool:
    if not external_id:
        return False
    return (
        db.query(models.DismissedPosting)
        .filter_by(source=source, source_external_id=str(external_id))
        .first()
        is not None
    )


def dismiss(db, opportunity) -> None:
    """휴지통 — 수집 공고면 번호만 남겨 다시 들이지 않게 한다. 지우는 것은 부르는 쪽이 한다."""
    if opportunity.source_external_id and not is_dismissed(
        db, opportunity.source, opportunity.source_external_id
    ):
        db.add(models.DismissedPosting(
            source=opportunity.source,
            source_external_id=str(opportunity.source_external_id),
        ))


def collect_from(db, collector) -> dict:
    """수집원 하나를 실행한다."""
    try:
        raw_items = collector.fetch()
    except collectors.base.CollectorError as error:
        return {
            "source": collector.SOURCE_NAME,
            "status": "failed",
            "error": str(error),
            "fetched": 0,
            "created": 0,
            "updated": 0,
        }

    created = 0
    updated = 0
    skipped = 0

    for raw in raw_items:
        try:
            normalized = collector.normalize(raw)
        except collectors.base.CollectorError:
            # 형태가 어긋난 항목 하나 때문에 수집 전체를 멈추지 않는다.
            skipped += 1
            continue

        # 휴지통으로 지운 공고는 다시 들이지 않는다.
        if is_dismissed(db, normalized["source"], normalized.get("source_external_id")):
            skipped += 1
            continue

        _, was_created = save_opportunity(db, normalized)

        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "source": collector.SOURCE_NAME,
        "status": "completed",
        "fetched": len(raw_items),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


# 모집 부문을 읽어 직무를 판단할 수 있는 수집원. 부문이 없는 공고는 판단하지 않는다.
FIT_SOURCES = ("work24",)


def review_fit(db) -> dict:
    """이미 들여온 공고를 다시 판단한다 — 데이터 · AI 직무가 아니면 보관함으로.

    수집 규칙을 고쳐도 전에 들어온 공고는 그대로 남는다. 실제로 났다 — 건강식품 온라인 영업이
    88점으로 기회 목록 위쪽에 있었다. 그래서 저장된 설명의 모집 부문을 다시 읽어 판단한다.

    건드리지 않는 것
      - 지원서가 있는 공고 — 이미 사람이 판단했다
      - "그래도 검토" 로 되살린 공고 (keep_anyway)

    뺀 공고는 스킬 연결을 끊는다. 안 그러면 영업 공고가 "데이터 분석" 수요로 세어진다.
    다시 맞다고 판단되면 스킬을 다시 잇는다.
    """
    from . import job_fit

    filtered = restored = 0

    rows = (
        db.query(models.Opportunity)
        .filter(
            models.Opportunity.source.in_(FIT_SOURCES),
            models.Opportunity.opportunity_type == "job",
            models.Opportunity.keep_anyway.is_(False),
        )
        .all()
    )

    for opportunity in rows:
        if opportunity.applications:
            continue

        sections = job_fit.parse_sections(opportunity.description)
        if not sections:
            continue

        judged = job_fit.judge_sections(sections)

        if not judged["fits"]:
            if opportunity.filtered_reason != judged["reason"]:
                if not opportunity.filtered_reason:
                    filtered += 1
                opportunity.filtered_reason = judged["reason"]
            opportunity.skills = []
        elif opportunity.filtered_reason:
            opportunity.filtered_reason = ""
            link_skills(db, opportunity)
            restored += 1

    db.commit()

    return {"filtered": filtered, "restored": restored}


def keep_anyway(db, opportunity):
    """자동으로 뺀 공고를 사람이 되살린다. 다시 자동으로 빼지 않는다."""
    opportunity.keep_anyway = True
    opportunity.filtered_reason = ""
    link_skills(db, opportunity)
    db.commit()
    db.refresh(opportunity)
    return opportunity


def collect_all(db) -> dict:
    """사용 가능한 모든 수집원을 실행한다."""
    results = [
        collect_from(db, collector)
        for collector in collectors.available_collectors()
    ]

    # 새로 들어온 것과 이미 있던 것을 같은 규칙으로 다시 본다.
    fit = review_fit(db)

    return {
        "fit": fit,
        "sources": results,
        "fetched": sum(r["fetched"] for r in results),
        "created": sum(r["created"] for r in results),
        "updated": sum(r["updated"] for r in results),
    }


# --------------------------------
# 매칭 점수
# --------------------------------

def days_until(deadline, now=None):
    """마감까지 남은 일수. 마감이 없으면 None."""
    if deadline is None:
        return None

    now = now or datetime.now()

    return (deadline.date() - now.date()).days


def _relevance(opportunity, priority_by_skill_id, top_score):
    """지금 배워야 할 스킬을 요구하는 기회일수록 높다.

    학습 우선순위 1위 스킬 대비 상대값으로 계산한다.
    """
    if not opportunity.skills or top_score <= 0:
        return 0.0, []

    scores = []
    names = []

    for skill in opportunity.skills:
        entry = priority_by_skill_id.get(skill.id)

        if entry is None:
            continue

        scores.append(entry["priority_score"])

        if entry["priority_score"] > 0:
            names.append(skill.name)

    if not scores:
        return 0.0, []

    ratio = max(scores) / top_score

    return min(1.0, ratio), names


def _readiness(opportunity):
    """요구 스킬 중 이미 보유한 비율 — 찾은 스킬이 적을수록 100% 로 단정하지 않는다.

    전에는 보유 수 / 요구 수 그대로였다. 공고에서 "데이터 분석" 하나만 뽑혀도 1/1 = 100%
    라서, 건강식품 온라인 영업이 "요구 스킬을 다 갖췄다" 로 88점이 됐다. 스킬 하나로는
    준비됐다고 말할 근거가 약하다. 그래서 가진 것 하나 · 없는 것 하나를 미리 깔고 센다
    (보유+1)/(요구+2): 1/1 → 67%, 3/3 → 80%, 6/6 → 88%. 많이 찾을수록 실제 비율에 가까워진다.
    화면의 "요구 스킬 N개 중 M개" 는 실제 수 그대로다.
    """
    if not opportunity.skills:
        return 0.0, 0, 0

    have = sum(1 for skill in opportunity.skills if (skill.level or 0) > 0)
    required = len(opportunity.skills)

    return (have + 1) / (required + 2), have, required


def _portfolio_value(opportunity, priority_by_skill_id):
    """포트폴리오 증거가 되는 정도.

    공모전과 대외활동은 결과물이 남으므로 기본값이 높다.
    증거가 없는 스킬을 요구할수록 더 높다.
    """
    base = 0.5 if opportunity.opportunity_type in (
        "competition",
        "external_activity",
    ) else 0.2

    if not opportunity.skills:
        return base

    without_evidence = [
        skill
        for skill in opportunity.skills
        if not priority_by_skill_id.get(skill.id, {}).get(
            "has_project_evidence", False
        )
    ]

    if without_evidence:
        base += 0.5 * (len(without_evidence) / len(opportunity.skills))

    return min(1.0, base)


def hours_per_day(estimated_hours, days_left):
    """마감을 맞추려면 하루에 몇 시간을 써야 하는가.

    판단할 수 없으면 None.
    """
    if estimated_hours is None or days_left is None or days_left < 0:
        return None

    # 오늘이 마감이어도 0 으로 나누지 않는다.
    return estimated_hours / max(1, days_left)


def _deadline_feasibility(days_left, estimated_hours=None):
    """마감까지 현실적인가.

    필요 시간을 알면 "하루에 몇 시간" 으로 판단한다.
    모르면 남은 날짜만으로 판단한다.
    마감 정보가 없으면 판단할 수 없으므로 중립값을 준다.
    """
    if days_left is None:
        return 0.5, "no_deadline"

    if days_left < 0:
        return 0.0, "passed"

    per_day = hours_per_day(estimated_hours, days_left)

    if per_day is not None:
        if per_day <= HOURS_PER_DAY_COMFORTABLE:
            return 1.0, "comfortable"

        if per_day <= HOURS_PER_DAY_WORKABLE:
            return 0.75, "workable"

        if per_day <= HOURS_PER_DAY_TIGHT:
            return 0.35, "tight"

        return 0.05, "unrealistic"

    if days_left < TIGHT_DEADLINE_DAYS:
        return 0.3, "tight"

    if days_left >= COMFORTABLE_DEADLINE_DAYS:
        return 1.0, "comfortable"

    span = COMFORTABLE_DEADLINE_DAYS - TIGHT_DEADLINE_DAYS
    ratio = (days_left - TIGHT_DEADLINE_DAYS) / span

    return 0.3 + 0.7 * ratio, "workable"


# 지원서가 이 상태면 그 기회는 끝난 것이다 — 보관함으로 간다.
ENDED_APPLICATION = {
    "withdrawn": "지원서 철회",
    "rejected": "불합격",
    "accepted": "합격",
}


def lane_of(opportunity, application, days_left):
    """이 기회가 기회 화면의 어느 칸에 있어야 하는가 — (칸, 보관 이유).

    전에는 칸을 기회 상태(보류 · 관심 없음)로만 나눴다. 그래서 지원서를 철회한 공고가
    검토 중 목록에 "오늘 마감 · 지금 할 만해요" 로 남았고, 이미 지원한 공고도 검토 목록에
    섞였다. 판단이 끝난 것은 판단할 목록에서 빠져야 한다.

      archived        직접 닫음 · 지원서 철회/불합격/합격 · 마감 지남
      applied         지원서가 진행 중 (지원서 화면이 맡는다)
      on_hold · not_interested  사람이 옮긴 것
      review          나머지
    """
    if opportunity.status == "closed":
        return "archived", "직접 닫음"

    if application is not None and application["status"] in ENDED_APPLICATION:
        return "archived", ENDED_APPLICATION[application["status"]]

    if opportunity.status in ("on_hold", "not_interested"):
        return opportunity.status, None

    if application is not None:
        return "applied", None

    # 직무가 맞지 않아 자동으로 뺀 공고. "그래도 검토" 로 되살릴 수 있다.
    if opportunity.filtered_reason:
        return "archived", "직무가 달라 자동으로 뺌"

    if days_left is not None and days_left < 0:
        return "archived", "지난 행사" if opportunity.opportunity_type == "job_event" else "마감 지남"

    return "review", None


def _application_summary(opportunity):
    """이 기회에 달린 지원서 하나 (가장 최근)."""
    applications = sorted(
        opportunity.applications, key=lambda item: item.id, reverse=True
    )

    if not applications:
        return None

    return {"id": applications[0].id, "status": applications[0].status}


def build_match(db, opportunity, priority_entries=None) -> dict:
    """이 기회를 지금 하는 게 가치가 있는지 판단한다.

    모든 숫자는 저장된 데이터에서 나온다. 지어내지 않는다.
    """
    if priority_entries is None:
        priority_entries = priority_service.build_skill_priorities(db)

    priority_by_skill_id = {
        entry["skill"].id: entry for entry in priority_entries
    }

    top_score = max(
        (entry["priority_score"] for entry in priority_entries),
        default=0,
    )

    relevance, relevant_names = _relevance(
        opportunity, priority_by_skill_id, top_score
    )
    readiness, have, required = _readiness(opportunity)

    # 공고에서 스킬을 하나도 못 찾았으면 "요구 스킬이 없다" 가 아니라 "모른다" 다.
    # 실제로 났다 — 조선해양 "데이터 사이언티스트" 부문은 설명이 "상세 모집요강 참조" 뿐이라
    # 스킬이 안 뽑혀 10점으로 맨 아래에 있었다. 마감일을 모를 때(0.5)처럼 중간값으로 둔다.
    if not opportunity.skills:
        relevance = UNKNOWN_SKILL_VALUE
        readiness = UNKNOWN_SKILL_VALUE

    portfolio = _portfolio_value(opportunity, priority_by_skill_id)

    days_left = days_until(opportunity.deadline)
    deadline_score, deadline_state = _deadline_feasibility(
        days_left, opportunity.estimated_hours
    )
    per_day = hours_per_day(opportunity.estimated_hours, days_left)

    flags = posting_parser.find_requirement_flags(opportunity.description or "")

    application = _application_summary(opportunity)
    lane, archive_reason = lane_of(opportunity, application, days_left)

    score = round(
        relevance * WEIGHT_RELEVANCE
        + readiness * WEIGHT_READINESS
        + portfolio * WEIGHT_PORTFOLIO
        + deadline_score * WEIGHT_DEADLINE
    )

    # 마감이 지났으면 점수와 무관하게 건너뛴다.
    if deadline_state == "passed":
        recommendation = "skip"
    elif score >= RECOMMEND_THRESHOLD:
        recommendation = "recommended"
    elif score >= CONSIDER_THRESHOLD:
        recommendation = "consider"
    else:
        recommendation = "skip"

    # 끝난 기회에 "지금 할 만해요" 를 붙이지 않는다.
    if lane == "archived":
        recommendation = "skip"
    elif opportunity.opportunity_type == "job_event" and lane == "review":
        # 채용 행사는 요구 스킬이 없어 점수가 늘 낮다. 스킬 점수로 "지금은 아니에요" 에 묻지 않고,
        # 가 볼지 사람이 정하게 검토 목록에 둔다.
        recommendation = "consider"

    return {
        "opportunity_id": opportunity.id,
        # 기회 화면의 칸. 화면이 상태 · 지원서 · 마감을 따로 조합하지 않게 서버가 정한다.
        "lane": lane,
        "archive_reason": archive_reason,
        "title": opportunity.title,
        "organization": opportunity.organization,
        "opportunity_type": opportunity.opportunity_type,
        # 화면이 "공고 보기" 링크를 만들려면 이게 있어야 한다.
        # 없으면 지원하러 갈 때마다 주소를 다시 찾아야 한다.
        "source_url": opportunity.source_url,
        # 사람인 약관이 출처 표시를 요구한다. 화면이 이걸 보고 붙인다.
        "source": opportunity.source,
        # 여러 부문을 뽑는 공채에서 내게 맞는 부문.
        "role": opportunity.role,
        # 자동으로 뺐으면 왜 뺐는지. 보관함에서 그대로 보인다.
        "filtered_reason": opportunity.filtered_reason,
        # 보류 · 관심 없음을 화면이 따로 모으려면 상태가 있어야 한다.
        "status": opportunity.status,
        "deadline": opportunity.deadline,
        # 이미 지원서가 있으면 "지원서 만들기" 대신 "지원서 열기" 를 준다.
        "application": application,
        # 점수만 보고 자격 요건을 놓치지 않게 (예: "학계 1년 이상").
        "requirement_flags": flags,
        # 그 경고 옆에 놓을 내 어학 · 자격. 충족 여부는 판단하지 않는다.
        "my_certificates": certificate_service.relevant(db, flags),
        "have_skills": [
            skill.name for skill in opportunity.skills if (skill.level or 0) > 0
        ],
        "match_score": score,
        "recommendation": recommendation,
        "days_until_deadline": days_left,
        "deadline_state": deadline_state,
        "estimated_hours": opportunity.estimated_hours,
        "hours_per_day": round(per_day, 1) if per_day is not None else None,
        "required_skills": [skill.name for skill in opportunity.skills],
        "skills_i_have": have,
        "skills_required": required,
        "breakdown": {
            "relevance": round(relevance * WEIGHT_RELEVANCE),
            "readiness": round(readiness * WEIGHT_READINESS),
            "portfolio_value": round(portfolio * WEIGHT_PORTFOLIO),
            "deadline": round(deadline_score * WEIGHT_DEADLINE),
        },
        "reasons": _build_reasons(
            opportunity=opportunity,
            relevant_names=relevant_names,
            have=have,
            required=required,
            days_left=days_left,
            deadline_state=deadline_state,
            recommendation=recommendation,
            per_day=per_day,
        ),
    }


def _build_reasons(
    *,
    opportunity,
    relevant_names,
    have,
    required,
    days_left,
    deadline_state,
    recommendation,
    per_day=None,
) -> list[str]:
    """왜 이 점수인지 설명한다. 설명할 수 없으면 추천하지 않는다."""
    reasons = []

    if required == 0:
        reasons.append(
            "공고에서 요구 스킬을 찾지 못해 관련성 · 준비도를 중간으로 봤습니다. 원문을 확인하세요."
        )
    else:
        if relevant_names:
            reasons.append(
                "지금 우선순위가 높은 스킬을 요구합니다: "
                + ", ".join(relevant_names[:3])
                + "."
            )
        else:
            reasons.append(
                "지금 우선순위가 높은 스킬과는 겹치지 않습니다."
            )

        reasons.append(
            f"요구 스킬 {required}개 중 {have}개를 보유하고 있습니다."
        )

    if opportunity.opportunity_type in ("competition", "external_activity"):
        reasons.append("결과물이 포트폴리오 증거로 남습니다.")

    if deadline_state == "passed":
        reasons.append(f"마감이 {abs(days_left)}일 지났습니다.")
    elif deadline_state == "no_deadline":
        reasons.append("마감일 정보가 없습니다.")
    elif per_day is not None:
        # 필요 시간을 아는 경우가 가장 정확하다.
        reasons.append(
            f"마감까지 {days_left}일이고 약 {opportunity.estimated_hours}시간이 "
            f"필요합니다 — 하루 {per_day:.1f}시간."
        )

        if deadline_state == "unrealistic":
            reasons.append("지금 일정으로는 끝내기 어렵습니다.")
        elif deadline_state == "tight":
            reasons.append("빠듯합니다.")
    elif deadline_state == "tight":
        reasons.append(f"마감까지 {days_left}일뿐이라 촉박합니다.")
    else:
        reasons.append(f"마감까지 {days_left}일 남았습니다.")

    if recommendation == "skip" and deadline_state != "passed":
        reasons.append(
            "지금은 다른 것을 먼저 하는 편이 낫습니다."
        )

    return reasons


def score_opportunity(db, opportunity, priority_entries=None) -> dict:
    """점수를 계산하고 결과를 저장한다."""
    match = build_match(db, opportunity, priority_entries)

    opportunity.match_score = match["match_score"]
    opportunity.match_recommendation = match["recommendation"]
    opportunity.scored_at = datetime.now()

    db.commit()
    db.refresh(opportunity)

    return match


def score_all(db) -> list[dict]:
    """모든 기회를 다시 채점한다. 점수 높은 순으로 돌려준다."""
    priority_entries = priority_service.build_skill_priorities(db)

    opportunities = db.query(models.Opportunity).all()

    matches = [
        score_opportunity(db, opportunity, priority_entries)
        for opportunity in opportunities
    ]

    matches.sort(key=lambda item: item["match_score"], reverse=True)

    return matches


def recommended(db, limit: int = 3) -> list[dict]:
    """지금 할 만한 기회만 추린다.

    목록을 길게 주는 것이 목적이 아니다.
    추천할 만한 게 없으면 빈 목록을 돌려준다.
    """
    matches = score_all(db)

    worth_doing = [
        match
        for match in matches
        if match["recommendation"] in ("recommended", "consider")
    ]

    return worth_doing[:limit]


# --------------------------------
# 계획에 추가 (Phase 3)
#
# 기회를 보고 "할 만하다" 고 판단했으면 오늘 계획으로 이어져야 한다.
# 여기서 끊기면 DISCOVER 가 북마크 목록으로 끝난다.
# --------------------------------

DEFAULT_PLAN_MINUTES = 30


def add_to_plan(db, opportunity, minutes: int = DEFAULT_PLAN_MINUTES) -> dict:
    """이 기회를 오늘 계획에 올린다.

    지원서가 없으면 관심 상태로 하나 만든다.
    기회만 계획에 넣고 지원서를 안 만들면
    나중에 "이거 어떻게 됐더라" 를 추적할 곳이 없다.
    """
    from . import today as today_service

    application = (
        db.query(models.Application)
        .filter(models.Application.opportunity_id == opportunity.id)
        .first()
    )

    created_application = application is None

    if application is None:
        application = models.Application(
            opportunity_id=opportunity.id,
            status="interested",
            deadline=opportunity.deadline,
        )
        db.add(application)
        db.flush()

    today = date.today()

    existing_task = (
        db.query(models.DailyPlanTask)
        .filter(
            models.DailyPlanTask.plan_date == today,
            models.DailyPlanTask.application_id == application.id,
            models.DailyPlanTask.status == "planned",
        )
        .first()
    )

    if existing_task is not None:
        db.commit()

        return {
            "already_planned": True,
            "application_id": application.id,
            "created_application": created_application,
            "task": today_service.serialize_task(existing_task),
        }

    position = (
        db.query(models.DailyPlanTask)
        .filter(models.DailyPlanTask.plan_date == today)
        .count()
    )

    days = days_until(opportunity.deadline)

    reason = f"{opportunity.title} 을(를) 계획에 추가했습니다."

    if days is not None:
        reason = (
            f"마감까지 {days}일 — {opportunity.title} 을(를) 계획에 추가했습니다."
        )

    task = models.DailyPlanTask(
        plan_date=today,
        position=position,
        task_type="application",
        title=f"지원 준비 — {opportunity.title}",
        minutes=minutes,
        reason=reason,
        status="planned",
        application_id=application.id,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "already_planned": False,
        "application_id": application.id,
        "created_application": created_application,
        "task": today_service.serialize_task(task),
    }
