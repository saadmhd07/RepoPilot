from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    gitlab_token: str | None
    openai_api_key: str
    github_api_url: str = "https://api.github.com"
    gitlab_api_url: str = "https://gitlab.com/api/v4"
    max_files: int = 40
    max_patch_chars: int = 12000
    max_total_chars: int = 45000

    @classmethod
    def from_env(cls) -> "Settings":
        github_token = os.getenv("GITHUB_TOKEN", "").strip()
        gitlab_token = os.getenv("GITLAB_TOKEN", "").strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if not openai_api_key:
            raise ValueError("Missing required environment variable: OPENAI_API_KEY")

        return cls(
            github_token=github_token or None,
            gitlab_token=gitlab_token or None,
            openai_api_key=openai_api_key,
            github_api_url=os.getenv("REPOPILOT_GITHUB_API_URL", "https://api.github.com").strip(),
            gitlab_api_url=os.getenv("REPOPILOT_GITLAB_API_URL", "https://gitlab.com/api/v4").strip(),
            max_files=int(os.getenv("REPOPILOT_MAX_FILES", "40")),
            max_patch_chars=int(os.getenv("REPOPILOT_MAX_PATCH_CHARS", "12000")),
            max_total_chars=int(os.getenv("REPOPILOT_MAX_TOTAL_CHARS", "45000")),
        )
