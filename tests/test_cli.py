import json

from repopilot.cli import parse_github_event, parse_pr_url, parse_repo


def test_parse_pr_url():
    ref = parse_pr_url("https://github.com/openai/openai-python/pull/123")
    assert ref.owner == "openai"
    assert ref.repo == "openai-python"
    assert ref.number == 123


def test_parse_repo():
    owner, repo = parse_repo("octocat/Hello-World")
    assert owner == "octocat"
    assert repo == "Hello-World"


def test_parse_github_event(tmp_path, monkeypatch):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps({"pull_request": {"number": 42}}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octocat/Hello-World")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    ref = parse_github_event()

    assert ref.owner == "octocat"
    assert ref.repo == "Hello-World"
    assert ref.number == 42
