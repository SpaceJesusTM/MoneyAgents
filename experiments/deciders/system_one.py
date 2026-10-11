"""SystemOneDecider: the swarm's bounded decisions expressed as typed questions.

Each decision point becomes one or two Choice/Noul questions about a short text state, answered by
whichever backend is configured (local logprob model, real Jev, or the labeled mock). Generative
work stays with the main model: this decider never writes a query, a sub-objective or an answer.
When a decision implies that new text is needed (a new search query, a follow-up objective), it
returns None and the engine's generative path takes over.

Decision points and the question asked:

    route               Choice  ATOM / WIDE / DEEP / ENTITY_COLLECT
    atom: stop?         Noul    "the findings are enough to answer the objective"
    atom: read which?   Choice  one of the unread search results, or NONE (search again)
    review: finish?     Noul    "results already cover what the pending researchers are doing"
    review: follow up?  Noul    "the results reveal a gap or lead nobody covers"
    verify?             Noul    "the claim is already supported by two independent sources"
    redundant?          Noul    "these two objectives look for the same information"

Thresholds are explicit options because a probability is only useful with a cost-aware cut-off:
delegating (WIDE/DEEP) multiplies the work, so below the root it needs a clear margin.
"""
from __future__ import annotations

import time

from webswarm_baseline.decisions import AtomAction, Decider, Decision, GenerativeDecider, ReviewDecision
from webswarm_baseline.textutil import domain_of, objective_key, overlap

from .primitives import Backend, Choice, Noul

ROUTE_CRITERIA = {
    "ATOM": "One focused lookup a single researcher can do with a few searches: a named entity and a "
            "specific fact, metric or narrow topic.",
    "WIDE": "Several named entities to compare, or several independent factors/dimensions that each need "
            "their own research before being combined.",
    "DEEP": "The key entity or cause is not named and must be discovered first and then examined, or a "
            "claim needs step-by-step checking.",
    "ENTITY_COLLECT": "The answer itself is a list of entities that has to be discovered.",
}

DEFAULTS = {
    "delegate_threshold": 0.6,      # below the root: delegate only if P(mode) >= this, else ATOM
    "sufficient_threshold": 0.7,    # ATOM stops when P(findings sufficient) >= this
    "finish_threshold": 0.85,       # manager finishes early when P(pending work is redundant) >= this
    "followup_threshold": 0.7,      # manager asks the main model for follow-ups when P(gap) >= this
    "verify_skip_threshold": 0.8,   # DEEP skips the verifier when P(already double-sourced) >= this
    "redundant_threshold": 0.7,
    "fallback_below": 0.0,          # route: confidence below this defers to the generative router
    "use_for": ["route", "atom", "review", "verify", "redundant"],
}


class SystemOneDecider(Decider):
    def __init__(self, name: str, backend_factory, options: dict | None = None):
        self.name = name
        self._factory = backend_factory
        self.opts = {**DEFAULTS, **(options or {})}
        self.backend: Backend | None = None
        self._generative = GenerativeDecider()

    def bind(self, swarm) -> None:
        super().bind(swarm)
        self._generative.bind(swarm)
        self.backend = self._factory(swarm)

    def _on(self, point: str) -> bool:
        return point in self.opts["use_for"]

    # ---- route ------------------------------------------------------------------------------

    def route(self, node, modes: list[str]) -> Decision:
        if not self._on("route"):
            return self._generative.route(node, modes)
        sw = self.swarm
        t0 = time.perf_counter()
        parent = sw.nodes.get(node.parent) if node.parent is not None else None
        state = f"Research objective: {node.objective}\n"
        state += (f"This objective is one part that a manager already split out of: {parent.objective}\n"
                  if parent else "This is the user's original question.\n")
        ans = self.backend.ask(state, {"mode": Choice(
            "How should this research objective be investigated?", {m: ROUTE_CRITERIA[m] for m in modes})},
            node=node, kind="route")["mode"]
        mode, p = ans.choice, ans.probabilities.get(ans.choice, 1.0)
        reason = "p=" + ", ".join(f"{k}:{v:.2f}" for k, v in sorted(ans.probabilities.items(), key=lambda x: -x[1]))
        if (ans.confidence or 1.0) < self.opts["fallback_below"]:
            d = self._generative.route(node, modes)
            d.reason = f"[typed router unsure ({reason}); generative fallback] {d.reason}"
            d.fallback, d.secs = True, time.perf_counter() - t0
            return d
        if mode != "ATOM" and node.depth >= 1 and p < self.opts["delegate_threshold"]:
            reason += f"; {mode} below delegation threshold {self.opts['delegate_threshold']}, so ATOM"
            mode = "ATOM"
        return Decision("route", mode, self.name, confidence=ans.confidence, reason=reason,
                        secs=time.perf_counter() - t0)

    # ---- ATOM: stop / read which ------------------------------------------------------------

    def atom_next(self, node, st, steps_left: int) -> AtomAction | None:
        if not self._on("atom") or not st.results:
            return None          # the first search query is written by the main model
        unread = [i for i in range(1, len(st.results) + 1) if i not in st.read][-6:]
        if not st.findings and not unread:
            return None
        sw = self.swarm
        state = f"Research objective: {sw._atom_objective(node)}\n\nFindings so far:\n"
        state += (sw._render_findings(st.findings, 8) or "(none)")
        questions = {}
        if st.findings:
            questions["sufficient"] = Noul(
                "The findings so far are enough to answer the research objective.",
                {"true": "every part of the objective is answered by specific facts in the findings",
                 "false": "an important part of the objective is still unanswered"})
        if unread:
            opts = {f"R{i}": f"[{domain_of(st.results[i - 1].url)}] {st.results[i - 1].title[:80]} - "
                             f"{st.results[i - 1].snippet[:130]}" for i in unread}
            opts["NONE"] = "none of these would help; a different search is needed"
            questions["next"] = Choice("Which search result should be opened next to find evidence for the "
                                       "research objective? Prefer official or primary sources.", opts)
        ans = self.backend.ask(state, questions, node=node, kind="atom_next")
        if "sufficient" in ans and ans["sufficient"].noul >= self.opts["sufficient_threshold"]:
            return AtomAction("finish", provider=self.name, thought=f"P(sufficient)={ans['sufficient'].noul:.2f}")
        if "next" in ans and ans["next"].choice != "NONE":
            pick = ans["next"]
            return AtomAction("read", result=int(pick.choice[1:]), provider=self.name,
                              thought=f"P({pick.choice})={pick.probabilities.get(pick.choice, 1.0):.2f}")
        return None              # a new query is needed: generative

    # ---- manager review ---------------------------------------------------------------------

    def review(self, node, rt) -> ReviewDecision | None:
        if not self._on("review"):
            return None
        sw = self.swarm
        b = sw.cfg.budgets
        pending = [sw.nodes[c].objective for c in rt.pending] + [s["objective"] for s in rt.held]
        followups_left = min(b.max_followups - rt.followups_used, b.max_nodes - sw.budget.nodes)
        state = (f"Research objective: {node.objective}\n\nResults so far:\n{sw._render_child_results(rt, 70)}\n\n"
                 "Researchers still working on:\n" + ("\n".join(f"- {p}" for p in pending) or "(nobody)"))
        questions = {}
        if pending:
            questions["finish"] = Noul(
                "The results so far already cover everything the researchers still working are looking into.",
                {"true": "waiting for them could not change the answer",
                 "false": "they are covering parts that the results do not address yet"})
        if followups_left > 0:
            questions["gap"] = Noul(
                "The results reveal an important gap or new lead for the objective that no researcher, finished "
                "or still working, covers.")
        if not questions:
            return ReviewDecision("finish", provider=self.name, reason="nothing pending, no follow-ups left")
        ans = self.backend.ask(state, questions, node=node, kind="review")
        why = ", ".join(f"P({k})={v.noul:.2f}" for k, v in ans.items())
        if "finish" in ans and ans["finish"].noul >= self.opts["finish_threshold"]:
            return ReviewDecision("finish", provider=self.name, reason=why)
        if "gap" in ans and ans["gap"].noul >= self.opts["followup_threshold"]:
            sw.tracer.event("decision", node.id, point="review_gate", value="write_follow_ups", provider=self.name,
                            reason=why)
            return None          # the main model writes the follow-up objectives
        return ReviewDecision("wait" if pending else "finish", provider=self.name, reason=why)

    # ---- verification -----------------------------------------------------------------------

    def needs_verification(self, node, claim: str, steps: list[dict]) -> Decision:
        if not self._on("verify"):
            return super().needs_verification(node, claim, steps)
        sw = self.swarm
        t0 = time.perf_counter()
        ids = {s["node"] for s in steps if s["kind"] == "investigate"}
        domains = sorted({sw.evidence.sources[f.source_id].domain for f in sw.evidence.findings if f.node_id in ids})
        evidence = "\n".join(f"- {s['answer'][:300]}" for s in steps if s["kind"] == "investigate" and s["answer"])
        state = (f"Claim: {claim}\n\nEvidence gathered so far:\n{evidence}\n\n"
                 f"Websites the evidence came from: {', '.join(domains) or '(none)'}")
        p = self.backend.ask(state, {"supported": Noul(
            "The claim is already directly supported by evidence from at least two independent websites.")},
            node=node, kind="verify")["supported"].noul
        need = p < self.opts["verify_skip_threshold"]
        return Decision("verify", need, self.name, confidence=abs(p - 0.5) * 2,
                        reason=f"P(already double-sourced)={p:.2f}; domains={len(domains)}",
                        secs=time.perf_counter() - t0)

    # ---- redundancy -------------------------------------------------------------------------

    def redundant(self, objective: str, existing: list[str]) -> bool:
        key = objective_key(objective)
        if any(key == objective_key(e) for e in existing):
            return True
        if not self._on("redundant"):
            return False
        for e in existing:
            sim = overlap(objective, e)
            if sim >= 0.8:
                return True
            if sim >= 0.4:   # only borderline pairs are worth a model call
                p = self.backend.ask(f"Objective 1: {objective}\nObjective 2: {e}", {"same": Noul(
                    "A researcher given objective 1 and a researcher given objective 2 would look for the "
                    "same information.")}, kind="redundant")["same"].noul
                if p >= self.opts["redundant_threshold"]:
                    return True
        return False
