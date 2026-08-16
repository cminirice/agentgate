"""Evaluation Cases and Datasets."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from .base import DomainModel, FrozenJsonObject
from .expectation import Expectation


def utcnow() -> datetime:
    return datetime.now(UTC)


class Case(DomainModel):
    id: str
    name: str
    input: FrozenJsonObject
    initial_state: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    expected_skill: str | None = None
    expectations: tuple[Expectation, ...] = ()
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    policy_rules: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class Dataset(DomainModel):
    id: str
    name: str
    version: str
    cases: tuple[Case, ...]
    metadata: FrozenJsonObject = Field(default_factory=FrozenJsonObject)
    created_at: datetime = Field(default_factory=utcnow)
