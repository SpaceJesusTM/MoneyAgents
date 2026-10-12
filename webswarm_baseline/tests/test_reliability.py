"""Regression tests for the failures recorded in BASELINE_RESULTS.md: D1 (a statement about missing
data "verified"), W1 (non-GAAP figure labelled GAAP), W2 (wrong ranking of correct figures) and
A2 (a 4.9 MB PDF silently truncated).

The model is SCRIPTED: it replays the outputs the real model produced in the baseline runs, so
these tests show what the engine does with those outputs. They do not show what the real model
does when the guards are on; RELIABILITY_IMPROVEMENTS.md reports the live runs separately.

Each failure is tested twice: with the frozen baseline settings (the failure must still reproduce,
which is what keeps the baseline a baseline) and with the guard on.
"""
import re

import pytest

from webswarm_baseline import web as webmod
from webswarm_baseline.config import PACKAGE_DIR, SwarmConfig
from webswarm_baseline.evidence import cited_ids
from webswarm_baseline.mock import MockProvider, default_handlers, mock_fetch, mock_setup
from webswarm_baseline.run import execute
from webswarm_baseline.runtime import Budget, Tracer
from webswarm_baseline.tests.test_guards import (AMD_F1, AMD_PAGE, AMD_QUOTE, D1_CLAIM, D1_STEP1, D1_STEP2, NVDA_F3,
                                                 NVDA_F5, NVDA_QUOTE, NVDA_TABLE, W2_ANSWER, W2_CHILDREN, W2_QUESTION)
from webswarm_baseline.web import Cassette, WebClient, pdf_extract


def run(question, handlers, overrides=(), web_kwargs=None):
    cfg, extra = mock_setup(SwarmConfig().override(list(overrides)), handlers=handlers)
    if web_kwargs:
        extra["web_kwargs"] = web_kwargs
    return execute(question, cfg, echo=False, **extra)


def events(art, type_):
    return [e for e in art.tracer.events if e["type"] == type_]


def recite(text: str, user: str) -> str:
    """Point a recorded answer's citations at a source id that exists in this scripted run."""
    sid = re.search(r"\[(S\d+)\]", user).group(1)
    return re.sub(r"\[S\d+\]", f"[{sid}]", text)


def test_the_frozen_baseline_config_has_every_guard_off_and_the_patched_config_has_them_on():
    base = SwarmConfig.load(PACKAGE_DIR / "configs" / "baseline.json")
    assert (base.verify_guard, base.claim_checks, base.numeric_guard) == (False, False, False)
    assert base.oversize_policy == "truncate" and base.max_pdf_bytes == 0 and base.pdf_max_pages == 15
    assert {k: v for k, v in base.to_dict().items() if k != "name"} == \
           {k: v for k, v in SwarmConfig().to_dict().items() if k != "name"}
    fixed = SwarmConfig.load(PACKAGE_DIR / "configs" / "reliability_v1.json")
    assert fixed.verify_guard and fixed.claim_checks and fixed.numeric_guard and fixed.oversize_policy == "fail"
    assert 3_000_000 < fixed.max_pdf_bytes <= 16_000_000              # larger than before, still bounded
    changed = {k for k, v in fixed.to_dict().items() if base.to_dict()[k] != v}
    assert changed == {"name", "verify_guard", "claim_checks", "numeric_guard", "oversize_policy",
                       "max_pdf_bytes", "pdf_max_pages"}


# =================================================================================================
# D1: DEEP verification
# =================================================================================================

D1_Q = ("Which supplier's advanced-packaging capacity most constrains shipments of NVIDIA's latest AI accelerators, "
        "and how fast can that capacity grow?")
D1_STEPS = [   # REAL: the three investigate steps of the baseline D1 run and what each returned
    ("Who is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips?", D1_STEP1),
    ("What is the current maximum advanced-packaging capacity of Amkor for NVIDIA chips, and what is the projected "
     "annual growth rate?", D1_STEP2),
    ("What are the specific advanced-packaging capacity figures (in units per year) and projected annual growth rate "
     "for Amkor's $1.5 billion deal with NVIDIA?", D1_CLAIM.replace("with NVIDIA.", "with NVIDIA [S3].") + " [S4]"),
]


def d1_handlers(steps=D1_STEPS, verdict="survived", explanation="The deal and Amkor's role are confirmed [S1].",
                final=None):
    h = default_handlers("DEEP")
    by_question = dict(steps)

    def deep_step(system, user, schema):
        done = user.count("INVESTIGATE:")
        if done < len(steps):
            return {"reason": "", "action": "investigate", "text": steps[done][0]}
        if final is not None and "VERIFY" not in user:
            return final
        # REAL: the model asked for the last question again, slightly reworded, with no rounds left
        return {"reason": "", "action": "investigate", "text": steps[-1][0].replace("What are", "What were")}

    def answer(system, user, schema):
        if "verdict" in schema["properties"]:
            return {"verdict": verdict, "answer": recite(explanation, user) if "[S" in explanation else explanation,
                    "gaps": ""}
        objective = re.search(r"OBJECTIVE: (.*)", user).group(1)
        return {"answer": recite(by_question[objective], user), "confidence": "medium", "gaps": ""}

    h["deep_step"], h["answer"] = deep_step, answer
    return h


def test_d1_baseline_still_sends_the_missing_data_statement_to_the_verifier_and_reports_it_verified():
    """The recorded failure, reproduced with the frozen settings."""
    art = run(D1_Q, d1_handlers())
    nodes = art.swarm.nodes
    kids = [nodes[c] for c in nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "research", "verifier"]
    assert kids[3].objective.startswith("The provided findings do not contain specific advanced-packaging capacity")
    assert nodes[0].result.verdict == "survived" and nodes[0].result.confidence == "high"
    assert art.outcome["status"] == "ok"


def test_d1_with_the_guard_the_verifier_checks_the_positive_claim_and_the_answer_is_not_called_complete():
    art = run(D1_Q, d1_handlers(), overrides=["verify_guard=true"])
    nodes = art.swarm.nodes
    kids = [nodes[c] for c in nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "research", "verifier"]
    claim = kids[3].objective
    assert claim.startswith("Amkor is the primary supplier of advanced packaging technology for NVIDIA")
    assert "do not contain" not in claim and "lacks" not in claim and "[S" not in claim
    assert any("verifying an earlier finding instead" in n for n in nodes[0].notes)
    root = nodes[0].result
    assert root.verdict == "survived"                      # the scripted verifier confirmed the positive claim
    assert root.confidence != "high" and art.outcome["status"] == "partial"
    assert "not established" in root.gaps and "projected annual growth rate" in root.gaps


def test_when_every_step_only_reports_missing_information_no_verifier_is_sent_at_all():
    steps = [(q, D1_STEP2) for q, _ in D1_STEPS]             # all three rounds come back empty-handed
    art = run(D1_Q, d1_handlers(steps=steps), overrides=["verify_guard=true"])
    nodes = art.swarm.nodes
    assert [nodes[c].role for c in nodes[0].children] == ["research", "research", "research"]
    assert len(events(art, "verify_refused")) == 1
    root = nodes[0].result
    assert root.verdict == "" and root.confidence != "high" and art.outcome["status"] == "partial"
    assert "not independently verified" in root.gaps and "not established" in root.gaps


def test_the_models_own_verify_text_is_also_refused_when_it_describes_missing_data():
    final = {"reason": "", "action": "verify", "text": D1_CLAIM}
    art = run(D1_Q, d1_handlers(steps=D1_STEPS[:2], final=final), overrides=["verify_guard=true"])
    kids = [art.swarm.nodes[c] for c in art.swarm.nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "verifier"]
    assert kids[2].objective.startswith("Amkor is the primary supplier")
    baseline = run(D1_Q, d1_handlers(steps=D1_STEPS[:2], final=final))
    assert baseline.swarm.nodes[baseline.swarm.nodes[0].children[2]].objective.startswith("The provided findings do not")


def test_a_positive_verdict_that_cites_no_evidence_is_not_accepted():
    h = d1_handlers(steps=D1_STEPS[:1], verdict="survived", explanation="It checks out.",
                    final={"reason": "", "action": "finish", "text": ""})
    art = run(D1_Q, h, overrides=["verify_guard=true"])
    nodes = art.swarm.nodes
    verifier = nodes[nodes[0].children[-1]]
    assert verifier.role == "verifier" and verifier.result.verdict == "unverifiable"
    assert any("not accepted" in n and "cited no evidence" in n for n in verifier.notes)
    assert nodes[0].result.verdict == "unverifiable" and nodes[0].result.confidence != "high"
    off = run(D1_Q, h)                                      # baseline: the bare assertion was taken at its word
    assert off.swarm.nodes[0].result.verdict == "survived" and off.swarm.nodes[0].result.confidence == "high"


def test_a_sound_verification_is_unchanged_by_the_guard():
    """The guard must not get in the way when the claim is a real one and the verdict is cited."""
    art = run("What could affect Acme Corp data center revenue growth?", default_handlers("DEEP"),
              overrides=["verify_guard=true"])
    root = art.swarm.nodes[0]
    kids = [art.swarm.nodes[c] for c in root.children]
    assert [k.role for k in kids] == ["research", "verifier"]
    assert kids[1].objective.startswith("Borealis Semiconductor will double advanced packaging capacity")
    assert root.result.verdict == "survived" and root.result.confidence == "high" and art.outcome["status"] == "ok"


# =================================================================================================
# W2: ranking
# =================================================================================================

W2_RIGHT = ("Amazon generated the highest revenue at $638 billion [S1], followed by Alphabet at $350.018 billion [S1]. "
            "Microsoft recorded the lowest at $245.12 billion [S1].")


def w2_handlers(second_draft):
    h = default_handlers("WIDE")
    answers = {sub: ans for sub, ans, _ in W2_CHILDREN}
    calls = []

    def answer(system, user, schema):
        objective = re.search(r"OBJECTIVE: (.*)", user).group(1)
        return {"answer": recite(answers[objective], user), "confidence": "high", "gaps": ""}

    def synthesize(system, user, schema):
        calls.append((system, user))
        return recite(W2_ANSWER if len(calls) == 1 else second_draft, user)

    h["plan"] = lambda s, u, sc: {"reason": "", "children": [sub for sub, _, _ in W2_CHILDREN]}
    h["answer"], h["synthesize"] = answer, synthesize
    return h, calls


def test_w2_baseline_still_returns_the_wrong_ranking_unchallenged():
    h, calls = w2_handlers(W2_RIGHT)
    art = run(W2_QUESTION, h)
    assert len(calls) == 1 and "FIGURES PICKED OUT BY CODE" not in calls[0][1]
    assert "Alphabet generated the highest revenue" in art.outcome["answer"]
    assert art.outcome["status"] == "ok" and art.outcome["confidence"] == "high"
    assert "consistency" not in art.outcome["audit"]


def test_w2_with_the_guard_the_figures_are_sorted_by_code_and_the_contradiction_triggers_one_retry():
    h, calls = w2_handlers(W2_RIGHT)
    art = run(W2_QUESTION, h, overrides=["numeric_guard=true"])
    assert len(calls) == 2
    first_user, retry_system = calls[0][1], calls[1][0]
    assert "FIGURES PICKED OUT BY CODE" in first_user
    assert first_user.index("1. Amazon: $638 billion") < first_user.index("2. Alphabet: $350.018 billion") \
        < first_user.index("3. Microsoft: $245.12 billion")
    assert "Your previous draft contradicted the figures" in retry_system and "$638 billion" in retry_system
    assert "Alphabet generated the highest" not in art.outcome["answer"]
    assert art.outcome["answer"].startswith("Amazon generated the highest revenue")
    assert art.outcome["audit"]["consistency"]["clean"] and art.outcome["status"] == "ok"
    assert any("asked again" in n for n in art.swarm.nodes[0].notes)


def test_w2_if_the_model_repeats_the_error_a_labelled_computed_correction_is_appended():
    h, calls = w2_handlers(W2_ANSWER)                       # second draft is as wrong as the first
    art = run(W2_QUESTION, h, overrides=["numeric_guard=true"])
    answer = art.outcome["answer"]
    assert len(calls) == 2
    assert "Correction (computed from the figures, not written by the model)" in answer
    assert "Amazon ($638 billion) > Alphabet ($350.018 billion) > Microsoft ($245.12 billion)" in answer
    assert "Alphabet generated the highest revenue" in answer        # nothing the model wrote is deleted
    assert art.outcome["status"] == "partial" and art.outcome["confidence"] != "high"
    assert "computed correction" in art.outcome["gaps"]
    assert len(art.outcome["audit"]["consistency"]["ordering_issues"]) >= 1   # still reported, not hidden
    assert cited_ids(answer)


def test_a_clean_synthesis_costs_no_extra_model_call():
    h, calls = w2_handlers(W2_RIGHT)
    calls.append(("", ""))                                  # make the handler return the correct draft first
    art = run(W2_QUESTION, h, overrides=["numeric_guard=true"])
    assert len(calls) == 2 and art.outcome["answer"].startswith("Amazon generated the highest")
    assert art.outcome["audit"]["consistency"]["clean"] and not events(art, "numeric_issue")


# =================================================================================================
# W1: figures tied to their quote and accounting basis
# =================================================================================================

def one_page(text, proposals):
    """A scripted ATOM run that reads one page with `text` and has `proposals` extracted from it."""
    url = "https://example-ir.test/filing"
    h = default_handlers("ATOM")
    h["extract"] = lambda s, u, sc: {"findings": [{"claim": c, "quote": q} for c, q in proposals]}

    class Provider:
        name = "one"

        def search(self, query, n):
            return [{"title": "Results release", "url": url, "snippet": "Full-year financial results.", "date": ""}]

    def fetcher(u):
        return {"url": u, "final_url": u, "status": 200, "content_type": "text/html", "title": "Results release",
                "text": text, "nbytes": len(text)}

    return h, {"provider": Provider(), "fetcher": fetcher}


NVDA_GAAP_QUOTE = "FY25 FY24 Y/Y Revenue $130,497 $60,922 Up 114% Gross margin 75.0% 72.7% Up 2.3 pts"
NVDA_PROPOSALS = [(NVDA_F3, NVDA_QUOTE), (NVDA_F5, NVDA_QUOTE),
                  ("NVIDIA's GAAP gross margin for fiscal year 2025 was 75.0%.", NVDA_GAAP_QUOTE)]


def test_w1_baseline_still_stores_the_non_gaap_figure_under_a_gaap_label():
    h, web = one_page(NVDA_TABLE, NVDA_PROPOSALS)
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, web_kwargs=web)
    claims = [f.claim for f in art.swarm.evidence.findings]
    assert NVDA_F3 in claims and all(f.basis == "" for f in art.swarm.evidence.findings)


def test_w1_with_claim_checks_the_mislabelled_figure_never_becomes_evidence():
    h, web = one_page(NVDA_TABLE, NVDA_PROPOSALS)
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, overrides=["claim_checks=true"], web_kwargs=web)
    by_claim = {f.claim: f for f in art.swarm.evidence.findings}
    assert NVDA_F3 not in by_claim
    assert by_claim[NVDA_F5].basis == "non-gaap"
    assert by_claim["NVIDIA's GAAP gross margin for fiscal year 2025 was 75.0%."].basis == "gaap"
    reasons = [e["reason"] for e in events(art, "finding_rejected")]
    assert reasons == ["claim says gaap but the passage is labelled non-gaap (heading)"]
    assert "GAAP gross margin was 75.5%" not in art.outcome["answer"]
    assert art.outcome["audit"]["consistency"]["basis_conflicts"] == []


def test_w1_with_claim_checks_an_unsupported_clause_is_cut_from_the_claim():
    h, web = one_page(AMD_PAGE, [(AMD_F1, AMD_QUOTE)])
    art = run("What was AMD's gross margin for 2024?", h, overrides=["claim_checks=true"], web_kwargs=web)
    assert [f.claim for f in art.swarm.evidence.findings] == ["AMD's GAAP gross margin for the full year 2024 was 49%."]
    adjusted = events(art, "finding_adjusted")
    assert len(adjusted) == 1 and adjusted[0]["before"] == AMD_F1 and art.stats["findings_adjusted"] == 1
    off = run("What was AMD's gross margin for 2024?", h, web_kwargs=web)
    assert [f.claim for f in off.swarm.evidence.findings] == [AMD_F1]


def test_a_basis_label_in_the_answer_that_contradicts_the_passage_does_not_survive():
    h, web = one_page(NVDA_TABLE, [(NVDA_F5, NVDA_QUOTE)])
    drafts = []

    def answer(system, user, schema):
        drafts.append(system)
        return {"answer": recite("NVIDIA's GAAP gross margin for fiscal year 2025 was 75.5% [S1].", user),
                "confidence": "high", "gaps": ""}

    h["answer"] = answer
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, overrides=["claim_checks=true"], web_kwargs=web)
    assert len(drafts) == 2 and "75.5% is called gaap, but its passage shows non-gaap" in drafts[1]
    assert "GAAP gross margin for fiscal year 2025 was 75.5%" not in art.outcome["answer"].replace("non-GAAP", "")
    assert art.outcome["answer"].startswith("NVIDIA's non-GAAP gross margin for fiscal year 2025 was 75.5%")
    assert art.outcome["confidence"] == "low" and art.outcome["audit"]["consistency"]["basis_conflicts"] == []
    drafts.clear()
    off = run("What was NVIDIA's gross margin for fiscal year 2025?", h, web_kwargs=web)     # baseline: it stands
    assert len(drafts) == 1 and "NVIDIA's GAAP gross margin for fiscal year 2025 was 75.5%" in off.outcome["answer"]


# =================================================================================================
# A2: oversized responses
# =================================================================================================

def make_pdf(pages: list[str], pad: int = 0) -> bytes:
    """A small valid PDF with one line of text per page, optionally padded with an unused stream."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages))),
                                                         len(pages))).encode(),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for i, text in enumerate(pages):
        content = f"BT /F1 10 Tf 40 720 Td ({text}) Tj ET".encode()
        objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                     "/Contents %d 0 R >>" % (5 + 2 * i)).encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    if pad:
        objs.append(b"<< /Length %d >>\nstream\n" % pad + b"0" * pad + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


STATEMENT = ("Apple Inc. CONDENSED CONSOLIDATED STATEMENTS OF OPERATIONS In millions. Net sales by category: "
             "iPhone 46,222 43,805 201,183 200,583 Mac 7,744 7,614 29,984 29,357 iPad 6,950 6,443 26,694 28,300 "
             "Wearables, Home and Accessories 9,042 9,322 37,005 39,845 Services 24,972 22,314 96,169 85,200 "
             "Total net sales 94,930 89,498 391,035 383,285")
FILING_URL = "https://example-ir.test/FY24_Q4_Consolidated_Financial_Statements.pdf"


class FakeResponse:
    def __init__(self, body: bytes, ctype="application/pdf", declare=True, status=200):
        self.status_code, self._body, self.served = status, body, 0
        self.headers = {"Content-Type": ctype, **({"Content-Length": str(len(body))} if declare else {})}

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            self.served += len(self._body[i:i + n])
            yield self._body[i:i + n]

    def close(self):
        pass


def client(monkeypatch, response=None, overrides=(), fetcher=None):
    cfg = SwarmConfig().override(["respect_robots=false", *overrides])
    tracer = Tracer(echo=None)
    c = WebClient(cfg, tracer, Budget(cfg.budgets, tracer), provider=MockProvider(), fetcher=fetcher)
    monkeypatch.setattr(webmod, "validate_url", lambda url: None)      # no DNS in tests; the guard has its own tests
    if response is not None:
        c.session.get = lambda *a, **k: response
    return c, tracer


FIXED = ["oversize_policy=fail", "max_pdf_bytes=8000000"]


def test_a2_baseline_silently_fails_on_the_truncated_pdf_but_now_marks_it(monkeypatch):
    """REAL failure, at the fetch level: 4.9 MB filing, 3 MB cap, 'no extractable text'."""
    resp = FakeResponse(make_pdf([STATEMENT], pad=4_900_000))
    c, tracer = client(monkeypatch, resp)
    page = c.fetch(FILING_URL)
    assert not page.ok and page.error == "no extractable text (script-rendered or empty page)"
    assert page.nbytes == 3_000_000 and page.truncated               # the cause is at least recorded now
    assert [e for e in tracer.events if e["type"] == "web_call"][0]["truncated"] is True


def test_a2_with_a_bounded_pdf_limit_the_filing_is_read_in_full(monkeypatch):
    resp = FakeResponse(make_pdf([STATEMENT], pad=4_900_000))
    c, _ = client(monkeypatch, resp, FIXED)
    page = c.fetch(FILING_URL)
    assert page.ok and "Services 24,972 22,314 96,169 85,200" in page.text
    assert not page.truncated and 4_900_000 < page.nbytes < 8_000_000


@pytest.mark.parametrize("declare", [True, False])
def test_a_response_over_the_limit_is_an_explicit_failure_not_truncated_content(monkeypatch, declare):
    resp = FakeResponse(make_pdf([STATEMENT], pad=9_000_000), declare=declare)
    c, _ = client(monkeypatch, resp, FIXED)
    page = c.fetch(FILING_URL)
    assert not page.ok and page.text == "" and page.truncated
    assert page.error.startswith("too large:") and "limit 8,000,000" in page.error and "nothing parsed" in page.error
    if declare:
        assert "bytes declared" in page.error and resp.served == 0      # refused before any body was downloaded
    else:
        assert resp.served <= 8_000_000 + 65536                          # never read past the limit


def test_the_larger_limit_applies_to_pdfs_only(monkeypatch):
    html = ("<html><body><p>" + "Acme revenue was $4.2 billion. " * 150_000 + "</p></body></html>").encode()
    assert len(html) > 3_000_000
    resp = FakeResponse(html, ctype="text/html")
    c, _ = client(monkeypatch, resp, FIXED)
    page = c.fetch("https://example-ir.test/huge.html")
    assert not page.ok and "limit 3,000,000" in page.error
    c2, _ = client(monkeypatch, FakeResponse(html, ctype="text/html"))    # baseline: parsed as far as it arrived
    page2 = c2.fetch("https://example-ir.test/huge.html")
    assert page2.ok and page2.truncated


def test_long_pdfs_are_read_up_to_a_page_limit_and_say_so(monkeypatch):
    pages = [f"Page {i} of the annual report. " + STATEMENT for i in range(1, 8)]
    info = pdf_extract(make_pdf(pages), max_pages=3)
    assert info["pages"] == 7 and info["pages_read"] == 3 and "Page 3 of" in info["text"] and "Page 4 of" not in info["text"]
    assert pdf_extract(b"%PDF-1.4 not really a pdf", max_pages=3)["error"].startswith("unreadable PDF")
    c, tracer = client(monkeypatch, FakeResponse(make_pdf(pages)), [*FIXED, "pdf_max_pages=3"])
    page = c.fetch(FILING_URL)
    assert page.ok and page.partial == "read 3 of 7 PDF pages"
    assert [e for e in tracer.events if e["type"] == "web_call"][0]["partial"] == "read 3 of 7 PDF pages"


LEGACY = {"url": FILING_URL, "final_url": FILING_URL, "status": 200, "content_type": "application/pdf",
          "nbytes": 3_000_000, "title": "", "text": "",
          "error": "no extractable text (script-rendered or empty page)"}       # shape of the recorded A2 entry
FULL = {"url": FILING_URL, "final_url": FILING_URL, "status": 200, "content_type": "application/pdf",
        "nbytes": 4_900_000, "title": "", "text": STATEMENT}


def recorded(tmp_path, monkeypatch, overrides, fetcher):
    Cassette(str(tmp_path)).put("fetch", FILING_URL, LEGACY, 0.0)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    c, _ = client(monkeypatch, overrides=[f"cassette={tmp_path}", "replay_latency=false", *overrides], fetcher=fetcher)
    return c, before


def test_a_truncated_recording_is_refetched_under_the_larger_limit_and_the_old_recording_is_kept(tmp_path, monkeypatch):
    calls = []
    c, before = recorded(tmp_path, monkeypatch, [*FIXED, "web_mode=replay_or_record"],
                         lambda url: calls.append(url) or FULL)
    page = c.fetch(FILING_URL)
    assert calls == [FILING_URL] and page.ok and "96,169" in page.text
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert len(after) == 2 and all(after[name] == data for name, data in before.items())   # original untouched
    c2, _ = client(monkeypatch, overrides=[f"cassette={tmp_path}", "replay_latency=false", *FIXED, "web_mode=replay"],
                   fetcher=lambda url: pytest.fail("live fetch during replay"))
    assert "96,169" in c2.fetch(FILING_URL).text                       # the second recording replays


def test_a_truncated_recording_is_an_explicit_failure_when_it_cannot_be_refetched(tmp_path, monkeypatch):
    boom = lambda url: pytest.fail("live fetch attempted")              # noqa: E731
    c, _ = recorded(tmp_path, monkeypatch, ["oversize_policy=fail", "web_mode=replay_or_record"], boom)
    page = c.fetch(FILING_URL)                                           # no larger limit applies
    assert not page.ok and page.truncated
    assert page.error.startswith("too large: the recorded copy was cut off at 3,000,000 bytes")
    c, _ = recorded(tmp_path, monkeypatch, [*FIXED, "web_mode=replay"], boom)
    assert c.fetch(FILING_URL).error == "not in cassette (replay mode)"  # replay never goes to the network


def test_the_baseline_replays_a_truncated_recording_exactly_as_it_was_recorded(tmp_path, monkeypatch):
    c, _ = recorded(tmp_path, monkeypatch, ["web_mode=replay_or_record"], lambda url: pytest.fail("live fetch"))
    page = c.fetch(FILING_URL)
    assert page.error == LEGACY["error"] and len(list(tmp_path.iterdir())) == 1


def test_an_unreadable_oversized_page_is_named_in_the_agent_tree():
    h = default_handlers("ATOM")

    def fetcher(url):
        if "acme-q4" in url:
            return {"url": url, "status": 200, "content_type": "application/pdf", "nbytes": 0, "truncated": True,
                    "error": "too large: 9,400,000 bytes declared, limit 8,000,000; nothing parsed"}
        return mock_fetch(url)

    art = run("Acme Corp fourth quarter revenue", h, overrides=FIXED,
              web_kwargs={"provider": MockProvider(), "fetcher": fetcher})
    assert any(n.startswith("page not read, example-ir.test: too large: 9,400,000 bytes declared")
               for n in art.swarm.nodes[0].notes)
    assert art.stats["fetch_truncated"] == 1


# =================================================================================================
# W1, second failure (found in the first live run of the patched config): quarter shown as full year
# =================================================================================================

NVDA_Q4_TABLE = ("Q4 Fiscal 2025 Summary\nGAAP\n($ in millions, except earnings\nper share)\nQ4 FY25\nQ3 FY25\nQ/Q\n"
                 "Revenue\n$39,331\n$35,082\nUp 12%\nGross margin\n73.0%\n74.6%\nDown 1.6 pts\n")
NVDA_Q4_QUOTE = "Q4 FY25 Q3 FY25 Q/Q Revenue $39,331 $35,082 Up 12% Gross margin 73.0% 74.6% Down 1.6 pts"
Q4_FINDING = ("In the fourth quarter of fiscal year 2025 (ended January 26, 2025), NVIDIA's GAAP gross margin was "
              "73.0%, which was 1.6 percentage points lower than the previous quarter.")
MISLABELLED = "NVIDIA's GAAP gross margin for fiscal year 2025 was 73.0% [S1], while its non-GAAP gross margin was 75.5% [S1]."
RELABELLED = ("NVIDIA's non-GAAP gross margin for fiscal year 2025 was 75.5% [S1]. Its GAAP gross margin for the fourth "
              "quarter of fiscal year 2025 was 73.0% [S1].")


def period_handlers(second):
    h, web = one_page(NVDA_Q4_TABLE + NVDA_TABLE, [(Q4_FINDING, NVDA_Q4_QUOTE), (NVDA_F5, NVDA_QUOTE)])
    calls = []

    def answer(system, user, schema):
        calls.append(system)
        return {"answer": recite(MISLABELLED if len(calls) == 1 else second, user), "confidence": "high",
                "gaps": "" if len(calls) == 1 else "The full-year GAAP gross margin is not in the findings."}

    h["answer"] = answer
    return h, web, calls


def test_baseline_still_lets_a_quarterly_figure_stand_in_for_the_fiscal_year():
    h, web, calls = period_handlers(RELABELLED)
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, web_kwargs=web)
    assert len(calls) == 1 and "fiscal year 2025 was 73.0%" in art.outcome["answer"]
    assert art.outcome["confidence"] == "high"


def test_with_claim_checks_a_mislabelled_period_triggers_one_retry_that_names_the_problem():
    h, web, calls = period_handlers(RELABELLED)
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, overrides=["claim_checks=true"], web_kwargs=web)
    assert len(calls) == 2
    assert "73.0% is given as a full-year figure, but the finding it comes from gives it for a quarter" in calls[1]
    assert "fourth quarter of fiscal year 2025 was 73.0%" in art.outcome["answer"]
    assert "full-year GAAP gross margin is not in the findings" in art.outcome["gaps"]
    assert art.outcome["audit"]["consistency"]["clean"]
    assert len(events(art, "label_issue")) == 1 and art.stats["guard_events"]["label_issue"] == 1


def test_if_the_retry_is_still_mislabelled_the_findings_are_returned_as_extracted_instead():
    """REAL, fourth live W1 run: the retry came back with the same mislabel. Keeping a sentence known
    to be wrong helps nobody; the extracted findings carry the right labels."""
    h, web, calls = period_handlers(MISLABELLED)
    art = run("What was NVIDIA's gross margin for fiscal year 2025?", h, overrides=["claim_checks=true"], web_kwargs=web)
    answer = art.outcome["answer"]
    assert len(calls) == 2 and "fiscal year 2025 was 73.0%" not in answer
    assert "In the fourth quarter of fiscal year 2025" in answer and "NVIDIA's GAAP gross margin was 73.0%" in answer
    assert "non-GAAP gross margin for fiscal year 2025 was 75.5%" in answer and cited_ids(answer) == ["S1"]
    assert art.outcome["confidence"] == "low"
    assert "73.0% is the figure for a quarter, not for the full year" in art.outcome["gaps"]
    assert "mislabel" not in art.outcome["gaps"]            # the parent is told the fact, not the story of the draft
    assert art.outcome["audit"]["consistency"]["clean"]
    assert any("replaced by the findings as extracted" in n for n in art.swarm.nodes[0].notes)


# REAL: the root's sentence in the second live W1 run. The child had written "for the same period",
# and the root turned the fiscal-year 75.5% into a fourth-quarter figure.
ROOT_MISLABELLED = ("NVIDIA reported a non-GAAP gross margin of 75.5% in Q4 FY2025 [S1], which is higher than its GAAP "
                    "figure of 73.0% for the same period [S1].")
ROOT_RELABELLED = ("NVIDIA's non-GAAP gross margin for fiscal year 2025 was 75.5% [S1]; its GAAP gross margin in the "
                   "fourth quarter was 73.0% [S1].")


def manager_period_handlers(second):
    h, web = one_page(NVDA_Q4_TABLE + NVDA_TABLE, [(Q4_FINDING, NVDA_Q4_QUOTE), (NVDA_F5, NVDA_QUOTE)])
    wide = default_handlers("WIDE")
    h["route"] = wide["route"]
    h["plan"] = lambda s, u, sc: {"reason": "", "children": ["NVIDIA gross margin performance for fiscal year 2025",
                                                             "NVIDIA gross margin in the fourth quarter of fiscal 2025"]}
    h["answer"] = lambda s, u, sc: {"answer": recite(RELABELLED, u), "confidence": "high", "gaps": ""}
    calls = []

    def synthesize(system, user, schema):
        calls.append(system)
        return recite(ROOT_MISLABELLED if len(calls) == 1 else second, user)

    h["synthesize"] = synthesize
    return h, web, calls


def test_a_manager_synthesis_that_mislabels_a_period_is_asked_again():
    h, web, calls = manager_period_handlers(ROOT_RELABELLED)
    art = run("Summarise NVIDIA's gross margin.", h, overrides=["claim_checks=true"], web_kwargs=web)
    assert len(calls) == 2 and "75.5% is given as a quarterly figure" in calls[1]
    assert "fiscal year 2025 was 75.5%" in art.outcome["answer"] and art.outcome["audit"]["consistency"]["clean"]
    assert art.outcome["status"] == "ok"


def test_a_label_problem_that_survives_the_retry_is_reported_and_the_answer_is_not_called_complete():
    h, web, calls = manager_period_handlers(ROOT_MISLABELLED)
    art = run("Summarise NVIDIA's gross margin.", h, overrides=["claim_checks=true"], web_kwargs=web)
    assert len(calls) == 2 and "75.5% in Q4 FY2025" in art.outcome["answer"]
    assert art.outcome["status"] == "partial" and art.outcome["confidence"] != "high"
    assert "label check failed: 75.5% is given as a quarterly figure" in art.outcome["gaps"]
    off = manager_period_handlers(ROOT_MISLABELLED)
    base = run("Summarise NVIDIA's gross margin.", off[0], web_kwargs=off[1])
    assert len(off[2]) == 1 and base.outcome["status"] == "ok" and base.outcome["gaps"] == ""


def test_a_failed_consistency_audit_caps_the_final_outcome_even_when_no_retry_path_caught_it():
    """An ATOM root whose answer step is not re-checked for ordering: the final audit still speaks up."""
    h, web = one_page(NVDA_Q4_TABLE + NVDA_TABLE, [(Q4_FINDING, NVDA_Q4_QUOTE), (NVDA_F5, NVDA_QUOTE)])
    h["answer"] = lambda s, u, sc: {"answer": recite("Of the two, NVIDIA's quarterly figure of 73.0% is higher than "
                                                     "its 75.5% [S1].", u), "confidence": "high", "gaps": ""}
    art = run("What was NVIDIA's gross margin?", h, overrides=["numeric_guard=true"], web_kwargs=web)
    assert art.outcome["audit"]["consistency"]["ordering_issues"]
    assert art.outcome["status"] == "partial" and art.outcome["confidence"] == "medium"
    assert "consistency check failed: 73.0% is said to be higher than 75.5%" in art.outcome["gaps"]
