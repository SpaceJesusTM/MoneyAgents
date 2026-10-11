"""TypeSafe Jev (System One) backend over the documented REST API.

STATUS: implemented from the public documentation and exercised only against a local stub server
(experiments/tests/test_jev_contract.py). It has NOT been run against the real service: no
TYPESAFE_API_KEY was available when this was written. Nothing here measures Jev.

Contract used (https://docs.typesafe.ai/api and /introduction/quickstart, checked 2026-10-10):

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer <TYPESAFE_API_KEY>
    {"state": <string|object|array>, "model": "jev-latest", "questions": {id: {type, instructions, criteria}}}
    -> {"model": "jev-1.13.0", "answers": {id: {...}}, "usage": {"input_tokens": n, "output_tokens": n}}
    401 bad key | 422 validation | 429 rate limited | 529 overloaded (retry 429/529 with backoff)

Two safeguards, because this is a paid third-party API that receives research text:
  - it refuses to start unless the key is set AND `allow_external_calls` is explicitly true;
  - it never logs the key, and the trace records only question ids, timing and token usage.
"""
from __future__ import annotations

import os
import time

import requests

from .primitives import Answer, Backend

DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
RETRY_STATUS = (429, 529)


class JevError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class JevBackend(Backend):
    name = "jev"
    external = True
    answers_in_one_request = True   # the API evaluates all questions of a request in parallel

    def __init__(self, api_key: str | None = None, *, url: str | None = None, model: str = DEFAULT_MODEL,
                 timeout: float = 10.0, max_retries: int = 3, backoff: float = 0.5,
                 allow_external_calls: bool = False, tracer=None, session=None):
        self.url = url or os.getenv("TYPESAFE_API_URL", DEFAULT_URL)
        key = api_key or os.getenv("TYPESAFE_API_KEY", "")
        if not key:
            raise JevError("TYPESAFE_API_KEY is not set. Create a key at https://console.typesafe.ai/keys "
                           "and put it in .env (never commit it).")
        if not allow_external_calls:
            raise JevError("Jev is a paid external API and research text would be sent to it. Set "
                           "decider_options.allow_external_calls=true to confirm you want that.")
        self._key = key
        self.model, self.timeout, self.max_retries, self.backoff = model, timeout, max_retries, backoff
        self.tracer = tracer
        self.session = session or requests.Session()
        self.usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "retries": 0}
        self.served_model = ""

    def ask(self, state, questions: dict, *, node=None, kind: str = "") -> dict:
        if not questions:
            return {}
        body = {"state": state, "model": self.model, "questions": {k: q.to_wire() for k, q in questions.items()}}
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        t0 = time.perf_counter()
        attempt = 0
        while True:
            try:
                r = self.session.post(self.url, json=body, headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                if attempt >= self.max_retries:
                    raise JevError(f"request failed: {type(e).__name__}") from e
                r = None
            if r is not None and r.status_code == 200:
                break
            if r is not None and r.status_code not in RETRY_STATUS:
                raise JevError(_explain(r), r.status_code)
            if attempt >= self.max_retries:
                raise JevError(f"gave up after {attempt + 1} attempts ({_explain(r) if r is not None else 'network'})",
                               getattr(r, "status_code", None))
            delay = self.backoff * (2 ** attempt)
            if r is not None and r.headers.get("Retry-After", "").replace(".", "", 1).isdigit():
                delay = min(float(r.headers["Retry-After"]), 10.0)
            time.sleep(delay)
            attempt += 1
            self.usage["retries"] += 1
        data = r.json()
        answers = data.get("answers") or {}
        missing = set(questions) - set(answers)
        if missing:
            raise JevError(f"response is missing answers for {sorted(missing)}")
        out = {k: Answer.from_wire(answers[k]) for k in questions}
        for k, q in questions.items():
            if out[k].type != q.to_wire()["type"]:
                raise JevError(f"answer {k!r} has type {out[k].type!r}, expected {q.to_wire()['type']!r}")
        u = data.get("usage") or {}
        self.usage["requests"] += 1
        self.usage["input_tokens"] += int(u.get("input_tokens") or 0)
        self.usage["output_tokens"] += int(u.get("output_tokens") or 0)
        self.served_model = data.get("model", self.served_model)
        if self.tracer is not None:
            self.tracer.event("decision_call", getattr(node, "id", None), kind=kind, provider=self.name,
                              model=self.served_model, secs=round(time.perf_counter() - t0, 3), queue_wait=0.0,
                              prompt_tokens=u.get("input_tokens"), output_tokens=u.get("output_tokens"),
                              questions=sorted(questions), retries=attempt)
        return out


def _explain(r) -> str:
    hint = {401: "missing or invalid API key", 422: "request failed validation",
            429: "rate limit exceeded", 529: "service overloaded"}.get(r.status_code, "unexpected status")
    detail = ""
    try:
        detail = str(r.json())[:200]
    except ValueError:
        detail = (r.text or "")[:200]
    return f"HTTP {r.status_code} ({hint}) {detail}".strip()
