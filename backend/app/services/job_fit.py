"""이 공고가 데이터 · AI 직무인가 — 모집 부문 하나하나를 본다.

전에는 공고 전체에서 "데이터 분석" 같은 말이 한 번이라도 나오면 들여왔다.
요즘은 마케팅 · 영업 · 생산 직무 설명에도 "데이터 분석 기반 …" 이 흔히 들어가서,
2026-09-17 고용24 공채속보에서 들여온 18건 중 10건이 건강식품 온라인 영업,
홈쇼핑 MD, 타이어 생산기술, 공장 미생물팀 같은 것이었다. 그 한 줄 때문에 스킬이
"데이터 분석" 하나만 연결돼, 요구 스킬을 100% 갖춘 것으로 계산되어 88점까지 나왔다.

그래서 **부문마다** 판단한다. 여러 부문을 한꺼번에 뽑는 대기업 공채는 한 부문만
맞아도 들이고, 맞는 부문이 무엇인지 남긴다.

한 부문이 맞으려면 (위에서부터)
  1. 부문 이름에 빼는 말(영업 · 마케팅 · 생산 · 품질 …)이 없어야 하고
  2. 경력만 뽑는 부문이 아니어야 하고 (2027-02 졸업 예정 신입)
  3. 셋 중 하나
     - 부문 이름에 데이터 · AI 직무 말이 있다            ("데이터 사이언티스트", "AI/DX 전략")
     - 부문 이름이 IT · 개발 계열이고 설명에 데이터 말이 있다 ("IT" + "데이터 기반 AI 모델 개발")
     - 설명에 직무를 특정하는 말이 있다                  ("머신러닝", "채권모형 개발")

AI 판단이 아니라 규칙이다. 앱에는 아직 LLM 을 넣지 않기로 했고(DECISIONS 17장),
규칙이면 왜 뺐는지 한 줄로 댈 수 있다. 틀리게 뺀 공고는 사람이 "그래도 검토" 로 되살린다.
"""

import re


# 부문 이름에 있으면 데이터 · AI 직무다.
CORE_NAME_WORDS = (
    "데이터", "data", "ai", "인공지능", "머신러닝", "딥러닝", "빅데이터", "dx",
    "애널리스트", "analyst", "사이언티스트", "scientist", "ml", "llm", "nlp", "추천",
)

# 부문 이름이 이 계열이면, 설명에 데이터 말이 있을 때만 맞다.
TECH_NAME_WORDS = ("it", "디지털", "전산", "개발", "시스템", "sw", "소프트웨어", "정보")

# 설명에 있으면 데이터 계열 일이 섞여 있다는 뜻. 혼자로는 약하다.
WEAK_JOB_WORDS = (
    "데이터 분석", "데이터분석", "빅데이터", "데이터 파이프라인", "데이터 기반",
    "ai", "인공지능", "data 분석", "데이터 엔지니어링",
)

# 설명에 있으면 직무 자체가 데이터 · AI 다. 혼자로도 충분하다.
STRONG_JOB_WORDS = (
    "데이터 사이언티스트", "데이터사이언티스트", "데이터 엔지니어", "머신러닝", "딥러닝",
    "ai 모델", "추천시스템", "추천 시스템", "nlp", "llm", "mlops", "컴퓨터비전",
    "모형 개발", "모델 개발", "모델링", "통계 분석",
)

# 부문 이름에 있으면 설명과 상관없이 뺀다.
EXCLUDE_NAME_WORDS = (
    "영업", "마케팅", "md", "pd", "생산", "품질", "qc", "설비", "포장", "미생물",
    "보상", "인사", "구매", "물류", "회계", "재무", "크리에이터", "creator", "콘텐츠",
    "디자인", "완전성", "밸리데이션", "보건", "제조", "조리",
)


def _has(text: str, words) -> list[str]:
    """단어 경계를 지켜 찾는다. 영문 짧은 말("ai", "it", "md")이 다른 낱말에 걸리지 않게."""
    found = []
    lowered = (text or "").lower()
    for word in words:
        if re.fullmatch(r"[a-z]+", word):
            if re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", lowered):
                found.append(word)
        elif word in lowered:
            found.append(word)
    return found


def _career_only(career: str) -> bool:
    parts = {part.strip() for part in (career or "").split("|") if part.strip()}
    return parts == {"경력"}


def judge_section(name: str, career: str = "", job: str = "") -> tuple[bool, str]:
    """(맞는가, 이유). 이유는 화면에 그대로 보인다."""
    excluded = _has(name, EXCLUDE_NAME_WORDS)
    if excluded:
        return False, f"{name} — 데이터 · AI 직무가 아니에요"

    if _career_only(career):
        return False, f"{name} — 경력만 뽑아요"

    if _has(name, CORE_NAME_WORDS):
        return True, f"{name} — 부문 이름이 데이터 · AI 직무"

    if _has(name, TECH_NAME_WORDS) and _has(job, WEAK_JOB_WORDS + STRONG_JOB_WORDS):
        return True, f"{name} — IT 부문에 데이터 · AI 일이 있어요"

    strong = _has(job, STRONG_JOB_WORDS)
    if strong:
        return True, f"{name} — 하는 일에 '{strong[0]}'"

    return False, f"{name} — 데이터 · AI 직무가 아니에요"


def judge_sections(sections: list[dict]) -> dict:
    """공고 하나. sections: [{name, career, job}]"""
    kept, dropped = [], []

    for section in sections:
        ok, why = judge_section(
            section.get("name", ""), section.get("career", ""), section.get("job", "")
        )
        (kept if ok else dropped).append({**section, "why": why})

    return {"fits": bool(kept), "kept": kept, "dropped": dropped, "reason": reason_of(kept, dropped)}


def reason_of(kept: list[dict], dropped: list[dict]) -> str:
    if kept:
        return ""

    if len(dropped) == 1:
        return dropped[0]["why"]

    names = ", ".join(section["name"] for section in dropped[:4])
    more = f" 외 {len(dropped) - 4}개" if len(dropped) > 4 else ""
    career_only = all("경력만" in section["why"] for section in dropped)
    tail = "모두 경력만 뽑아요" if career_only else "모두 데이터 · AI 직무가 아니에요"
    return f"모집 부문 {len(dropped)}개({names}{more}) {tail}"


# 저장된 설명에서 부문을 다시 읽는다 — 이미 들여온 공고를 다시 판단할 때 쓴다.
# work24.normalize 가 쓰는 형식: "모집 부문: 이름 · 경력 · 지역 — 하는 일"
_SECTION_LINE = re.compile(r"^모집 부문: (?P<head>.*?)(?: — (?P<job>.*))?$")
_CAREER = re.compile(r"^(신입|경력|인턴|무관|경력무관)(\|(신입|경력|인턴|무관|경력무관))*$")


def parse_sections(description: str) -> list[dict]:
    sections = []

    for line in (description or "").splitlines():
        match = _SECTION_LINE.match(line.strip())
        if not match:
            continue

        parts = [part for part in match.group("head").split(" · ")]
        name = parts[0] if parts else ""
        career = next((part for part in parts[1:] if _CAREER.match(part.strip())), "")

        sections.append({"name": name, "career": career, "job": match.group("job") or ""})

    return sections
