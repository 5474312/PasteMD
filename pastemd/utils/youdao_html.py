"""Youdao Cloud Note HTML compatibility helpers."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from .html_formatter import extract_html_body

_DISPLAY_MATH_RE = re.compile(r"^\s*\$\$(?P<formula>.*?)\$\$\s*$", re.DOTALL)
_ANY_DISPLAY_MATH_RE = re.compile(r"\$\$(?P<formula>.*?)\$\$", re.DOTALL)


def format_youdao_html(html: str) -> str:
    """Return a clean HTML fragment tailored for Youdao Cloud Note paste."""
    soup = BeautifulSoup(extract_html_body(html), "html.parser")
    _flatten_list_paragraphs(soup)
    _mark_formula_blocks(soup)
    _split_embedded_display_formulas(soup)
    return _fragment_html(soup)


def _flatten_list_paragraphs(soup: BeautifulSoup) -> None:
    """Youdao can garble direct ``<li><p>...</p></li>`` list items."""
    for li in soup.find_all("li"):
        for child in list(li.children):
            if isinstance(child, Tag) and child.name == "p":
                if child.get("yne-bulb-block") == "formula":
                    continue
                if _extract_display_formula(child) is not None:
                    continue
                child.unwrap()


def _mark_formula_blocks(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["p", "div"]):
        if not isinstance(tag, Tag):
            continue
        formula = _extract_display_formula(tag)
        if formula is None:
            continue

        tag["yne-bulb-block"] = "formula"
        tag["yne-bulb-formula-syntax"] = "latex"
        tag["yne-bulb-formula-content"] = formula
        tag.clear()
        tag.append(f"$${formula}$$")


def _split_embedded_display_formulas(soup: BeautifulSoup) -> None:
    """Handle Pandoc output such as ``<li>label $$formula$$</li>``."""
    for text_node in list(soup.find_all(string=_ANY_DISPLAY_MATH_RE)):
        parent = text_node.parent
        if not isinstance(parent, Tag):
            continue
        if parent.get("yne-bulb-block") == "formula":
            continue
        if parent.find_parent(["pre", "code"]) or parent.name in ("pre", "code"):
            continue

        text = str(text_node)
        match = _ANY_DISPLAY_MATH_RE.search(text)
        if not match:
            continue

        formula = _normalize_formula(match.group("formula"))
        if not formula:
            continue

        before = text[: match.start()]
        after = text[match.end() :]
        text_node.replace_with(NavigableString(before))

        formula_tag = _new_formula_tag(soup, formula)
        if parent.name == "li":
            parent.append(formula_tag)
        else:
            parent.insert_after(formula_tag)

        if after.strip():
            formula_tag.insert_after(NavigableString(after))


def _extract_display_formula(tag: Tag) -> str | None:
    text = tag.get_text("", strip=False)
    match = _DISPLAY_MATH_RE.match(text)
    if not match:
        return None

    return _normalize_formula(match.group("formula"))


def _normalize_formula(formula: str) -> str | None:
    formula = formula.strip()
    if not formula:
        return None
    return re.sub(r"\s+", " ", formula)


def _new_formula_tag(soup: BeautifulSoup, formula: str) -> Tag:
    tag = soup.new_tag("p")
    tag["yne-bulb-block"] = "formula"
    tag["yne-bulb-formula-syntax"] = "latex"
    tag["yne-bulb-formula-content"] = formula
    tag.append(f"$${formula}$$")
    return tag


def _fragment_html(soup: BeautifulSoup) -> str:
    body = soup.body
    root = body if body is not None else soup
    parts: list[str] = []
    for child in root.contents:
        if isinstance(child, NavigableString):
            text = str(child)
            if text.strip():
                parts.append(text)
            continue
        parts.append(str(child))
    return "".join(parts).strip()
