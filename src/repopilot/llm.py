from __future__ import annotations

import json
from importlib import resources

from openai import OpenAI

from repopilot.models import ReviewReport


class LLMReviewError(RuntimeError):
    pass


class OpenAIReviewer:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = self._load_prompt("system.txt")
        self.user_prompt_template = self._load_prompt("user.txt")

    def review_pull_request(self, pr_context: str) -> ReviewReport:
        user_prompt = self.user_prompt_template.replace("{{pull_request_context}}", pr_context)
        response = self.client.responses.create(
            model=self.model,
            input=user_prompt,
            instructions=self.system_prompt,
        )

        raw_output = getattr(response, "output_text", "").strip()
        if not raw_output:
            raise LLMReviewError("OpenAI response did not contain output_text")

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise LLMReviewError(f"Model did not return valid JSON: {exc}") from exc

        try:
            return ReviewReport.model_validate(payload).validate_groupings()
        except Exception as exc:  # pragma: no cover - keeps CLI errors readable
            raise LLMReviewError(f"Model output failed schema validation: {exc}") from exc

    @staticmethod
    def _load_prompt(name: str) -> str:
        return resources.files("repopilot.prompts").joinpath(name).read_text(encoding="utf-8")
