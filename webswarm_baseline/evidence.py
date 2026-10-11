"""Run-wide evidence store: sources and the findings extracted from them.

Source ids (S1, S2, ...) are global to a run, so a citation written by a leaf agent still points
at the same URL when it reaches the root answer. The model only ever writes ids; URLs in the
final report come from this store, never from generated text.
"""
from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .textutil import domain_of, numbers_in, quote_in_text

CITE = re.compile(r"\[\s*S(\d+)((?:\s*[,;]\s*S\d+)*)\s*\]")


@dataclass
class Source:
    id: str
    url: str
    title: str
    domain: str
    kind: str            # "page" (fetched and read) or "snippet" (search-result text only)
    retrieved_at: str
    first_node: int | None = None


@dataclass
class Finding:
    id: str
    claim: str
    quote: str
    source_id: str
    node_id: int
    t: float             # seconds since run start
    verified: bool       # the quote was found in the retrieved text


class EvidenceStore:
    def __init__(self, tracer):
        self.tracer = tracer
        self.sources: dict[str, Source] = {}
        self.findings: list[Finding] = []
        self._by_url: dict[tuple[str, str], str] = {}
        self._texts: dict[str, str] = {}   # source id -> text the findings were extracted from
        self._lock = threading.Lock()

    def add_source(self, url: str, title: str, kind: str, node_id: int | None, text: str = "") -> Source:
        with self._lock:
            sid = self._by_url.get((url, kind))
            if sid is None:
                sid = f"S{len(self.sources) + 1}"
                self._by_url[(url, kind)] = sid
                self.sources[sid] = Source(sid, url, (title or "").strip()[:160], domain_of(url), kind,
                                           datetime.now(timezone.utc).isoformat(timespec="seconds"), node_id)
            if text and text not in self._texts.get(sid, ""):
                self._texts[sid] = (self._texts.get(sid, "") + "\n" + text)[:200_000]
            return self.sources[sid]

    def record(self, claim: str, quote: str, url: str, title: str, kind: str, node_id: int,
               text: str) -> Finding | None:
        """Check a proposed finding against the retrieved `text` and store it if its quote is real.

        The source is only registered once a finding from it has been accepted, so a page that
        produced nothing verifiable never becomes a citable source.
        """
        claim, quote = (claim or "").strip(), (quote or "").strip()
        if len(claim) < 8:
            return None
        if not quote_in_text(quote, text):
            self.tracer.event("finding_rejected", node_id, url=url, claim=claim[:160],
                              quote=quote[:160], reason="quote not found in retrieved text")
            return None
        return self.add_finding(claim, quote, self.add_source(url, title, kind, node_id, text), node_id, text)

    def add_finding(self, claim: str, quote: str, source: Source, node_id: int, text: str) -> Finding | None:
        """Store a finding only if its quote really appears in `text`. Returns None when rejected."""
        claim, quote = (claim or "").strip(), (quote or "").strip()
        if len(claim) < 8:
            return None
        verified = quote_in_text(quote, text)
        if not verified:
            self.tracer.event("finding_rejected", node_id, url=source.url, claim=claim[:160],
                              quote=quote[:160], reason="quote not found in retrieved text")
            return None
        with self._lock:
            for f in self.findings:  # same claim from the same source: keep one
                if f.source_id == source.id and f.claim.lower() == claim.lower():
                    return f
            f = Finding(f"F{len(self.findings) + 1}", claim[:400], quote[:400], source.id, node_id,
                        round(self.tracer.now(), 3), True)
            self.findings.append(f)
        self.tracer.event("finding", node_id, id=f.id, source=source.id, kind=source.kind,
                          domain=source.domain, claim=f.claim[:200])
        return f

    def text_of(self, sid: str) -> str:
        with self._lock:
            return self._texts.get(sid, "")

    def findings_for_sources(self, sids: set[str]) -> list[Finding]:
        with self._lock:
            return [f for f in self.findings if f.source_id in sids]

    def snapshot(self) -> dict:
        with self._lock:
            return {"sources": [asdict(s) for s in self.sources.values()],
                    "findings": [asdict(f) for f in self.findings]}


def cited_ids(text: str) -> list[str]:
    """Source ids cited in `text`, in order of first appearance."""
    out: list[str] = []
    for m in CITE.finditer(text or ""):
        for n in re.findall(r"S(\d+)", m.group(0)):
            sid = f"S{n}"
            if sid not in out:
                out.append(sid)
    return out


def strip_unknown_citations(text: str, known: set[str]) -> tuple[str, list[str]]:
    """Remove citations to ids that do not exist; returns (clean text, removed ids)."""
    removed: list[str] = []

    def fix(m: re.Match) -> str:
        ids = [f"S{n}" for n in re.findall(r"S(\d+)", m.group(0))]
        keep = [i for i in ids if i in known]
        removed.extend(i for i in ids if i not in known)
        return "[" + ", ".join(keep) + "]" if keep else ""

    return re.sub(r"[ \t]+([.,;])", r"\1", CITE.sub(fix, text or "")), removed


def audit_answer(answer: str, store: EvidenceStore) -> dict:
    """Programmatic grounding check of a final answer. No model involved.

    - citation validity: every cited id must exist in the store;
    - numeric grounding: every figure in a sentence should appear in the retrieved text of a
      source cited in that sentence ("cited"), or failing that somewhere in the run's evidence
      ("elsewhere"); the rest are "ungrounded" and are the claims to distrust first.
    """
    known = set(store.sources)
    cites = cited_ids(answer)
    unknown = [c for c in cites if c not in known]
    all_text = " ".join(store.text_of(s) for s in known)
    all_nums = set(numbers_in(all_text))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", answer or "") if s.strip()]
    total = cited_ok = elsewhere = 0
    ungrounded: list[dict] = []
    uncited_claims = 0
    for sent in sentences:
        ids = [c for c in cited_ids(sent) if c in known]
        nums = numbers_in(sent)
        if nums and not ids:
            uncited_claims += 1
        if not nums:
            continue
        src_nums = set(numbers_in(" ".join(store.text_of(i) for i in ids))) if ids else set()
        for n in dict.fromkeys(nums):
            total += 1
            if n in src_nums:
                cited_ok += 1
            elif n in all_nums:
                elsewhere += 1
            else:
                ungrounded.append({"number": n, "sentence": sent[:200]})
    kinds = [store.sources[c].kind for c in cites if c in known]
    return {
        "citations": len(cites), "unknown_citations": unknown,
        "cited_pages": kinds.count("page"), "cited_snippets": kinds.count("snippet"),
        "cited_domains": sorted({store.sources[c].domain for c in cites if c in known}),
        "numbers": total, "numbers_in_cited_source": cited_ok, "numbers_elsewhere_in_evidence": elsewhere,
        "numbers_ungrounded": len(ungrounded), "ungrounded_examples": ungrounded[:8],
        "sentences_with_figures_but_no_citation": uncited_claims,
        "numeric_grounding": round(cited_ok / total, 3) if total else None,
    }
