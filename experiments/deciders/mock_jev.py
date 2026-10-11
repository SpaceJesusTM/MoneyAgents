"""MOCK Jev: a stand-in that speaks the System One wire format. It is NOT Jev.

Two things live here, both for plumbing validation only:

  MockJevBackend   answers typed questions in-process with keyword heuristics
  serve_stub()     a local HTTP server implementing the documented REST contract (auth header,
                   request validation, 401/422/429/529), so the real `JevBackend` HTTP code path
                   can be tested end to end without a key and without any paid call

The answers come from trivial lexical overlap, and the latency is whatever this laptop takes to
run a few string operations. Neither number says anything about the real service. Every trace
event from this module carries provider="MOCK_jev" so it cannot be mistaken for a measurement.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from webswarm_baseline.textutil import overlap

from .primitives import Answer, Backend, peak_confidence

MOCK_MODEL = "MOCK-jev-not-a-model"


def heuristic_answer(state, q: dict) -> dict:
    """Deterministic fake answer for one wire-format question. Lexical overlap, nothing more."""
    text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    kind = q.get("type")
    if kind == "choice":
        opts = list(q["criteria"])
        scores = {o: 0.05 + overlap(text, f"{o} {q['criteria'][o] or ''}") for o in opts}
        total = sum(scores.values())
        probs = {o: round(s / total, 4) for o, s in scores.items()}
        best = max(probs, key=probs.get)
        return {"type": "choice", "choice": best, "probabilities": probs,
                "confidence": round(peak_confidence(probs), 4)}
    if kind == "noul":
        return {"type": "noul", "noul": round(min(0.95, 0.15 + 2 * overlap(text, str(q["instructions"]))), 4)}
    if kind == "score":
        n = len(q["criteria"])
        mid = n // 2
        probs = {str(i): (1.0 if i == mid else 0.0) for i in range(n)}
        return {"type": "score", "score": float(mid), "confidence": 1.0, "probabilities": probs,
                "legend": {str(i): c for i, c in enumerate(q["criteria"])}}
    raise ValueError(f"unknown question type {kind!r}")


class MockJevBackend(Backend):
    name = "MOCK_jev"
    external = False
    answers_in_one_request = True

    def __init__(self, tracer=None):
        self.tracer = tracer

    def ask(self, state, questions: dict, *, node=None, kind: str = "") -> dict:
        t0 = time.perf_counter()
        out = {k: Answer.from_wire(heuristic_answer(state, q.to_wire())) for k, q in questions.items()}
        if self.tracer is not None:
            self.tracer.event("decision_call", getattr(node, "id", None), kind=kind, provider=self.name,
                              model=MOCK_MODEL, secs=round(time.perf_counter() - t0, 4), queue_wait=0.0,
                              prompt_tokens=None, output_tokens=None, mock=True)
        return out


# ---- local stub of the REST contract (tests only) -----------------------------------------------

def validate_request(body) -> str | None:
    """Return a validation message for a malformed System One request, else None (per docs/api)."""
    if not isinstance(body, dict):
        return "body must be an object"
    for f in ("state", "model", "questions"):
        if f not in body:
            return f"missing required field: {f}"
    if not isinstance(body["state"], (str, dict, list)):
        return "state must be a string, object or array"
    if not isinstance(body["model"], str):
        return "model must be a string"
    qs = body["questions"]
    if not isinstance(qs, dict) or not qs:
        return "questions must be a non-empty object"
    for qid, q in qs.items():
        if not isinstance(q, dict) or q.get("type") not in ("choice", "noul", "score"):
            return f"questions.{qid}.type must be choice, noul or score"
        if "instructions" not in q:
            return f"questions.{qid}.instructions is required"
        if q["type"] == "choice":
            c = q.get("criteria")
            if not isinstance(c, dict) or not c or len(c) > 255:
                return f"questions.{qid}.criteria must be an object with 1 to 255 options"
        if q["type"] == "score":
            c = q.get("criteria")
            if not isinstance(c, list) or not 2 <= len(c) <= 10:
                return f"questions.{qid}.criteria must be an array of 2 to 10 levels"
    return None


def serve_stub(api_key: str = "test-key", fail_first: list[int] | None = None):
    """Start the stub on 127.0.0.1 (random port). Returns (server, url, log).

    `fail_first` is a list of HTTP statuses to return before succeeding (to test retries).
    `log` collects one dict per request: status, and the Authorization header that was sent.
    """
    queue = list(fail_first or [])
    log: list[dict] = []
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep test output quiet
            pass

        def _send(self, status: int, payload: dict):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            auth = self.headers.get("Authorization", "")
            with lock:
                forced = queue.pop(0) if queue else None
            entry = {"path": self.path, "auth": auth, "status": 200}
            log.append(entry)
            if self.path != "/v1/systemone":
                entry["status"] = 404
                return self._send(404, {"error": "not found"})
            if auth != f"Bearer {api_key}":
                entry["status"] = 401
                return self._send(401, {"error": "invalid api key"})
            if forced:
                entry["status"] = forced
                return self._send(forced, {"error": "forced failure (stub)"})
            try:
                body = json.loads(raw or b"{}")
            except ValueError:
                body = None
            problem = validate_request(body)
            if problem:
                entry["status"] = 422
                return self._send(422, {"error": problem})
            entry["body"] = body
            answers = {qid: heuristic_answer(body["state"], q) for qid, q in body["questions"].items()}
            self._send(200, {"model": MOCK_MODEL, "answers": answers,
                             "usage": {"input_tokens": len(raw) // 4, "output_tokens": 3 * len(answers)}})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1/systemone", log
