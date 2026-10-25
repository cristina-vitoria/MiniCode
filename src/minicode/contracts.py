"""Contratos entre modelo, harness e runner; nenhum deles recebe shell livre."""
from pathlib import Path
from typing import Any, Callable, Protocol, TypedDict


class TestResult(TypedDict, total=False):
    passed: bool
    verified: bool
    tests: int
    discovered: int
    output: str
    error: str
    source_digest: str | None
    revision: int
    returncode: int | None
    timed_out: bool
    seconds: float


class ModelClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class Runner(Protocol):
    @property
    def description(self) -> str: ...

    def run(self) -> TestResult: ...


Acceptance = Callable[[Path], dict[str, Any]]
