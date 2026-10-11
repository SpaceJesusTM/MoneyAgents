"""Orchestration tests with a SCRIPTED model and canned pages (see webswarm_baseline/mock.py).

These check control flow: recursion, evidence propagation, incremental review, cancellation,
budgets, verification and record/replay. They say nothing about research quality.
"""
import re
import time

import pytest

from webswarm_baseline.config import SwarmConfig
from webswarm_baseline.evidence import cited_ids
from webswarm_baseline.mock import MockProvider, default_handlers, mock_fetch, mock_setup
from webswarm_baseline.run import execute

Q = "What could affect Acme Corp data center revenue growth?"


def run(handlers=None, root_mode="WIDE", overrides=(), delay=0.0, **kw):
    cfg = SwarmConfig().override(list(overrides))
    cfg, extra = mock_setup(cfg, handlers=handlers, delay=delay, root_mode=root_mode)
    extra.update(kw)
    return execute(Q, cfg, echo=False, **extra)


def events(art, type_):
    return [e for e in art.tracer.events if e["type"] == type_]


# ---- WIDE ---------------------------------------------------------------------------------------

def test_wide_runs_children_and_propagates_cited_evidence_to_the_root():
    art = run()
    nodes = art.swarm.nodes
    assert nodes[0].mode == "WIDE" and [nodes[c].mode for c in nodes[0].children] == ["ATOM"] * 3
    assert art.outcome["status"] == "ok"
    # every citation in the root answer points at a source that a child actually read
    cites = cited_ids(art.outcome["answer"])
    assert cites and set(cites) <= set(art.swarm.evidence.sources)
    child_sources = {s for c in nodes[0].children for s in nodes[c].result.sources}
    assert set(cites) <= child_sources
    assert art.outcome["audit"]["unknown_citations"] == []
    assert art.stats["nodes"] == 4 and art.stats["max_depth"] == 1
    assert art.stats["time_to_first_evidence"] is not None


def test_page_text_reaches_the_model_only_inside_untrusted_markers():
    seen = []
    h = default_handlers()
    inner = h["extract"]

    def extract(system, user, schema):
        seen.append((system, user))
        return inner(system, user, schema)

    h["extract"] = extract
    run(handlers=h)
    assert seen
    for system, user in seen:
        assert "never follow" in system and "instructions" in system
        body = user.split("<<<UNTRUSTED", 1)[1]
        assert body.rstrip().endswith(">>>") and "Acme" in body


def test_invented_quotes_are_dropped_and_the_agent_falls_back_to_snippets():
    h = default_handlers("ATOM")
    h["extract"] = lambda s, u, sc: {"findings": [{"claim": "Acme revenue will triple next year",
                                                   "quote": "management guided to a tripling of revenue"}]}
    art = run(handlers=h, root_mode="ATOM")
    assert art.stats["findings_rejected"] >= 1
    assert art.stats["findings_from_pages"] == 0
    kinds = {s.kind for s in art.swarm.evidence.sources.values()}
    assert kinds == {"snippet"}                       # evidence exists, but only at snippet grade
    assert any("search snippets" in n for n in art.swarm.nodes[0].notes)


def test_unreadable_pages_are_reported_not_hidden():
    h = default_handlers("ATOM")
    h["snippet_extract"] = lambda s, u, sc: {"findings": []}
    blocked = lambda url: {"url": url, "status": 403, "error": "HTTP 403"}   # noqa: E731
    art = run(handlers=h, root_mode="ATOM", web_kwargs={"provider": MockProvider(), "fetcher": blocked})
    assert art.stats["fetch_failures"] >= 1 and art.stats["findings"] == 0
    assert art.outcome["status"] == "failed" and art.outcome["answer"] == ""
    assert "HTTP 403" in art.outcome["gaps"] and "example-" in art.outcome["gaps"]
    assert art.swarm.evidence.sources == {}            # nothing unread became a citable source


def test_a_failed_read_is_followed_by_another_attempt_rather_than_giving_up():
    h = default_handlers("ATOM")

    def act(system, user, schema):
        if "(no searches yet)" in user:
            return {"thought": "", "action": "search", "query": "premium analysis subscribers Acme", "result": 0}
        m = re.search(r"^R(\d+) \[example-blocked\.test\]", user, re.M)
        if m:
            return {"thought": "", "action": "read", "query": "", "result": int(m.group(1))}
        return {"thought": "", "action": "finish", "query": "", "result": 0}   # gives up with no evidence

    h["act"] = act
    art = run(handlers=h, root_mode="ATOM")
    assert art.stats["fetch_failures"] == 1
    assert any("finish with no evidence overridden" in n for n in art.swarm.nodes[0].notes)
    assert art.outcome["status"] == "ok" and art.stats["findings_from_pages"] > 0


# ---- incremental consumption --------------------------------------------------------------------

def _slow_web():
    """The 'competition' page is slow to fetch, so that child's result arrives well after the others.
    (The delay is in web I/O on purpose: a slow *model* call would hold the single model slot and
    make the manager's review queue behind it, which is real behaviour but not what is tested here.)"""
    def fetcher(url):
        if "competition" in url:
            time.sleep(0.6)
        return mock_fetch(url)
    return {"provider": MockProvider(), "fetcher": fetcher}


def test_incremental_policy_reviews_before_all_children_have_finished():
    art = run(overrides=["review_policy=incremental"], web_kwargs=_slow_web())
    reviews = [e for e in events(art, "decision") if e["point"] == "review"]
    assert len(reviews) >= 2
    assert reviews[0]["pending"] >= 1                 # the manager acted while a child was still working
    last_child_done = max(e["t"] for e in events(art, "node_end") if e["node"] != 0)
    assert reviews[0]["t"] < last_child_done


def test_batch_policy_reviews_once_after_everything_arrived():
    art = run(overrides=["review_policy=batch"], web_kwargs=_slow_web())
    reviews = [e for e in events(art, "decision") if e["point"] == "review"]
    assert len(reviews) == 1 and reviews[0]["pending"] == 0


def test_early_finish_cancels_outstanding_children():
    h = default_handlers()
    h["review"] = lambda s, u, sc: {"reason": "enough", "decision": "finish", "follow_ups": []}
    t0 = time.perf_counter()
    art = run(handlers=h, web_kwargs=_slow_web())
    assert events(art, "child_cancelled")
    assert art.swarm.nodes[0].result.gaps.endswith("finished before all sub-tasks reported")
    assert art.outcome["answer"]
    assert time.perf_counter() - t0 < 5


def test_follow_up_spawns_new_work_from_returned_evidence():
    h = default_handlers()
    state = {"asked": False}

    def review(system, user, schema):
        if not state["asked"] and "Borealis" in user:      # a lead that only appears in child evidence
            state["asked"] = True
            return {"reason": "new lead", "decision": "follow_up",
                    "follow_ups": ["Borealis Semiconductor advanced packaging capacity expansion investment"]}
        return {"reason": "", "decision": "wait" if "(nothing pending)" not in user else "finish", "follow_ups": []}

    h["review"] = review
    art = run(handlers=h)
    root = art.swarm.nodes[0]
    assert len(root.children) == 4
    follow = art.swarm.nodes[root.children[-1]]
    assert follow.context.get("follow_up") and follow.objective.startswith("Borealis")
    assert follow.status == "ok" and follow.forced_mode == "ATOM"     # a follow-up is one targeted lookup


def test_follow_ups_are_capped():
    h = default_handlers()
    n = {"i": 0}

    def review(system, user, schema):
        n["i"] += 1
        return {"reason": "", "decision": "follow_up",
                "follow_ups": [f"Acme Corp follow-up topic number {n['i']} about packaging supply"]}

    h["review"] = review
    art = run(handlers=h, overrides=["budgets.max_followups=2"])
    assert len(art.swarm.nodes[0].children) == 3 + 2


def test_duplicate_sub_objectives_are_dropped():
    h = default_handlers()
    h["plan"] = lambda s, u, sc: {"reason": "", "children": [
        "Acme Corp fourth quarter revenue and data center revenue figures",
        "Acme Corp fourth quarter revenue and data-center revenue figures!",     # same after normalisation
        "Acme Corp competition from rival accelerators and customer concentration"]}
    art = run(handlers=h)
    assert len(art.swarm.nodes[0].children) == 2
    assert art.stats["redundancy"]["objectives_dropped_as_duplicate"] == 1


# ---- DEEP ---------------------------------------------------------------------------------------

def test_deep_investigates_then_sends_an_independent_verifier():
    art = run(root_mode="DEEP")
    nodes = art.swarm.nodes
    kids = [nodes[c] for c in nodes[0].children]
    assert [k.role for k in kids] == ["research", "verifier"]
    assert all(k.mode == "ATOM" for k in kids)
    assert "known" not in kids[1].context               # the verifier does not see the proposer's evidence
    assert kids[1].result.verdict == "survived"
    assert nodes[0].result.verdict == "survived" and nodes[0].result.confidence == "high"


def test_deep_forces_verification_when_the_model_tries_to_finish_without_it():
    h = default_handlers("DEEP")

    def deep_step(system, user, schema):
        if "(none yet)" in user:
            return {"reason": "", "action": "investigate", "text": "Which partner constrains Acme Corp packaging supply?"}
        return {"reason": "", "action": "finish", "text": ""}

    h["deep_step"] = deep_step
    art = run(handlers=h, root_mode="DEEP")
    roles = [art.swarm.nodes[c].role for c in art.swarm.nodes[0].children]
    assert roles == ["research", "verifier"]
    assert any("verification sent before finishing" in n for n in art.swarm.nodes[0].notes)


def test_deep_verify_policy_never_skips_the_verifier():
    art = run(root_mode="DEEP", overrides=["verify_policy=never"])
    assert [art.swarm.nodes[c].role for c in art.swarm.nodes[0].children] == ["research"]


def test_deep_rounds_are_bounded():
    h = default_handlers("DEEP")
    n = {"i": 0}

    def deep_step(system, user, schema):
        n["i"] += 1
        return {"reason": "", "action": "investigate", "text": f"Acme Corp packaging question number {n['i']} to research"}

    h["deep_step"] = deep_step
    art = run(handlers=h, root_mode="DEEP", overrides=["budgets.deep_max_rounds=2"])
    kids = [art.swarm.nodes[c] for c in art.swarm.nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "verifier"]


# ---- ENTITY_COLLECT -----------------------------------------------------------------------------

def test_entity_collect_merges_paths_and_reports_support():
    art = run(root_mode="ENTITY_COLLECT")
    root = art.swarm.nodes[0]
    assert root.mode == "ENTITY_COLLECT"
    collectors = [c for c in root.children if art.swarm.nodes[c].role == "collector"]
    assert len(collectors) == 3
    names = {e["name"]: e["support"] for e in root.result.entities}
    assert "Acme Corp" in names and max(names.values()) >= 2
    assert "search paths" in art.outcome["answer"] and cited_ids(art.outcome["answer"])


# ---- limits -------------------------------------------------------------------------------------

def test_depth_limit_forces_atom():
    art = run(overrides=["budgets.max_depth=0"])
    root = art.swarm.nodes[0]
    assert root.model_mode == "WIDE" and root.mode == "ATOM" and not root.children
    assert any("max depth" in n for n in root.notes)


def test_node_budget_is_never_exceeded():
    art = run(overrides=["budgets.max_nodes=3"])
    assert len(art.swarm.nodes) == 3
    assert "max_nodes" in art.stats["budget_hits"]
    assert art.outcome["answer"]


def test_llm_budget_exhaustion_still_ends_with_an_answer():
    art = run(overrides=["budgets.max_llm_calls=14", "budgets.reserve_llm_calls=2"])
    assert art.stats["llm_calls"] <= 14
    assert "max_llm_calls" in art.stats["budget_hits"]
    assert art.outcome["answer"]                       # the reserve let the root synthesize


def test_web_budget_exhaustion_is_survivable():
    art = run(overrides=["budgets.max_web_calls=3"])
    assert art.stats["web_calls"] <= 3
    assert "max_web_calls" in art.stats["budget_hits"]


def test_deadline_stops_the_run_promptly():
    t0 = time.perf_counter()
    art = run(overrides=["budgets.max_seconds=0.6"], delay=0.25)
    assert time.perf_counter() - t0 < 6
    assert "max_seconds" in art.stats["budget_hits"]
    assert art.outcome["stragglers"] == 0


def test_a_crashing_node_does_not_take_the_run_down():
    h = default_handlers()
    inner = h["extract"]

    def extract(system, user, schema):
        if "competition" in user.lower().split("<<<UNTRUSTED")[0]:
            raise RuntimeError("boom")
        return inner(system, user, schema)

    h["extract"] = extract
    art = run(handlers=h)
    assert art.outcome["answer"] and art.outcome["status"] in ("ok", "partial")


# ---- optional mechanisms ------------------------------------------------------------------------

def test_web_probing_runs_before_planning_and_is_counted():
    art = run(overrides=["web_probing=true"])
    assert len(events(art, "probe")) == 1
    assert art.stats["llm_calls_by_kind"].get("probe") == 1
    plan = events(art, "plan")[0]
    assert plan["probing"] == "distributed"


def test_experience_sharing_runs_scouts_first_then_passes_tips():
    h = default_handlers()
    h["plan"] = lambda s, u, sc: {"reason": "", "children": [
        "Acme Corp fourth quarter revenue and data center revenue figures",
        "Acme Corp advanced packaging supply constraints and partner capacity expansion",
        "Acme Corp competition from rival accelerators and customer concentration",
        "Acme Corp gross margin and first quarter revenue outlook"]}
    art = run(handlers=h, overrides=["experience_sharing=true"])
    root = art.swarm.nodes[0]
    d = events(art, "dispatch")
    assert d[0]["scouting"] and len(d[0]["started"]) == 2 and d[0]["held"] == 2
    exp = events(art, "experience")
    assert len(exp) == 1 and "example-" in exp[0]["tips"]
    late = [art.swarm.nodes[c] for c in root.children[2:]]
    assert len(late) == 2 and all(n.context.get("tips") for n in late)
    scouts_done = max(art.swarm.nodes[c].finished for c in root.children[:2])
    assert all(n.started >= scouts_done for n in late)


# ---- record / replay ----------------------------------------------------------------------------

class ExplodingProvider:
    name = "none"

    def search(self, query, n):
        raise AssertionError("live search attempted during replay")


def test_cassette_replay_reproduces_a_run_without_touching_the_network(tmp_path):
    cfg = SwarmConfig()
    cfg, extra = mock_setup(cfg)
    rec = SwarmConfig.from_dict({**cfg.to_dict(), "web_mode": "record", "cassette": str(tmp_path / "c")})
    a = execute(Q, rec, echo=False, **extra)
    assert list((tmp_path / "c").glob("search_*.json")) and list((tmp_path / "c").glob("fetch_*.json"))

    rep = SwarmConfig.from_dict({**cfg.to_dict(), "web_mode": "replay", "cassette": str(tmp_path / "c"),
                                 "replay_latency": False})
    def boom(url):
        raise AssertionError("live fetch attempted during replay")
    b = execute(Q, rep, echo=False, llm_factory=extra["llm_factory"],
                web_kwargs={"provider": ExplodingProvider(), "fetcher": boom})
    # children finish in a thread-dependent order, so compare content rather than exact text
    urls = lambda art: {art.swarm.evidence.sources[c].url for c in cited_ids(art.outcome["answer"])}   # noqa: E731
    assert urls(a) == urls(b) and urls(a)
    assert {f.claim for f in a.swarm.evidence.findings} == {f.claim for f in b.swarm.evidence.findings}
    assert b.stats["web_from_cassette"] == b.stats["web_calls"] == a.stats["web_calls"]


def test_replay_miss_is_an_explicit_failure_not_a_silent_live_call(tmp_path):
    cfg, extra = mock_setup(SwarmConfig())
    rep = SwarmConfig.from_dict({**cfg.to_dict(), "web_mode": "replay", "cassette": str(tmp_path / "empty")})
    art = execute(Q, rep, echo=False, llm_factory=extra["llm_factory"],
                  web_kwargs={"provider": ExplodingProvider(), "fetcher": mock_fetch})
    assert art.stats["search_failures"] == art.stats["searches"] > 0
    assert art.outcome["answer"] == ""


def test_run_artifacts_are_saved(tmp_path):
    cfg, extra = mock_setup(SwarmConfig())
    art = execute(Q, cfg, echo=False, out_dir=tmp_path, **extra)
    assert {p.name for p in art.path.iterdir()} == {"run.json", "trace.jsonl", "report.md"}
    assert "## Agent tree" in (art.path / "report.md").read_text()


def test_mock_provider_is_deterministic():
    assert MockProvider().search("acme packaging supply", 2) == MockProvider().search("acme packaging supply", 2)


# ---- behaviour found and fixed during live testing ----------------------------------------------

def test_cancelled_agents_make_no_further_model_calls():
    """After a manager finishes early, its outstanding children must stop instead of going on to
    write answers nobody will read (seen in the first live run: ~65 s of wasted model time)."""
    h = default_handlers()
    h["review"] = lambda s, u, sc: {"reason": "enough", "decision": "finish", "follow_ups": []}
    art = run(handlers=h, web_kwargs=_slow_web())
    cancelled = {e["child"] for e in events(art, "child_cancelled")}
    assert cancelled
    cancel_t = min(e["t"] for e in events(art, "child_cancelled"))
    late = [e for e in events(art, "llm_call") if e["node"] in cancelled and e["t"] > cancel_t + 0.7]
    assert late == []
    assert all(art.swarm.nodes[c].status in ("cancelled", "partial", "failed") for c in cancelled)


def test_empty_search_is_retried_once_with_a_simpler_query():
    from webswarm_baseline.swarm import simplify_query
    assert simplify_query('Microsoft Q3 FY2027 "GPU capacity" utilization rate transcript PDF site:microsoft.com') == \
        "Microsoft Q3 FY2027 GPU capacity utilization rate"
    assert simplify_query("acme revenue") == ""          # nothing to simplify

    class Picky(MockProvider):
        def search(self, query, n):
            return [] if len(query.split()) > 7 else super().search(query, n)

    h = default_handlers("ATOM")
    inner = h["act"]

    def act(system, user, schema):
        if "(no searches yet)" in user:
            return {"thought": "", "action": "search", "result": 0,
                    "query": "Acme Corp fourth quarter revenue official confirmed report PDF transcript figures"}
        return inner(system, user, schema)

    h["act"] = act
    art = run(handlers=h, root_mode="ATOM", web_kwargs={"provider": Picky(), "fetcher": mock_fetch})
    assert any("retried as" in n for n in art.swarm.nodes[0].notes)
    assert art.stats["searches"] == 2 and art.outcome["status"] == "ok"


def test_schema_strings_are_bounded():
    """Unbounded strings let the model ramble until the token limit truncates the JSON (7 failed
    calls in the first live run). Every free-text field must carry a maxLength."""
    from webswarm_baseline import prompts

    def unbounded(schema, path=""):
        out = []
        if schema.get("type") == "string" and "enum" not in schema and "maxLength" not in schema:
            out.append(path)
        for k, v in schema.get("properties", {}).items():
            out += unbounded(v, f"{path}.{k}")
        if "items" in schema:
            out += unbounded(schema["items"], path + "[]")
        return out

    schemas = [v for k, v in vars(prompts).items() if k.endswith("_SCHEMA")] + [prompts.route_schema(["ATOM"])]
    assert len(schemas) >= 9
    assert [p for s in schemas for p in unbounded(s)] == []


def test_wrap_up_makes_agents_answer_with_what_they_have_before_the_deadline():
    """Past the soft deadline agents stop gathering and write up, so the root synthesizes every
    branch instead of being cut off (second live run: 2 of 4 branches missed a hard deadline)."""
    art = run(overrides=["budgets.max_seconds=4", "budgets.wrap_up_fraction=0.1"], delay=0.12)
    assert "wrap_up" in art.stats["budget_hits"] and "max_seconds" not in art.stats["budget_hits"]
    root = art.swarm.nodes[0]
    assert all(art.swarm.nodes[c].status in ("ok", "partial") for c in root.children)
    assert art.outcome["answer"] and not events(art, "child_cancelled")


def test_deep_verify_step_phrased_as_a_question_is_investigated_instead():
    """Seen live: the model asked the verifier a question; a verifier needs a statement to check."""
    h = default_handlers("DEEP")
    n = {"i": 0}

    def deep_step(system, user, schema):
        n["i"] += 1
        if n["i"] == 1:
            return {"reason": "", "action": "investigate", "text": "Which partner constrains Acme Corp packaging supply?"}
        if n["i"] == 2:
            return {"reason": "", "action": "verify", "text": "How fast is Borealis Semiconductor packaging capacity growing?"}
        return {"reason": "", "action": "finish", "text": "Borealis Semiconductor will double packaging capacity."}

    h["deep_step"] = deep_step
    art = run(handlers=h, root_mode="DEEP")
    kids = [art.swarm.nodes[c] for c in art.swarm.nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "verifier"]
    assert kids[2].objective.startswith("Borealis Semiconductor will double")
    assert any("phrased as a question" in x for x in art.swarm.nodes[0].notes)


# ---- optional: line-reference extraction ----------------------------------------------------------

def test_line_mode_cites_lines_and_builds_exact_quotes():
    art = run(overrides=["extract_mode=lines"])
    assert art.outcome["status"] == "ok" and art.stats["findings_from_pages"] > 0
    store = art.swarm.evidence
    for f in store.findings:                      # every stored quote is verbatim page text
        assert f.quote in store.text_of(f.source_id)
    seen = [e for e in art.tracer.events if e["type"] == "page_read"]
    assert seen and all(e["accepted"] <= e["proposed"] for e in seen)


def test_line_mode_rejects_claims_whose_figures_are_not_on_the_cited_line():
    h = default_handlers("ATOM")

    def extract(system, user, schema):
        rows = [(int(n), t) for n, t in re.findall(r"^\[(\d+)\] (.*)$", user, re.M)]
        n, text = next((n, t) for n, t in rows if "$2.9 billion" in t)
        return {"findings": [{"claim": "Data center revenue was $2.9 billion", "line": n},
                             {"claim": "Data center revenue was $7.7 billion", "line": n},      # wrong figure
                             {"claim": "Something on a line that does not exist", "line": 999}]}

    h["extract"] = extract
    art = run(handlers=h, root_mode="ATOM", overrides=["extract_mode=lines"])
    claims = [f.claim for f in art.swarm.evidence.findings if art.swarm.evidence.sources[f.source_id].kind == "page"]
    assert "Data center revenue was $2.9 billion" in claims
    assert not any("7.7" in c for c in claims)
    reasons = [e["reason"] for e in art.tracer.events if e["type"] == "finding_rejected"]
    assert any("not on the cited line" in r for r in reasons) and any("does not exist" in r for r in reasons)


def test_default_extract_mode_is_unchanged_by_the_optional_variant():
    assert SwarmConfig().extract_mode == "quote"
    art = run()
    kinds = art.stats["llm_calls_by_kind"]
    assert kinds["extract"] >= 1 and art.stats["findings_from_pages"] > 0


# ---- optional: citation retry ---------------------------------------------------------------------

def _uncited_then(second):
    h = default_handlers()
    calls = {"n": 0}

    def synthesize(system, user, schema):
        calls["n"] += 1
        return "Acme grew strongly and supply is easing." if calls["n"] == 1 else second
    h["synthesize"] = synthesize
    return h, calls


def test_cite_retry_asks_again_when_a_synthesis_drops_every_citation():
    h, calls = _uncited_then("Acme revenue was $4.2 billion [S1].")
    art = run(handlers=h, overrides=["cite_retry=true"])
    assert calls["n"] == 2 and cited_ids(art.outcome["answer"]) == ["S1"]
    assert any("asked again" in n for n in art.swarm.nodes[0].notes)


def test_cite_retry_falls_back_to_cited_sub_results_rather_than_uncited_prose():
    h, calls = _uncited_then("Still fluent, still uncited.")
    art = run(handlers=h, overrides=["cite_retry=true"])
    assert calls["n"] == 2 and cited_ids(art.outcome["answer"])
    assert art.outcome["answer"].startswith("- Acme Corp")
    assert art.outcome["audit"]["citations"] >= 1


def test_without_cite_retry_the_baseline_behaviour_is_unchanged():
    h, calls = _uncited_then("unused")
    art = run(handlers=h)
    assert calls["n"] == 1 and cited_ids(art.outcome["answer"]) == [] and SwarmConfig().cite_retry is False
