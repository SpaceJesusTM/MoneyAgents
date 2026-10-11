"""Experimental deciders. Selected with `decider=<name>` in a SwarmConfig.

    rules      deterministic heuristics, no model calls                          (really tested)
    local_s1   typed decisions from a local Ollama model via token logprobs      (really tested)
    jev        TypeSafe Jev over its REST API                                    (needs a key; stub-tested only)
    mock_jev   in-process MOCK that speaks the Jev wire format                   (plumbing only)
"""
from __future__ import annotations

from .rules import RulesDecider
from .system_one import SystemOneDecider

DECIDERS = ("rules", "local_s1", "jev", "mock_jev")


def build(name: str, options: dict):
    options = dict(options or {})
    if name == "rules":
        return RulesDecider(options)
    if name == "local_s1":
        from .local_s1 import LocalLogprobBackend
        model = options.pop("model", None)
        return SystemOneDecider("local_s1", lambda sw: LocalLogprobBackend(sw.llm, model=model), options)
    if name == "jev":
        from .jev import JevBackend
        allow = bool(options.pop("allow_external_calls", False))
        url = options.pop("url", None)
        model = options.pop("model", "jev-latest")
        return SystemOneDecider("jev", lambda sw: JevBackend(url=url, model=model, allow_external_calls=allow,
                                                             tracer=sw.tracer), options)
    if name == "mock_jev":
        from .mock_jev import MockJevBackend
        return SystemOneDecider("MOCK_jev", lambda sw: MockJevBackend(tracer=sw.tracer), options)
    raise ValueError(f"unknown decider {name!r}; available: generative, {', '.join(DECIDERS)}")
