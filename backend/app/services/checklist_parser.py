"""붙여넣은 체크리스트를 읽는다 — 규칙 기반.

다른 세션에서 만든 주차 체크리스트(아티팩트 HTML · Markdown · 그냥 줄글)를
붙여넣으면 제목 · 묶음 · 항목 · 자료 링크를 골라 미리보기로 돌려준다.
저장은 하지 않는다. 사람이 미리보기를 고친 뒤 저장한다.

- **붙여넣은 글만 읽는다.** 링크를 열지 않는다.
- 체크 상태는 글에 **적혀 있을 때만** 가져온다 (`[x]`, `checked`).
  아티팩트 화면에서 누른 체크는 파일에 남지 않아 읽을 수 없다.
- 표는 가져오지 않는다. 표의 한 줄이 할 일인지 설명인지 규칙으로 가를 수 없다.
- 링크는 http(s) 만 받는다. 그 밖의 주소는 화면에서 눌렸을 때 위험하다.
"""

import re
from html.parser import HTMLParser


MAX_ITEMS = 200
MAX_TEXT = 300
MAX_SECTION = 120
MAX_LINKS = 30

# 안의 글자가 할 일이 아닌 태그. head 는 넣지 않는다 — <title> 을 읽어야 한다.
SKIP_TAGS = {"script", "style", "svg", "button", "noscript", "template", "select", "textarea"}
SECTION_TAGS = {"h2", "h3", "h4"}

SAFE_URL = re.compile(r"^https?://\S+$")


def _clean(text: str, limit: int = MAX_TEXT) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:limit].strip()


def _new_section(title: str = "") -> dict:
    return {"title": _clean(title, MAX_SECTION), "note": "", "items": []}


class _Result:
    def __init__(self):
        self.title = ""
        self.sections = [_new_section()]
        self.links: list[dict] = []
        self.warnings: list[str] = []
        self.dropped = 0

    @property
    def current(self) -> dict:
        return self.sections[-1]

    def start_section(self, title: str):
        title = _clean(title, MAX_SECTION)
        if not title:
            return
        self.sections.append(_new_section(title))

    def add_item(self, text: str, done: bool = False):
        text = _clean(text)
        if not text:
            return
        if sum(len(section["items"]) for section in self.sections) >= MAX_ITEMS:
            self.dropped += 1
            return
        self.current["items"].append({"text": text, "done": bool(done)})

    def add_note(self, text: str):
        text = _clean(text)
        if not text:
            return
        note = self.current["note"]
        self.current["note"] = f"{note} {text}".strip()[:MAX_TEXT]

    def add_link(self, text: str, url: str):
        url = (url or "").strip()
        if not SAFE_URL.match(url) or len(self.links) >= MAX_LINKS:
            return
        if any(link["url"] == url for link in self.links):
            return
        self.links.append({"text": _clean(text) or url[:MAX_TEXT], "url": url})

    def finish(self) -> dict:
        sections = [s for s in self.sections if s["items"] or s["note"]]
        if self.dropped:
            self.warnings.append(
                f"항목이 {MAX_ITEMS}개를 넘어 뒤의 {self.dropped}개는 가져오지 않았어요."
            )
        return {
            "title": self.title,
            "sections": sections,
            "links": self.links,
            "task_count": sum(len(s["items"]) for s in sections),
            "done_count": sum(1 for s in sections for i in s["items"] if i["done"]),
            "warnings": self.warnings,
        }


# --------------------------------
# HTML (아티팩트)
# --------------------------------

class _HtmlReader(HTMLParser):
    """열린 캡처마다 글자를 모았다가 닫힐 때 결과에 넣는다."""

    def __init__(self, result: _Result):
        super().__init__(convert_charrefs=True)
        self.result = result
        self.skip = 0
        self.stack: list[dict] = []
        self.document_title = ""

    def _open(self, tag, kind, **extra):
        self.stack.append({"tag": tag, "kind": kind, "buf": [], **extra})

    def _open_li(self):
        return next((cap for cap in reversed(self.stack) if cap["kind"] == "item"), None)

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return

        attributes = dict(attrs)
        classes = attributes.get("class") or ""

        if tag == "title":
            self._open(tag, "document_title")
        elif tag == "h1":
            self._open(tag, "title")
        elif tag in SECTION_TAGS:
            self._open(tag, "section")
        elif tag == "li":
            parent = self._open_li()
            if parent is not None:
                # 목록 안의 목록 — 부모 줄을 먼저 끊어 넣는다.
                self.result.add_item("".join(parent["buf"]), parent["done"])
                parent["buf"] = []
            self._open(tag, "item", done=False)
        elif tag == "input":
            item = self._open_li()
            if item is not None and attributes.get("type") == "checkbox" and "checked" in attributes:
                item["done"] = True
        elif tag == "a":
            href = attributes.get("href") or ""
            self._open(tag, "link", url=href)
        elif tag in ("p", "div", "span") and "note" in classes and self._open_li() is None:
            self._open(tag, "note")
        elif tag == "code":
            self._append("`")
        elif tag == "br":
            self._append(" ")

    def handle_startendtag(self, tag, attrs):
        # <input ... /> 같은 빈 태그. 여는 태그와 같게 다룬다.
        self.handle_starttag(tag, attrs)
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return

        if tag == "code":
            self._append("`")
            return

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                capture = self.stack.pop(index)
                self._close(capture)
                return

    def handle_data(self, data):
        if not self.skip:
            self._append(data)

    def _append(self, text):
        for capture in self.stack:
            capture["buf"].append(text)

    def _close(self, capture):
        text = "".join(capture["buf"])
        kind = capture["kind"]

        if kind == "document_title":
            self.document_title = _clean(text)
        elif kind == "title":
            if not self.result.title:
                self.result.title = _clean(text)
        elif kind == "section":
            self.result.start_section(text)
        elif kind == "item":
            self.result.add_item(text, capture["done"])
        elif kind == "note":
            self.result.add_note(text)
        elif kind == "link":
            self.result.add_link(text, capture["url"])


def _parse_html(text: str) -> dict:
    result = _Result()
    reader = _HtmlReader(result)
    reader.feed(text)
    reader.close()

    if not result.title and reader.document_title:
        result.title = reader.document_title

    return result.finish()


# --------------------------------
# Markdown · 줄글
# --------------------------------

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
CHECKBOX = re.compile(r"^(?:[-*+]\s+)?\[([ xX✓✔])\]\s+(.*)$")
BOX = re.compile(r"^([☐□◻⬜☑✅✔✓])\s*(.*)$")
BULLET = re.compile(r"^(?:[-*+•·▪◦]|\d+[.)])\s+(.*)$")
MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
BARE_URL = re.compile(r"^(https?://\S+)$")
RULE = re.compile(r"^[-=*_]{3,}$")

DONE_BOXES = {"☑", "✅", "✔", "✓"}


def _strip_markup(text: str, result: _Result) -> str:
    for label, url in MD_LINK.findall(text):
        result.add_link(label, url)
    text = MD_LINK.sub(lambda match: match.group(1), text)
    return text.replace("**", "").replace("__", "")


def _parse_text(text: str) -> dict:
    result = _Result()
    table_rows = 0

    for raw in text.splitlines():
        line = raw.strip()

        if not line or RULE.match(line):
            continue

        if line.startswith("|"):
            table_rows += 1
            continue

        heading = HEADING.match(line)
        if heading:
            content = _strip_markup(heading.group(2), result)
            if len(heading.group(1)) == 1 and not result.title:
                result.title = _clean(content)
            else:
                result.start_section(content)
            continue

        if line.startswith(">"):
            result.add_note(_strip_markup(line.lstrip("> "), result))
            continue

        bare = BARE_URL.match(line)
        if bare:
            result.add_link("", bare.group(1))
            continue

        only_link = MD_LINK.fullmatch(line.lstrip("-*+ ").strip())
        if only_link:
            result.add_link(only_link.group(1), only_link.group(2))
            continue

        checkbox = CHECKBOX.match(line)
        if checkbox:
            result.add_item(
                _strip_markup(checkbox.group(2), result),
                checkbox.group(1).strip() != "",
            )
            continue

        box = BOX.match(line)
        if box:
            result.add_item(_strip_markup(box.group(2), result), box.group(1) in DONE_BOXES)
            continue

        bullet = BULLET.match(line)
        if bullet:
            result.add_item(_strip_markup(bullet.group(1), result))
            continue

        content = _strip_markup(line, result)

        # "수업 실습:" 처럼 짧고 콜론으로 끝나면 묶음 이름으로 본다.
        if content.endswith(":") and len(content) <= 60:
            result.start_section(content[:-1])
        else:
            result.add_item(content)

    if table_rows:
        result.warnings.append(
            f"표 {table_rows}줄은 가져오지 않았어요. 할 일이면 목록으로 적어 주세요."
        )

    return result.finish()


def looks_like_html(text: str) -> bool:
    return bool(re.search(r"<(html|body|ul|ol|li|h1|h2|div|section)\b", text, re.IGNORECASE))


def parse_checklist(text: str) -> dict:
    """붙여넣은 글 → {title, sections[{title, note, items[{text, done}]}], links, …}."""
    text = text or ""
    parsed = _parse_html(text) if looks_like_html(text) else _parse_text(text)
    parsed["format"] = "html" if looks_like_html(text) else "text"

    if parsed["task_count"] == 0:
        parsed["warnings"].append("체크할 항목을 찾지 못했어요. 한 줄에 할 일 하나씩 적어 주세요.")

    return parsed
