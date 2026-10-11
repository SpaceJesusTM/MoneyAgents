"""Local model access through Ollama's native HTTP API, plus a scripted fake for tests.

Every call goes through the shared `LLMGate` (so the number of concurrent generations is bounded)
and is recorded in the trace with its queue wait, duration and token counts.
"""
from __future__ import annotations

import json
import time

import requests

from .config import SwarmConfig
from .runtime import Budget, BudgetExceeded, LLMGate, Tracer

# Call kinds allowed to use the reserved budget, so a run can always end with an answer.
RESERVED_KINDS = {"synthesize"}


class LLMError(RuntimeError):
    pass


class OllamaLLM:
    def __init__(self, cfg: SwarmConfig, tracer: Tracer, budget: Budget, gate: LLMGate):
        self.cfg, self.tracer, self.budget, self.gate = cfg, tracer, budget, gate
        self.url = cfg.ollama_url.rstrip("/") + "/api/chat"
        self.session = requests.Session()

    # ---- public API -------------------------------------------------------------------------

    def check(self) -> None:
        """Fail fast with a readable message if the server or model is missing."""
        base = self.cfg.ollama_url.rstrip("/")
        try:
            tags = self.session.get(base + "/api/tags", timeout=5).json()
        except Exception as e:  # noqa: BLE001
            raise SystemExit(f"Cannot reach Ollama at {base}: {e}\nStart it with `ollama serve`.")
        names = {m.get("name") for m in tags.get("models", [])}
        if self.cfg.model not in names:
            raise SystemExit(f"Model {self.cfg.model!r} is not installed (have: {sorted(names)}).\n"
                             f"Run: ollama pull {self.cfg.model}")

    def json(self, kind: str, node, system: str, user: str, schema: dict, max_tokens: int = 300) -> dict:
        """One generative call constrained to `schema`. Returns the parsed object."""
        last: Exception | None = None
        for attempt in range(self.cfg.budgets.llm_retries + 1):
            try:
                text = self._chat(kind, node, system, user, max_tokens, schema=schema, attempt=attempt)
                return json.loads(text)
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001 - transport, timeout or truncated JSON
                last = e
                max_tokens = int(max_tokens * 1.5)  # the usual cause is output cut off mid-object
        raise LLMError(f"{kind} failed: {type(last).__name__}: {last}")

    def text(self, kind: str, node, system: str, user: str, max_tokens: int = 500) -> str:
        last: Exception | None = None
        for attempt in range(self.cfg.budgets.llm_retries + 1):
            try:
                return self._chat(kind, node, system, user, max_tokens, attempt=attempt).strip()
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001
                last = e
        raise LLMError(f"{kind} failed: {type(last).__name__}: {last}")

    def raw(self, kind: str, node, body: dict, model: str | None = None, provider: str = "") -> dict:
        """Low-level chat call for typed-decision backends (logprobs etc.). Not budgeted as a
        generative call, but it does occupy the model slot and is traced as `decision_call`."""
        body = {"model": model or self.cfg.model, "stream": False, "think": False,
                "keep_alive": self.cfg.keep_alive, **body}
        depth = getattr(node, "depth", 0)
        with self.gate.slot("decision", depth) as waited:
            t0 = time.perf_counter()
            r = self.session.post(self.url, json=body, timeout=min(self.cfg.llm_timeout, 60))
            secs = time.perf_counter() - t0
        d = r.json()
        if d.get("error"):
            raise LLMError(str(d["error"])[:300])
        self.tracer.event("decision_call", getattr(node, "id", None), kind=kind, provider=provider,
                          model=body["model"], secs=round(secs, 3), queue_wait=round(waited, 3),
                          prompt_tokens=d.get("prompt_eval_count"), output_tokens=d.get("eval_count"))
        return d

    # ---- internals --------------------------------------------------------------------------

    def _chat(self, kind, node, system, user, max_tokens, schema=None, attempt=0) -> str:
        self.budget.take_llm(reserved=kind in RESERVED_KINDS)
        body = {
            "model": self.cfg.model, "stream": False, "think": self.cfg.think,
            "keep_alive": self.cfg.keep_alive,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": self.cfg.temperature, "seed": self.cfg.seed,
                        "num_ctx": self.cfg.num_ctx, "num_predict": max_tokens},
        }
        if schema is not None:
            body["format"] = schema
        depth = getattr(node, "depth", 0)
        nid = getattr(node, "id", None)
        rec = {"kind": kind, "attempt": attempt, "ok": False}
        with self.gate.slot(kind, depth) as waited:
            t0 = time.perf_counter()
            try:
                r = self.session.post(self.url, json=body, timeout=self.cfg.llm_timeout)
                d = r.json()
                if d.get("error"):
                    raise LLMError(str(d["error"])[:300])
                content = (d.get("message") or {}).get("content") or ""
                rec.update(ok=True, prompt_tokens=d.get("prompt_eval_count"),
                           output_tokens=d.get("eval_count"),
                           prompt_secs=round((d.get("prompt_eval_duration") or 0) / 1e9, 3),
                           gen_secs=round((d.get("eval_duration") or 0) / 1e9, 3),
                           done_reason=d.get("done_reason"))
                if schema is not None:
                    try:
                        json.loads(content)  # raise here so the failed attempt is recorded as such
                    except ValueError:
                        rec["output_preview"] = content[:240]
                        raise
                return content
            except Exception as e:
                rec.update(ok=False, error=f"{type(e).__name__}: {e}"[:300])
                raise
            finally:
                rec.update(secs=round(time.perf_counter() - t0, 3), queue_wait=round(waited, 3))
                self.tracer.event("llm_call", nid, **rec)


class ScriptedLLM:
    """Deterministic stand-in for tests and plumbing checks. NOT a model: outputs are scripted.

    `handlers` maps a call kind to `fn(system, user, schema) -> dict | str`. Calls are budgeted,
    gated and traced exactly like real ones so orchestration behaviour can be tested offline.
    """

    def __init__(self, cfg: SwarmConfig, tracer: Tracer, budget: Budget, gate: LLMGate,
                 handlers: dict, delay: float = 0.0):
        self.cfg, self.tracer, self.budget, self.gate = cfg, tracer, budget, gate
        self.handlers, self.delay = handlers, delay

    def check(self) -> None:
        pass

    def _call(self, kind, node, system, user, schema):
        self.budget.take_llm(reserved=kind in RESERVED_KINDS)
        if kind not in self.handlers:
            raise LLMError(f"ScriptedLLM has no handler for kind {kind!r}")
        with self.gate.slot(kind, getattr(node, "depth", 0)) as waited:
            t0 = time.perf_counter()
            if self.delay:
                time.sleep(self.delay)
            try:
                out = self.handlers[kind](system, user, schema)
                ok, err = True, None
                return out
            except Exception as e:
                ok, err = False, f"{type(e).__name__}: {e}"
                raise LLMError(err) from e
            finally:
                self.tracer.event("llm_call", getattr(node, "id", None), kind=kind, ok=ok, error=err,
                                  secs=round(time.perf_counter() - t0, 3), queue_wait=round(waited, 3),
                                  prompt_tokens=None, output_tokens=None, scripted=True)

    def json(self, kind, node, system, user, schema, max_tokens=300) -> dict:
        return self._call(kind, node, system, user, schema)

    def text(self, kind, node, system, user, max_tokens=500) -> str:
        return str(self._call(kind, node, system, user, None))

    def raw(self, kind, node, body, model=None, provider=""):
        raise LLMError("ScriptedLLM does not serve raw decision calls")
