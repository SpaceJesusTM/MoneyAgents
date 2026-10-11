"""The recursive research engine.

Every agent node runs the same LangGraph lifecycle in its own thread:

    START -> route -+-> atom ------------------------------------------> END
                    +-> plan -> dispatch -> collect -> review -+-> dispatch   (follow-up work)
                                              ^----------------+-> collect    (keep waiting)
                                                               +-> synthesize -> END

`route` picks the search mode. ATOM is a ReAct-style loop (search / read / extract) in plain
Python. The three manager modes share plan -> dispatch -> collect -> review -> synthesize and
differ only in policy:

    WIDE            plan independent children, run them concurrently, review results as they arrive
    DEEP            one step at a time: investigate, read the result, decide the next step, then
                    send an independent verifier before finishing
    ENTITY_COLLECT  several discovery paths, merge and de-duplicate, verify weakly supported names

`dispatch` starts child threads that run this same graph, which is where the recursion comes from.
Children push their id onto the parent's queue when they finish; `collect` is what lets a manager
act on early results instead of waiting for the whole batch (config: review_policy).
"""
from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from . import prompts
from .config import SwarmConfig
from .decisions import AtomAction, Decider, Decision, ReviewDecision
from .evidence import EvidenceStore, Finding, audit_answer, cited_ids, strip_unknown_citations
from .llm import LLMError
from .runtime import Budget, BudgetExceeded, Cancelled, Tracer
from .textutil import (clean_page_text, domain_of, norm, number_lines, numbers_in, objective_key,
                       select_passages)
from .web import SearchResult, WebClient

MANAGER_MODES = ("WIDE", "DEEP", "ENTITY_COLLECT")


class AgentState(TypedDict):
    nid: int
    next: str


@dataclass
class NodeResult:
    status: str = "failed"        # ok | partial | failed
    answer: str = ""
    confidence: str = "low"
    gaps: str = ""
    verdict: str = ""             # verifiers only
    entities: list = field(default_factory=list)   # collectors / ENTITY_COLLECT only
    sources: list = field(default_factory=list)    # source ids cited in the answer


@dataclass
class Node:
    id: int
    parent: int | None
    depth: int
    objective: str
    role: str = "research"        # research | verifier | collector
    forced_mode: str | None = None
    mode: str | None = None       # what was executed
    model_mode: str | None = None  # what the decider chose (differs when a limit overrode it)
    status: str = "pending"       # pending | running | ok | partial | failed | cancelled
    reason: str = ""
    notes: list = field(default_factory=list)
    children: list = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created: float = 0.0
    started: float | None = None
    finished: float | None = None
    result: NodeResult | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def public(self) -> dict:
        d = {k: v for k, v in asdict_safe(self).items() if k not in ("cancel", "context")}
        d["context_keys"] = sorted(self.context)
        return d


def asdict_safe(node: Node) -> dict:
    out = {}
    for k, v in node.__dict__.items():
        if k == "cancel":
            continue
        out[k] = asdict(v) if isinstance(v, NodeResult) else v
    return out


@dataclass
class AtomState:
    results: list = field(default_factory=list)      # SearchResult, numbered from 1 in prompts
    read: dict = field(default_factory=dict)         # result index -> "ok" | failure reason
    queries: list = field(default_factory=list)
    findings: list = field(default_factory=list)     # Finding
    last_query: str = ""
    batch_start: int = 1                             # index of the first result of the latest search


@dataclass
class ManagerRT:
    """Mutable per-manager state that does not belong in the graph state (queues, sets)."""
    queue: "queue.Queue[int]" = field(default_factory=queue.Queue)
    pending: set = field(default_factory=set)
    done: list = field(default_factory=list)         # child ids in arrival order
    fresh: list = field(default_factory=list)        # arrived since the last review
    to_dispatch: list = field(default_factory=list)  # child specs waiting to be started
    held: list = field(default_factory=list)         # specs held back until scouts report
    scouts: set = field(default_factory=set)
    tips: str = ""
    hint: dict = field(default_factory=dict)         # web-probing result
    followups_used: int = 0
    reviews: int = 0
    rounds: int = 0                                  # DEEP investigate rounds used
    verified: bool = False                           # DEEP: a verifier has been sent
    steps: list = field(default_factory=list)        # DEEP step log
    phase: str = ""                                  # ENTITY_COLLECT: discover | verify
    table: list = field(default_factory=list)        # ENTITY_COLLECT merged entities
    early_finish: bool = False


class Swarm:
    def __init__(self, cfg: SwarmConfig, llm, web: WebClient, tracer: Tracer, budget: Budget,
                 evidence: EvidenceStore, decider: Decider):
        self.cfg, self.llm, self.web, self.tracer = cfg, llm, web, tracer
        self.budget, self.evidence, self.decider = budget, evidence, decider
        self.today = date.today().isoformat()
        self.root_question = ""
        self.nodes: dict[int, Node] = {}
        self._rt: dict[int, ManagerRT] = {}
        self._threads: list[threading.Thread] = []
        self._lock = threading.RLock()
        self.failed_domains: dict[str, str] = {}
        self.graph = self._build_graph()
        decider.bind(self)

    # =============================================================================================
    # graph
    # =============================================================================================

    def _build_graph(self):
        g = StateGraph(AgentState)
        g.add_node("route", self._g_route)
        g.add_node("atom", self._g_atom)
        g.add_node("plan", self._g_plan)
        g.add_node("dispatch", self._g_dispatch)
        g.add_node("collect", self._g_collect)
        g.add_node("review", self._g_review)
        g.add_node("synthesize", self._g_synthesize)
        nxt = lambda s: s["next"]  # noqa: E731
        g.add_edge(START, "route")
        g.add_conditional_edges("route", nxt, {"atom": "atom", "plan": "plan"})
        g.add_edge("atom", END)
        g.add_conditional_edges("plan", nxt, {"dispatch": "dispatch", "atom": "atom", "synthesize": "synthesize"})
        g.add_conditional_edges("dispatch", nxt, {"collect": "collect", "synthesize": "synthesize"})
        g.add_edge("collect", "review")
        g.add_conditional_edges("review", nxt, {"dispatch": "dispatch", "collect": "collect",
                                                "synthesize": "synthesize"})
        g.add_edge("synthesize", END)
        return g.compile()

    # =============================================================================================
    # run
    # =============================================================================================

    def run(self, question: str) -> dict:
        self.root_question = question.strip()
        root = self._new_node(self.root_question, None)
        self._run_node(root)
        for n in list(self.nodes.values()):   # stop anything still working (early finish, deadline)
            n.cancel.set()
        stragglers = 0
        for t in self._threads:
            t.join(timeout=90)
            stragglers += t.is_alive()
        res = root.result or NodeResult()
        answer, removed = strip_unknown_citations(res.answer, set(self.evidence.sources))
        audit = audit_answer(answer, self.evidence) if self.cfg.final_audit else {}
        self.tracer.event("run_end", root.id, status=root.status, stragglers=stragglers,
                          removed_citations=removed)
        return {"answer": answer, "status": root.status, "confidence": res.confidence, "gaps": res.gaps,
                "audit": audit, "removed_citations": removed, "stragglers": stragglers}

    def _new_node(self, objective: str, parent: Node | None, role: str = "research",
                  forced_mode: str | None = None, context: dict | None = None) -> Node | None:
        if not self.budget.take_node():
            return None
        with self._lock:
            node = Node(id=len(self.nodes), parent=parent.id if parent else None,
                        depth=parent.depth + 1 if parent else 0, objective=objective.strip(),
                        role=role, forced_mode=forced_mode, context=dict(context or {}),
                        created=round(self.tracer.now(), 3))
            self.nodes[node.id] = node
            if parent:
                parent.children.append(node.id)
        self.tracer.event("node_created", node.id, parent=node.parent, depth=node.depth, role=role,
                          objective=node.objective)
        return node

    def _run_node(self, node: Node) -> None:
        node.status, node.started = "running", round(self.tracer.now(), 3)
        try:
            self._checkpoint(node)
            self.graph.invoke({"nid": node.id, "next": ""}, {"recursion_limit": 120})
        except Cancelled:
            node.status = "cancelled"
        except BudgetExceeded as e:
            node.notes.append(f"stopped: budget {e}")
        except Exception as e:  # noqa: BLE001 - one broken node must not take the run down
            node.notes.append(f"error: {type(e).__name__}: {e}"[:300])
            node.status = "failed"
        finally:
            if node.result is None:
                node.result = NodeResult(status="failed", gaps="no result produced")
            if node.status == "running":
                node.status = node.result.status
            node.finished = round(self.tracer.now(), 3)
            self.tracer.event("node_end", node.id, status=node.status, mode=node.mode,
                              secs=round(node.finished - (node.started or node.finished), 3),
                              confidence=node.result.confidence, verdict=node.result.verdict or None)
            if node.parent is not None:
                self._rt[node.parent].queue.put(node.id)

    def _stopped(self, node: Node) -> bool:
        if self.budget.expired():
            return True
        n: Node | None = node
        while n is not None:
            if n.cancel.is_set():
                return True
            n = self.nodes.get(n.parent) if n.parent is not None else None
        return False

    def _checkpoint(self, node: Node) -> None:
        if self._stopped(node):
            raise Cancelled()

    def _note(self, node: Node, text: str) -> None:
        node.notes.append(text)
        self.tracer.event("note", node.id, text=text)

    def _decision(self, node: Node, d: Decision) -> None:
        self.tracer.event("decision", node.id, point=d.point, value=d.value, provider=d.provider,
                          confidence=d.confidence, reason=d.reason[:240], secs=round(d.secs, 3),
                          fallback=d.fallback)

    # =============================================================================================
    # route
    # =============================================================================================

    def _g_route(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        b = self.cfg.budgets
        if node.forced_mode:
            node.mode = node.model_mode = node.forced_mode
            node.reason = "assigned by parent"
        else:
            modes = ["ATOM", "WIDE", "DEEP"] + (["ENTITY_COLLECT"] if self.cfg.allow_entity_collect else [])
            try:
                d = self.decider.route(node, modes)
                mode = d.value if d.value in modes else "ATOM"
                self._decision(node, d)
                node.reason = d.reason
            except (LLMError, BudgetExceeded) as e:
                mode = "ATOM"
                self._note(node, f"routing failed ({e}); defaulted to ATOM")
            node.model_mode = node.mode = mode
            if mode != "ATOM" and node.depth >= b.max_depth:
                self._note(node, f"max depth {b.max_depth} reached; {mode} forced to ATOM")
                node.mode = "ATOM"
            elif mode != "ATOM" and self.budget.nodes >= b.max_nodes:
                self._note(node, f"node budget exhausted; {mode} forced to ATOM")
                node.mode = "ATOM"
        self.tracer.event("node_mode", node.id, mode=node.mode, model_mode=node.model_mode)
        if node.mode in MANAGER_MODES:
            self._rt[node.id] = ManagerRT()
            return {"next": "plan"}
        return {"next": "atom"}

    # =============================================================================================
    # ATOM: ReAct-style focused research
    # =============================================================================================

    def _g_atom(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        node.mode = node.mode or "ATOM"
        st = AtomState(results=list(node.context.get("seed_results", [])))
        steps = self.cfg.budgets.atom_max_steps
        try:
            for step in range(steps):
                self._checkpoint(node)
                if self.budget.wrapping_up() and (st.findings or st.results):
                    self._note(node, "time budget: stopped gathering to write up")
                    break
                action = self._atom_next(node, st, steps - step)
                self.tracer.event("atom_action", node.id, step=step, action=action.kind, query=action.query,
                                  result=action.result, provider=action.provider, thought=action.thought[:160])
                if action.kind == "finish":
                    break
                if action.kind == "search":
                    st.queries.append(action.query)
                    st.last_query = action.query
                    found = self.web.search(action.query, node)
                    if not found:
                        simpler = simplify_query(action.query)
                        if simpler and norm(simpler) not in {norm(q) for q in st.queries}:
                            self._note(node, f"search returned nothing; retried as {simpler!r}")
                            st.queries.append(simpler)
                            found = self.web.search(simpler, node)
                    known = {r.url for r in st.results}
                    st.batch_start = len(st.results) + 1
                    st.results.extend(r for r in found if r.url not in known)
                elif action.kind == "read":
                    self._atom_read(node, st, action.result)
        except (BudgetExceeded, Cancelled) as e:
            self._note(node, f"research cut short: {type(e).__name__} {e}".strip())
        except LLMError as e:
            self._note(node, f"research cut short: {e}")
        if self._stopped(node):
            # cancelled or out of time: no further model calls. Keep what was found, unwritten.
            node.result = self._raw_result(node, st, "stopped before an answer was written")
            if not st.findings:
                raise Cancelled()
            return {"next": ""}
        if not st.findings and st.results:
            self._snippet_fallback(node, st)
        node.result = self._atom_answer(node, st)
        return {"next": ""}

    @staticmethod
    def _raw_result(node: Node, st: AtomState, why: str) -> NodeResult:
        """Findings returned as-is (no model call). They are real evidence even without prose."""
        answer = " ".join(f"{f.claim} [{f.source_id}]" for f in st.findings[:6])
        return NodeResult(status="partial" if st.findings else "failed", answer=answer, confidence="low",
                          gaps=why, sources=sorted({f.source_id for f in st.findings}),
                          verdict="unverifiable" if node.role == "verifier" else "")

    def _atom_next(self, node: Node, st: AtomState, steps_left: int) -> AtomAction:
        unread = [i for i in range(1, len(st.results) + 1) if i not in st.read]
        # when a choice has to be repaired, prefer results of the latest search over leftovers
        best_unread = next((i for i in unread if i >= st.batch_start), unread[0] if unread else 0)
        action = self.decider.atom_next(node, st, steps_left)   # None = no opinion
        if action is None:
            action = self._act_generative(node, st, steps_left)

        # ---- guards: a small model's malformed choice is repaired, and every repair is recorded ----
        if not st.results and not st.queries and action.kind != "search":
            self._note(node, f"first action was {action.kind!r} with no results; searched the objective instead")
            return AtomAction("search", query=node.objective[:200], provider="guard")
        if action.kind == "search":
            q = re.sub(r"\s+", " ", action.query).strip()
            if not q or norm(q) in {norm(x) for x in st.queries}:
                if unread:
                    self._note(node, "repeated/empty query; read the next unread result instead")
                    return AtomAction("read", result=best_unread, provider="guard")
                if not st.queries:
                    return AtomAction("search", query=node.objective[:200], provider="guard")
                return AtomAction("finish", provider="guard")
            action.query = q[:200]
        if action.kind == "read" and action.result not in unread:
            if unread:
                self._note(node, f"asked to read result {action.result}, which is not an unread result; "
                                 f"read {best_unread} instead")
                action.result = best_unread
            else:
                return AtomAction("finish", provider="guard")
        if action.kind == "finish" and not st.findings and unread and steps_left > 1:
            self._note(node, "finish with no evidence overridden; read the next unread result")
            return AtomAction("read", result=best_unread, provider="guard")
        return action

    def _act_generative(self, node: Node, st: AtomState, steps_left: int) -> AtomAction:
        out = self.llm.json("act", node, prompts.ACT_SYSTEM, prompts.ACT_USER.format(
            today=self.today, objective=self._atom_objective(node), context=self._atom_context(node),
            queries="; ".join(f'"{q}"' for q in st.queries) or "(none)",
            results=self._render_results(st) or ("(no searches yet)" if not st.results else "(none left)"),
            opened=self._render_opened(st),
            findings=self._render_findings(st.findings, 8) or "(none)", steps_left=steps_left),
            prompts.ACT_SCHEMA, max_tokens=120)
        return AtomAction(out.get("action", "finish"), query=str(out.get("query", "")),
                          result=int(out.get("result") or 0), thought=str(out.get("thought", "")))

    def _atom_objective(self, node: Node) -> str:
        if node.role == "verifier":
            return f"Verify this claim independently, from primary sources: {node.objective}"
        return node.objective

    def _atom_context(self, node: Node) -> str:
        lines = []
        if node.context.get("known"):
            lines.append("Known from earlier steps: " + node.context["known"])
        if node.context.get("tips"):
            lines.append("Tips from sibling researchers: " + node.context["tips"])
        return "\n".join(lines)

    def _render_results(self, st: AtomState, limit: int = 8) -> str:
        """Only unread results are offered, so an already-opened page cannot be chosen again."""
        rows = []
        for i, r in enumerate(st.results, start=1):
            if i in st.read:
                continue
            mark = ""
            if self.cfg.experience_sharing and domain_of(r.url) in self.failed_domains:
                mark = " (this site failed for another researcher)"
            rows.append(f"R{i} [{domain_of(r.url)}] {r.title[:90]} - {r.snippet[:170]}{mark}")
        return "\n".join(rows[-limit:])

    @staticmethod
    def _render_opened(st: AtomState) -> str:
        parts = [f"R{i} {domain_of(st.results[i - 1].url)} ({'read' if why == 'ok' else 'could not be read'})"
                 for i, why in st.read.items()]
        return ", ".join(parts) or "(none)"

    @staticmethod
    def _render_findings(findings: list[Finding], limit: int = 12) -> str:
        return "\n".join(f"[{f.source_id}] {f.claim}" for f in findings[-limit:])

    def _atom_read(self, node: Node, st: AtomState, idx: int) -> None:
        r: SearchResult = st.results[idx - 1]
        page = self.web.fetch(r.url, node)
        if not page.ok:
            st.read[idx] = page.error or "empty page"
            with self._lock:
                self.failed_domains[domain_of(r.url)] = st.read[idx]
            return
        st.read[idx] = "ok"
        focus = f"{node.objective} {st.last_query}"
        text = clean_page_text(page.text)   # quotes are checked against the same text the model saw
        excerpt = select_passages(text, focus, self.cfg.page_chars)
        head = dict(objective=self._atom_objective(node), title=(page.title or r.title)[:120],
                    domain=domain_of(page.final_url or r.url))
        if self.cfg.extract_mode == "lines":
            proposals = self._extract_by_line(node, excerpt, head)
        else:
            out = self.llm.json("extract", node, prompts.EXTRACT_SYSTEM.format(max_findings=3),
                                prompts.EXTRACT_USER.format(text=excerpt, **head),
                                prompts.EXTRACT_SCHEMA, max_tokens=340)
            proposals = [(f.get("claim", ""), f.get("quote", "")) for f in out.get("findings", [])[:4]]
        out = {"findings": proposals}
        accepted = 0
        for claim, quote in proposals:
            got = self.evidence.record(claim, quote, r.url, page.title or r.title, "page", node.id, text)
            if got and got not in st.findings:
                st.findings.append(got)
                accepted += 1
        self.tracer.event("page_read", node.id, url=r.url, domain=domain_of(r.url), chars=len(page.text),
                          shown_chars=len(excerpt), proposed=len(out.get("findings", [])), accepted=accepted)

    def _extract_by_line(self, node: Node, excerpt: str, head: dict) -> list[tuple[str, str]]:
        """extract_mode="lines": the model cites a line number; the line itself becomes the quote.

        The quote is exact by construction, so the check moves to the claim: every figure in the
        claim must appear on the cited line or the line next to it, otherwise it is dropped."""
        lines = number_lines(excerpt)
        shown = "\n".join(f"[{i}] {ln}" for i, ln in enumerate(lines, 1))
        out = self.llm.json("extract", node, prompts.EXTRACT_LINES_SYSTEM.format(max_findings=3),
                            prompts.EXTRACT_USER.format(text=shown, **head),
                            prompts.EXTRACT_LINES_SCHEMA, max_tokens=220)
        proposals = []
        for f in out.get("findings", [])[:4]:
            i = int(f.get("line") or 0)
            claim = str(f.get("claim", ""))
            if not 1 <= i <= len(lines):
                self.tracer.event("finding_rejected", node.id, claim=claim[:160], quote="",
                                  reason=f"cited line {i} does not exist")
                continue
            near = " ".join(lines[max(0, i - 2):i + 1])
            missing = [n for n in numbers_in(claim) if n not in set(numbers_in(near))]
            if missing:
                self.tracer.event("finding_rejected", node.id, claim=claim[:160], quote=lines[i - 1][:160],
                                  reason=f"figures {missing[:3]} are not on the cited line")
                continue
            proposals.append((claim, lines[i - 1][:400]))
        return proposals

    def _snippet_fallback(self, node: Node, st: AtomState) -> None:
        """No page yielded evidence: fall back to the search-result snippets, marked as weaker."""
        rows = st.results[:8]
        text = "\n".join(f"{i} [{domain_of(r.url)}] {r.title[:90]}: {r.snippet}" for i, r in enumerate(rows, 1))
        try:
            out = self.llm.json("snippet_extract", node, prompts.EXTRACT_SYSTEM.format(max_findings=3),
                                prompts.SNIPPET_EXTRACT_USER.format(objective=self._atom_objective(node), text=text),
                                prompts.SNIPPET_EXTRACT_SCHEMA, max_tokens=380)
        except (LLMError, BudgetExceeded) as e:
            self._note(node, f"snippet fallback failed: {e}")
            return
        for f in out.get("findings", []):
            i = int(f.get("result") or 0)
            if not 1 <= i <= len(rows):
                continue
            r = rows[i - 1]
            snippet_text = f"{r.title} {r.snippet}"
            got = self.evidence.record(f.get("claim", ""), f.get("quote", ""), r.url, r.title, "snippet",
                                       node.id, snippet_text)
            if got and got not in st.findings:
                st.findings.append(got)
        self._note(node, f"no page evidence; used search snippets ({len(st.findings)} findings)")

    def _atom_answer(self, node: Node, st: AtomState) -> NodeResult:
        failures = [f"{domain_of(st.results[i - 1].url)}: {why}" for i, why in st.read.items() if why != "ok"]
        if not st.findings:
            gaps = "No usable evidence was retrieved."
            if failures:
                gaps += " Pages that could not be read: " + "; ".join(failures[:4]) + "."
            verdict = "unverifiable" if node.role == "verifier" else ""
            return NodeResult(status="failed", answer="", confidence="low", gaps=gaps, verdict=verdict)
        findings = self._render_findings(st.findings, 12)
        known = {f.source_id for f in st.findings}
        try:
            if node.role == "verifier":
                out = self.llm.json("answer", node, prompts.VERIFY_ANSWER_SYSTEM,
                                    prompts.VERIFY_ANSWER_USER.format(today=self.today, objective=node.objective,
                                                                      findings=findings),
                                    prompts.VERIFY_ANSWER_SCHEMA, max_tokens=260)
                answer, _ = strip_unknown_citations(out.get("answer", ""), known)
                return NodeResult(status="ok", answer=answer, verdict=out.get("verdict", "unverifiable"),
                                  confidence="medium", gaps=out.get("gaps", ""), sources=cited_ids(answer))
            if node.role == "collector":
                target = node.context.get("collect_for", node.objective)
                out = self.llm.json("answer", node, prompts.ENTITY_ANSWER_SYSTEM,
                                    prompts.ANSWER_USER.format(today=self.today, objective=target, findings=findings),
                                    prompts.ENTITY_ANSWER_SCHEMA, max_tokens=520)
                ents = []
                for e in out.get("entities", []):
                    srcs = [s for s in (str(x).strip("[] ") for x in e.get("sources", [])) if s in known]
                    if e.get("name") and srcs:
                        ents.append({"name": e["name"].strip(), "note": e.get("note", "").strip(), "sources": srcs})
                answer = "; ".join(f"{e['name']} [{', '.join(e['sources'])}]" for e in ents)
                return NodeResult(status="ok" if ents else "failed", answer=answer, entities=ents,
                                  confidence="medium" if ents else "low", gaps=out.get("gaps", ""),
                                  sources=sorted({s for e in ents for s in e["sources"]}))
            words = 200 if node.parent is None else 110
            out = self.llm.json("answer", node, prompts.ANSWER_SYSTEM.format(words=words),
                                prompts.ANSWER_USER.format(today=self.today, objective=node.objective,
                                                           findings=findings),
                                prompts.ANSWER_SCHEMA, max_tokens=int(words * 2.2) + 80)
            answer, removed = strip_unknown_citations(out.get("answer", ""), known)
            if removed:
                self._note(node, f"removed citations to unknown sources: {removed}")
            status = "ok" if cited_ids(answer) else "partial"
            if failures and status == "ok" and not out.get("gaps"):
                out["gaps"] = ""
            return NodeResult(status=status, answer=answer, confidence=out.get("confidence", "low"),
                              gaps=out.get("gaps", ""), sources=cited_ids(answer))
        except (LLMError, BudgetExceeded) as e:
            self._note(node, f"answer step failed ({e}); returning raw findings")
            return self._raw_result(node, st, "answer not written (model call failed)")

    # =============================================================================================
    # managers: plan
    # =============================================================================================

    def _g_plan(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        rt = self._rt[node.id]
        try:
            self._checkpoint(node)
            if node.mode == "WIDE":
                ok = self._plan_wide(node, rt)
            elif node.mode == "DEEP":
                ok = self._deep_decide(node, rt) == "dispatch"
            else:
                ok = self._plan_entity(node, rt)
        except Cancelled:
            raise
        except (LLMError, BudgetExceeded) as e:
            ok = False
            self._note(node, f"planning failed ({e})")
        if ok and rt.to_dispatch:
            return {"next": "dispatch"}
        self._note(node, f"{node.mode} produced no sub-tasks; handled as ATOM")
        node.mode = "ATOM"
        return {"next": "atom"}

    def _plan_wide(self, node: Node, rt: ManagerRT) -> bool:
        hint_text = ""
        max_children = self.cfg.budgets.max_children
        if self.cfg.web_probing:
            self._probe(node, rt)
            h = rt.hint
            if h:
                hint_text = f"\nHow the information is organised on the web: {h['topology']}. {h.get('note', '')}"
                if h["topology"] == "distributed" and h.get("axis"):
                    hint_text += f" Organise the sub-objectives by: {h['axis']}."
                elif h["topology"].startswith("centralized") and h.get("hub_results"):
                    max_children = min(max_children, 2 if h["topology"] == "centralized" else 3)
                    hint_text += (" A few hub pages cover most of it, so use few sub-objectives, each aimed at "
                                  "extracting one part from those pages.")
        out = self.llm.json("plan", node, prompts.PLAN_SYSTEM.format(max_children=max_children),
                            prompts.PLAN_USER.format(today=self.today, root=self.root_question,
                                                     objective=node.objective, hint=hint_text),
                            prompts.PLAN_SCHEMA, max_tokens=360)
        kids = [k.strip() for k in out.get("children", []) if isinstance(k, str) and len(k.strip()) > 12]
        self.tracer.event("plan", node.id, reason=out.get("reason", "")[:240], proposed=kids,
                          probing=rt.hint.get("topology") if rt.hint else None)
        if len(kids) > max_children:
            self._note(node, f"{len(kids)} sub-objectives proposed; kept the first {max_children}")
            kids = kids[:max_children]
        seeds = rt.hint.get("hub_results", []) if rt.hint else []
        rt.to_dispatch = [{"objective": k, "context": {"seed_results": list(seeds)} if seeds else {}} for k in kids]
        return bool(kids)

    def _probe(self, node: Node, rt: ManagerRT) -> None:
        """Web probing (WebSwarm 3.3): look at how the information is organised before splitting."""
        try:
            results = self.web.search(node.objective[:200], node)
            if not results:
                return
            text = "\n".join(f"{i} [{domain_of(r.url)}] {r.title[:90]} - {r.snippet[:200]}"
                             for i, r in enumerate(results, 1))
            out = self.llm.json("probe", node, prompts.PROBE_SYSTEM,
                                prompts.PROBE_USER.format(objective=node.objective, results=text),
                                prompts.PROBE_SCHEMA, max_tokens=140)
        except (LLMError, BudgetExceeded) as e:
            self._note(node, f"web probing failed ({e}); planning without it")
            return
        hubs = [results[i - 1] for i in out.get("hubs", []) if isinstance(i, int) and 1 <= i <= len(results)]
        rt.hint = {"topology": out.get("topology", "distributed"), "axis": out.get("axis", "").strip(),
                   "note": out.get("note", "").strip()[:200], "hub_results": hubs}
        self.tracer.event("probe", node.id, topology=rt.hint["topology"], axis=rt.hint["axis"],
                          note=rt.hint["note"], hubs=[h.url for h in hubs])

    def _plan_entity(self, node: Node, rt: ManagerRT) -> bool:
        paths = self.cfg.budgets.entity_paths
        out = self.llm.json("entity_plan", node, prompts.ENTITY_PLAN_SYSTEM.format(paths=paths),
                            prompts.ENTITY_PLAN_USER.format(today=self.today, objective=node.objective),
                            prompts.ENTITY_PLAN_SCHEMA, max_tokens=300)
        angles = [a.strip() for a in out.get("angles", []) if isinstance(a, str) and len(a.strip()) > 12][:paths]
        self.tracer.event("plan", node.id, reason="entity discovery paths", proposed=angles)
        rt.phase = "discover"
        rt.to_dispatch = [{"objective": a, "role": "collector", "forced_mode": "ATOM",
                           "context": {"collect_for": node.objective}} for a in angles]
        return bool(angles)

    # =============================================================================================
    # managers: dispatch / collect
    # =============================================================================================

    def _g_dispatch(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        rt = self._rt[node.id]
        specs, rt.to_dispatch = rt.to_dispatch, []
        if self._stopped(node):
            specs = []

        # sibling experience sharing (WebSwarm 3.3): run scouts first, hold the rest back
        if (self.cfg.experience_sharing and node.mode == "WIDE" and not rt.done and not rt.scouts
                and len(specs) >= 3):
            n_scouts = min(self.cfg.scout_count, len(specs) - 1)
            specs, rt.held = specs[:n_scouts], specs[n_scouts:]
            scouting = True
        else:
            scouting = False

        existing = self._lineage_objectives(node)
        started = []
        for spec in specs:
            obj = spec["objective"]
            if self.decider.redundant(obj, existing):
                self._note(node, f"dropped redundant sub-objective: {obj[:100]!r}")
                self.tracer.event("redundant_dropped", node.id, objective=obj)
                continue
            child = self._new_node(obj, node, role=spec.get("role", "research"),
                                   forced_mode=spec.get("forced_mode"), context=spec.get("context"))
            if child is None:
                self._note(node, f"node budget reached; not started: {obj[:100]!r}")
                continue
            existing.append(obj)
            if spec.get("step_kind"):
                child.context["step_kind"] = spec["step_kind"]
            rt.pending.add(child.id)
            if scouting:
                rt.scouts.add(child.id)
            started.append(child)
        for child in started:
            t = threading.Thread(target=self._run_node, args=(child,), name=f"node-{child.id}", daemon=True)
            self._threads.append(t)
            t.start()
        self.tracer.event("dispatch", node.id, started=[c.id for c in started], held=len(rt.held),
                          scouting=scouting)
        if not rt.pending and not rt.held:
            return {"next": "synthesize"}
        return {"next": "collect"}

    def _lineage_objectives(self, node: Node) -> list[str]:
        out = [self.nodes[c].objective for c in node.children]
        n: Node | None = node
        while n is not None:
            out.append(n.objective)
            n = self.nodes.get(n.parent) if n.parent is not None else None
        return out

    def _g_collect(self, state: AgentState) -> dict:
        """Wait for child results. `incremental`: return as soon as one arrives (plus anything else
        already queued). `batch`: return only when every pending child has reported."""
        node = self.nodes[state["nid"]]
        rt = self._rt[node.id]
        wait_all = self.cfg.review_policy == "batch"
        while rt.pending:
            if self._stopped(node):
                self._cancel_children(node, rt, "manager stopped")
                break
            try:
                cid = rt.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._arrived(node, rt, cid)
            while True:  # drain anything else that is already there
                try:
                    self._arrived(node, rt, rt.queue.get_nowait())
                except queue.Empty:
                    break
            if not wait_all:
                break
        return {"next": ""}

    def _arrived(self, node: Node, rt: ManagerRT, cid: int) -> None:
        if cid not in rt.pending:
            return
        rt.pending.discard(cid)
        rt.done.append(cid)
        rt.fresh.append(cid)
        child = self.nodes[cid]
        self.tracer.event("child_result", node.id, child=cid, status=child.status,
                          pending=len(rt.pending), confidence=child.result.confidence if child.result else None)

    def _cancel_children(self, node: Node, rt: ManagerRT, why: str) -> None:
        for cid in list(rt.pending):
            self.nodes[cid].cancel.set()
            self.tracer.event("child_cancelled", node.id, child=cid, reason=why)
        rt.pending.clear()
        rt.held.clear()

    # =============================================================================================
    # managers: review
    # =============================================================================================

    def _g_review(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        rt = self._rt[node.id]
        fresh, rt.fresh = rt.fresh, []
        try:
            if self._stopped(node):
                self._cancel_children(node, rt, "manager stopped")
                return {"next": "synthesize"}
            if node.mode == "DEEP":
                for cid in fresh:
                    self._deep_record(rt, self.nodes[cid])
                return {"next": self._deep_decide(node, rt)}
            if node.mode == "ENTITY_COLLECT":
                return {"next": self._review_entity(node, rt)}
            return {"next": self._review_wide(node, rt, fresh)}
        except (LLMError, BudgetExceeded) as e:
            self._note(node, f"review failed ({e}); continuing without it")
            return {"next": "collect" if rt.pending else "synthesize"}

    def _review_wide(self, node: Node, rt: ManagerRT, fresh: list[int]) -> str:
        # scouts have all reported: pass their process experience to the siblings that were held back
        if rt.held and not (rt.scouts & rt.pending):
            rt.tips = self._experience(node, rt)
            for spec in rt.held:
                if rt.tips:
                    spec.setdefault("context", {})["tips"] = rt.tips
            rt.to_dispatch, rt.held = rt.held, []
            return "dispatch"

        b = self.cfg.budgets
        followups_left = min(b.max_followups - rt.followups_used, b.max_nodes - self.budget.nodes)
        if self.budget.wrapping_up():
            followups_left = 0                      # no new work this late; let what is running finish
        if not fresh:                               # nothing new to look at
            return "collect" if rt.pending else "synthesize"
        rd = self.decider.review(node, rt)          # None = no opinion
        if rd is None:
            rd = self._review_generative(node, rt, max(0, followups_left))
        rt.reviews += 1
        self.tracer.event("decision", node.id, point="review", value=rd.decision, provider=rd.provider,
                          reason=rd.reason[:240], follow_ups=rd.follow_ups, pending=len(rt.pending),
                          done=len(rt.done))
        if rd.decision == "follow_up":
            new = [f.strip() for f in rd.follow_ups if isinstance(f, str) and len(f.strip()) > 12]
            new = new[:max(0, followups_left)]
            if new:
                rt.followups_used += len(new)
                # a follow-up is a targeted gap-filler, so it is a single focused lookup (ATOM)
                rt.to_dispatch = [{"objective": f, "forced_mode": "ATOM", "context": {"follow_up": True}}
                                  for f in new]
                return "dispatch"
            if rd.follow_ups:
                self._note(node, "follow-up requested but none allowed (limit reached)")
        if rd.decision == "finish" and (rt.pending or rt.held):
            rt.early_finish = True
            self._note(node, f"finished early with {len(rt.pending) + len(rt.held)} sub-task(s) outstanding")
            self._cancel_children(node, rt, "manager finished early")
            return "synthesize"
        return "collect" if rt.pending else "synthesize"

    def _review_generative(self, node: Node, rt: ManagerRT, followups_left: int) -> ReviewDecision:
        pending = [self.nodes[c].objective for c in rt.pending] + [s["objective"] for s in rt.held]
        out = self.llm.json("review", node, prompts.REVIEW_SYSTEM.format(max_new=max(1, min(2, followups_left))),
                            prompts.REVIEW_USER.format(
                                today=self.today, objective=node.objective,
                                results=self._render_child_results(rt, 150) or "(none)",
                                pending="\n".join(f"- {p}" for p in pending) or "(nothing pending)",
                                followups_left=followups_left),
                            prompts.REVIEW_SCHEMA, max_tokens=240)
        return ReviewDecision(out.get("decision", "wait"), list(out.get("follow_ups") or []),
                              str(out.get("reason", "")), "generative")

    def _render_child_results(self, rt: ManagerRT, words: int, usable_only: bool = False) -> str:
        blocks = []
        for cid in sorted(rt.done):   # creation order, not arrival order: keeps prompts reproducible
            c = self.nodes[cid]
            r = c.result or NodeResult()
            if usable_only and not r.answer:
                continue
            ans = " ".join(r.answer.split()[:words]) or "(no evidence found)"
            head = f"- Sub-objective: {c.objective}\n  status: {c.status}"
            if r.verdict:
                head += f", verdict: {r.verdict}"
            elif r.answer:
                head += f", confidence: {r.confidence}"
            block = f"{head}\n  result: {ans}"
            if r.gaps:
                block += f"\n  gaps: {' '.join(r.gaps.split()[:40])}"
            blocks.append(block)
        return "\n".join(blocks)

    def _experience(self, node: Node, rt: ManagerRT) -> str:
        """Process-level tips from the scouts' traces: where evidence came from, what failed.

        WebSwarm extracts this with a model call; here it is read straight from the trace."""
        scouts = set(rt.scouts)
        good, bad, queries = [], [], []
        for ev in self.tracer.events:
            if ev.get("node") not in scouts:
                continue
            if ev["type"] == "finding" and ev.get("kind") == "page" and ev["domain"] not in good:
                good.append(ev["domain"])
            elif ev["type"] == "web_call" and ev["kind"] == "fetch" and not ev["ok"]:
                d = domain_of(ev["target"])
                if d not in bad:
                    bad.append(d)
            elif ev["type"] == "atom_action" and ev["action"] == "search" and ev.get("query"):
                queries.append(ev["query"])
        parts = []
        if good:
            parts.append("useful evidence came from " + ", ".join(good[:4]))
        if bad:
            parts.append("these sites could not be read, skip them: " + ", ".join(bad[:4]))
        if queries and good:
            parts.append(f'a query style that worked: "{queries[0][:80]}"')
        tips = "; ".join(parts)
        self.tracer.event("experience", node.id, scouts=sorted(scouts), tips=tips)
        return tips

    # ---- DEEP ---------------------------------------------------------------------------------

    def _deep_record(self, rt: ManagerRT, child: Node) -> None:
        r = child.result or NodeResult()
        rt.steps.append({"kind": child.context.get("step_kind", "investigate"), "node": child.id,
                         "text": child.objective, "status": child.status, "answer": r.answer,
                         "verdict": r.verdict, "gaps": r.gaps})

    def _deep_known(self, rt: ManagerRT, chars: int = 700) -> str:
        parts = [re.sub(r"\s*\[S\d+(?:,\s*S\d+)*\]", "", s["answer"]) for s in rt.steps
                 if s["kind"] == "investigate" and s["answer"]]
        return " ".join(parts)[-chars:]

    def _deep_decide(self, node: Node, rt: ManagerRT) -> str:
        """Choose the next DEEP step from the evidence so far. Returns the next graph node."""
        b = self.cfg.budgets
        rounds_left = b.deep_max_rounds - rt.rounds
        last = rt.steps[-1] if rt.steps else None
        if last and last["kind"] == "verify" and (last["verdict"] == "survived" or rounds_left <= 0):
            return "synthesize"
        if rt.steps and self.budget.wrapping_up():
            self._note(node, "time budget: no further steps")
            return "synthesize"
        steps_text = "\n".join(
            f"{i}. {s['kind'].upper()}: {s['text']}\n   -> " +
            (f"verdict {s['verdict']}: " if s["kind"] == "verify" else "") +
            (" ".join(s["answer"].split()[:90]) or f"(no evidence; {s['gaps'][:120]})")
            for i, s in enumerate(rt.steps, 1)) or "(none yet)"
        try:
            out = self.llm.json("deep_step", node, prompts.DEEP_SYSTEM,
                                prompts.DEEP_USER.format(today=self.today, objective=node.objective,
                                                         steps=steps_text, rounds_left=max(0, rounds_left),
                                                         verified="yes" if rt.verified else "no"),
                                prompts.DEEP_SCHEMA, max_tokens=200)
            action, text, reason = out.get("action", "finish"), str(out.get("text", "")).strip(), out.get("reason", "")
        except (LLMError, BudgetExceeded) as e:
            if rt.steps:
                self._note(node, f"step decision failed ({e}); finishing with what was found")
                return "synthesize"
            action, text, reason = "investigate", node.objective, f"step decision failed ({e})"
        self.tracer.event("decision", node.id, point="deep_step", value=action, provider="generative",
                          reason=str(reason)[:240], text=text[:240])

        if not rt.steps and action != "investigate":
            self._note(node, f"first DEEP step was {action!r}; investigating the objective instead")
            action, text = "investigate", node.objective
        if action == "verify" and text.rstrip().endswith("?"):
            # a verifier checks a statement; a question is still something to find out
            self._note(node, "verify step was phrased as a question; treated as investigate")
            action = "investigate"
        if action == "investigate":
            seen = {objective_key(s["text"]) for s in rt.steps}
            if rounds_left > 0 and len(text) > 12 and objective_key(text) not in seen:
                rt.rounds += 1
                rt.to_dispatch = [{"objective": text, "forced_mode": "ATOM", "step_kind": "investigate",
                                   "context": {"known": self._deep_known(rt)} if rt.steps else {}}]
                return "dispatch"
            self._note(node, "no investigate rounds left (or repeated step); moving to verification")
            action, text = "finish", ""

        # verify explicitly, or as a forced check before finishing
        candidate = next((s for s in reversed(rt.steps) if s["kind"] == "investigate" and s["answer"]), None)
        if rt.verified or self.cfg.verify_policy == "never" or candidate is None:
            return "synthesize"
        claim = text if len(text) > 25 else re.sub(r"\s*\[S\d+(?:,\s*S\d+)*\]", "", candidate["answer"])
        claim = " ".join(claim.split()[:60])
        if self.cfg.verify_policy == "decider":
            d = self.decider.needs_verification(node, claim, rt.steps)
            self._decision(node, d)
            if not d.value:
                self._note(node, "verification skipped by decider")
                return "synthesize"
        if action == "finish":
            self._note(node, "verification sent before finishing")
        rt.verified = True
        rt.to_dispatch = [{"objective": claim, "role": "verifier", "forced_mode": "ATOM", "step_kind": "verify"}]
        return "dispatch"

    # ---- ENTITY_COLLECT -----------------------------------------------------------------------

    def _review_entity(self, node: Node, rt: ManagerRT) -> str:
        if rt.pending:
            return "collect"   # merging needs every discovery path; nothing to decide yet
        if rt.phase == "discover":
            lists = [(cid, (self.nodes[cid].result or NodeResult()).entities) for cid in rt.done]
            rt.table = merge_entities(lists)
            paths_with_hits = sum(1 for _, ents in lists if ents)
            self.tracer.event("entity_merge", node.id, paths=len(lists), paths_with_hits=paths_with_hits,
                              entities=[(e["name"], e["support"]) for e in rt.table])
            rt.phase = "verify"
            weak = [e for e in rt.table if e["support"] == 1] if paths_with_hits >= 2 else []
            weak = weak[:self.cfg.budgets.entity_verify_max]
            if weak and self.cfg.verify_policy != "never" and not self._stopped(node):
                for e in weak:
                    e["verify_claim"] = f'"{e["name"]}" belongs in the answer to: {node.objective}'
                rt.to_dispatch = [{"objective": e["verify_claim"], "role": "verifier", "forced_mode": "ATOM"}
                                  for e in weak]
                return "dispatch"
            return "synthesize"
        # verification results are in: attach verdicts
        by_claim = {self.nodes[c].objective: self.nodes[c] for c in rt.done if self.nodes[c].role == "verifier"}
        for e in rt.table:
            v = by_claim.get(e.get("verify_claim", ""))
            if v is not None and v.result:
                e["verdict"] = v.result.verdict or "unverifiable"
                e["verify_sources"] = v.result.sources
        return "synthesize"

    # =============================================================================================
    # managers: synthesize
    # =============================================================================================

    def _g_synthesize(self, state: AgentState) -> dict:
        node = self.nodes[state["nid"]]
        rt = self._rt[node.id]
        if rt.pending:
            self._cancel_children(node, rt, "synthesis started")
        if node.mode == "ENTITY_COLLECT":
            node.result = self._synth_entity(node, rt)
            return {"next": ""}
        usable = [c for c in rt.done if (self.nodes[c].result and self.nodes[c].result.answer)]
        if not usable:
            gaps = "; ".join(filter(None, ((self.nodes[c].result.gaps if self.nodes[c].result else "") for c in rt.done)))
            node.result = NodeResult(status="failed", gaps=gaps[:400] or "no sub-task returned evidence")
            return {"next": ""}
        is_root = node.parent is None
        words = 320 if is_root else 150
        known = set(self.evidence.sources)
        try:
            answer = self.llm.text("synthesize", node,
                                   prompts.SYNTH_SYSTEM.format(words=words,
                                                               extra=prompts.SYNTH_ROOT_EXTRA if is_root else ""),
                                   prompts.SYNTH_USER.format(
                                       today=self.today, objective=node.objective,
                                       results=self._render_child_results(rt, 170, usable_only=True),
                                       missing="\n".join(f"- {self.nodes[c].objective}" for c in rt.done
                                                         if c not in usable) or "(nothing)"),
                                   max_tokens=int(words * 2.0) + 120)
        except (LLMError, BudgetExceeded) as e:
            self._note(node, f"synthesis failed ({e}); returning sub-results joined")
            answer = "\n".join(f"- {self.nodes[c].objective}: {self.nodes[c].result.answer}" for c in usable)
        answer, removed = strip_unknown_citations(answer, known)
        if removed:
            self._note(node, f"removed citations to unknown sources: {removed}")
        failed = [c for c in rt.done if c not in usable]
        gaps = []
        if failed:
            gaps.append("no evidence for: " + "; ".join(self.nodes[c].objective[:80] for c in failed))
        if rt.early_finish:
            gaps.append("finished before all sub-tasks reported")
        verdicts = [s["verdict"] for s in rt.steps if s["kind"] == "verify"]
        conf = _combine_confidence([self.nodes[c].result.confidence for c in usable
                                    if self.nodes[c].role == "research"])
        if verdicts:
            conf = {"survived": "high", "weakened": "medium", "refuted": "low"}.get(verdicts[-1], conf)
        node.result = NodeResult(status="ok" if cited_ids(answer) and not failed else "partial", answer=answer,
                                 confidence=conf, gaps="; ".join(gaps), verdict=verdicts[-1] if verdicts else "",
                                 sources=cited_ids(answer))
        return {"next": ""}

    def _synth_entity(self, node: Node, rt: ManagerRT) -> NodeResult:
        """The merged table is the answer; it is written out directly rather than re-generated."""
        n_paths = sum(1 for c in rt.done if self.nodes[c].role == "collector")
        kept = [e for e in rt.table if e.get("verdict") != "refuted"]
        dropped = [e["name"] for e in rt.table if e.get("verdict") == "refuted"]
        if not kept:
            return NodeResult(status="failed", gaps="no entities were found by any discovery path")
        lines = []
        for e in kept:
            cites = ", ".join(e["sources"][:4])
            tag = f"{e['support']} of {n_paths} search paths"
            if e.get("verdict"):
                v = ", ".join(e.get("verify_sources") or [])
                tag += f"; independent check: {e['verdict']}" + (f" [{v}]" if v else "")
            elif e["support"] == 1 and n_paths > 1:
                tag += "; single path, not independently checked"
            lines.append(f"- {e['name']}: {e['note']} [{cites}] ({tag})")
        answer = "\n".join(lines)
        if dropped:
            answer += "\nRejected after an independent check: " + ", ".join(dropped) + "."
        multi = sum(1 for e in kept if e["support"] > 1)
        conf = "high" if multi >= max(1, len(kept) // 2) else "medium"
        return NodeResult(status="ok", answer=answer, confidence=conf, entities=kept,
                          gaps="acronym/alias variants of the same entity may be listed separately",
                          sources=cited_ids(answer))


# ---- helpers ------------------------------------------------------------------------------------

_QUERY_NOISE = frozenset("pdf transcript official officially confirmed report reports statement announcement "
                         "site units press release".split())


def simplify_query(query: str, keep: int = 7) -> str:
    """A shorter, plainer version of a query that returned nothing (search engines return no hits
    for long, over-specified keyword strings)."""
    q = re.sub(r"\bsite:\S+", " ", query)
    q = re.sub(r"[\"'()]", " ", q)
    words = [w for w in q.split() if w.lower().strip(".,") not in _QUERY_NOISE]
    out = " ".join(words[:keep])
    return out if out and out.lower() != query.lower().strip() else ""


_SUFFIX = re.compile(r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|ag|sa|nv|"
                     r"holdings?|group|the)\b\.?", re.I)


def entity_key(name: str) -> str:
    key = re.sub(r"\([^)]*\)", " ", name.lower())
    key = _SUFFIX.sub(" ", key)
    return re.sub(r"[^a-z0-9]+", " ", key).strip()


def merge_entities(lists: list[tuple[int, list[dict]]]) -> list[dict]:
    """Merge candidate lists from several discovery paths; `support` = number of paths naming it."""
    table: dict[str, dict] = {}
    for path_id, ents in lists:
        for e in ents:
            key = entity_key(e.get("name", ""))
            if not key:
                continue
            row = table.setdefault(key, {"name": e["name"].strip(), "note": e.get("note", ""),
                                         "sources": [], "paths": []})
            if path_id not in row["paths"]:
                row["paths"].append(path_id)
            for s in e.get("sources", []):
                if s not in row["sources"]:
                    row["sources"].append(s)
            if len(e.get("note", "")) > len(row["note"]):
                row["note"] = e["note"]
    out = []
    for row in table.values():
        row["support"] = len(row["paths"])
        out.append(row)
    return sorted(out, key=lambda r: (-r["support"], r["name"].lower()))


def _combine_confidence(levels: list[str]) -> str:
    if not levels:
        return "low"
    rank = {"low": 0, "medium": 1, "high": 2}
    avg = sum(rank.get(x, 0) for x in levels) / len(levels)
    return "high" if avg >= 1.6 else "medium" if avg >= 0.7 else "low"
