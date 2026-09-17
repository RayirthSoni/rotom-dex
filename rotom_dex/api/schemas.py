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
    """Body of a 400, 404 or 503 response."""

    detail: str


class ValidationError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationProblem(BaseModel):
    """Body of a 422 response. FastAPI's validation shape differs from `Problem`."""

    detail: list[ValidationError]


class ChatLimits(BaseModel):
    max_message_chars: int
    max_history_turns: int
    max_tool_calls: int
    deadline_s: float


class ChatStatus(BaseModel):
    """Whether Rotom can answer. The Dex, team and preparation endpoints never consult this."""

    enabled: bool
    provider: str
    model: str | None = None
    research_enabled: bool = False
    reason: str = ""
    limits: ChatLimits
