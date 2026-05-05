from repopilot.github import GitHubClient, IssueComment, PullRequestRef


def test_find_repopilot_comment_returns_latest_marked_comment():
    client = GitHubClient(token="test-token")
    ref = PullRequestRef(owner="octocat", repo="hello", number=1)

    client._get_paginated = lambda path: [  # type: ignore[method-assign]
        {"id": 10, "body": "human comment", "user": {"login": "octocat"}},
        {"id": 11, "body": "<!-- repopilot-review -->\nold", "user": {"login": "octocat"}},
        {"id": 12, "body": "<!-- repopilot-review -->\nnew", "user": {"login": "octocat"}},
    ]

    comment = client.find_repopilot_comment(ref)

    assert comment is not None
    assert comment.comment_id == 12
    assert comment.user_login == "octocat"


def test_upsert_repopilot_comment_updates_existing_comment():
    client = GitHubClient(token="test-token")
    ref = PullRequestRef(owner="octocat", repo="hello", number=1)
    calls: list[tuple[str, int | None, str]] = []

    client.find_repopilot_comment = lambda pr_ref: IssueComment(  # type: ignore[method-assign]
        comment_id=22,
        body="old body",
        user_login="octocat",
    )
    client.update_issue_comment = lambda pr_ref, comment_id, body: calls.append(  # type: ignore[method-assign]
        ("update", comment_id, body)
    ) or {"id": comment_id}

    action = client.upsert_repopilot_comment(ref, "updated body")

    assert action == "updated"
    assert calls == [("update", 22, "updated body")]


def test_upsert_repopilot_comment_skips_when_unchanged():
    client = GitHubClient(token="test-token")
    ref = PullRequestRef(owner="octocat", repo="hello", number=1)
    calls: list[tuple[str, int | None, str]] = []

    client.find_repopilot_comment = lambda pr_ref: IssueComment(  # type: ignore[method-assign]
        comment_id=22,
        body="same body",
        user_login="octocat",
    )
    client.update_issue_comment = lambda pr_ref, comment_id, body: calls.append(  # type: ignore[method-assign]
        ("update", comment_id, body)
    ) or {"id": comment_id}

    action = client.upsert_repopilot_comment(ref, "same body")

    assert action == "unchanged"
    assert calls == []


def test_upsert_repopilot_comment_creates_when_missing():
    client = GitHubClient(token="test-token")
    ref = PullRequestRef(owner="octocat", repo="hello", number=1)
    calls: list[tuple[str, int | None, str]] = []

    client.find_repopilot_comment = lambda pr_ref: None  # type: ignore[method-assign]
    client.post_issue_comment = lambda pr_ref, body: calls.append(("create", None, body)) or {"id": 33}  # type: ignore[method-assign]

    action = client.upsert_repopilot_comment(ref, "fresh body")

    assert action == "created"
    assert calls == [("create", None, "fresh body")]
