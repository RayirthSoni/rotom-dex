"""Response envelope shared by every endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GameSummary(BaseModel):
    id: int
    slug: str
    name: str
    version_group: str
    generation: int
    support_tier: str


class CoverageRow(BaseModel):
    feature: str
    subject: str
    status: str
    note: str
    evidence_id: str


class Pagination(BaseModel):
    limit: int
    offset: int
    total: int


class Envelope(BaseModel):
    game: GameSummary | None = None
    snapshot_id: str
    coverage_status: str
    coverage: list[CoverageRow] = Field(default_factory=list)
    data: Any = None
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    pagination: Pagination | None = None


class Problem(BaseModel):
    detail: str
