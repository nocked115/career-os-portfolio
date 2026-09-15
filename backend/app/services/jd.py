"""JD 분석과 경험 매칭 - Phase 5.

**LLM 이 아니다.** 저장된 스킬 이름을 JD 텍스트에서 찾는다.
다만 기존 `collector.link_skills_from_description` 보다 정확하게 한다.

    기존:  "go" in description       → "Google" 에도 걸린다
    지금:  단어 경계를 본다 + 언급 횟수와 위치로 강조도를 낸다

할 수 없는 것은 하지 않는다.
JD 를 읽고 요약하거나 문장을 생성하는 것은 LLM 이 있어야 한다.
"""

import re

from .. import models


# 강조도 계산.
# 여러 번 나오고 앞쪽에 나올수록 그 공고가 중요하게 보는 역량이다.
MENTION_WEIGHT = 10
POSITION_WEIGHT = 30

# 보유 판정. 우선순위 계산과 같은 상한을 쓴다.
STRONG_LEVEL = 3
MEDIUM_LEVEL = 1


# 한국어는 조사가 명사에 붙는다. "딥러닝을", "파이썬으로", "머신러닝과".
# 뒤에 한글이 오면 무조건 막는 규칙은 영문("Go" vs "Google")은 지키지만
# 한국어를 통째로 놓친다. 실제 공고에서 "딥러닝을" 을 못 찾았다.
#
# 긴 것부터 둔다. "으로" 가 "로" 보다 먼저 걸려야 한다.
PARTICLES = (
    "으로부터", "에서부터", "이라고", "라고", "으로써", "으로서",
    "로써", "로서", "에게서", "한테서", "으로", "에서", "에게",
    "한테", "부터", "까지", "처럼", "보다", "마다", "조차", "라도",
    "이나", "이란", "이라", "과의", "와의", "의", "을", "를",
    "이", "가", "은", "는", "과", "와", "로", "에", "도", "만",
    "및", "등",
)


def _pattern(name: str):
    """단어 경계를 지키는 정규식.

    영문은 단어 경계로 자른다 — "Go" 가 "Google" 에,
    "C" 가 "CSS" 에 걸리지 않게 한다.

    한글이 섞인 이름은 뒤에 조사가 붙는 것까지 허용한다.
    조사 목록에 없는 한글이 이어지면 여전히 막는다 —
    "딥러닝기술" 같은 합성어를 같은 것으로 세지 않기 위해서다.
    """
    escaped = re.escape(name)

    has_hangul = re.search(r"[가-힣]", name) is not None

    if has_hangul:
        particles = "|".join(re.escape(p) for p in PARTICLES)
        tail = (
            r"(?:(?![0-9A-Za-z가-힣])"
            rf"|(?=(?:{particles})(?![가-힣])))"
        )
    else:
        tail = r"(?![0-9A-Za-z가-힣])"

    return re.compile(
        r"(?<![0-9A-Za-z가-힣])" + escaped + tail,
        re.IGNORECASE,
    )


def skill_names(skill) -> list[str]:
    """이 스킬을 부르는 모든 이름.

    한글 공고에 "Machine Learning" 은 안 걸리고 영문 공고에
    "머신러닝" 은 안 걸린다. 별칭이 그 간극을 메운다.
    """
    names = [skill.name]

    for alias in (skill.aliases or "").split(","):
        alias = alias.strip()

        if alias and alias.lower() not in {n.lower() for n in names}:
            names.append(alias)

    return names


def extract_skills(db, text: str) -> list[dict]:
    """JD 텍스트에서 등록된 스킬을 찾는다.

    등록되지 않은 스킬은 찾을 수 없다. 그게 이 방식의 한계다.
    """
    if not text:
        return []

    length = len(text)
    found = []

    for skill in db.query(models.Skill).all():
        matches = []

        for name in skill_names(skill):
            matches.extend(_pattern(name).finditer(text))

        matches.sort(key=lambda m: m.start())

        if not matches:
            continue

        first = matches[0].start()

        # 앞에 나올수록 1 에 가깝다
        position_score = 1 - (first / length) if length else 0

        emphasis = round(
            len(matches) * MENTION_WEIGHT + position_score * POSITION_WEIGHT
        )

        found.append({
            "skill_id": skill.id,
            "skill": skill.name,
            "source": "text",
            "mentions": len(matches),
            "first_at": first,
            "emphasis": emphasis,
            "my_level": skill.level or 0,
            "strength": _strength(skill.level or 0),
        })

    found.sort(key=lambda item: item["emphasis"], reverse=True)

    return found


def _strength(level: int) -> str:
    if level >= STRONG_LEVEL:
        return "strong"
    if level >= MEDIUM_LEVEL:
        return "medium"
    return "gap"


# --------------------------------
# 경험 매칭
# --------------------------------

def _experience_terms(experience) -> set[str]:
    """이 경험이 내세울 수 있는 것들."""
    terms = {skill.name.lower() for skill in experience.skills}

    for chunk in (experience.technologies or "").split(","):
        cleaned = chunk.strip().lower()
        if cleaned:
            terms.add(cleaned)

    return terms


def score_experience(experience, required: list[dict]) -> dict:
    """이 경험이 요구 역량을 얼마나 덮는가.

    강조도가 높은 역량을 덮을수록 점수가 높다.
    """
    if not required:
        return {
            "score": 0,
            "covered": [],
            "message": "JD 에서 요구 역량을 찾지 못해 매칭할 수 없습니다.",
        }

    terms = _experience_terms(experience)

    total_emphasis = sum(item["emphasis"] for item in required)

    covered = [
        item for item in required
        if item["skill"].lower() in terms
    ]

    got = sum(item["emphasis"] for item in covered)

    score = round(got / total_emphasis * 100) if total_emphasis else 0

    return {
        "score": score,
        "covered": [item["skill"] for item in covered],
        "message": None,
    }


def recommend_experiences(db, required: list[dict], limit: int = 3) -> list[dict]:
    """요구 역량을 가장 잘 덮는 경험부터.

    덮는 게 하나도 없으면 넣지 않는다.
    관련 없는 경험을 추천하면 자소서가 더 나빠진다.
    """
    results = []

    for experience in db.query(models.Experience).all():
        scored = score_experience(experience, required)

        if scored["score"] <= 0:
            continue

        results.append({
            "experience_id": experience.id,
            "title": experience.title,
            "experience_type": experience.experience_type,
            "score": scored["score"],
            "covered": scored["covered"],
        })

    results.sort(key=lambda item: item["score"], reverse=True)

    return results[:limit]


# --------------------------------
# 지원서 분석
# --------------------------------

def _job_description(application) -> tuple[str, str]:
    """분석할 JD 텍스트와 그 출처."""
    if application.opportunity is not None:
        return (
            application.opportunity.description or "",
            application.opportunity.title,
        )

    if application.legacy_job is not None:
        return (
            application.legacy_job.description or "",
            application.legacy_job.title,
        )

    return "", ""


def _linked_skills(application) -> list[dict]:
    """사람이 공고에 직접 연결해 둔 스킬.

    본문 표기가 등록된 이름과 다르면(예: "AI/Agent" 와 "AI Agent")
    찾기가 실패한다. 실제 공고에서 그랬다. 그때 사람이 붙인 연결을
    근거로 쓴다. 본문 언급이 없으니 강조도는 모두 같게 둔다.
    """
    posting = application.opportunity

    if posting is None:
        return []

    return [
        {
            "skill_id": skill.id,
            "skill": skill.name,
            "source": "linked",
            "mentions": 0,
            "first_at": None,
            "emphasis": MENTION_WEIGHT,
            "my_level": skill.level or 0,
            "strength": _strength(skill.level or 0),
        }
        for skill in sorted(posting.skills, key=lambda item: item.name)
    ]


def analyze_application(db, application) -> dict:
    """이 지원서의 JD 를 분석하고 쓸 경험을 고른다."""
    text, title = _job_description(application)

    required = extract_skills(db, text)
    basis = "text"

    if text.strip() and not required:
        linked = _linked_skills(application)

        if linked:
            required = linked
            basis = "linked"

    strong = [r for r in required if r["strength"] == "strong"]
    gaps = [r for r in required if r["strength"] == "gap"]

    recommended = recommend_experiences(db, required)

    match_score = 0

    if required:
        total = sum(r["emphasis"] for r in required)
        have = sum(
            r["emphasis"] for r in required if r["strength"] != "gap"
        )
        match_score = round(have / total * 100) if total else 0

    return {
        "application_id": application.id,
        "title": title,
        "has_description": bool(text.strip()),
        "basis": basis,
        "match_score": match_score,
        "required_skills": required,
        "strong_count": len(strong),
        "gap_skills": [r["skill"] for r in gaps],
        "recommended_experiences": recommended,
        "notes": _notes(text, required, recommended, basis),
    }


def _notes(text, required, recommended, basis="text") -> list[str]:
    """분석의 한계를 숨기지 않는다."""
    notes = []

    if not (text or "").strip():
        notes.append(
            "공고 본문이 비어 있어 요구 역량을 뽑을 수 없습니다."
        )
        return notes

    if not required:
        notes.append(
            "등록된 스킬 중 이 공고에서 발견된 것이 없습니다. "
            "스킬을 먼저 등록하면 분석이 됩니다."
        )
        return notes

    if basis == "linked":
        notes.append(
            "공고 본문에서 등록된 스킬 이름을 찾지 못해, 이 공고에 직접 "
            f"연결한 스킬 {len(required)}개를 기준으로 봤습니다. "
            "본문 언급 횟수가 없어 강조도는 모두 같게 둡니다."
        )
    else:
        notes.append(
            "등록된 스킬 이름을 본문에서 찾는 방식입니다. "
            "등록되지 않은 역량은 찾지 못합니다."
        )

    if not recommended:
        notes.append(
            "요구 역량을 덮는 경험이 Experience Bank 에 없습니다. "
            "관련 없는 경험을 억지로 추천하지 않습니다."
        )

    return notes


# --------------------------------
# 자동 매칭 저장
# --------------------------------

def auto_match(db, application) -> dict:
    """분석 결과를 경험 매칭으로 저장한다.

    사람이 직접 넣어둔 메모는 덮어쓰지 않는다.
    """
    analysis = analyze_application(db, application)

    saved = []

    for item in analysis["recommended_experiences"]:
        match = db.get(
            models.ApplicationExperienceMatch,
            (application.id, item["experience_id"]),
        )

        if match is None:
            match = models.ApplicationExperienceMatch(
                application_id=application.id,
                experience_id=item["experience_id"],
            )
            db.add(match)

        match.match_score = item["score"]

        # 사람이 쓴 메모가 있으면 건드리지 않는다.
        if not (match.match_notes or "").strip():
            match.match_notes = (
                "자동 매칭 — 덮는 역량: " + ", ".join(item["covered"])
            )

        saved.append(item)

    db.commit()

    return {
        "application_id": application.id,
        "matched": len(saved),
        "experiences": saved,
        "notes": analysis["notes"],
    }
