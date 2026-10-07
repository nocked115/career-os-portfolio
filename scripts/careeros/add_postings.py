"""주간 공고 묶음을 파일에서 읽어 앱에 넣는다.

  python3 add_postings.py <파일>          # 무엇을 넣을지만 보여준다
  python3 add_postings.py <파일> --apply

GPT 가 매주 주는 목록처럼 **여러 건이 한 덩어리로 된 글**을 받는다.
서버가 공고 단위로 자르고(/opportunities/split) 각각을 해석한다(/opportunities/parse).

해석기가 못 잡는 것을 여기서 보정한다:

  제목이 "1. NAVER Cloud — Video Agent 연구·개발 인턴" 처럼 오면
  회사명을 못 찾는다. 앞의 번호를 떼고 대시 앞을 회사, 뒤를 직무로 나눈다.
  회사명이 비면 선호 회사 점수도, 화면의 회사 칸도 비게 된다 (실제로 17건이 그랬다).

이미 있는 공고는 건너뛴다 — 주소가 같거나, 회사+직무가 같으면 같은 것으로 본다.
"""

import re
import sys

from career_api import Api, norm

DASHES = "—–-"
NUMBER_PREFIX = re.compile(r"^\s*\d+[.)]\s*")

# 해석기가 본문 속 주소를 안 잡는다 — 직접 찾는다.
# 마크다운 링크([글](주소))로 와도 되게 닫는 괄호와 뒤따르는 문장부호를 떼어낸다.
URL = re.compile(r"https?://[^\s<>\]\)]+")


def find_url(block: str) -> str:
    """본문에서 첫 주소를 찾는다. 추적용 꼬리(utm_*)는 떼고 남긴다."""
    match = URL.search(block or "")
    if not match:
        return ""

    url = match.group(0).rstrip(".,;")
    base, sep, query = url.partition("?")
    if not sep:
        return url

    keep = [
        part for part in query.split("&")
        if part and not part.lower().startswith(("utm_", "source="))
    ]
    return base + ("?" + "&".join(keep) if keep else "")


def split_title(raw: str) -> tuple[str, str]:
    """'1. 회사 — 직무' → (회사, 직무). 나눌 수 없으면 (빈 문자열, 원문)."""
    text = NUMBER_PREFIX.sub("", (raw or "").strip())

    for dash in DASHES:
        if dash in text:
            left, _, right = text.partition(dash)
            left, right = left.strip(), right.strip()
            # 회사명이 문장처럼 길면 나눈 게 아니라 제목 안의 대시다.
            if left and right and len(left) <= 24:
                return left, right

    return "", text


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)

    try:
        text = open(args[0], encoding="utf-8").read()
    except OSError as error:
        sys.exit(f"파일을 못 읽었어요: {error}")

    api = Api()

    status, split = api.call("POST", "/opportunities/split", {"text": text})
    if status != 200:
        sys.exit(f"자르지 못했어요 (HTTP {status}): {split}")
    blocks = split.get("blocks") or []
    print(f"{args[0]} 에서 공고 {len(blocks)}건을 찾았어요\n")

    existing = api.get("/opportunities")
    existing = existing if isinstance(existing, list) else existing.get("opportunities", [])
    urls = {str(r.get("source_url") or "").strip().lower() for r in existing if r.get("source_url")}

    def already(org, title, url):
        if url and url.strip().lower() in urls:
            return "같은 주소가 이미 있음"
        for r in existing:
            if norm(r.get("title")) and norm(r.get("title")) == norm(title) \
               and norm(r.get("organization")) == norm(org):
                return f"같은 회사·직무가 이미 있음 (#{r['id']})"
        return None

    plan = []
    for block in blocks:
        status, parsed = api.call("POST", "/opportunities/parse", {"text": block})
        if status != 200:
            print(f"⚠ 해석 실패 (HTTP {status}) — 건너뜁니다")
            continue

        def field(name):
            v = parsed.get(name)
            return (v.get("value") if isinstance(v, dict) else v) or ""

        org = field("organization")
        title = field("title")
        if not org:
            org, title = split_title(title)
        else:
            _, title = split_title(title) if split_title(title)[1] else ("", title)

        row = {
            "opportunity_type": field("opportunity_type") or "job",
            "title": title,
            "organization": org,
            "source": "manual",
            "source_url": field("source_url") or find_url(block),
            "location": field("location"),
            "employment_type": field("employment_type"),
            "deadline": field("deadline") or None,
            "description": block,
        }
        skip = already(org, title, row["source_url"])

        mark = "건너뜀" if skip else "넣음  "
        print(f"  [{mark}] {org or '(회사 못 찾음)':16} {title[:44]}")
        print(f"            마감 {row['deadline'] or '없음':20} {row['employment_type'] or ''} {row['location'][:24]}")
        if skip:
            print(f"            → {skip}")
        else:
            plan.append(row)
        print()

    print(f"새로 넣을 것 {len(plan)}건")
    if not plan:
        return
    if not apply:
        print("지금은 보여주기만 했어요. 넣으려면 --apply 를 붙이세요.")
        return

    for row in plan:
        status, made = api.call("POST", "/opportunities", row)
        if status != 201:
            print(f"⚠ {row['title'][:34]} 실패 (HTTP {status}): {str(made)[:70]}")
            continue
        print(f"✅ #{made['id']} {row['organization']} — {row['title'][:40]}")

    print("\n기회 화면에서 매칭 점수와 판정을 확인하세요.")


if __name__ == "__main__":
    main()
