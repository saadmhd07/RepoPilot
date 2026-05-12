from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

from repopilot.constants import REPOPILOT_COMMENT_MARKER
from repopilot.github import PullRequestDetails, PullRequestFile, PullRequestRef


class GitLabAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class MergeRequestNote:
    note_id: int
    body: str
    author_username: str


class GitLabClient:
    def __init__(self, token: str, api_url: str = "https://gitlab.com/api/v4") -> None:
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "PRIVATE-TOKEN": token,
                "User-Agent": "RepoPilot/0.1.0",
            }
        )

    def get_merge_request(self, ref: PullRequestRef) -> PullRequestDetails:
        project_id = self._project_id(ref)
        mr_data = self._get(f"/projects/{project_id}/merge_requests/{ref.number}")
        diffs = self._get_paginated(
            f"/projects/{project_id}/merge_requests/{ref.number}/diffs",
            params={"unidiff": "true"},
        )
        return PullRequestDetails(
            ref=ref,
            title=mr_data["title"],
            body=mr_data.get("description"),
            base_branch=mr_data["target_branch"],
            head_branch=mr_data["source_branch"],
            author=mr_data.get("author", {}).get("username", "unknown"),
            files=[self._build_file(item) for item in diffs],
        )

    def upsert_repopilot_comment(self, ref: PullRequestRef, body: str) -> str:
        existing_note = self.find_repopilot_note(ref)
        if existing_note is None:
            self.post_merge_request_note(ref, body)
            return "created"

        if existing_note.body == body:
            return "unchanged"

        self.update_merge_request_note(ref, existing_note.note_id, body)
        return "updated"

    def find_repopilot_note(self, ref: PullRequestRef) -> MergeRequestNote | None:
        project_id = self._project_id(ref)
        notes = self._get_paginated(
            f"/projects/{project_id}/merge_requests/{ref.number}/notes",
            params={"sort": "desc", "order_by": "updated_at"},
        )
        for item in notes:
            body = item.get("body") or ""
            if REPOPILOT_COMMENT_MARKER not in body:
                continue
            return MergeRequestNote(
                note_id=item["id"],
                body=body,
                author_username=item.get("author", {}).get("username", "unknown"),
            )
        return None

    def post_merge_request_note(self, ref: PullRequestRef, body: str) -> dict[str, Any]:
        project_id = self._project_id(ref)
        return self._post(
            f"/projects/{project_id}/merge_requests/{ref.number}/notes",
            {"body": body},
        )

    def update_merge_request_note(self, ref: PullRequestRef, note_id: int, body: str) -> dict[str, Any]:
        project_id = self._project_id(ref)
        return self._put(
            f"/projects/{project_id}/merge_requests/{ref.number}/notes/{note_id}",
            {"body": body},
        )

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(f"{self.api_url}{path}", params=params, timeout=30)
        return self._parse_response(response)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(f"{self.api_url}{path}", data=payload, timeout=30)
        return self._parse_response(response)

    def _put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(f"{self.api_url}{path}", data=payload, timeout=30)
        return self._parse_response(response)

    def _get_paginated(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            request_params = {"page": page, "per_page": 100}
            if params:
                request_params.update(params)
            response = self.session.get(f"{self.api_url}{path}", params=request_params, timeout=30)
            data = self._parse_response(response)
            if not isinstance(data, list):
                raise GitLabAPIError(f"Expected list response for {path}, got {type(data).__name__}")
            items.extend(data)
            next_page = response.headers.get("X-Next-Page", "")
            if not next_page:
                return items
            page = int(next_page)

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        if response.ok:
            return response.json()
        message = response.text.strip()
        raise GitLabAPIError(f"GitLab API error {response.status_code}: {message}")

    @staticmethod
    def _project_id(ref: PullRequestRef) -> str:
        return quote(f"{ref.owner}/{ref.repo}", safe="")

    @staticmethod
    def _build_file(item: dict[str, Any]) -> PullRequestFile:
        status = "modified"
        if item.get("new_file"):
            status = "added"
        elif item.get("deleted_file"):
            status = "removed"
        elif item.get("renamed_file"):
            status = "renamed"

        return PullRequestFile(
            filename=item.get("new_path") or item.get("old_path") or "unknown",
            status=status,
            additions=0,
            deletions=0,
            changes=0,
            patch=item.get("diff"),
        )
