"""RulesDecider: every bounded decision made by deterministic heuristics. No model calls.

This is the "is a model even needed for control?" arm. The rules are deliberately simple and
readable; where they are crude (evidence sufficiency especially) that is the point of measuring
them against the model-made decisions.
"""
from __future__ import annotations

import re

from webswarm_baseline.decisions import AtomAction, Decider, Decision, ReviewDecision
from webswarm_baseline.textutil import content_terms, domain_of, objective_key, overlap

_ENTITY = re.compile(r"^\s*(which|what|name|list|identify|who)\b.{0,25}\b(companies|firms|suppliers|vendors|"
                     r"manufacturers|makers|providers|customers|competitors|countries|products)\b|"
                     r"^\s*which\s+(\w+\s+){0,2}\w+s\s+(are|have|supply|make|manufacture|sell|provide|design|"
                     r"produce|build|offer)\b", re.I)
_DEEP = re.compile(r"\b(which|who|what (company|supplier|firm|vendor|customer|factor|country))\b.{3,140}"
                   r"\b(and|,)\s+(how|when|why|what|where|is|are|in which)\b|\bwhy did\b|\bwhat caused\b|"
                   r"\bis it true\b|\bverify\b|\broot cause\b|\btrace\b", re.I)
_WIDE = re.compile(r"\bcompare\b|\bcomparison\b|\bversus\b|\bvs\.?\b|\beach of\b|\bfor each\b|\brespectively\b|"
                   r"\b(main|key|major|biggest|primary)\s+(factors|drivers|risks|reasons|trends|challenges|"
                   r"catalysts|headwinds|tailwinds)\b|\bdrivers and risks\b|\bpros and cons\b", re.I)
_LIST3 = re.compile(r"\b[A-Z][\w&.\-]+(?:\s[A-Z][\w&.\-]+)?,\s+[A-Z][\w&.\-]+(?:\s[A-Z][\w&.\-]+)?,?\s+(?:and|or)\s+[A-Z]")

# Source priors for choosing which result to read. Small, obvious, and easy to edit.
_PRIMARY = ("sec.gov", "investor.", "ir.", "nvidianews.", "q4cdn.com", "federalreserve.gov", "bls.gov",
            "bea.gov", "treasury.gov", "europa.eu", "newsroom.", "press.", ".gov")
_REPUTABLE = ("reuters.com", "apnews.com", "cnbc.com", "bloomberg.com", "ft.com", "wsj.com", "nasdaq.com",
              "marketwatch.com", "finance.yahoo.com", "investopedia.com", "wikipedia.org", "statista.com")
_OFTEN_BLOCKED = ("wsj.com", "ft.com", "bloomberg.com", "seekingalpha.com", "barrons.com", "nytimes.com")

DEFAULTS = {"coverage_to_stop": 0.6, "max_reads": 3, "redundant_overlap": 0.6}


class RulesDecider(Decider):
    name = "rules"

    def __init__(self, options: dict | None = None):
        self.opts = {**DEFAULTS, **(options or {})}

    # ---- route ------------------------------------------------------------------------------

    def route(self, node, modes: list[str]) -> Decision:
        text = node.objective
        mode, why = "ATOM", "no multi-part or unknown-target pattern"
        if _DEEP.search(text):
            mode, why = "DEEP", "unknown target followed by a dependent question, or a claim to check"
        elif "ENTITY_COLLECT" in modes and _ENTITY.search(text):
            mode, why = "ENTITY_COLLECT", "asks for a list of entities to discover"
        elif _WIDE.search(text) or _LIST3.search(text):
            mode, why = "WIDE", "comparison, enumeration, or 'main factors' pattern"
        if node.depth >= 1 and mode == "WIDE" and not (_LIST3.search(text) or re.search(r"\bcompare\b", text, re.I)):
            mode, why = "ATOM", "below the root only explicit multi-entity comparisons are split again"
        return Decision("route", mode, self.name, confidence=None, reason=why)

    # ---- ATOM -------------------------------------------------------------------------------

    def atom_next(self, node, st, steps_left: int) -> AtomAction | None:
        if not st.results and not st.queries:
            return AtomAction("search", query=self._query(node.objective), provider=self.name,
                              thought="rule: first query = objective keywords")
        unread = [i for i in range(1, len(st.results) + 1) if i not in st.read]
        reads_ok = sum(1 for v in st.read.values() if v == "ok")
        enough, why = self._sufficient(node.objective, st.findings, reads_ok)
        if enough:
            return AtomAction("finish", provider=self.name, thought="rule: " + why)
        if st.findings and steps_left <= 1:
            return AtomAction("finish", provider=self.name, thought="rule: last step, have evidence")
        if unread:
            best = max(unread, key=lambda i: self._result_score(node.objective, st.results[i - 1]))
            return AtomAction("read", result=best, provider=self.name, thought="rule: best-scoring unread result")
        if len(st.queries) < 2:
            return None          # nothing left to read: let the main model write a different query
        return AtomAction("finish", provider=self.name, thought="rule: nothing left to read")

    def _sufficient(self, objective: str, findings: list, reads_ok: int) -> tuple[bool, str]:
        """Crude evidence-sufficiency rule: stop when the findings mention most of what the objective
        asks about (and include a figure if it asks for one), or after enough pages either way."""
        if reads_ok >= self.opts["max_reads"]:
            return True, f"{reads_ok} pages read"
        if len(findings) < 2:
            return False, ""
        terms = [t for t in content_terms(objective) if not t.isdigit()]
        said = " ".join(f.claim.lower() for f in findings)
        cover = sum(1 for t in terms if t in said) / len(terms) if terms else 1.0
        wants_figure = bool(re.search(r"\b(how much|how many|revenue|margin|sales|rate|growth|price|cost|share|"
                                      r"capex|expenditure|profit|income)\b", objective, re.I))
        has_figure = bool(re.search(r"\d", said))
        if cover >= self.opts["coverage_to_stop"] and (has_figure or not wants_figure):
            return True, f"findings cover {cover:.0%} of the objective's terms"
        if reads_ok >= 2 and len(findings) >= 3:
            return True, f"{len(findings)} findings from {reads_ok} pages"
        return False, ""

    @staticmethod
    def _query(objective: str) -> str:
        return " ".join(content_terms(objective)[:9])

    def _result_score(self, objective: str, r) -> float:
        d = domain_of(r.url)
        s = overlap(objective, f"{r.title} {r.snippet}")
        if any(p in d or d.startswith(p) for p in _PRIMARY):
            s += 0.25
        elif any(d.endswith(p) for p in _REPUTABLE):
            s += 0.10
        if any(d.endswith(p) for p in _OFTEN_BLOCKED):
            s -= 0.20
        if d in self.swarm.failed_domains:
            s -= 0.50        # another agent already failed to read this site in this run
        if re.search(r"\d", r.snippet):
            s += 0.05
        return s

    # ---- managers ---------------------------------------------------------------------------

    def review(self, node, rt) -> ReviewDecision | None:
        """Wait for everyone, then finish. No follow-ups: writing one needs a model."""
        if rt.pending or rt.held:
            return ReviewDecision("wait", provider=self.name, reason="rule: wait for all sub-tasks")
        return ReviewDecision("finish", provider=self.name, reason="rule: all sub-tasks reported")

    def needs_verification(self, node, claim: str, steps: list[dict]) -> Decision:
        sw = self.swarm
        ids = {s["node"] for s in steps if s["kind"] == "investigate"}
        domains = {sw.evidence.sources[f.source_id].domain for f in sw.evidence.findings if f.node_id in ids}
        need = len(domains) < 2
        return Decision("verify", need, self.name,
                        reason=f"rule: evidence from {len(domains)} independent site(s); verify if fewer than 2")

    def redundant(self, objective: str, existing: list[str], fuzzy: bool = True) -> bool:
        key = objective_key(objective)
        return any(key == objective_key(e) or (fuzzy and overlap(objective, e) >= self.opts["redundant_overlap"])
                   for e in existing)
