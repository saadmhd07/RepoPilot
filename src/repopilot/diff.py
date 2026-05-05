from __future__ import annotations

from repopilot.github import PullRequestDetails


def build_review_context(
    pr: PullRequestDetails,
    *,
    max_files: int,
    max_patch_chars: int,
    max_total_chars: int,
) -> str:
    sections = [
        f"Repository: {pr.ref.owner}/{pr.ref.repo}",
        f"Pull request: #{pr.ref.number}",
        f"Title: {pr.title}",
        f"Author: {pr.author}",
        f"Base branch: {pr.base_branch}",
        f"Head branch: {pr.head_branch}",
        "Description:",
        pr.body.strip() if pr.body else "(no description provided)",
        "",
        "Changed files:",
    ]
    total_chars = sum(len(section) for section in sections)

    for index, file in enumerate(pr.files[:max_files], start=1):
        patch = file.patch or "(binary or patch unavailable)"
        if len(patch) > max_patch_chars:
            patch = patch[:max_patch_chars] + "\n... [patch truncated]"

        block = (
            f"\nFile {index}: {file.filename}\n"
            f"Status: {file.status}\n"
            f"Additions: {file.additions} | Deletions: {file.deletions} | Changes: {file.changes}\n"
            "Patch:\n"
            f"{patch}\n"
        )

        if total_chars + len(block) > max_total_chars:
            sections.append("\n... [remaining files omitted to stay within prompt budget]")
            break

        sections.append(block)
        total_chars += len(block)

    if len(pr.files) > max_files:
        sections.append(f"\n... [{len(pr.files) - max_files} additional files omitted]")

    return "\n".join(sections)
