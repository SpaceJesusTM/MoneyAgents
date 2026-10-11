"""Unit tests for the deterministic pieces: text helpers, evidence checks, SSRF guard, budgets, gate.

No model and no network (the SSRF tests use literal IP addresses, which resolve locally).
"""
import threading
import time

import pytest

from webswarm_baseline.config import Budgets, SwarmConfig
from webswarm_baseline.evidence import EvidenceStore, audit_answer, cited_ids, strip_unknown_citations
from webswarm_baseline.runtime import Budget, BudgetExceeded, LLMGate, Tracer
from webswarm_baseline.swarm import entity_key, merge_entities
from webswarm_baseline.textutil import (clean_page_text, numbers_in, overlap, quote_in_text,
                                        select_passages)
from webswarm_baseline.web import html_to_text, validate_url

PAGE = ("Acme Corp reported fourth quarter revenue of $4.2 billion, up 18% from a year ago. "
        "Data center revenue was $2.9 billion, a record.")


# ---- text helpers -------------------------------------------------------------------------------

def test_quote_must_really_be_in_the_page():
    assert quote_in_text("Data center revenue was $2.9 billion, a record", PAGE)
    assert quote_in_text("data center revenue was  $2.9 billion", PAGE)          # whitespace/case drift
    assert not quote_in_text("Data center revenue was $3.9 billion, a record", PAGE)   # altered figure
    assert not quote_in_text("Acme expects strong demand to continue next year", PAGE)  # invented
    assert not quote_in_text("record", PAGE)                                    # too short to count


def test_numbers_are_normalised_and_citations_ignored():
    assert numbers_in("Revenue was $115.2 billion, up 142% [S1].") == ["115.2", "142"]
    assert numbers_in("about 1,000 units and 12.50% margin") == ["1000", "12.5"]
    assert numbers_in("3 factors were found [S12]") == []     # small counts and source ids are not claims


def test_select_passages_keeps_the_relevant_part_with_its_heading():
    filler = "\n".join(f"Paragraph {i} about corporate governance and unrelated matters." * 3 for i in range(60))
    doc = filler + "\nData Center\n- Full-year data center revenue rose 142% to a record $115.2 billion.\n" + filler
    out = select_passages(doc, "NVIDIA data center revenue fiscal year 2025", 900)
    assert len(out) <= 1000
    assert "$115.2 billion" in out and "Data Center" in out


def test_clean_page_text_collapses_empty_table_cells():
    raw = "|  |  | Revenue |  |  | $ | 39,331 |  |  |\n| --- | --- |\n\n\nNext line"
    assert clean_page_text(raw) == "Revenue | $ | 39,331\nNext line"


def test_overlap_is_a_lexical_similarity():
    a = "NVIDIA data center revenue growth drivers"
    assert overlap(a, a) == 1.0
    assert overlap(a, "Intel foundry capital expenditure plans") == 0.0


def test_html_to_text_drops_scripts():
    html = "<html><head><title>T</title><script>evil()</script></head><body><p>" + "Real text. " * 40 + "</p></body></html>"
    title, text = html_to_text(html)
    assert title == "T" and "Real text." in text and "evil" not in text


# ---- evidence -----------------------------------------------------------------------------------

def _store():
    store = EvidenceStore(Tracer())
    src = store.add_source("https://ex.test/a", "Acme results", "page", 1, PAGE)
    return store, src


def test_findings_with_invented_quotes_are_rejected():
    store, src = _store()
    ok = store.add_finding("Data center revenue was $2.9B", "Data center revenue was $2.9 billion, a record", src, 1, PAGE)
    bad = store.add_finding("Revenue will double", "management expects revenue to double next year", src, 1, PAGE)
    assert ok is not None and bad is None
    assert len(store.findings) == 1
    assert [e["type"] for e in store.tracer.events].count("finding_rejected") == 1


def test_same_url_gets_one_source_id():
    store, src = _store()
    again = store.add_source("https://ex.test/a", "Acme results", "page", 2, "")
    assert again.id == src.id == "S1"


def test_citation_parsing_and_stripping():
    assert cited_ids("x [S1] y [S2, S3] z [S1]") == ["S1", "S2", "S3"]
    clean, removed = strip_unknown_citations("A [S1]. B [S9]. C [S1, S7].", {"S1"})
    assert removed == ["S9", "S7"]
    assert clean == "A [S1]. B. C [S1]."


def test_audit_separates_grounded_and_ungrounded_figures():
    store, _ = _store()
    a = audit_answer("Revenue was $4.2 billion [S1]. Margin was 61.5% [S1]. Growth was 18% [S9].", store)
    assert a["unknown_citations"] == ["S9"]
    assert a["numbers"] == 3
    assert a["numbers_in_cited_source"] == 1          # 4.2 is in S1
    assert a["numbers_elsewhere_in_evidence"] == 1    # 18 is in the evidence but not via a valid citation
    assert a["numbers_ungrounded"] == 1               # 61.5 appears nowhere in retrieved text
    assert a["ungrounded_examples"][0]["number"] == "61.5"


def test_entity_merge_counts_support_across_paths():
    assert entity_key("SK Hynix Inc.") == entity_key("SK hynix")
    table = merge_entities([(1, [{"name": "SK Hynix Inc.", "note": "a", "sources": ["S1"]}]),
                            (2, [{"name": "SK hynix", "note": "longer note", "sources": ["S2"]},
                                 {"name": "Micron", "note": "m", "sources": ["S3"]}])])
    assert [(r["name"], r["support"]) for r in table] == [("SK Hynix Inc.", 2), ("Micron", 1)]
    assert table[0]["sources"] == ["S1", "S2"] and table[0]["note"] == "longer note"


# ---- SSRF guard ---------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin", "http://localhost/", "http://10.0.0.5/", "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "http://0.0.0.0/",
    "file:///etc/passwd", "ftp://example.com/x", "http://user:pw@8.8.8.8/", "http://8.8.8.8:8080/",
    "http://[::ffff:127.0.0.1]/", "gopher://8.8.8.8/",
])
def test_ssrf_guard_blocks_non_public_and_odd_urls(url):
    assert validate_url(url) is not None


def test_ssrf_guard_allows_public_ip():
    assert validate_url("https://8.8.8.8/") is None


# ---- budgets and the model gate -----------------------------------------------------------------

def test_budget_counts_and_reserve():
    tr = Tracer()
    b = Budget(Budgets(max_llm_calls=4, reserve_llm_calls=2, max_web_calls=1, max_nodes=2), tr)
    b.take_llm(); b.take_llm()
    with pytest.raises(BudgetExceeded):
        b.take_llm()                      # only the reserve is left
    b.take_llm(reserved=True); b.take_llm(reserved=True)
    with pytest.raises(BudgetExceeded):
        b.take_llm(reserved=True)
    b.take_web()
    with pytest.raises(BudgetExceeded):
        b.take_web()
    assert b.take_node() and b.take_node() and not b.take_node()
    assert set(b.hits()) == {"max_llm_calls", "max_web_calls", "max_nodes"}


def test_deadline_expires():
    b = Budget(Budgets(max_seconds=0.05), Tracer())
    assert not b.expired()
    time.sleep(0.08)
    assert b.expired()
    with pytest.raises(BudgetExceeded):
        b.take_web()


def _queue_order(policy):
    """Hold the single slot, queue three callers, release, and record who is served in what order."""
    gate = LLMGate(1, policy)
    order, started = [], threading.Event()

    def holder():
        with gate.slot("act", 0):
            started.set()
            time.sleep(0.25)

    def caller(kind, depth):
        with gate.slot(kind, depth):
            order.append(kind)

    h = threading.Thread(target=holder); h.start(); started.wait()
    threads = []
    for kind, depth in [("plan", 0), ("act", 1), ("answer", 1)]:   # arrival order
        t = threading.Thread(target=caller, args=(kind, depth)); t.start(); threads.append(t)
        time.sleep(0.03)
    for t in [h] + threads:
        t.join()
    return order


def test_gate_fifo_serves_in_arrival_order():
    assert _queue_order("fifo") == ["plan", "act", "answer"]


def test_gate_finish_first_serves_completing_calls_first():
    assert _queue_order("finish_first") == ["answer", "act", "plan"]


def test_config_overrides_and_validation():
    cfg = SwarmConfig().override(["web_probing=true", "budgets.max_nodes=5", "review_policy=batch"])
    assert cfg.web_probing is True and cfg.budgets.max_nodes == 5 and cfg.review_policy == "batch"
    assert SwarmConfig.from_dict(cfg.to_dict()).to_dict() == cfg.to_dict()
    with pytest.raises(ValueError):
        SwarmConfig().override(["no_such_key=1"])
    with pytest.raises(ValueError):
        SwarmConfig.from_dict({"bogus": 1})
