"""Configuration: LM Studio connection (from .env) and recursion safety limits."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

EXPERIMENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXPERIMENT_DIR.parent
PLACEHOLDER_MODEL = "REPLACE_WITH_MODEL_ID"


@dataclass
class Settings:
    base_url: str
    api_key: str
    model: str
    temperature: float
    timeout: float
    structured_method: str  # "json_schema" (LM Studio structured output) or "prompt"

    def public(self) -> dict:
        d = asdict(self)
        d.pop("api_key")
        return d


@dataclass
class Limits:
    max_depth: int = 3      # root is depth 0; nodes at max_depth are forced to ATOM
    max_children: int = 4   # per node; extra proposed children are dropped
    max_nodes: int = 25     # whole tree; hard cap on routing calls too


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    method = os.getenv("WEBSWARM_STRUCTURED_METHOD", "json_schema")
    if method not in ("json_schema", "prompt"):
        raise SystemExit(f"WEBSWARM_STRUCTURED_METHOD must be json_schema or prompt, got {method!r}")
    return Settings(
        base_url=os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
        model=os.getenv("LM_STUDIO_MODEL", ""),
        temperature=float(os.getenv("WEBSWARM_TEMPERATURE", "0.2")),
        timeout=float(os.getenv("WEBSWARM_TIMEOUT", "300")),
        structured_method=method,
    )
