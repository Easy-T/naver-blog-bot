"""Deterministic stdlib HTMLParser-based HTML parsing helpers."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterator


class HtmlNode:
    def __init__(
        self,
        tag: str,
        attrs: dict[str, str],
        children: list["HtmlNode | str"],
    ) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children = children

    def class_names(self) -> list[str]:
        raw = self.attrs.get("class", "")
        return raw.split() if raw else []

    def text_content(self) -> str:
        parts: list[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child.text_content())
        return "".join(parts)


# Tags whose content should not be recursed into for text purposes.
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._root = HtmlNode("__root__", {}, [])
        self._stack: list[HtmlNode] = [self._root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {k: (v or "") for k, v in attrs}
        node = HtmlNode(tag, attr_dict, [])
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i].tag == tag:
                self._stack = self._stack[: i + 1]
                self._stack.pop()
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)

    def root(self) -> HtmlNode:
        return self._root


def parse_html(html: str) -> HtmlNode:
    builder = _Builder()
    builder.feed(html)
    return builder.root()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def element_children(node: HtmlNode) -> list[HtmlNode]:
    return [child for child in node.children if isinstance(child, HtmlNode)]


def iter_descendants(node: HtmlNode) -> Iterator[HtmlNode]:
    for child in node.children:
        if isinstance(child, HtmlNode):
            yield child
            yield from iter_descendants(child)


def _matches_tag(node: HtmlNode, tag: str) -> bool:
    return node.tag == tag


def _matches_class(node: HtmlNode, cls: str) -> bool:
    return cls in node.class_names()


def _matches_id(node: HtmlNode, id_val: str) -> bool:
    return node.attrs.get("id", "") == id_val


def matches_selector(node: HtmlNode, selector: str) -> bool:
    """Supports: tag, .class, #id, tag.class."""
    if selector.startswith("#"):
        return _matches_id(node, selector[1:])
    if selector.startswith("."):
        return _matches_class(node, selector[1:])
    if "." in selector:
        tag, cls = selector.split(".", 1)
        return _matches_tag(node, tag) and _matches_class(node, cls)
    return _matches_tag(node, selector)


def select_all(node: HtmlNode, selector: str) -> list[HtmlNode]:
    return [desc for desc in iter_descendants(node) if matches_selector(desc, selector)]


def select_first(node: HtmlNode, selectors: list[str]) -> HtmlNode | None:
    for selector in selectors:
        results = select_all(node, selector)
        if results:
            return results[0]
    return None


def first_title(root: HtmlNode) -> str:
    title_node = select_first(root, ["title"])
    if title_node is None:
        return ""
    raw = normalize_text(title_node.text_content())
    # Strip " : 네이버 블로그" suffix if present
    for suffix in [" : 네이버 블로그", " - 네이버 블로그"]:
        if raw.endswith(suffix):
            return raw[: -len(suffix)]
    return raw
