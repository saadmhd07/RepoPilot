from repopilot.gitlab import GitLabClient, MergeRequestNote
from repopilot.github import PullRequestRef


def test_gitlab_project_id_is_url_encoded():
    ref = PullRequestRef(owner="group/subgroup", repo="project", number=1)
    assert GitLabClient._project_id(ref) == "group%2Fsubgroup%2Fproject"


def test_gitlab_build_file_statuses():
    added = GitLabClient._build_file({"new_path": "src/app.py", "new_file": True, "diff": "@@"})
    removed = GitLabClient._build_file({"old_path": "old.py", "deleted_file": True, "diff": "@@"})
    renamed = GitLabClient._build_file({"new_path": "new.py", "renamed_file": True, "diff": "@@"})

    assert added.status == "added"
    assert removed.status == "removed"
    assert renamed.status == "renamed"


def test_gitlab_upsert_note_updates_existing_note():
    client = GitLabClient(token="test-token")
    ref = PullRequestRef(owner="group", repo="project", number=1)
    calls: list[tuple[int, str]] = []

    client.find_repopilot_note = lambda mr_ref: MergeRequestNote(  # type: ignore[method-assign]
        note_id=42,
        body="old body",
        author_username="bot",
    )
    client.update_merge_request_note = lambda mr_ref, note_id, body: calls.append((note_id, body)) or {"id": note_id}  # type: ignore[method-assign]

    action = client.upsert_repopilot_comment(ref, "new body")

    assert action == "updated"
    assert calls == [(42, "new body")]


def test_gitlab_upsert_note_skips_when_unchanged():
    client = GitLabClient(token="test-token")
    ref = PullRequestRef(owner="group", repo="project", number=1)
    calls: list[tuple[int, str]] = []

    client.find_repopilot_note = lambda mr_ref: MergeRequestNote(  # type: ignore[method-assign]
        note_id=42,
        body="same body",
        author_username="bot",
    )
    client.update_merge_request_note = lambda mr_ref, note_id, body: calls.append((note_id, body)) or {"id": note_id}  # type: ignore[method-assign]

    action = client.upsert_repopilot_comment(ref, "same body")

    assert action == "unchanged"
    assert calls == []
