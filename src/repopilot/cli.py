from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from urllib.parse import urlparse

from repopilot.config import Settings
from repopilot.diff import build_review_context
from repopilot.gitlab import GitLabAPIError, GitLabClient
from repopilot.github import GitHubAPIError, GitHubClient, PullRequestRef
from repopilot.render import render_review_markdown


@dataclass(frozen=True)
class ReviewTarget:
    provider: str
    ref: PullRequestRef
    api_url: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repopilot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review", help="Review an existing pull request")
    review_parser.add_argument("--pr-url", help="GitHub pull request URL")
    review_parser.add_argument("--gitlab-mr-url", help="GitLab merge request URL")
    review_parser.add_argument("--repo", help="Repository in OWNER/REPO format")
    review_parser.add_argument("--pr-number", type=int, help="Pull request number")
    review_parser.add_argument("--gitlab-project", help="GitLab project path in GROUP/PROJECT format")
    review_parser.add_argument("--gitlab-mr-iid", type=int, help="GitLab merge request IID")
    review_parser.add_argument(
        "--from-github-event",
        action="store_true",
        help="Read repository and pull request number from the GitHub Actions event payload",
    )
    review_parser.add_argument(
        "--from-gitlab-ci",
        action="store_true",
        help="Read project and merge request IID from GitLab CI predefined variables",
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
        except GitLabAPIError as exc:
            return _report_error(_humanize_gitlab_error(str(exc)))
        except Exception as exc:
            return _report_error(str(exc))

    parser.error(f"Unsupported command: {args.command}")
    return 2


def run_review(args: argparse.Namespace) -> None:
    from repopilot.llm import OpenAIReviewer

    settings = Settings.from_env()
    target = resolve_review_target(
        pr_url=args.pr_url,
        gitlab_mr_url=args.gitlab_mr_url,
        repo=args.repo,
        pr_number=args.pr_number,
        gitlab_project=args.gitlab_project,
        gitlab_mr_iid=args.gitlab_mr_iid,
        from_github_event=args.from_github_event,
        from_gitlab_ci=args.from_gitlab_ci,
    )

    review_client = build_review_client(target, settings)
    if target.provider == "github":
        pr = review_client.get_pull_request(target.ref)
    else:
        pr = review_client.get_merge_request(target.ref)

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
        action = review_client.upsert_repopilot_comment(target.ref, markdown)
        if action == "created":
            print(f"Posted RepoPilot review on {format_target(target)}")
            return
        if action == "updated":
            print(f"Updated RepoPilot review on {format_target(target)}")
            return
        print(f"RepoPilot review unchanged on {format_target(target)}")
        return

    print(markdown)


def resolve_review_target(
    *,
    pr_url: str | None,
    gitlab_mr_url: str | None,
    repo: str | None,
    pr_number: int | None,
    gitlab_project: str | None,
    gitlab_mr_iid: int | None,
    from_github_event: bool,
    from_gitlab_ci: bool,
) -> ReviewTarget:
    if from_github_event:
        return ReviewTarget(provider="github", ref=parse_github_event())

    if from_gitlab_ci:
        return ReviewTarget(provider="gitlab", ref=parse_gitlab_ci())

    if pr_url:
        return ReviewTarget(provider="github", ref=parse_pr_url(pr_url))

    if gitlab_mr_url:
        return parse_gitlab_mr_url(gitlab_mr_url)

    if gitlab_project or gitlab_mr_iid is not None:
        if not gitlab_project or gitlab_mr_iid is None:
            raise ValueError("Use both --gitlab-project and --gitlab-mr-iid")
        owner, repo_name = parse_project_path(gitlab_project)
        return ReviewTarget(
            provider="gitlab",
            ref=PullRequestRef(owner=owner, repo=repo_name, number=gitlab_mr_iid),
        )

    if not repo or pr_number is None:
        raise ValueError("Use --pr-url, --gitlab-mr-url, --from-github-event, --from-gitlab-ci, or explicit repo/MR options")

    owner, repo_name = parse_repo(repo)
    return ReviewTarget(provider="github", ref=PullRequestRef(owner=owner, repo=repo_name, number=pr_number))


def parse_pr_url(pr_url: str) -> PullRequestRef:
    parsed = urlparse(pr_url)
    parts = [part for part in parsed.path.split("/") if part]
    if parsed.netloc != "github.com" or len(parts) < 4 or parts[2] != "pull":
        raise ValueError(f"Unsupported pull request URL: {pr_url}")
    return PullRequestRef(owner=parts[0], repo=parts[1], number=int(parts[3]))


def parse_gitlab_mr_url(mr_url: str) -> ReviewTarget:
    parsed = urlparse(mr_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Unsupported GitLab merge request URL: {mr_url}")

    parts = [part for part in parsed.path.split("/") if part]
    try:
        marker_index = parts.index("-")
    except ValueError as exc:
        raise ValueError(f"Unsupported GitLab merge request URL: {mr_url}") from exc

    if len(parts) <= marker_index + 2 or parts[marker_index + 1] != "merge_requests":
        raise ValueError(f"Unsupported GitLab merge request URL: {mr_url}")

    project_parts = parts[:marker_index]
    if len(project_parts) < 2:
        raise ValueError(f"Unsupported GitLab merge request URL: {mr_url}")

    return ReviewTarget(
        provider="gitlab",
        ref=PullRequestRef(
            owner="/".join(project_parts[:-1]),
            repo=project_parts[-1],
            number=int(parts[marker_index + 2]),
        ),
        api_url=f"{parsed.scheme}://{parsed.netloc}/api/v4",
    )


def parse_repo(repo: str) -> tuple[str, str]:
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Repository must be in OWNER/REPO format")
    return parts[0], parts[1]


def parse_project_path(project_path: str) -> tuple[str, str]:
    parts = [part for part in project_path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitLab project must be in GROUP/PROJECT format")
    return "/".join(parts[:-1]), parts[-1]


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


def parse_gitlab_ci() -> PullRequestRef:
    project_path = os.getenv("CI_MERGE_REQUEST_PROJECT_PATH", "").strip() or os.getenv("CI_PROJECT_PATH", "").strip()
    mr_iid = os.getenv("CI_MERGE_REQUEST_IID", "").strip()

    if not project_path:
        raise ValueError("Missing CI_PROJECT_PATH for --from-gitlab-ci")
    if not mr_iid:
        raise ValueError("Missing CI_MERGE_REQUEST_IID for --from-gitlab-ci. Use a merge request pipeline.")

    owner, repo_name = parse_project_path(project_path)
    return PullRequestRef(owner=owner, repo=repo_name, number=int(mr_iid))


def build_review_client(target: ReviewTarget, settings: Settings) -> GitHubClient | GitLabClient:
    if target.provider == "github":
        if not settings.github_token:
            raise ValueError("Missing required environment variable for GitHub: GITHUB_TOKEN")
        return GitHubClient(token=settings.github_token, api_url=settings.github_api_url)

    if not settings.gitlab_token:
        raise ValueError("Missing required environment variable for GitLab: GITLAB_TOKEN")
    return GitLabClient(token=settings.gitlab_token, api_url=target.api_url or settings.gitlab_api_url)


def format_target(target: ReviewTarget) -> str:
    symbol = "#" if target.provider == "github" else "!"
    return f"{target.ref.owner}/{target.ref.repo}{symbol}{target.ref.number}"


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


def _humanize_gitlab_error(message: str) -> str:
    if "401" in message or "403" in message:
        return (
            "GitLab token cannot perform this action. "
            "Check that GITLAB_TOKEN can read merge requests and write notes on the project."
        )
    if "404" in message:
        return (
            "GitLab project or merge request not found. "
            "For private projects, confirm that GITLAB_TOKEN can access the target project."
        )
    return message
