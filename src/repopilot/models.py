from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["high", "medium", "low"]
Category = Literal["risk", "tests", "suggestion"]


class Finding(BaseModel):
    category: Category
    severity: Severity
    title: str = Field(min_length=3, max_length=160)
    file_path: str = Field(min_length=1)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=10)
    recommendation: str = Field(min_length=10)


class ReviewReport(BaseModel):
    summary: str = Field(min_length=20)
    risks: list[Finding] = Field(default_factory=list)
    missing_tests: list[Finding] = Field(default_factory=list)
    suggestions: list[Finding] = Field(default_factory=list)

    def validate_groupings(self) -> "ReviewReport":
        for finding in self.risks:
            if finding.category != "risk":
                raise ValueError("Risk findings must use category='risk'")
        for finding in self.missing_tests:
            if finding.category != "tests":
                raise ValueError("Test findings must use category='tests'")
        for finding in self.suggestions:
            if finding.category != "suggestion":
                raise ValueError("Suggestion findings must use category='suggestion'")
        return self
