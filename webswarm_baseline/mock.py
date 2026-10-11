"""Scripted model and canned web content for offline plumbing tests.

NOTHING HERE IS A MODEL OR A REAL WEB PAGE. The "LLM" returns hand-written structures keyed on the
call kind, and the "web" serves a few invented pages about an invented company. This exists to test
orchestration (recursion, budgets, cancellation, evidence flow, citations) deterministically.
Results from it must never be reported as research quality or as timing measurements.
"""
from __future__ import annotations

import re

from .config import SwarmConfig
from .llm import ScriptedLLM

PAGES = {
    "https://example-ir.test/acme-q4": (
        "Acme Corp fourth quarter results",
        "Acme Corp reported fourth quarter revenue of $4.2 billion, up 18% from a year ago. "
        "Data center revenue was $2.9 billion, a record, driven by demand for accelerators. "
        "Gross margin was 61.5%. The company expects first quarter revenue of $4.5 billion, plus or minus 2%. "
        "Supply of advanced packaging remained constrained during the quarter, the company said. " * 2),
    "https://example-news.test/acme-supply": (
        "Acme supply constraints ease as packaging partner expands",
        "Packaging partner Borealis Semiconductor said it will double advanced packaging capacity by the end of "
        "next year. Analysts said the expansion should ease the supply constraint that limited Acme shipments. "
        "Borealis plans to invest $3.1 billion in two new facilities. " * 3),
    "https://example-news.test/acme-competition": (
        "Rivals close in on Acme accelerators",
        "Competitor Zenith Micro launched a rival accelerator priced 20% below Acme's flagship product. "
        "Two large cloud customers said they are testing in-house chips to reduce reliance on Acme. "
        "Acme's largest customer accounted for 19% of revenue in the last fiscal year. " * 3),
    "https://example-blocked.test/paywall": ("", ""),
}

RESULTS = [
    {"title": "Acme Corp fourth quarter results", "url": "https://example-ir.test/acme-q4",
     "snippet": "Acme Corp reported fourth quarter revenue of $4.2 billion, up 18% from a year ago.", "date": ""},
    {"title": "Acme supply constraints ease as packaging partner expands",
     "url": "https://example-news.test/acme-supply",
     "snippet": "Borealis Semiconductor said it will double advanced packaging capacity by the end of next year.",
     "date": ""},
    {"title": "Rivals close in on Acme accelerators", "url": "https://example-news.test/acme-competition",
     "snippet": "Competitor Zenith Micro launched a rival accelerator priced 20% below Acme's flagship.", "date": ""},
    {"title": "Premium analysis (subscribers only)", "url": "https://example-blocked.test/paywall",
     "snippet": "Subscribe to read our analysis of Acme.", "date": ""},
]


class MockProvider:
    name = "mock"

    def search(self, query: str, n: int) -> list[dict]:
        stems = {w[:5] for w in re.findall(r"[a-z]{4,}", query.lower())}   # crude stemming: 5-letter prefixes
        ranked = sorted(RESULTS, key=lambda r: -sum(st in (r["title"] + " " + r["snippet"]).lower() for st in stems))
        return ranked[:n]


def mock_fetch(url: str) -> dict:
    title, text = PAGES.get(url, ("", ""))
    if not text:
        return {"url": url, "status": 403, "error": "HTTP 403"}
    return {"url": url, "final_url": url, "status": 200, "content_type": "text/html", "title": title,
            "text": text, "nbytes": len(text)}


def default_handlers(root_mode: str = "WIDE") -> dict:
    """Scripted behaviour: the root is `root_mode`, children are ATOM, atoms search then read."""

    def route(system, user, schema):
        is_root = "original question" in user
        return {"reason": "scripted", "mode": root_mode if is_root else "ATOM"}

    def plan(system, user, schema):
        return {"reason": "scripted split", "children": [
            "Acme Corp fourth quarter revenue and data center revenue figures",
            "Acme Corp advanced packaging supply constraints and partner capacity expansion",
            "Acme Corp competition from rival accelerators and customer concentration"]}

    def act(system, user, schema):
        if "(no searches yet)" in user:
            obj = re.search(r"OBJECTIVE: (.*)", user).group(1)
            return {"thought": "scripted", "action": "search", "query": obj[:80], "result": 0}
        unread = [int(m.group(1)) for m in re.finditer(r"^R(\d+) \[", user, re.M)]
        has_findings = "Findings so far:\n(none)" not in user
        if has_findings or not unread:
            return {"thought": "scripted", "action": "finish", "query": "", "result": 0}
        return {"thought": "scripted", "action": "read", "query": "", "result": unread[0]}

    def extract(system, user, schema):
        text = user.split("<<<UNTRUSTED", 1)[1]
        sents = [s.strip() for s in re.split(r"(?<=[.])\s+", text) if re.search(r"\d", s) and len(s.split()) >= 6]
        return {"findings": [{"claim": s, "quote": s} for s in dict.fromkeys(sents[:3])]}

    def snippet_extract(system, user, schema):
        m = re.search(r"^(\d+) \[[^\]]*\] [^:]*: (.*)$", user, re.M)
        return {"findings": [{"result": int(m.group(1)), "claim": m.group(2), "quote": m.group(2)}]} if m else {"findings": []}

    def answer(system, user, schema):
        rows = re.findall(r"^\[(S\d+)\] (.*)$", user, re.M)
        if "verdict" in schema["properties"]:
            return {"verdict": "survived", "answer": f"{rows[0][1]} [{rows[0][0]}]", "gaps": ""}
        if "entities" in schema["properties"]:
            names = sorted(set(re.findall(r"\b(Acme Corp|Borealis Semiconductor|Zenith Micro)\b", user)))
            sid = rows[0][0]
            return {"entities": [{"name": n, "note": "named in findings", "sources": [sid]} for n in names], "gaps": ""}
        return {"answer": " ".join(f"{c} [{s}]" for s, c in rows[:3]), "confidence": "medium", "gaps": ""}

    def review(system, user, schema):
        return {"reason": "scripted", "decision": "wait" if "(nothing pending)" not in user else "finish",
                "follow_ups": []}

    def synthesize(system, user, schema):
        cites = re.findall(r"result: (.*)", user)
        return "Scripted synthesis. " + " ".join(cites)[:900] + "\nUncertainty: scripted."

    def deep_step(system, user, schema):
        if "(none yet)" in user:
            return {"reason": "scripted", "action": "investigate",
                    "text": "Which partner constrains Acme Corp advanced packaging supply?"}
        if "VERIFY" not in user:
            return {"reason": "scripted", "action": "verify",
                    "text": "Borealis Semiconductor will double advanced packaging capacity by the end of next year."}
        return {"reason": "scripted", "action": "finish", "text": ""}

    def entity_plan(system, user, schema):
        return {"angles": ["Find companies named in Acme Corp quarterly results coverage",
                           "Find Acme Corp packaging partners and suppliers",
                           "Find Acme Corp competitors with rival accelerators"]}

    def probe(system, user, schema):
        return {"topology": "distributed", "hubs": [], "axis": "factor", "note": "scripted"}

    return {"route": route, "plan": plan, "act": act, "extract": extract, "snippet_extract": snippet_extract,
            "answer": answer, "review": review, "synthesize": synthesize, "deep_step": deep_step,
            "entity_plan": entity_plan, "probe": probe}


def mock_setup(cfg: SwarmConfig, handlers: dict | None = None, delay: float = 0.0, root_mode: str = "WIDE"):
    """Returns (config, execute-kwargs) for a fully offline scripted run."""
    cfg = SwarmConfig.from_dict({**cfg.to_dict(), "web_mode": "live", "cassette": "", "respect_robots": False,
                                 "min_search_interval": 0.0, "name": cfg.name + "-MOCK", "decider": "generative"})
    h = handlers or default_handlers(root_mode)

    def factory(c, tracer, budget, gate):
        return ScriptedLLM(c, tracer, budget, gate, h, delay=delay)

    return cfg, {"llm_factory": factory, "web_kwargs": {"provider": MockProvider(), "fetcher": mock_fetch}}
