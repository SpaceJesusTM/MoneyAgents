"""Run configuration: model/server settings, hard budgets, and mechanism switches.

Every experiment arm is this dataclass with a few fields changed, so a run's `config` block in
its trace fully describes what was executed. `configs/baseline.json` is the frozen reference.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent


@dataclass
class Budgets:
    """Hard limits. When one is hit, nodes stop and return what they have; nothing loops forever."""
    max_depth: int = 2            # root is depth 0; a node at max_depth cannot delegate (forced ATOM)
    max_nodes: int = 12           # whole tree, including the root
    max_children: int = 4         # per dispatch batch
    max_followups: int = 2        # extra children a manager may add after its first batch
    max_llm_calls: int = 110      # generative calls, whole run
    max_web_calls: int = 60       # searches + page fetches, whole run
    max_seconds: float = 900.0    # wall-clock deadline for the whole run
    wrap_up_fraction: float = 0.7 # after this share of max_seconds, agents stop gathering and write up
    atom_max_steps: int = 4       # tool actions (search/read) per ATOM agent
    deep_max_rounds: int = 3      # investigate rounds per DEEP manager (verification is extra)
    entity_paths: int = 3         # discovery paths per ENTITY_COLLECT manager (paper uses 3)
    entity_verify_max: int = 2    # low-support candidates verified per ENTITY_COLLECT manager
    llm_retries: int = 1          # retries per failed/malformed generative call
    reserve_llm_calls: int = 2    # held back so the root can always synthesize


@dataclass
class SwarmConfig:
    name: str = "baseline"

    # --- local model serving (Ollama) ---
    model: str = "qwen3.5:4b-q4_K_M"
    ollama_url: str = "http://127.0.0.1:11434"
    temperature: float = 0.0
    seed: int = 7
    num_ctx: int = 8192
    think: bool = False           # qwen3.5 defaults to thinking on; off keeps calls short
    llm_timeout: float = 180.0
    llm_concurrency: int = 1      # Ollama serialises requests on this machine; see DESIGN_DECISIONS
    keep_alive: str = "30m"

    # --- web ---
    search_provider: str = "ddgs"
    search_results: int = 5
    web_concurrency: int = 4
    web_mode: str = "live"        # live | record | replay | replay_or_record
    cassette: str = ""            # directory for recorded web responses
    replay_latency: bool = True   # when replaying, sleep for the recorded latency (fair timing)
    fetch_timeout: float = 12.0
    max_page_bytes: int = 3_000_000
    page_chars: int = 3200        # characters of (relevance-selected) page text shown to the extractor
                                  # (financial text runs ~2.2 chars/token, so this is ~1.4k prompt tokens)
    respect_robots: bool = True
    min_search_interval: float = 0.7   # seconds between searches (provider politeness)

    # --- orchestration mechanisms (baseline values; experiment arms flip these) ---
    decider: str = "generative"         # who makes bounded decisions: generative | rules | local_s1 | jev | mock_jev
    decider_options: dict = field(default_factory=dict)
    review_policy: str = "incremental"  # incremental: review as child results arrive | batch: wait for all
    scheduler: str = "fifo"             # order in which queued model calls get the single model slot
    web_probing: bool = False           # probe information topology before WIDE planning
    experience_sharing: bool = False    # scouts first, then pass process tips to remaining siblings
    scout_count: int = 2
    verify_policy: str = "always"       # DEEP candidate verification: always | decider | never
    allow_entity_collect: bool = True
    final_audit: bool = True            # programmatic citation + numeric grounding audit of the answer
    extract_mode: str = "quote"         # quote: model copies a supporting quote (baseline)
                                        # lines: page shown as numbered lines, model cites a line number

    budgets: Budgets = field(default_factory=Budgets)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SwarmConfig":
        d = dict(d)
        b = d.pop("budgets", {}) or {}
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        bknown = {f.name for f in fields(Budgets)}
        bunknown = set(b) - bknown
        if bunknown:
            raise ValueError(f"unknown budget keys: {sorted(bunknown)}")
        return cls(**d, budgets=Budgets(**b))

    @classmethod
    def load(cls, path: str | Path) -> "SwarmConfig":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def override(self, pairs: list[str]) -> "SwarmConfig":
        """Apply `key=value` overrides (`budgets.max_nodes=8`, `web_probing=true`, ...)."""
        d = self.to_dict()
        for pair in pairs:
            if "=" not in pair:
                raise ValueError(f"override must be key=value, got {pair!r}")
            key, raw = pair.split("=", 1)
            target = d
            parts = key.strip().split(".")
            for p in parts[:-1]:
                if not isinstance(target.get(p), dict):
                    raise ValueError(f"unknown config section {p!r} in {key!r}")
                target = target[p]
            leaf = parts[-1]
            if leaf not in target and parts[0] != "decider_options":
                raise ValueError(f"unknown config key {key!r}")
            target[leaf] = _coerce(raw, target.get(leaf))
        return SwarmConfig.from_dict(d)


def _coerce(raw: str, current):
    raw = raw.strip()
    if isinstance(current, bool):
        if raw.lower() in ("1", "true", "yes", "on"):
            return True
        if raw.lower() in ("0", "false", "no", "off"):
            return False
        raise ValueError(f"expected a boolean, got {raw!r}")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, str):
        return raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
