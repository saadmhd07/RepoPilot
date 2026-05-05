from repopilot.cli import parse_pr_url, parse_repo


def test_parse_pr_url():
    ref = parse_pr_url("https://github.com/openai/openai-python/pull/123")
    assert ref.owner == "openai"
    assert ref.repo == "openai-python"
    assert ref.number == 123


def test_parse_repo():
    owner, repo = parse_repo("octocat/Hello-World")
    assert owner == "octocat"
    assert repo == "Hello-World"
