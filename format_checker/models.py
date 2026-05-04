from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Severity = Literal["error", "warning", "info"]
BBox = tuple[float, float, float, float]


@dataclass
class Issue:
    severity: Severity
    check: str
    message: str
    page: int | None = None
    expected: str = ""
    actual: str = ""
    bbox: BBox | None = None


@dataclass
class PageClassification:
    body: list[int] = field(default_factory=list)
    references: list[int] = field(default_factory=list)
    appendix: list[int] = field(default_factory=list)
    ethics: list[int] = field(default_factory=list)
    ambiguous: bool = False


@dataclass
class PaperReport:
    pdf_path: Path
    profile_name: str
    page_count: int
    issues: list[Issue] = field(default_factory=list)
    body_font: str = ""
    body_font_size: float = 0.0
    classification: PageClassification = field(default_factory=PageClassification)
    rendered_pages: list[Path] = field(default_factory=list)

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def status(self) -> Literal["pass", "warn", "fail"]:
        if self.n_errors:
            return "fail"
        if self.n_warnings:
            return "warn"
        return "pass"
