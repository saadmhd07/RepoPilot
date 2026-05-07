from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlparse

from repopilot.config import Settings
from repopilot.diff import build_review_context
from repopilot.github import GitHubAPIError, GitHubClient, PullRequestRef
from repopilot.render import render_review_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repopilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review", help="Review an existing pull request")
    review_parser.add_argument("--pr-url", help="GitHub pull request URL")
    review_parser.add_argument("--repo", help="Repository in OWNER/REPO format")
    review_parser.add_argument("--pr-number", type=int, help="Pull request number")
    review_parser.add_argument(
        "--from-github-event",
        action="store_true",
        help="Read repository and pull request number from the GitHub Actions event payload",
    )
    review_parser.add_argument("--model", default="gpt-4.1", help="OpenAI model to use")
    review_parser.add_argument(
        "--post",
        action="store_true",
        help="Post the generated review as a PR comment instead of printing only",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "review":
        try:
            run_review(args)
            return 0
        except ValueError as exc:
            return _report_error(str(exc))
        except GitHubAPIError as exc:
            return _report_error(_humanize_github_error(str(exc)))
        except Exception as exc:
            return _report_error(str(exc))

    parser.error(f"Unsupported command: {args.command}")
    return 2


def run_review(args: argparse.Namespace) -> None:
    from repopilot.llm import OpenAIReviewer

    settings = Settings.from_env()
    ref = resolve_pr_ref(
        pr_url=args.pr_url,
        repo=args.repo,
        pr_number=args.pr_number,
        from_github_event=args.from_github_event,
    )

    github = GitHubClient(token=settings.github_token, api_url=settings.github_api_url)
    pr = github.get_pull_request(ref)

    context = build_review_context(
        pr,
        max_files=settings.max_files,
        max_patch_chars=settings.max_patch_chars,
        max_total_chars=settings.max_total_chars,
    )

    reviewer = OpenAIReviewer(api_key=settings.openai_api_key, model=args.model)
    report = reviewer.review_pull_request(context)
    markdown = render_review_markdown(report)

    if args.post:
        action = github.upsert_repopilot_comment(ref, markdown)
        if action == "created":
            print(f"Posted RepoPilot review on {ref.owner}/{ref.repo}#{ref.number}")
            return
        if action == "updated":
            print(f"Updated RepoPilot review on {ref.owner}/{ref.repo}#{ref.number}")
            return
        print(f"RepoPilot review unchanged on {ref.owner}/{ref.repo}#{ref.number}")
        return

    print(markdown)


def resolve_pr_ref(
    *,
    pr_url: str | None,
    repo: str | None,
    pr_number: int | None,
    from_github_event: bool,
) -> PullRequestRef:
    if from_github_event:
        return parse_github_event()

    if pr_url:
        return parse_pr_url(pr_url)

    if not repo or pr_number is None:
        raise ValueError("Use either --pr-url or both --repo and --pr-number")

    owner, repo_name = parse_repo(repo)
    return PullRequestRef(owner=owner, repo=repo_name, number=pr_number)


def parse_pr_url(pr_url: str) -> PullRequestRef:
    parsed = urlparse(pr_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc != "github.com" or len(parts) < 4 or parts[2] != "pull":
        raise ValueError(f"Unsupported pull request URL: {pr_url}")
    return PullRequestRef(owner=parts[0], repo=parts[1], number=int(parts[3]))


def parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Repository must be in OWNER/REPO format")
    return parts[0], parts[1]


def parse_github_event() -> PullRequestRef:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()

    if not repo:
        raise ValueError("Missing GITHUB_REPOSITORY for --from-github-event")
    if not event_path:
        raise ValueError("Missing GITHUB_EVENT_PATH for --from-github-event")

    owner, repo_name = parse_repo(repo)

    with open(event_path, "r", encoding="utf-8") as handle:
        event = json.load(handle)

    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict) or "number" not in pull_request:
        raise ValueError("GitHub event does not contain pull_request.number")

    return PullRequestRef(owner=owner, repo=repo_name, number=int(pull_request["number"]))


def _report_error(message: str) -> int:
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::error::{message}")
    else:
        print(f"Error: {message}")
    return 1


def _humanize_github_error(message: str) -> str:
    if "Resource not accessible by personal access token" in message:
        return (
            "GitHub token cannot perform this action. "
            "Check pull request and issue comment permissions for the repository."
        )
    if 'GitHub API error 404: {"message":"Not Found"' in message:
        return (
            "GitHub resource not found. "
            "For private repositories, confirm that the token can access the target repository."
        )
    return message
