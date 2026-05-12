# RepoPilot

RepoPilot is a local-first CLI that reviews an existing GitHub pull request or GitLab merge request by:

1. Fetching the PR/MR metadata and file diffs from the hosting API
2. Asking an OpenAI model to analyze the change set
3. Rendering a structured markdown review
4. Optionally posting that review back to the PR/MR

It can run locally first, as a reusable GitHub Action on `pull_request` events, or inside GitLab CI merge request pipelines.

## Requirements

- Python 3.10+
- `OPENAI_API_KEY`
- `GITHUB_TOKEN` for GitHub
- `GITLAB_TOKEN` for GitLab

The GitHub token needs permission to read pull requests and, if you post the result, write issue comments. The GitLab token needs access to read merge requests and write merge request notes.

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

Review a GitLab merge request locally:

```bash
repopilot review \
  --gitlab-mr-url https://gitlab.com/GROUP/PROJECT/-/merge_requests/123 \
  --model gpt-5.2
```

Post the generated review to a GitLab merge request:

```bash
repopilot review \
  --gitlab-project GROUP/PROJECT \
  --gitlab-mr-iid 123 \
  --model gpt-5.2 \
  --post
```

Inside GitHub Actions, RepoPilot can derive the PR directly from the event payload:

```bash
repopilot review --from-github-event --model gpt-5.2 --post
```

Inside GitLab CI, RepoPilot can derive the MR directly from predefined CI variables:

```bash
repopilot review --from-gitlab-ci --model gpt-5.2 --post
```

## GitHub Action

RepoPilot ships as a composite GitHub Action via `action.yml`.

For consumers, prefer a version tag instead of `@main`.

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
      - uses: saadmhd07/RepoPilot@v0.1.0
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
- pinning to `@v0.1.0` avoids drift from future changes on `main`
- if `OPENAI_API_KEY` is missing, the action skips cleanly with a warning instead of failing obscurely

## GitLab CI

Add `OPENAI_API_KEY` and `GITLAB_TOKEN` as CI/CD variables, then add a merge request pipeline job:

```yaml
repopilot_review:
  image: python:3.11-slim
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  variables:
    PIP_DISABLE_PIP_VERSION_CHECK: "1"
  before_script:
    - python -m pip install git+https://github.com/saadmhd07/RepoPilot.git@main
  script:
    - repopilot review --from-gitlab-ci --model gpt-5.2 --post
```

A ready-to-copy example also lives in `examples/gitlab-ci.yml`.
Once GitLab support is released, pin this install URL to the release tag instead of `@main`.

## Environment variables

Optional overrides:

- `REPOPILOT_GITHUB_API_URL`: defaults to `https://api.github.com`
- `REPOPILOT_GITLAB_API_URL`: defaults to `https://gitlab.com/api/v4`
- `REPOPILOT_MAX_FILES`: defaults to `40`
- `REPOPILOT_MAX_PATCH_CHARS`: defaults to `12000`
- `REPOPILOT_MAX_TOTAL_CHARS`: defaults to `45000`

## Project layout

- `src/repopilot/github.py`: GitHub API integration
- `src/repopilot/gitlab.py`: GitLab API integration
- `src/repopilot/llm.py`: OpenAI review engine
- `src/repopilot/prompts/`: review prompts kept separate from application logic
- `src/repopilot/render.py`: markdown rendering
- `src/repopilot/cli.py`: local CLI entrypoint

## Notes

- This first version posts a single PR-level comment, not inline review comments.
- Large pull requests are truncated before being sent to the model.
- Re-running the action updates the existing RepoPilot comment instead of posting duplicates.

## Release

To publish the first reusable action version:

```bash
git add action.yml README.md examples/review.yml
git commit -m "Prepare RepoPilot v0.1.0 release"
git push origin main
git tag -a v0.1.0 -m "RepoPilot v0.1.0"
git push origin v0.1.0
```

Then consumers should reference:

```yaml
uses: saadmhd07/RepoPilot@v0.1.0
```
