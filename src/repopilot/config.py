from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    github_token: str
    openai_api_key: str
    github_api_url: str = "https://api.github.com"
    max_files: int = 40
    max_patch_chars: int = 12000
    max_total_chars: int = 45000

    @classmethod
    def from_env(cls) -> "Settings":
        github_token = os.getenv("GITHUB_TOKEN", "").strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if not github_token:
            raise ValueError("Missing required environment variable: GITHUB_TOKEN")
        if not openai_api_key:
            raise ValueError("Missing required environment variable: OPENAI_API_KEY")

        return cls(
            github_token=github_token,
            openai_api_key=openai_api_key,
            github_api_url=os.getenv("REPOPILOT_GITHUB_API_URL", "https://api.github.com").strip(),
            max_files=int(os.getenv("REPOPILOT_MAX_FILES", "40")),
            max_patch_chars=int(os.getenv("REPOPILOT_MAX_PATCH_CHARS", "12000")),
            max_total_chars=int(os.getenv("REPOPILOT_MAX_TOTAL_CHARS", "45000")),
        )
