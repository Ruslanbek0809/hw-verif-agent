# LLM client abstraction supporting multiple providers.
# Supports Google AI Studio (Gemini), OpenAI (GPT-4o), and Anthropic. Provider is selected via config.

import os
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    usage: dict | None = None


# Unified LLM client that wraps multiple providers.
class LLMClient:

    def __init__(self, provider: str, model: str, temperature: float = 0.7, max_tokens: int = 4096):
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.provider == "google":
            from google import genai
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY not set")
            self._client = genai.Client(api_key=api_key)

        elif self.provider == "openai":
            from openai import OpenAI
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY or OPENAI_API_KEY not set")
            self._client = OpenAI(api_key=api_key, base_url=base_url)

        elif self.provider == "anthropic":
            from anthropic import Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self._client = Anthropic(api_key=api_key)

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    # Generate a completion given system and user prompts.
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        try:
            if self.provider == "google":
                return self._generate_google(system_prompt, user_prompt)
            elif self.provider == "openai":
                return self._generate_openai(system_prompt, user_prompt)
            elif self.provider == "anthropic":
                return self._generate_anthropic(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _generate_openai(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        for attempt in range(5):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                         {"role": "system", "content": system_prompt},
                         {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                text = response.choices[0].message.content or ""
                usage = None
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    }
                return LLMResponse(text=text, usage=usage)
            except Exception as e:
               wait = 60 * (attempt + 1)
               logger.warning(f"Connection error (attempt {attempt+1}/5), retrying in {wait}s: {e}")
               time.sleep(wait)
        raise RuntimeError("Max retries exceeded")
    def _generate_google(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )
        return LLMResponse(
            text=response.text,
            usage={"total_tokens": response.usage_metadata.total_token_count}
            if response.usage_metadata else None,
        )

    def _generate_openai(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        text = response.choices[0].message.content or ""
        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return LLMResponse(text=text, usage=usage)

    def _generate_anthropic(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        text = "".join(b.text for b in response.content if hasattr(b, "text"))
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return LLMResponse(text=text, usage=usage)
