"""
config.py — Load environment variables and expose a Settings dataclass.

Reads from a .env file (if present) via python-dotenv, then falls back to
the process environment.  No third-party validation library is used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env into os.environ (no-op if file is absent)
load_dotenv()


@dataclass
class Settings:
    """Application-wide configuration derived from environment variables."""

    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    llm_base_url: str = field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    )
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))

    @property
    def is_demo_mode(self) -> bool:
        """True when no LLM API key is configured — app runs on bundled seed data."""
        return not bool(self.llm_api_key)


# Module-level singleton — import this everywhere instead of instantiating per-call.
settings = Settings()
