"""Very small subset of BeautifulSoup used for unit testing."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import List, Optional

from bs4.element import Tag


class _SoupParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = Tag("document", attrs={})
        self.stack: List[Tag] = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attr_dict = {name: value for name, value in attrs}
        new_tag = Tag(tag, attr_dict)
        self.stack[-1].append(new_tag)
        self.stack.append(new_tag)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].name == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        self.stack[-1].append_text(data)


class BeautifulSoup(Tag):
    """Parse HTML data into a navigable tree."""

    def __init__(self, markup: str, parser: str = "html.parser") -> None:  # noqa: D401
        self._parser = _SoupParser()
        self._parser.feed(markup)
        super().__init__("document", attrs={})
        self.children = self._parser.root.children
        for child in self.children:
            child.parent = self

    def find_all(self, name: Optional[str] = None, class_: Optional[str] = None):
        matches = []
        for child in self.children:
            if child._matches(name, class_):
                matches.append(child)
            matches.extend(child.find_all(name=name, class_=class_))
        return matches

    def find(self, name: Optional[str] = None, class_: Optional[str] = None):
        for child in self.children:
            if child._matches(name, class_):
                return child
            result = child.find(name=name, class_=class_)
            if result:
                return result
        return None
