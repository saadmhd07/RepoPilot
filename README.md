# RepoPilot

RepoPilot is a local-first CLI that reviews an existing GitHub pull request by:

1. Fetching the PR metadata and file diffs from the GitHub API
2. Asking an OpenAI model to analyze the change set
3. Rendering a structured markdown review
4. Optionally posting that review back to the PR

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
