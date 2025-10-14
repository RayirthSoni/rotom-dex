"""Extremely small subset of Pydantic required for unit tests."""
from __future__ import annotations

from typing import Any, Dict, Type, TypeVar


T = TypeVar("T", bound="BaseModel")


class BaseModel:
    def __init__(self, **data: Any) -> None:
        for key, value in data.items():
            setattr(self, key, value)

    def dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)

    def model_dump(self) -> Dict[str, Any]:
        return self.dict()

    @classmethod
    def parse_obj(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(**data)

    @classmethod
    def model_validate(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls.parse_obj(data)


def Field(default: Any = ..., **_: Any) -> Any:
    return default


__all__ = ["BaseModel", "Field"]
