"""Shared immutable contracts for CLI, API, tests and future Web clients."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
from typing import Any, Protocol


@dataclass(frozen=True)
class Inquiry:
    text: str
    domain: str | None = None
    method_id: str | None = None
    casting_method: str | None = None
    input_datetime: str | None = None
    timezone: str | None = None
    location: str | None = None
    # Explicit context; never assume missing keys or null mean a condition is met.
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chart:
    chart_id: str
    casting_method: str
    method_version: str
    # JSON serialized once: caller cannot mutate nested dicts shared by components.
    payload_json: str
    validation_status: str

    def facts(self) -> dict:
        return json.loads(self.payload_json)


@dataclass(frozen=True)
class CastingResult:
    status: str
    chart: Chart | None
    reason: str


@dataclass(frozen=True)
class Claim:
    kind: str  # chart_fact / rule_binding
    reference: str
    key: str
    value_json: str


@dataclass(frozen=True)
class Analysis:
    claims: tuple[Claim, ...]


class InquiryInterpreter(Protocol):
    def interpret(self, inquiry: Inquiry) -> dict: ...


class CastingEngine(Protocol):
    def cast(self, inquiry: Inquiry) -> CastingResult: ...


class ModelGateway(Protocol):
    def analyze(self, inquiry: Inquiry, chart: Chart, rules: tuple[dict, ...]) -> Analysis: ...


class GenerationError(RuntimeError):
    """Transport, truncation or structured-output failure; distinct from evidence error."""


class ModelUnavailable(RuntimeError):
    pass
