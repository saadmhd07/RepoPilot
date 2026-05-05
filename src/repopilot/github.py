from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

REPOPILOT_COMMENT_MARKER = "<!-- repopilot-review -->"


class GitHubAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class PullRequestRef:
    owner: str
    repo: str
    number: int


@dataclass(frozen=True)
class PullRequestFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None


@dataclass(frozen=True)
class PullRequestDetails:
    ref: PullRequestRef
    title: str
    body: str | None
    base_branch: str
    head_branch: str
    author: str
    files: list[PullRequestFile]


@dataclass(frozen=True)
class IssueComment:
    comment_id: int
    body: str
    user_login: str


class GitHubClient:
    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "RepoPilot/0.1.0",
            }
        )

    def get_pull_request(self, ref: PullRequestRef) -> PullRequestDetails:
        pr_data = self._get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}")
        files = self._get_paginated(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/files")
        return PullRequestDetails(
            ref=ref,
            title=pr_data["title"],
            body=pr_data.get("body"),
            base_branch=pr_data["base"]["ref"],
            head_branch=pr_data["head"]["ref"],
            author=pr_data["user"]["login"],
            files=[
                PullRequestFile(
                    filename=item["filename"],
                    status=item["status"],
                    additions=item["additions"],
                    deletions=item["deletions"],
                    changes=item["changes"],
                    patch=item.get("patch"),
                )
                for item in files
            ],
        )

    def post_issue_comment(self, ref: PullRequestRef, body: str) -> dict[str, Any]:
        return self._post(
            f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments",
            {"body": body},
        )

    def upsert_repopilot_comment(self, ref: PullRequestRef, body: str) -> str:
        existing_comment = self.find_repopilot_comment(ref)
        if existing_comment is None:
            self.post_issue_comment(ref, body)
            return "created"

        if existing_comment.body == body:
            return "unchanged"

        self.update_issue_comment(ref, existing_comment.comment_id, body)
        return "updated"

    def find_repopilot_comment(self, ref: PullRequestRef) -> IssueComment | None:
        comments = self._get_paginated(f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments")
        for item in reversed(comments):
            body = item.get("body") or ""
            if REPOPILOT_COMMENT_MARKER not in body:
                continue
            return IssueComment(
                comment_id=item["id"],
                body=body,
                user_login=item["user"]["login"],
            )
        return None

    def update_issue_comment(self, ref: PullRequestRef, comment_id: int, body: str) -> dict[str, Any]:
        return self._patch(
            f"/repos/{ref.owner}/{ref.repo}/issues/comments/{comment_id}",
            {"body": body},
        )

    def _get(self, path: str) -> dict[str, Any]:
        response = self.session.get(f"{self.api_url}{path}", timeout=30)
        return self._parse_response(response)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{self.api_url}{path}", json=payload, timeout=30)
        return self._parse_response(response)

    def _patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.patch(f"{self.api_url}{path}", json=payload, timeout=30)
        return self._parse_response(response)

    def _get_paginated(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self.session.get(
                f"{self.api_url}{path}",
                params={"page": page, "per_page": 100},
                timeout=30,
            )
            data = self._parse_response(response)
            if not isinstance(data, list):
                raise GitHubAPIError(f"Expected list response for {path}, got {type(data).__name__}")
            items.extend(data)
            if len(data) < 100:
                return items
            page += 1

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        if response.ok:
            return response.json()
        message = response.text.strip()
        raise GitHubAPIError(f"GitHub API error {response.status_code}: {message}")
