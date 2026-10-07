"""공고에 적힌 도구 중 **내 스킬 목록에 없는 것**을 찾는다.

수요 계산은 등록된 스킬만 센다. 목록에 없으면 공고에 몇 번 나오든 0건이다.
그래서 앱은 **모르는 도구를 영원히 모른다** — 가장 중요한 것이 빠져 있어도
순위표는 멀쩡해 보인다.

2026-10-05 에 실제로 재 봤다. 데이터 · AI 공고 80건 중 —
  ETL · 데이터 파이프라인  20건 (25%)  목록에 없음  ← 넣으면 3위권
  GCP                      9건 (11%)  없음 (Azure 는 있는데 0건)
  데이터 시각화             8건 (10%)  없음
  BigQuery                 7건  (9%)  없음
수요 분모를 아무리 고쳐도 순위가 안 바뀌던 이유가 이것이었다. 같은 22개를
세는 한 비율만 같이 커질 뿐 순서는 그대로다.

**규칙이고 세기만 한다.** 본문에 있는 말만 세고, 없는 것을 지어내지 않는다.
LLM 을 쓰지 않는다 (DECISIONS 17장) — 왜 세어졌는지 한 줄로 댈 수 있어야 한다.

목록을 늘리는 것은 사람이 한다. 앱은 "이게 이만큼 나오는데 목록에 없어요"
까지만 말한다. 자동으로 스킬을 만들면 오타와 동의어가 그대로 쌓인다.
"""

import re

from .. import models
from . import market


# 공고에서 찾을 도구 · 역량. 이름 → 본문에서 알아보는 정규식.
#
# 한국어 표기를 같이 넣는다. 영문만 찾으면 "파이썬" 이라고만 쓴 공고를 놓친다
# (실제로 Statistics 가 "통계" 로만 적힌 공고 14건을 놓치고 있었다).
TERMS: dict[str, str] = {
    # 언어 · 질의
    "Python": r"\bPython\b|파이썬",
    "SQL": r"\bSQL\b",
    "Java": r"\bJava\b(?!Script)",
    "Scala": r"\bScala\b",
    # 데이터 엔지니어링
    "ETL · 데이터 파이프라인": r"\bE[TL]L\b|데이터\s*파이프라인|data\s*pipeline",
    "Spark": r"\bSpark\b|스파크",
    "Hadoop": r"\bHadoop\b|하둡",
    "Kafka": r"\bKafka\b|카프카",
    "Airflow": r"\bAirflow\b",
    "dbt": r"\bdbt\b",
    "데이터 모델링": r"데이터\s*모델링|data\s*model",
    # 창고 · 분석 플랫폼
    "BigQuery": r"\bBigQuery\b",
    "Snowflake": r"\bSnowflake\b",
    "Redshift": r"\bRedshift\b",
    # 클라우드 · 운영
    "AWS": r"\bAWS\b|아마존\s*웹",
    "GCP": r"\bGCP\b|Google\s*Cloud",
    "Azure": r"\bAzure\b",
    "Docker": r"\bDocker\b|도커",
    "Kubernetes": r"\bKubernetes\b|\bK8s\b|쿠버네티스",
    "Linux": r"\bLinux\b|리눅스",
    "CI/CD": r"\bCI\s*/\s*CD\b",
    "Terraform": r"\bTerraform\b",
    "MLOps": r"\bMLOps\b|\bLLMOps\b",
    "MLflow": r"\bMLflow\b",
    # 분석
    "Statistics": r"통계|\bStatistic",
    "A/B 테스트": r"A\s*/?\s*B\s*테스트|\bA/B\s*test",
    "데이터 시각화": r"시각화|Visuali[sz]ation",
    "Tableau": r"\bTableau\b|태블로",
    "Power BI": r"Power\s*BI",
    "Looker": r"\bLooker\b",
    "Time Series": r"시계열|Time\s*Series",
    "Pandas": r"\bPandas\b|판다스",
    "NumPy": r"\bNumPy\b",
    "scikit-learn": r"scikit-?learn|사이킷런",
    # 모델
    "Machine Learning": r"머신\s*러닝|Machine\s*Learning|기계\s*학습",
    "Deep Learning": r"딥\s*러닝|Deep\s*Learning",
    "PyTorch": r"\bPyTorch\b|파이토치",
    "TensorFlow": r"\bTensorFlow\b|텐서플로",
    "NLP": r"\bNLP\b|자연어",
    "Computer Vision": r"컴퓨터\s*비전|Computer\s*Vision",
    "추천시스템": r"추천\s*시스템|\bRecommend",
    "Reinforcement Learning": r"강화\s*학습|Reinforcement\s*Learning",
    "Transformers": r"\bTransformer|트랜스포머",
    # LLM 계열
    "LLM": r"\bLLM\b|거대\s*언어|대규모\s*언어",
    "생성형 AI": r"생성형\s*AI|\bGenAI\b|Generative\s*AI",
    "Prompt Engineering": r"프롬프트\s*엔지니어링|Prompt\s*Engineering",
    "RAG": r"\bRAG\b|검색\s*증강",
    "Vector DB": r"벡터\s*(DB|데이터베이스)|Pinecone|FAISS|Milvus|Chroma",
    "LangChain": r"\bLangChain\b|랭체인",
    "Hugging Face": r"Hugging\s*Face|허깅페이스",
    "AI Agent": r"\bAI\s*Agent|에이전트",
}

_COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in TERMS.items()}

# 이보다 적게 나오면 알리지 않는다. 한두 건은 그 회사 사정이지 시장이 아니다.
MIN_MENTIONS = 3


def _normalize(name: str) -> str:
    """같은 것을 다르게 적은 걸 같게 본다 — 공백 · 대소문자 · 가운뎃점."""
    return re.sub(r"[\s·/\-_]+", "", name).lower()


def scan(db, today=None) -> dict:
    """수요로 세는 공고의 본문에서 도구를 센다.

    모집단은 `market.demand_opportunities` 와 **같다.** 다른 모집단에서
    세면 "25%" 가 순위표의 % 와 다른 뜻이 되어 나란히 놓을 수 없다.
    """
    rows = market.demand_opportunities(db, today)
    total = len(rows)

    documents = [
        f"{row.title or ''}\n{row.description or ''}"
        for row in rows
    ]

    known = {_normalize(skill.name) for skill in db.query(models.Skill).all()}

    found = []

    for name, pattern in _COMPILED.items():
        count = sum(1 for text in documents if pattern.search(text))

        if not count:
            continue

        found.append({
            "name": name,
            "count": count,
            "percentage": round(count / total * 100) if total else 0,
            "in_my_skills": _normalize(name) in known,
        })

    found.sort(key=lambda item: -item["count"])

    missing = [
        item for item in found
        if not item["in_my_skills"] and item["count"] >= MIN_MENTIONS
    ]

    # 목록에 있는데 공고에 한 번도 안 나오는 것. 빼라는 말이 아니라,
    # **이걸 왜 올려뒀는지** 한 번 보라는 뜻이다. 공부할 이유가 시장
    # 수요가 아닐 수도 있다 (수업 과목이라든지).
    seen = {_normalize(item["name"]) for item in found}

    unused = sorted(
        skill.name
        for skill in db.query(models.Skill).all()
        if _normalize(skill.name) not in seen
        and not _mentioned(skill.name, documents)
    )

    return {
        "scanned": total,
        "missing": missing,
        "unused": unused,
        "found": found,
    }


def _mentioned(name: str, documents: list[str]) -> bool:
    """목록에 있는 스킬 이름이 본문에 그대로 나오는가.

    TERMS 에 없는 스킬도 사람이 직접 적어 넣었을 수 있다. 그것까지
    "안 나온다" 고 말하면 틀린다.
    """
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    return any(pattern.search(text) for text in documents)
