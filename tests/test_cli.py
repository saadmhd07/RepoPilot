import json

from repopilot.cli import (
    _humanize_github_error,
    _humanize_gitlab_error,
    parse_github_event,
    parse_gitlab_ci,
    parse_gitlab_mr_url,
    parse_pr_url,
    parse_project_path,
    parse_repo,
    resolve_review_target,
)


def test_parse_pr_url():
    ref = parse_pr_url("https://github.com/openai/openai-python/pull/123")
    assert ref.owner == "openai"
    assert ref.repo == "openai-python"
    assert ref.number == 123


def test_parse_repo():
    owner, repo = parse_repo("octocat/Hello-World")
    assert owner == "octocat"
    assert repo == "Hello-World"


def test_parse_project_path_with_subgroup():
    owner, repo = parse_project_path("group/subgroup/project")
    assert owner == "group/subgroup"
    assert repo == "project"


def test_parse_gitlab_mr_url():
    target = parse_gitlab_mr_url("https://gitlab.com/group/subgroup/project/-/merge_requests/17")
    assert target.provider == "gitlab"
    assert target.ref.owner == "group/subgroup"
    assert target.ref.repo == "project"
    assert target.ref.number == 17
    assert target.api_url == "https://gitlab.com/api/v4"


def test_parse_gitlab_mr_url_self_managed_host():
    target = parse_gitlab_mr_url("https://git.sia-partners.com/platforms/siagpt/-/merge_requests/2590")
    assert target.ref.owner == "platforms"
    assert target.ref.repo == "siagpt"
    assert target.ref.number == 2590
    assert target.api_url == "https://git.sia-partners.com/api/v4"


def test_parse_github_event(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"pull_request": {"number": 42}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octocat/Hello-World")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    ref = parse_github_event()

    assert ref.owner == "octocat"
    assert ref.repo == "Hello-World"
    assert ref.number == 42


def test_parse_gitlab_ci(monkeypatch):
    monkeypatch.setenv("CI_PROJECT_PATH", "group/subgroup/project")
    monkeypatch.setenv("CI_MERGE_REQUEST_IID", "24")

    ref = parse_gitlab_ci()

    assert ref.owner == "group/subgroup"
    assert ref.repo == "project"
    assert ref.number == 24


def test_resolve_review_target_for_gitlab_project():
    target = resolve_review_target(
        pr_url=None,
        gitlab_mr_url=None,
        repo=None,
        pr_number=None,
        gitlab_project="group/project",
        gitlab_mr_iid=9,
        from_github_event=False,
        from_gitlab_ci=False,
    )

    assert target.provider == "gitlab"
    assert target.ref.owner == "group"
    assert target.ref.repo == "project"
    assert target.ref.number == 9


def test_humanize_github_error_for_private_repo_access():
    message = 'GitHub API error 404: {"message":"Not Found","status":"404"}'
    assert "private repositories" in _humanize_github_error(message)


def test_humanize_github_error_for_permissions():
    message = "GitHub API error 403: Resource not accessible by personal access token"
    assert "Check pull request and issue comment permissions" in _humanize_github_error(message)


def test_humanize_gitlab_error_for_permissions():
    message = "GitLab API error 403: Forbidden"
    assert "GITLAB_TOKEN" in _humanize_gitlab_error(message)
