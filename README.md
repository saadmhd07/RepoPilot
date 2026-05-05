# RepoPilot

RepoPilot is a local-first CLI that reviews an existing GitHub pull request by:

1. Fetching the PR metadata and file diffs from the GitHub API
2. Asking an OpenAI model to analyze the change set
3. Rendering a structured markdown review
4. Optionally posting that review back to the PR

It can run locally first, then as a reusable GitHub Action on `pull_request` events.

## Requirements

- Python 3.10+
- `OPENAI_API_KEY`
- `GITHUB_TOKEN`

The GitHub token needs permission to read pull requests and, if you post the result, write issue comments.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

Preview a review locally:

```bash
repopilot review \
  --pr-url https://github.com/OWNER/REPO/pull/123 \
  --model gpt-4.1
```

Post the generated review to the pull request:

```bash
repopilot review \
  --pr-url https://github.com/OWNER/REPO/pull/123 \
  --model gpt-4.1 \
  --post
```

You can also pass the repository and pull request number explicitly:

```bash
repopilot review \
  --repo OWNER/REPO \
  --pr-number 123 \
  --model gpt-4.1
```

Inside GitHub Actions, RepoPilot can derive the PR directly from the event payload:

```bash
repopilot review --from-github-event --model gpt-5.2 --post
```

## GitHub Action

RepoPilot ships as a composite GitHub Action via `action.yml`.

Minimal workflow:

```yaml
name: RepoPilot

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: saadmhd07/RepoPilot@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
          model: gpt-5.2
```

A ready-to-copy example also lives in `examples/review.yml`.

Required repository secret:

- `OPENAI_API_KEY`

Notes:

- `secrets.GITHUB_TOKEN` is enough if the workflow has `pull-requests: write` and `issues: write`
- the action reads the PR from `GITHUB_EVENT_PATH`, so no PR URL input is needed in CI

## Environment variables

Optional overrides:

- `REPOPILOT_GITHUB_API_URL`: defaults to `https://api.github.com`
- `REPOPILOT_MAX_FILES`: defaults to `40`
- `REPOPILOT_MAX_PATCH_CHARS`: defaults to `12000`
- `REPOPILOT_MAX_TOTAL_CHARS`: defaults to `45000`

## Project layout

- `src/repopilot/github.py`: GitHub API integration
- `src/repopilot/llm.py`: OpenAI review engine
- `src/repopilot/prompts/`: review prompts kept separate from application logic
- `src/repopilot/render.py`: markdown rendering
- `src/repopilot/cli.py`: local CLI entrypoint

## Notes

- This first version posts a single PR-level comment, not inline review comments.
- Large pull requests are truncated before being sent to the model.
- Re-running the action updates the existing RepoPilot comment instead of posting duplicates.
