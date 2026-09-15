"""다른 세션에 넘길 학습 프롬프트.

주차 체크리스트는 Claude 세션이 잘 만든다. 기록 · 진행률 · 규칙은 Career OS 가 맡는다
(DECISIONS 30장). 둘 사이를 잇는 게 이 텍스트다 — 세션에 붙여넣으면 이번 주에 무엇을
해야 하는지, 지금까지 어디까지 했는지, Career OS 가 다시 읽을 수 있는 형식이 무엇인지가
한 번에 들어간다.

지어내지 않는다. 경로 설명 · 단계 · 마감 · 체크리스트는 저장된 그대로 옮기고,
없는 칸은 "없음" 이라고 적는다.
"""

from . import checklist as checklist_service


FORMAT_RULES = """\
Career OS 가 붙여넣기로 읽는 형식 (HTML 아티팩트 기준):
- <h1> 주차 제목 한 줄 → 단계 이름으로 제안된다
- <h2> 묶음 이름 (예: 논문 정독 · 실습 · 발표)
- <li> 체크 항목 — 한 줄에 한 번에 끝낼 수 있는 일 하나. 코드 이름은 <code> 로 감싼다
- <p class="note"> 묶음 설명 (체크하지 않는 안내)
- <a href="https://..."> 자료 링크 (http · https 만)
- 표(<table>) · 버튼 · 스크립트 안의 글자는 가져오지 않는다
- 체크 상태는 저장하지 않아도 된다. Career OS 에 붙여넣은 뒤 거기서 체크한다
Markdown 으로 줄 때: # 제목 / ## 묶음 / - [ ] 항목 / > 설명 / [이름](https://...)"""


def _line(label, value):
    return f"- {label}: {value if value not in (None, '') else '없음'}"


def build_step_handoff(step) -> str:
    path = step.learning_path
    steps = sorted(path.steps, key=lambda item: item.position) if path else [step]
    index = next((i for i, item in enumerate(steps) if item.id == step.id), 0)
    checklist = checklist_service.build_checklist(step)
    progress = checklist["progress"]

    lines = [
        f"# {path.title if path else '학습'} — {step.title} 체크리스트 만들기",
        "",
        "## 이 트랙",
        (path.description or "").strip()
        or "(경로 설명 없음 — Career OS 학습 경로 설명에 목표 · 진행 방식 · 기록 도구를 적어 두면 여기에 들어갑니다)",
        "",
        "## 이번 단계",
        _line("단계", f"{step.title} ({index + 1}/{len(steps)}번째)"),
        _line("마감", step.due_date.isoformat() if step.due_date else None),
        _line("예상 시간", f"{step.estimated_minutes}분" if step.estimated_minutes else None),
        _line("단계 설명", (step.description or "").strip()),
    ]

    lines += ["", "## 지금까지"]
    done_steps = [item.title for item in steps[:index] if item.status == "completed"]
    lines.append(_line("끝낸 이전 단계", ", ".join(done_steps)))

    if progress["total"]:
        lines.append(f"- 이 단계 체크리스트: {progress['total']}개 중 {progress['done']}개 체크")
        remaining = [
            f"  - [ ] {entry['text']}"
            for section in checklist["sections"]
            for entry in section["items"]
            if not entry["done"]
        ]
        if remaining:
            lines.append("- 남은 항목:")
            lines += remaining
        links = [f"  - {link['text']} — {link['url']}" for link in checklist["links"]]
        if links:
            lines.append("- 자료 링크:")
            lines += links
    else:
        lines.append("- 이 단계 체크리스트: 아직 없음")

    lines += [
        "",
        "## 부탁",
        "위 단계를 하루 30~60분 안에 끝낼 수 있는 체크 항목으로 쪼개 주세요.",
        "이미 있는 항목이 있으면 겹치지 않게 남은 부분만 채워 주세요.",
        "결과는 아래 형식의 HTML 아티팩트로 만들어 주세요.",
        "",
        "## 형식",
        FORMAT_RULES,
    ]

    return "\n".join(lines)
