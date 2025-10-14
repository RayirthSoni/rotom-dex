"""A tiny subset of BeautifulSoup's element API for testing purposes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional


def _normalise_classes(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part for part in value.split() if part]


@dataclass
class Tag:
    name: str
    attrs: Dict[str, str] | None = None
    parent: Optional["Tag"] = None
    children: List["Tag"] = field(default_factory=list)
    _text_parts: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.attrs is None:
            self.attrs = {}
        if "class" in self.attrs and not isinstance(self.attrs["class"], list):
            self.attrs["class"] = _normalise_classes(self.attrs["class"])

    @property
    def text(self) -> str:
        chunks = list(self._text_parts)
        for child in self.children:
            chunks.append(child.text)
        return "".join(chunks).strip()

    def get(self, key: str, default=None):
        return self.attrs.get(key, default)

    def __getitem__(self, key: str):
        return self.attrs[key]

    # Search helpers -----------------------------------------------------------------
    def _matches(self, name: Optional[str], class_: Optional[Iterable[str] | str]) -> bool:
        if name and self.name != name:
            return False
        if class_:
            classes = self.attrs.get("class", [])
            if isinstance(classes, str):
                classes = _normalise_classes(classes)
            if isinstance(class_, str):
                required = _normalise_classes(class_)
            else:
                required = list(class_)
            if not all(item in classes for item in required):
                return False
        return True

    def find_all(self, name: Optional[str] = None, class_: Optional[str] = None) -> List["Tag"]:
        matches: List[Tag] = []
        for child in self.children:
            if child._matches(name, class_):
                matches.append(child)
            matches.extend(child.find_all(name=name, class_=class_))
        return matches

    def find(self, name: Optional[str] = None, class_: Optional[str] = None) -> Optional["Tag"]:
        for child in self.children:
            if child._matches(name, class_):
                return child
            result = child.find(name=name, class_=class_)
            if result:
                return result
        return None

    # Sibling navigation --------------------------------------------------------------
    def find_next_sibling(self, name: Optional[str] = None, class_: Optional[str] = None):
        if not self.parent:
            return None
        siblings = self.parent.children
        for idx, candidate in enumerate(siblings):
            if candidate is self and idx + 1 < len(siblings):
                for sibling in siblings[idx + 1 :]:
                    if sibling._matches(name, class_):
                        return sibling
        return None

    def find_previous_sibling(self, name: Optional[str] = None, class_: Optional[str] = None):
        if not self.parent:
            return None
        siblings = self.parent.children
        for idx, candidate in enumerate(siblings):
            if candidate is self and idx > 0:
                for sibling in reversed(siblings[:idx]):
                    if sibling._matches(name, class_):
                        return sibling
        return None

    # Convenience ---------------------------------------------------------------------
    def append(self, child: "Tag") -> None:
        self.children.append(child)
        child.parent = self

    def append_text(self, text: str) -> None:
        if text:
            self._text_parts.append(text)
