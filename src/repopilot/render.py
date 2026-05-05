from __future__ import annotations

from repopilot.models import Finding, ReviewReport


def render_review_markdown(report: ReviewReport) -> str:
    parts = [
        "## RepoPilot Review",
        "",
        report.summary.strip(),
        "",
        _render_section("Potential Risks", report.risks),
        "",
        _render_section("Missing or Insufficient Tests", report.missing_tests),
        "",
        _render_section("Concrete Suggestions", report.suggestions),
    ]
    return "\n".join(parts).strip()


def _render_section(title: str, findings: list[Finding]) -> str:
    if not findings:
        return f"### {title}\n\n- None identified from the current diff."

    lines = [f"### {title}", ""]
    for finding in findings:
        location = _format_location(finding)
        lines.append(
            f"- **[{finding.severity.upper()}] {finding.title}** (`{location}`): "
            f"{finding.summary} Recommendation: {finding.recommendation}"
        )
    return "\n".join(lines)


def _format_location(finding: Finding) -> str:
    if finding.start_line and finding.end_line and finding.end_line != finding.start_line:
        return f"{finding.file_path}:{finding.start_line}-{finding.end_line}"
    if finding.start_line:
        return f"{finding.file_path}:{finding.start_line}"
    return finding.file_path
