from repopilot.constants import REPOPILOT_COMMENT_MARKER
from repopilot.models import Finding, ReviewReport
from repopilot.render import render_review_markdown


def test_render_review_markdown():
    report = ReviewReport(
        summary="The diff introduces a new write path with limited validation.",
        risks=[
            Finding(
                category="risk",
                severity="high",
                title="Missing guard around null payload",
                file_path="src/service.py",
                start_line=42,
                end_line=45,
                summary="The new branch dereferences request data without a null check.",
                recommendation="Validate the payload before access and add a failure-path test.",
            )
        ],
        missing_tests=[],
        suggestions=[],
    )

    markdown = render_review_markdown(report)

    assert markdown.startswith(REPOPILOT_COMMENT_MARKER)
    assert "## RepoPilot Review" in markdown
    assert "**Summary**" in markdown
    assert "**Overview** Risks: 1 | Missing tests: 0 | Suggestions: 0" in markdown
    assert "`src/service.py:42-45`" in markdown
    assert "### Potential Risks (1)" in markdown
    assert "Recommendation: Validate the payload before access and add a failure-path test." in markdown
    assert "Missing or Insufficient Tests" in markdown
