"""붙여넣은 공고 글에서 칸을 채운다 — 규칙 기반.

공고 사이트를 앱이 열지 않는다. 대부분의 채용 사이트는 약관에서 자동
수집을 막는다. 대신 사람이 읽은 공고를 복사해 붙여넣으면 여기서 제목 ·
마감 · 요구 스킬 · 지원 자격을 찾아 **미리보기**로 돌려준다. 저장하지
않는다. 틀린 칸은 사람이 고치고 저장한다.

**못 찾으면 비워 둔다.** 날짜와 회사를 짐작해서 채우지 않는다. 찾은 칸마다
근거가 된 줄을 같이 돌려준다 — 화면이 "어디서 이 값을 읽었는지" 를 보여준다.

지원 자격에서 걸림돌이 될 수 있는 표현(경력 N년 · 학위 · 어학)은 따로
표시한다. 한 대기업 공고의 "학계 1년 이상" 을 매칭 점수만 보고 놓친 일이
있었다. 충족하는지는 판단하지 않는다 — 문장을 찾아 눈에 띄게 할 뿐이다.
"""

import re
from datetime import date, datetime, timedelta

from . import certificates as certificate_service
from . import jd as jd_service


# --------------------------------
# 단서
# --------------------------------

DEADLINE_WORDS = (
    "마감", "접수기간", "접수 기간", "지원기간", "지원 기간", "모집기간",
    "모집 기간", "서류접수", "접수", "까지", "~",
)

ROLLING_WORDS = (
    "상시채용", "상시모집", "수시채용", "수시모집", "채용시마감", "채용시까지",
)

QUALIFICATION_HEADERS = (
    "지원자격", "자격요건", "필수요건", "우대사항", "모집전공", "공통지원자격",
    "지원요건", "이런분을찾고있어요", "필수조건", "우대조건",
)

SECTION_BREAKS = (
    "전형절차", "근무조건", "복리후생", "제출서류", "접수방법", "유의사항",
    "수행업무", "담당업무", "주요업무", "어떤일을", "기타사항", "근무지",
)

STRONG_TITLE = re.compile(r"채용|모집|공고|인턴십|인턴")
WEAK_TITLE = re.compile(
    r"부문|직무|포지션|Engineer|Scientist|Analyst|Developer|개발자|분석가|기획자|연구원"
)

ORGANIZATION = re.compile(
    r"(㈜\s*[\w가-힣&]+|\(주\)\s*[\w가-힣&]+|주식회사\s*[\w가-힣&]+|[\w가-힣&]+\s*주식회사)"
)
LABELED = re.compile(r"^(회사명|기업명|기관명|회사|주최|주관|근무지역|근무지|근무 장소|근무장소)\s*[:：]?\s*(.+)$")

EMPLOYMENT = (
    ("체험형 인턴", "체험형 인턴"),
    ("채용연계형", "채용연계형 인턴"),
    ("인턴", "인턴"),
    ("정규직", "정규직"),
    ("계약직", "계약직"),
    ("신입", "신입"),
)

COMPETITION = re.compile(r"공모전|경진대회|해커톤|챌린지")
ACTIVITY = re.compile(r"대외활동|서포터즈|기자단|봉사단|앰버서더")

# 걸림돌이 될 수 있는 자격 표현.
FLAGS = (
    ("career", "경력 요건", re.compile(r"\d+\s*년\s*이상|경력\s*\d+\s*년|경력자|학계|실무\s*경력")),
    ("degree", "학력 · 졸업 요건", re.compile(r"석사|박사|학위|졸업\s*예정|졸업자|기졸업")),
    ("language", "어학 요건", re.compile(r"OPIc|오픽|토익|TOEIC|토익스피킹|TOEFL|IELTS|어학|영어회화")),
    ("license", "자격증 요건", re.compile(r"자격증\s*(필수|소지)|기사\s*자격|자격\s*소지")),
)

FULL_DATE = re.compile(
    r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?"
    r"(?:\s*\([^)]{1,4}\))?"
    r"(?:\s*(\d{1,2})\s*[:시]\s*(\d{2})?)?"
)
SHORT_DATE = re.compile(
    r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일"
    r"(?:\s*\([^)]{1,4}\))?"
    r"(?:\s*(\d{1,2})\s*[:시]\s*(\d{2})?)?"
)

BULLETS = "□■●○◆◇▶▷-·*•※ \t"


def _compact(line: str) -> str:
    return re.sub(r"\s+", "", line)


def _clean(line: str) -> str:
    return line.strip().lstrip(BULLETS).strip()


def _field(value="", evidence="", note=None):
    return {"value": value, "found": bool(value), "evidence": evidence, "note": note}


# --------------------------------
# 마감
# --------------------------------

def _dates_in(line: str, today: date) -> list[tuple[int, datetime, bool, bool]]:
    """(위치, 날짜, 연도를 짐작했는가, 시각이 있었는가)."""
    found = []
    spans = []

    for match in FULL_DATE.finditer(line):
        year, month, day = (int(match.group(i)) for i in (1, 2, 3))
        hour = int(match.group(4)) if match.group(4) else None
        minute = int(match.group(5)) if match.group(5) else 0

        try:
            value = datetime(year, month, day, 23 if hour is None else hour, 59 if hour is None else minute)
        except ValueError:
            continue

        found.append((match.start(), value, False, hour is not None))
        spans.append(match.span())

    for match in SHORT_DATE.finditer(line):
        if any(start <= match.start() < end for start, end in spans):
            continue

        month, day = int(match.group(1)), int(match.group(2))
        hour = int(match.group(3)) if match.group(3) else None
        minute = int(match.group(4)) if match.group(4) else 0

        try:
            value = datetime(today.year, month, day, 23 if hour is None else hour, 59 if hour is None else minute)
        except ValueError:
            continue

        # 반년 넘게 지난 날짜면 내년 공고로 본다.
        if value.date() < today - timedelta(days=180):
            value = value.replace(year=today.year + 1)

        found.append((match.start(), value, True, hour is not None))

    found.sort(key=lambda item: item[0])

    return found


def _deadline(lines: list[str], today: date) -> dict:
    for line in lines:
        if not any(word in line for word in DEADLINE_WORDS):
            continue

        dates = _dates_in(line, today)

        if not dates:
            continue

        # 기간(9.8 ~ 9.15)이면 끝나는 날이 마감이다.
        _, value, guessed_year, had_time = dates[-1]

        notes = []
        if guessed_year:
            notes.append(f"연도가 없어 {value.year}년으로 봤어요")
        if not had_time:
            notes.append("시각이 없어 23:59 로 봤어요")

        return {
            "value": value.isoformat(timespec="minutes"),
            "found": True,
            "rolling": False,
            "evidence": line,
            "note": " · ".join(notes) or None,
        }

    for line in lines:
        if any(word in _compact(line) for word in ROLLING_WORDS):
            return {
                "value": None,
                "found": False,
                "rolling": True,
                "evidence": line,
                "note": "상시 · 수시 채용으로 보여 마감일을 비워 뒀어요.",
            }

    return {
        "value": None,
        "found": False,
        "rolling": False,
        "evidence": "",
        "note": "마감일을 찾지 못했어요. 공고를 보고 직접 넣어 주세요.",
    }


# --------------------------------
# 지원 자격
# --------------------------------

def _qualifications(lines: list[str]) -> list[str]:
    collected = []
    capturing = False
    taken = 0

    for line in lines:
        cleaned = _clean(line)
        compact = _compact(cleaned)

        header = next((h for h in QUALIFICATION_HEADERS if compact.startswith(h)), None)

        if header:
            capturing = True
            taken = 0
            rest = re.sub(r"^[^:：]*[:：]\s*", "", cleaned) if re.search(r"[:：]", cleaned) else ""
            if rest and rest not in collected:
                collected.append(rest)
            continue

        if capturing and any(compact.startswith(word) for word in SECTION_BREAKS):
            capturing = False
            continue

        if capturing and cleaned:
            if cleaned not in collected:
                collected.append(cleaned)
            taken += 1
            if taken >= 15:
                capturing = False

    return collected


def find_requirement_flags(text: str) -> list[dict]:
    """걸림돌이 될 수 있는 자격 표현이 있는 줄.

    자격 머리글 아래를 먼저 보고, 머리글이 없으면 글 전체를 본다.
    """
    lines = [_clean(line) for line in (text or "").splitlines() if line.strip()]
    scope = _qualifications(lines) or lines

    flags = []
    seen = set()

    for line in scope:
        for key, label, pattern in FLAGS:
            if pattern.search(line) and (key, line) not in seen:
                seen.add((key, line))
                flags.append({"kind": key, "label": label, "line": line})

    return flags


# --------------------------------
# 제목 · 회사 · 종류
# --------------------------------

def _title(lines: list[str]) -> dict:
    head = [line for line in lines[:15] if len(line) <= 80]

    for pattern in (STRONG_TITLE, WEAK_TITLE):
        line = next((item for item in head if pattern.search(item)), None)
        if line:
            return _field(_clean(line), line)

    return _field(note="제목으로 볼 줄을 찾지 못했어요.")


def _labeled(lines: list[str], names: tuple[str, ...]) -> tuple[str, str]:
    for line in lines:
        match = LABELED.match(_clean(line))
        if match and match.group(1) in names:
            value = match.group(2).strip()
            if value and len(value) <= 40:
                return value, line
    return "", ""


def _organization(lines: list[str]) -> dict:
    value, evidence = _labeled(lines, ("회사명", "기업명", "기관명", "회사", "주최", "주관"))
    if value:
        return _field(value, evidence)

    for line in lines[:20]:
        match = ORGANIZATION.search(line)
        if match:
            return _field(match.group(1).strip(), line)

    return _field(note="회사 이름을 찾지 못했어요. 직접 넣어 주세요.")


def _location(lines: list[str]) -> dict:
    value, evidence = _labeled(lines, ("근무지역", "근무지", "근무 장소", "근무장소"))
    return _field(value, evidence)


def _employment(text: str) -> dict:
    for needle, label in EMPLOYMENT:
        if needle in text:
            return _field(label, needle)
    return _field()


def _kind(text: str) -> dict:
    if COMPETITION.search(text):
        return {"value": "competition", "found": True, "evidence": COMPETITION.search(text).group(0), "note": None}
    if ACTIVITY.search(text):
        return {"value": "external_activity", "found": True, "evidence": ACTIVITY.search(text).group(0), "note": None}
    return {"value": "job", "found": False, "evidence": "", "note": "공모전 · 대외활동 표현이 없어 채용 공고로 봤어요."}


# --------------------------------
# 전체
# --------------------------------

def parse_posting(db, text: str, url: str = "", today: date | None = None) -> dict:
    today = today or date.today()
    text = text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    skills = [
        {"id": item["skill_id"], "name": item["skill"], "mentions": item["mentions"]}
        for item in jd_service.extract_skills(db, text)
    ]

    qualifications = _qualifications(lines)
    flags = find_requirement_flags(text)
    deadline = _deadline(lines, today)

    warnings = []

    if not skills:
        warnings.append(
            "등록된 스킬을 본문에서 찾지 못했어요. 저장 뒤 공고에 스킬을 직접 연결하지 "
            "않으면 수요 계산에서 분모만 늘어납니다."
        )
    if not qualifications:
        warnings.append("지원 자격 머리글을 찾지 못했어요. 자격 요건은 공고 원문에서 직접 확인하세요.")

    return {
        "title": _title(lines),
        "organization": _organization(lines),
        "opportunity_type": _kind(text),
        "employment_type": _employment(text),
        "location": _location(lines),
        "deadline": deadline,
        "skills": skills,
        "qualifications": qualifications,
        "requirement_flags": flags,
        "my_certificates": certificate_service.relevant(db, flags, today),
        "warnings": warnings,
        "source_url": url.strip(),
        "length": len(text),
    }
