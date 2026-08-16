"""Evaluator execution interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from agentgate.domain import Case, EvaluatorSpec, Kind, Trace

from .models import Evaluation, ResultResolver


class Evaluator(ABC):
    kind: ClassVar[Kind]
    evaluator_type: ClassVar[str]

    def applies_to(self, spec: EvaluatorSpec, case: Case) -> bool:
        return True

    @abstractmethod
    def evaluate(
        self, spec: EvaluatorSpec, case: Case, trace: Trace, resolve: ResultResolver
    ) -> Evaluation:
        raise NotImplementedError
