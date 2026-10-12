"""Deterministic reliability guards. No model, no network: regular expressions and arithmetic.

Everything here is opt-in from `SwarmConfig` and off in the frozen baseline:

    verify_guard   a verifier is only ever sent a positive, checkable claim, and a statement about
                   missing information can never come back "survived"          (failure seen: D1)
    claim_checks   a finding's figures must be in its quote, and a GAAP / non-GAAP label must be
                   one the passage actually shows                               (failure seen: W1)
    numeric_guard  compared figures are sorted by code before synthesis, and an ordering statement
                   that contradicts the figures is caught and corrected         (failure seen: W2)

The v2 grader (`experiments/bench/grade_v2.py`) uses the same functions, so what the engine guards
against is also what the evaluation penalises.

These are heuristics over English financial prose. They are tuned to be quiet rather than thorough:
a check that cannot tell says nothing. `RELIABILITY_IMPROVEMENTS.md` lists what they miss.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textutil import norm

# =================================================================================================
# 1. Statements about missing information
# =================================================================================================

_CITE = re.compile(r"\s*\[\s*S\d+(?:\s*[,;]\s*S\d+)*\s*\]")


def strip_cites(text: str) -> str:
    return _CITE.sub("", text or "")


def sentences(text: str) -> list[str]:
    """Split on sentence ends and line breaks. "U.S. production" and "$1.5 billion" stay whole."""
    parts = re.split(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9$])|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _clauses(sentence: str) -> list[str]:
    lead = re.match(r"\s*(?:while|although|though|whereas)\s+(.+?),\s+(.+)$", sentence, re.I | re.S)
    if lead:                      # "While X, Y": two statements, either of which may be the one about a gap
        return [c for part in lead.groups() for c in _clauses(part)]
    return [c for c in re.split(r",?\s+(?:but|however|although|though|whereas|yet)\s+|;\s+", sentence) if c.strip()]


_INFO = (r"(?:data|figures?|numbers?|details?|information|specifics|projections?|estimates?|evidence|"
         r"disclosures?|guidance|breakdowns?|metrics?|statistics|percentages?|values?|amounts?|sources?|"
         r"confirmation|mention|records?|results?)")
_EVID = r"(?:findings?|sources?|results?|text|evidence|snippets?|research|search(?:es)?|documents?|pages?|articles?)"

_ABSENCE = re.compile("|".join([
    # "the findings do not contain / state / specify ..."
    r"\b(?:do|does|did)\s+not\s+(?:\w+\s+){0,2}?(?:contain|state|provide|specify|mention|include|give|report|"
    r"disclose|address|show|indicate|identify|list|reveal|offer|cover|quantify)\b",
    # "could not be established", "was not found", "is not publicly available", "has not been disclosed"
    r"\b(?:could|can|was|were|is|are|has|have)\s*(?:not|n't)\s+(?:yet\s+)?(?:been\s+|be\s+)?(?:publicly\s+)?"
    r"(?:found|established|determined|confirmed|verified|identified|retrieved|located|obtained|available|"
    r"disclosed|specified|stated|reported|provided|mentioned|known|clear)\b",
    r"\bcannot\s+(?:be\s+)?(?:found|established|determined|confirmed|verified|identified|determine|confirm|"
    r"verify|establish|find)\b",
    rf"\black(?:s|ed|ing)?\s+(?:\w+\s+){{0,3}}?{_INFO}\b",
    rf"\bmissing\s+(?:from\b|(?:\w+\s+){{0,2}}?{_INFO}\b)|\b(?:is|are|was|were|remains?)\s+missing\b",
    rf"\bno\s+(?:\w+[\s-]+){{0,4}}?{_INFO}\b",
    rf"\bnone\s+of\s+the\s+(?:\w+\s+){{0,2}}?{_EVID}\b",
    r"\bno\b[^.;]{0,80}?\b(?:was|were|is|are|has\s+been|have\s+been)\s+(?:found|reported|available|provided|"
    r"identified|disclosed|established|given|stated|located|retrieved)\b",
    r"\bunable\s+to\s+(?:find|determine|confirm|verify|establish|retrieve|locate|identify|access|read)\b",
    r"\bfailed\s+to\s+(?:find|retrieve|locate|identify|establish|determine|return|yield)\b",
    r"\b(?:remains?|is|are|was|were)\s+(?:currently\s+|still\s+)?(?:unknown|unclear|undisclosed|unspecified|"
    r"unavailable|undetermined|unconfirmed)\b",
    rf"\b(?:absence|lack)\s+of\s+(?:\w+\s+){{0,3}}?{_INFO}\b",
    rf"\binsufficient\s+{_INFO}\b",
    rf"\b{_EVID}\s+(?:returned|yielded|produced|found)\s+(?:nothing|no\b)",
]), re.I)

# A sentence whose subject is the evidence itself ("The text confirms ...", "They only confirm ...")
# is a remark about the research, not a self-contained statement a fresh researcher could check.
_META = re.compile(
    r"^\W*(?:(?:the|these|those|all|both)\s+)?(?:(?:provided|available|retrieved|cited|above|current|existing|"
    r"given)\s+)?(?:findings?|sources?|results?|text|evidence|snippets?|research|search(?:es)?)\b"
    r"|^\W*(?:they|it|this|these)\s+(?:(?:only|merely|just|also)\s+)?(?:confirm|state|show|indicate|mention|"
    r"note|say|describe|report)s?\b", re.I)


def is_absence_statement(text: str) -> bool:
    """True if `text` says that information is missing, was not found, or could not be established."""
    return bool(_ABSENCE.search(text or ""))


def verifiable_part(text: str, max_words: int = 60) -> str:
    """The part of `text` that asserts something about the world: clauses that neither report missing
    information nor talk about the evidence. Empty when there is nothing a verifier could check."""
    keep = []
    for sent in sentences(strip_cites(text)):
        for clause in _clauses(sent):
            c = clause.strip(" ,;")
            if len(c.split()) < 4 or _ABSENCE.search(c) or _META.search(c):
                continue
            c = c[0].upper() + c[1:]                       # a kept clause may have started mid-sentence
            keep.append(c if c.endswith((".", "?", "!")) else c + ".")
    out = " ".join(" ".join(keep).split()[:max_words])
    return out if len(out.split()) >= 5 else ""


def is_non_answer(text: str) -> bool:
    return not verifiable_part(text)


def positive_clauses(text: str) -> list[str]:
    """The clauses of `text` that do not report missing information (citations kept)."""
    return [c for sent in sentences(text) for c in _clauses(sent) if not _ABSENCE.search(strip_cites(c))]


def checked_verdict(claim: str, verdict: str, explanation: str, cited: bool) -> tuple[str, str]:
    """A verifier's verdict after the checks a model cannot be trusted to apply to itself.
    Returns (verdict, reason-if-changed)."""
    if verdict == "unverifiable":
        return verdict, ""
    if not verifiable_part(claim):
        return "unverifiable", "the claim only describes missing information, so there was nothing to verify"
    if not cited:
        return "unverifiable", f"verdict {verdict!r} cited no evidence"
    if verdict == "survived" and not verifiable_part(explanation):
        return "unverifiable", "the verifier's own explanation only describes missing information"
    return verdict, ""


# =================================================================================================
# 2. Quantities
# =================================================================================================

_SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "mn": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9,
          "trillion": 1e12, "tn": 1e12, "t": 1e12}
_QTY = re.compile(r"""
    (?:(?P<cur>US\$|\$|USD\s?)               # a currency sign starts a figure wherever it stands ("profit$17.34B")
      |(?<![A-Za-z0-9.,])
      |(?<=\d[BMKT]))                         # a table cell glued to the previous one: "$17.34B32.7%"
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    (?:(?P<abbr>[BMKTbmk])(?![A-Za-z])
      |\s?(?P<unit>%|percent(?:age\s+points?)?\b|ppts?\b|pts\b|basis\s+points?\b|bps\b
                  |trillion\b|billion\b|million\b|thousand\b|bn\b|mn\b))?
""", re.X | re.I)
_REFERENCE = re.compile(r"(?:\bfrom|\bversus|\bvs\.?|\bcompared\s+(?:to|with)|\bprior|\bprevious|\bup|\bdown|"
                        r"\bincrease\s+of|\bdecrease\s+of|\brise\s+of|\bdecline\s+of|\bgrew|\bgrowth\s+of|"
                        r"\brose|\bfell|\bby)\s+(?:about\s+|roughly\s+|approximately\s+|nearly\s+)?$", re.I)


@dataclass
class Quantity:
    kind: str          # percent | points | amount (has a currency sign or a scale word) | plain
    num: float         # the number as written (130.5 for "$130.5 billion")
    value: float       # with the scale applied (1.305e11)
    decimals: int
    raw: str
    start: int
    end: int
    grouped: bool = False     # written with thousands separators ("96,169")


def quantities(text: str) -> list[Quantity]:
    out = []
    for m in _QTY.finditer(strip_cites_keep_offsets(text or "")):
        raw_num = m.group("num")
        num = float(raw_num.replace(",", ""))
        decimals = len(raw_num.split(".")[1]) if "." in raw_num else 0
        unit = (m.group("unit") or "").lower()
        abbr = (m.group("abbr") or "").lower()
        if unit in ("%", "percent"):
            kind, value = "percent", num
        elif unit and ("point" in unit or unit in ("ppt", "ppts", "pts", "bps")):
            kind, value = "points", num
        elif unit or abbr:
            kind, value = "amount", num * _SCALE[re.sub(r"\s+", "", unit or abbr)]
        elif m.group("cur"):
            kind, value = "amount", num
        else:
            kind, value = "plain", num
        out.append(Quantity(kind, num, value, decimals, m.group(0).strip(), m.start(), m.end(), "," in raw_num))
    return out


def strip_cites_keep_offsets(text: str) -> str:
    """Blank out [S3]-style citations without moving anything, so offsets stay valid."""
    return re.sub(r"\[\s*[SF]\d+(?:\s*[,;]\s*[SF]\d+)*\s*\]", lambda m: " " * len(m.group(0)), text)


def _is_reference(text: str, q: Quantity) -> bool:
    """A figure quoted as a baseline or a change ("up from 46%", "grew 14%") rather than as the level."""
    return bool(_REFERENCE.search(text[max(0, q.start - 28):q.start]))


def _matches(q: Quantity, pool: list[Quantity], bare: bool = True) -> bool:
    """Is the figure `q` (from a claim) backed by some figure in `pool` (from the source)? Allows
    rounding in either direction ("$115.2 billion" and "115,186" back each other) and a change of
    scale ("$130.5 billion" vs "130,497"). With `bare=False`, undecorated integers in the pool (days of
    the month, counts) back nothing: over a whole page there are too many of them to mean anything."""
    tol = 0.5 * 10 ** (-q.decimals) + 1e-9
    for p in pool:
        if not bare and not _needs_support(p):
            continue
        ptol = 0.5 * 10 ** (-p.decimals)
        if q.kind in ("percent", "points"):
            if p.kind != "amount" and abs(q.num - p.num) <= max(tol, ptol):
                return True
        else:
            for k in (0, 3, -3, 6, -6, 9, -9):
                if abs(q.num - p.num * 10 ** k) <= max(tol, ptol * 10 ** k):
                    return True
    return False


def _needs_support(q: Quantity) -> bool:
    return q.kind != "plain" or q.decimals > 0 or q.grouped       # years and bare counts are left alone


# =================================================================================================
# 3. Accounting basis
# =================================================================================================

_NONGAAP = re.compile(r"\bnon[-\s]?gaap\b|\badjusted\b", re.I)
_GAAP = re.compile(r"(?<!non-)(?<!non )\bgaap\b", re.I)
_LABEL_LINE = re.compile(r"(?:non[-\s]?gaap|gaap)\b[^.]{0,40}", re.I)


def basis_labels(text: str) -> set[str]:
    out = set()
    if _NONGAAP.search(text or ""):
        out.add("non-gaap")
    if _GAAP.search(text or ""):
        out.add("gaap")
    return out


def _norm_with_map(text: str) -> tuple[str, list[int]]:
    """`norm(text)` plus, for every character of it, the offset it came from in `text`."""
    chars, idx, prev_space = [], [], True
    for i, ch in enumerate(text):
        n = norm(ch)
        if not n:                      # whitespace
            if not prev_space:
                chars.append(" ")
                idx.append(i)
            prev_space = True
            continue
        for c in n:
            chars.append(c)
            idx.append(i)
        prev_space = False
    return "".join(chars).rstrip(), idx


def locate(quote: str, text: str) -> tuple[int, int] | None:
    """(start, end) offsets of `quote` in `text`, tolerant of whitespace and line breaks. When only
    the opening of the quote can be found (the quote check itself is fuzzy), that is used."""
    q = norm(quote).strip(" .\"'")
    if len(q) < 8:
        return None
    t, idx = _norm_with_map(text)
    for probe in (q, q[:48], q[:24]):
        at = t.find(probe)
        if at >= 0 and probe:
            end = min(len(idx) - 1, at + len(q) - 1)
            return idx[at], idx[end] + 1
    return None


def basis_evidence(quote: str, text: str) -> tuple[set[str], str]:
    """Which accounting basis the passage itself shows for the quoted figures, and how we know:
    "quote" (label inside the quote), "heading" (a GAAP / Non-GAAP line above a table row),
    "contrast" (an unlabelled figure followed by "On a non-GAAP basis ..."), or "" (not shown)."""
    inside = basis_labels(quote)
    if inside:
        return inside, "quote"
    span = locate(quote, text)
    if span is None:
        return set(), ""
    start, end = span
    above = text[:start].splitlines()
    seen = 0
    for line in reversed(above[-45:]):                 # a table row is governed by the label line above it
        s = line.strip(" |\t")
        if s and len(s) <= 48 and _LABEL_LINE.fullmatch(s):
            return basis_labels(s), "heading"
        seen += len(line) + 1
        if seen > 2500 or len(s) > 400:                # ran into prose: no heading governs this quote
            break
    after = text[end:end + 320].split("\n")[0]
    if re.search(r"\bon\s+an?\s+non[-\s]?gaap\b", after, re.I):
        return {"gaap"}, "contrast"
    return set(), ""


def _neutralise_basis(claim: str) -> str:
    out = re.sub(r"\bon\s+an?\s+(?:non[-\s]?)?gaap\s+basis,?\s*", "", claim, flags=re.I)
    out = re.sub(r"\b(?:non[-\s]?gaap|gaap)\s+", "", out, flags=re.I)
    return out.rstrip(" .") + " (GAAP or non-GAAP basis not shown in the quoted passage)."


# =================================================================================================
# 4. Claim checks at extraction
# =================================================================================================

NEARBY = 400     # characters of page text either side of a quote that count as "next to it"


@dataclass
class ClaimCheck:
    ok: bool
    claim: str
    basis: str = ""          # gaap | non-gaap | both | "" (not shown by the passage)
    reason: str = ""         # why the claim was rejected or changed


def check_claim(claim: str, quote: str, text: str) -> ClaimCheck:
    """Tie a proposed claim to its quote.

    - A figure that is nowhere in the source text rejects the finding (main clause) or is cut
      (trailing clause). This is what stops invented and model-computed numbers.
    - A figure that is in the source but not in the quote or right next to it (within NEARBY
      characters) is attached to the wrong passage: a trailing clause carrying one is cut. In the
      main clause it is let through, because models often quote one sentence of the two they
      summarise and rejecting those would discard true findings (measured on the recorded runs).
    - A GAAP / non-GAAP label in the claim must not contradict what the passage shows; a label the
      passage does not show at all is removed and the claim says so.
    """
    quoted = quantities(quote)
    span = locate(quote, text)
    around = quantities(text[max(0, span[0] - NEARBY):span[1] + NEARBY]) if span is not None else []
    whole: list[Quantity] | None = None

    def near(q: Quantity) -> bool:
        return _matches(q, quoted) or _matches(q, around, bare=False)

    parts = re.split(r",\s+(?=[a-z])|;\s+", claim.strip())
    kept, dropped = [], []
    for i, part in enumerate(parts):
        far = [q for q in quantities(part) if _needs_support(q) and not near(q)]
        if not far:
            kept.append(part)
            continue
        if i:
            dropped += [q.raw for q in far]
            continue
        whole = quantities(text) if whole is None else whole
        absent = [q.raw for q in far if not _matches(q, whole, bare=False)]
        if absent:
            return ClaimCheck(False, claim, reason=f"figure {absent[0]} in the claim is not in the source text")
        kept.append(part)
    if dropped and not any(_needs_support(q) for part in kept for q in quantities(part)):
        # cutting the unsupported clause would leave a claim with no figure in it: nothing worth keeping
        return ClaimCheck(False, claim, reason=f"figure {dropped[0]} in the claim is not in or next to the quoted passage")
    reasons = []
    out = claim
    if dropped:
        out = ", ".join(kept).rstrip(" .,;") + "."
        reasons.append(f"dropped a clause whose figure(s) {', '.join(dropped[:3])} are not in or next to the "
                       f"quoted passage")

    shown, how = basis_evidence(quote, text)
    said = basis_labels(out)
    basis = "both" if len(shown) == 2 else next(iter(shown), "")
    if said and shown and not (said & shown):
        return ClaimCheck(False, claim, basis,
                          f"claim says {'/'.join(sorted(said))} but the passage is labelled "
                          f"{'/'.join(sorted(shown))} ({how})")
    if said and not shown:
        out = _neutralise_basis(out)
        reasons.append("removed a GAAP/non-GAAP label the quoted passage does not show")
    return ClaimCheck(True, out, basis, "; ".join(reasons))


# =================================================================================================
# 5. Comparisons
# =================================================================================================

_COMPARE = re.compile(r"\b(?:compare[sd]?|comparison|rank(?:ing|ed|s)?|versus|vs\.?|highest|largest|biggest|"
                      r"lowest|smallest|higher|lower|more\s+than|less\s+than|difference\s+between)\b", re.I)
_PCT_METRIC = re.compile(r"\b(?:margins?|rates?|growth|share|yield|percent(?:age)?|ratio|return|roe|roic)\b", re.I)
_AMT_METRIC = re.compile(r"\b(?:revenues?|sales|income|profits?|earnings|capex|expenditures?|spending|cash|debt|"
                         r"assets|market\s+cap(?:italization)?|valuation|costs?|backlog|bookings|ebitda|budget)\b",
                         re.I)
_NOT_ENTITY = frozenset("gaap non-gaap fy us u.s usd ai i q1 q2 q3 q4 h1 h2 ceo cfo eps ebitda".split())
_QUARTER = re.compile(r"\bq[1-4]\b|\bquarter(?:ly)?\b|\b(?:first|second|third|fourth)[-\s]quarter\b", re.I)
_ANNUAL = re.compile(r"\bfy\s?\d{2,4}\b|\bfiscal(?:\s+year)?\b|\bfull[-\s]year\b|\bannual\b|\bcalendar(?:\s+year)?\b|"
                     r"\byear\b", re.I)


def compared_entities(objective: str) -> list[str]:
    """Capitalised names in the objective, in order: what a "compare A, B and C" question compares."""
    names: list[str] = []
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9&.\-]*[A-Za-z0-9]\b|\b[A-Z]{2,}\b", objective or ""):
        w = m.group(0)
        if (m.start() == 0 and not w.isupper()) or w.lower() in _NOT_ENTITY or re.fullmatch(r"(?:FY|Q|H)\d+", w):
            continue
        if w not in names:
            names.append(w)
    return names


def metric_terms(objective: str, entities: list[str]) -> list[str]:
    """Five-letter stems of the words that name what is being compared ("margin", "reven")."""
    skip = {e.lower() for e in entities} | {"compare", "compared", "comparison", "fiscal", "calendar", "year",
                                             "years", "total", "annual", "between", "which", "their", "three"}
    out = []
    for w in re.findall(r"[A-Za-z]{5,}", objective or ""):
        if w.lower() not in skip and w.lower()[:5] not in out:
            out.append(w.lower()[:5])
    return out


@dataclass
class Row:
    entity: str
    label: str = ""
    value: float | None = None
    raw: str = ""
    ambiguous: bool = False
    basis: set = field(default_factory=set)
    period: set = field(default_factory=set)


@dataclass
class Comparison:
    kind: str
    entities: list
    metric: list
    rows: list
    warnings: list

    def ranked(self) -> list[Row]:
        return sorted((r for r in self.rows if r.value is not None and not r.ambiguous), key=lambda r: -r.value)

    def ranking(self) -> list[tuple[list[str], float]]:
        return [([r.entity], r.value) for r in self.ranked()]

    def order_text(self) -> str:
        return " > ".join(f"{r.entity} ({r.raw})" for r in self.ranked())

    def prompt_block(self) -> str:
        ranked = self.ranked()
        lines = []
        if len(ranked) >= 2:
            lines.append("FIGURES PICKED OUT BY CODE (one per compared entity, taken from the results above), "
                         "sorted from highest to lowest. Use this order; do not re-rank them yourself:")
            lines += [f"{i}. {r.entity}: {r.raw}" for i, r in enumerate(ranked, 1)]
        unclear = [r.entity for r in self.rows if r.value is not None and r.ambiguous]
        if unclear:
            lines.append("Several different figures were reported for: " + ", ".join(unclear) +
                         ". Say which figure you use and why.")
        missing = [r.entity for r in self.rows if r.value is None]
        if missing and len(ranked) >= 1:
            lines.append("No figure was found for: " + ", ".join(missing) + ". Do not rank or estimate it.")
        lines += [f"Caution: {w}" for w in self.warnings]
        return "\n".join(lines)


def _headline(answer: str, kind: str, annual: bool) -> tuple[list[Quantity], str]:
    """Candidate level figures of `kind` in a sub-result, with the sentence of the first one."""
    found, first_sentence = [], ""
    for sent in sentences(answer):
        if is_absence_statement(sent):
            continue
        for clause in _clauses(sent):
            if annual and _QUARTER.search(clause):
                continue                         # a quarterly figure is not the annual one that was asked for
            for q in quantities(clause):
                if q.kind == kind and not _is_reference(strip_cites_keep_offsets(clause), q):
                    found.append(q)
                    first_sentence = first_sentence or sent
    return found, first_sentence


def build_comparison(objective: str, children: list[tuple[str, str, bool]]) -> Comparison | None:
    """Line up one figure per compared entity from the sub-results.

    `children` is (sub-objective, answer, is_follow_up) in creation order. Returns None unless the
    objective asks for a comparison of named entities on one kind of figure."""
    entities = compared_entities(objective)
    if len(entities) < 2 or not _COMPARE.search(objective or ""):
        return None
    pct, amt = bool(_PCT_METRIC.search(objective)), bool(_AMT_METRIC.search(objective))
    if pct == amt:
        return None                              # no metric named, or both kinds: nothing safe to line up
    kind = "percent" if pct else "amount"
    rows = {e: Row(e) for e in entities}
    for sub, answer, _follow in sorted(children, key=lambda c: c[2]):      # planned children before follow-ups
        named = [e for e in entities if re.search(rf"(?<![A-Za-z0-9]){re.escape(e)}(?![A-Za-z0-9])", sub, re.I)]
        if len(named) != 1 or rows[named[0]].value is not None or not answer:
            continue
        cands, sent = _headline(answer, kind, bool(_ANNUAL.search(sub)) and not _QUARTER.search(sub))
        if not cands:
            continue
        distinct = [cands[0]]
        for q in cands[1:]:
            if all(abs(q.value - d.value) > 0.01 * max(abs(d.value), 1e-9) for d in distinct):
                distinct.append(q)
        row = rows[named[0]]
        row.label, row.value, row.raw, row.ambiguous = sub, cands[0].value, cands[0].raw, len(distinct) > 1
        row.basis = basis_labels(sent)
        row.period = ({"quarter"} if _QUARTER.search(sent) else set()) | ({"annual"} if _ANNUAL.search(sent) else set())
    out = Comparison(kind, entities, metric_terms(objective, entities), list(rows.values()), [])
    have = [r for r in out.rows if r.value is not None]
    gaap = [r.entity for r in have if r.basis == {"gaap"}]
    non = [r.entity for r in have if r.basis == {"non-gaap"}]
    if gaap and non:
        out.warnings.append(f"the figures are on different accounting bases ({', '.join(gaap)}: GAAP; "
                            f"{', '.join(non)}: non-GAAP), so they are not like for like. Say so.")
    quarterly = [r.entity for r in have if r.period == {"quarter"}]
    yearly = [r.entity for r in have if r.period == {"annual"}]
    if quarterly and yearly:
        out.warnings.append(f"the figures cover different periods ({', '.join(quarterly)}: a quarter; "
                            f"{', '.join(yearly)}: a year), so they are not like for like. Say so.")
    return out


CORRECTION_MARK = "Correction (computed from the figures, not written by the model)"

_MAX = re.compile(r"\b(?:highest|largest|biggest|greatest|the\s+most|ranks?\s+first|leads\s+(?:the|all|with)|"
                  r"tops\s+the)\b", re.I)
_MIN = re.compile(r"\b(?:lowest|smallest|the\s+least|ranks?\s+last|trails\s+(?:the|all|both))\b", re.I)
_PAIR = re.compile(r"\b(?:(?P<gt>higher|greater|larger|bigger|more)|(?P<lt>lower|smaller|less|fewer))\s+than\b|"
                   r"\b(?P<gt2>exceed(?:s|ed|ing)?|surpass(?:es|ed|ing)?|outpac(?:es|ed|ing))\b", re.I)
_GLUE = re.compile(r"[\s,)\]]*(?:(?:is|was|were|are|which|that|and|slightly|significantly|substantially|much|far|"
                   r"well|also|still|only|marginally)\s+)*", re.I)


def _other_name(between: str) -> bool:
    """Does the text between two figures introduce another subject (a capitalised name)?"""
    return bool(compared_entities("x " + between))


def _fmt(q: Quantity) -> str:
    return q.raw


def ordering_issues(answer: str, ranking: list[tuple[list[str], float | None]] | None = None,
                    metric: list[str] | None = None) -> list[dict]:
    """Ordering statements in `answer` that contradict figures.

    Three checks, each quiet unless it is sure of both sides:
    A. a superlative ("the highest ... $350 billion") with a larger (smaller) figure of the same kind
       attached to another name in the same sentence;
    B. "X is higher / lower than Y" with the two figures the wrong way round;
    C. given `ranking` (names with values, highest first) and `metric` stems: a sentence about that
       metric that calls a named entity the highest or lowest when the ranking says otherwise.
    """
    issues: list[dict] = []
    ranked = [(names, v) for names, v in (ranking or []) if names]
    answer = (answer or "").split(CORRECTION_MARK)[0]      # a correction we appended quotes the error; skip it
    for sent in sentences(answer):
        clean = strip_cites_keep_offsets(sent)
        qs = [q for q in quantities(sent) if q.kind in ("amount", "percent")]
        for rx, want_max in ((_MAX, True), (_MIN, False)):
            for m in rx.finditer(clean):
                # ---- A: figures in the same sentence ----
                after = [q for q in qs if q.start >= m.end() and not _is_reference(clean, q)]
                if after:
                    claimed = after[0]
                    for other in qs:
                        if other is claimed or other.kind != claimed.kind or _is_reference(clean, other):
                            continue
                        lo, hi = sorted((claimed.end, other.start)) if other.start > claimed.end else \
                            sorted((other.end, claimed.start))
                        if not _other_name(clean[lo:hi]):
                            continue             # both figures belong to the same subject: not a ranking
                        worse = other.value > claimed.value * 1.005 if want_max else other.value < claimed.value * 0.995
                        if worse:
                            issues.append({"check": "superlative", "sentence": sent[:240],
                                           "detail": f"{_fmt(claimed)} is called the {m.group(0).lower()} but "
                                                     f"{_fmt(other)} in the same sentence is "
                                                     f"{'larger' if want_max else 'smaller'}"})
                            break
                # ---- C: named entity against the known ranking ----
                if len(ranked) >= 2 and (not metric or any(t in clean.lower() for t in metric)):
                    best = None
                    for names, value in ranked:
                        for n in names:
                            for hit in re.finditer(rf"(?<![A-Za-z0-9]){n}(?![A-Za-z0-9])", clean, re.I):
                                if hit.start() < m.start() and (best is None or hit.start() > best[0]):
                                    best = (hit.start(), names[0], value)
                    if best is not None and all(v is not None for _, v in ranked):
                        target = ranked[0] if want_max else ranked[-1]
                        tie = abs(best[2] - target[1]) <= 0.005 * max(abs(target[1]), 1e-9)
                        if best[1].lower() != target[0][0].lower() and not tie:
                            issues.append({"check": "ranking", "sentence": sent[:240],
                                           "detail": f"{best[1]} is called the {m.group(0).lower()}, but by the "
                                                     f"figures it is {target[0][0]}"})
        # ---- B: pairwise comparatives ----
        for m in _PAIR.finditer(clean):
            before = [q for q in qs if q.end <= m.start() and m.start() - q.end <= 40]
            later = [q for q in qs if q.start >= m.end() and q.start - m.end() <= 90]
            if not before or not later:
                continue
            a, b = before[-1], later[0]
            if a.kind != b.kind or _is_reference(clean, a) or not _GLUE.fullmatch(clean[a.end:m.start()]):
                continue                         # only "<figure> is higher than <figure>", nothing in between
            greater = bool(m.group("gt") or m.group("gt2"))
            if (greater and a.value < b.value * 0.995) or (not greater and a.value > b.value * 1.005):
                issues.append({"check": "comparative", "sentence": sent[:240],
                               "detail": f"{_fmt(a)} is said to be {m.group(0).lower()} {_fmt(b)}"})
    seen, out = set(), []
    for i in issues:                              # one report per sentence and check
        key = (i["check"], i["sentence"])
        if key not in seen:
            seen.add(key)
            out.append(i)
    return out


def correction_note(issues: list[dict], cmp: Comparison | None) -> str:
    """A labelled, code-written correction appended to an answer whose ordering statements could not
    be repaired by asking the model again. Nothing in the model's text is deleted."""
    parts = [CORRECTION_MARK + ": " +
             "; ".join(i["detail"] for i in issues[:3]) + "."]
    if cmp is not None and len(cmp.ranked()) >= 2:
        parts.append("Ordered by the reported figures: " + cmp.order_text() + ".")
    return " ".join(parts)


# =================================================================================================
# 6. Answer-level audit
# =================================================================================================

def basis_conflicts(answer: str, findings: list[dict], known_sources: set[str]) -> list[dict]:
    """Sentences that put a GAAP / non-GAAP label on a figure when the passage the figure came from
    shows the other basis. `findings` are dicts with source_id, claim, quote and basis."""
    out = []
    for sent in sentences(answer):
        said = basis_labels(sent)
        if len(said) != 1:
            continue
        ids = [s for s in re.findall(r"S\d+", " ".join(re.findall(r"\[[^\]]*\]", sent))) if s in known_sources]
        if not ids:
            continue
        for q in quantities(sent):
            if q.kind not in ("percent", "amount"):
                continue
            shown = set()
            for f in findings:
                if f.get("source_id") in ids and f.get("basis") and \
                        _matches(q, quantities(f"{f.get('claim', '')} {f.get('quote', '')}")):
                    shown |= {"gaap", "non-gaap"} if f["basis"] == "both" else {f["basis"]}
            if shown and not (said & shown):
                out.append({"sentence": sent[:240], "figure": q.raw, "said": next(iter(said)),
                            "passage_shows": "/".join(sorted(shown))})
                break
    return out


_ANNUAL_LABEL = re.compile(r"\bfy\s?\d{2,4}\b|\bfiscal(?:\s+year)?(?:\s+\d{4})?\b|\bfull[-\s]year\b|\bannual\b|"
                           r"\bcalendar\s+year\b|\btwelve\s+months\b|\byear\s+ended\b|\bfor\s+the\s+year\b", re.I)
_LABEL_SPLIT = re.compile(r",?\s+(?:while|whereas|but|and|although|though)\s+|;\s+", re.I)
_NOT_A_PERIOD = re.compile(r"annuali[sz]ed|run[-\s]rate|trailing", re.I)
# a quarter the figure is FOR; "the previous quarter" and "quarter-over-quarter" are comparisons, not labels
_QUARTER_LABEL = re.compile(r"\bq[1-4]\b|\b(?:first|second|third|fourth)[-\s]quarter\b|\bquarterly\b|"
                            r"\b(?:three|3)\s+months\b|"
                            r"(?<!previous )(?<!prior )(?<!last )(?<!same )(?<!over-)(?<!over )\bquarter\b(?!-over|'s|\s+over)",
                            re.I)


def period_near(text: str, q: Quantity, figures: list[Quantity] = ()) -> str:
    """The reporting period `text` attaches to figure `q`: "quarter", "annual", or "" when there is
    no label or it cannot be told.

    In order: a label directly after the figure ("51% recorded in Q4", "49% for fiscal year 2024");
    else the nearest label before it with no other figure in between ("In the fourth quarter ...,
    gross margin was 73.0%"); else the nearest label after it with neither a figure nor another
    name in between. An annual label attached to a quarter label ("fourth quarter of fiscal year
    2025", "FY25 Q4") is part of naming the quarter."""
    if _NOT_A_PERIOD.search(text):
        return ""
    quarters = [(m.start(), m.end(), "quarter") for m in _QUARTER_LABEL.finditer(text)]
    marks = list(quarters)
    for m in _ANNUAL_LABEL.finditer(text):
        if not any(0 <= m.start() - e <= 30 or 0 <= s - m.end() <= 2 for s, e, _ in quarters):
            marks.append((m.start(), m.end(), "annual"))
    others = [o for o in figures if o is not q and o.kind in ("amount", "percent")]

    def figure_between(lo: int, hi: int) -> bool:
        return any(lo <= o.start and o.end <= hi for o in others)

    after = sorted((m for m in marks if m[0] >= q.end and not figure_between(q.end, m[0])
                    and not _other_name(text[q.end:m[0]])), key=lambda m: m[0])
    if after and after[0][0] - q.end <= 20 and "," not in text[q.end:after[0][0]]:
        return after[0][2]
    def taken(m: tuple) -> bool:      # "73% in Q4 FY2025 ... AMD's 49%": that label belongs to the 73%
        return any(0 <= m[0] - o.end <= 20 and "," not in text[o.end:m[0]] for o in others if o.end <= m[0])

    before = [m for m in marks if m[1] <= q.start and not figure_between(m[1], q.start) and not taken(m)]
    if before:
        return max(before, key=lambda m: m[1])[2]
    return after[0][2] if after else ""


def period_conflicts(answer: str, findings: list[dict], known_sources: set[str]) -> list[dict]:
    """Clauses that present a figure as a full-year one when the finding it was taken from gives it
    for a quarter, or the reverse. Seen live in the first patched W1 run: NVIDIA's fourth-quarter
    GAAP margin (73.0%) was written up as its fiscal-year margin."""
    out = []
    for sent in sentences(answer):
        ids = [s for s in re.findall(r"S\d+", " ".join(re.findall(r"\[[^\]]*\]", sent))) if s in known_sources]
        if not ids:
            continue
        for clause in _LABEL_SPLIT.split(strip_cites_keep_offsets(sent)):
            figures = quantities(clause)
            for q in figures:
                said = period_near(clause, q, figures)
                if not said or q.kind not in ("percent", "amount") or _is_reference(clause, q):
                    continue
                source = set()
                for f in findings:
                    if f.get("source_id") in ids:
                        for part in _LABEL_SPLIT.split(f.get("claim", "")):
                            theirs = quantities(part)
                            source |= {period_near(part, x, theirs) for x in theirs
                                       if x.kind == q.kind and _matches(q, [x])}
                if source and "" not in source and said not in source:
                    out.append({"sentence": sent[:240], "figure": q.raw, "said": said,
                                "finding_says": "/".join(sorted(source))})
                    break
    return out


def describe_label_issue(issue: dict) -> str:
    if "finding_says" in issue:
        said = {"annual": "full-year", "quarter": "quarterly"}[issue["said"]]
        source = {"annual": "the full year", "quarter": "a quarter"}.get(issue["finding_says"], issue["finding_says"])
        return f"{issue['figure']} is given as a {said} figure, but the finding it comes from gives it for {source}"
    return f"{issue['figure']} is called {issue['said']}, but its passage shows {issue['passage_shows']}"


def label_fact(issue: dict) -> str:
    """The plain fact behind a label problem, for passing on to a parent agent. It says what the figure
    is, not what went wrong with a draft nobody will see: in a live run the parent read "the written
    answer mislabelled a figure" and attached that remark to a different figure."""
    if "finding_says" in issue:
        period = {"annual": "the full year", "quarter": "a quarter"}
        return (f"{issue['figure']} is the figure for {period.get(issue['finding_says'], issue['finding_says'])}, "
                f"not for {period[issue['said']]}")
    label = {"gaap": "GAAP", "non-gaap": "non-GAAP"}
    return (f"{issue['figure']} is a {label.get(issue['passage_shows'], issue['passage_shows'])} figure, "
            f"not a {label[issue['said']]} one")


def consistency_audit(answer: str, findings: list[dict], known_sources: set[str],
                      cmp: Comparison | None = None) -> dict:
    ordering = ordering_issues(answer, cmp.ranking() if cmp else None, cmp.metric if cmp else None)
    basis = basis_conflicts(answer, findings, known_sources)
    period = period_conflicts(answer, findings, known_sources)
    return {"ordering_issues": ordering, "basis_conflicts": basis, "period_conflicts": period,
            "mixed_basis_or_period": list(cmp.warnings) if cmp else [],
            "clean": not ordering and not basis and not period}


# =================================================================================================
# 7. Identification questions ("which company ...?"): is the named entity actually supported?
# =================================================================================================
# Added after looking at why D1 answered Amkor and D2 answered Intel Foundry. In both, the model named
# an entity on the strength of one source reporting a deal or a plan, and no quoted passage stated the
# relationship that was asked about. Opt-in: SwarmConfig.identify_guard and SwarmConfig.support_check.

_WH_SECOND = re.compile(r",?\s+and\s+(?:(?:in|by|at|for|to|on)\s+)?(?:which|who|whom|what|how|when|where|why)\b", re.I)
_NOT_IDENTIFY = re.compile(r"what\s+(?:was|were|is|are|did|does|do)\b|which\s+of\b", re.I)
_PLAN = re.compile(r"\bwill\b|\bwould\b|\bplans?\s+to\b|\bplanned\b|\bexpected\s+to\b|\bintends?\s+to\b|\bset\s+to\b|"
                   r"\bagree(?:d|ment)\b|\bdeals?\b|\bpartnerships?\b|\bsigned\b|\bannounced\b|"
                   r"\bto\s+(?:manufacture|produce|build|make|supply|develop|expand)\b", re.I)


_OPENERS = frozenset("the this that these those it they there no none according based however in on for as a an its "
                     "their while although our we he she by at to from with and but or if when what which who".split())


def asks_to_identify(objective: str) -> bool:
    """Does the objective ask for an entity it does not name ("Which company ...", "Who ...")?"""
    o = (objective or "").strip()
    return bool(re.match(r"(?:which|who)\b|what\s+(?:company|supplier|firm|manufacturer|foundry|bank|vendor|maker)\b",
                         o, re.I)) and not _NOT_IDENTIFY.match(o)


def two_part_identification(objective: str) -> bool:
    """"Which X ..., and <a second question that depends on the answer>?" The second part cannot be
    right unless the first is, so such a question deserves step-by-step work and an independent
    check of the first answer rather than a single lookup."""
    o = (objective or "").strip()
    return bool(re.match(r"(?:which|who|what)\b", o, re.I)) and not _NOT_IDENTIFY.match(o) and bool(_WH_SECOND.search(o))


def first_part(objective: str) -> str:
    """The identification half of a two-part question, word for word.

    In D1 the model reworded "Which supplier's advanced-packaging capacity most constrains shipments
    ..." as "Who is the primary supplier of advanced packaging technology ...". The relationship that
    was asked about ("constrains shipments") was gone before the first search, and the search then
    returned a different relationship's news. Asking the first part verbatim keeps it."""
    o = (objective or "").strip()
    m = _WH_SECOND.search(o)
    return (o[:m.start()].rstrip(" ,;") + "?") if m else o


def identified_entity(objective: str, answer: str) -> str:
    """The first name in the answer's opening sentence that the objective did not already contain."""
    first = (sentences(strip_cites(answer)) or [""])[0]
    if is_absence_statement(first):
        return ""                                   # "The findings do not say ..." identifies nobody
    asked = (objective or "").lower()
    for name in compared_entities("x " + first):
        if name.lower() not in asked and name.lower() not in _OPENERS:
            return name
    return ""


@dataclass
class Support:
    entity: str
    domains: list
    flags: list          # empty when the identification is adequately supported


def identification_support(objective: str, answer: str, findings: list[dict], domain_of_source: dict) -> Support | None:
    """For an identification question: which quoted passages name the entity the answer gives, how
    many independent sites they come from, and whether they only describe a deal or a plan.
    Returns None when the objective is not an identification or the answer names no new entity."""
    if not asks_to_identify(objective):
        return None
    entity = identified_entity(objective, answer)
    if not entity:
        return None
    named = re.compile(rf"(?<![A-Za-z]){re.escape(entity)}(?![A-Za-z])", re.I)
    backing = [f for f in findings if named.search(f.get("quote", ""))]
    domains = sorted({domain_of_source.get(f.get("source_id"), "") for f in backing} - {""})
    flags = []
    if not backing:
        flags.append("no quoted passage names it")
    elif len(domains) < 2:
        flags.append(f"it rests on one source ({domains[0] if domains else 'unknown'})")
    if backing and all(_PLAN.search(f.get("quote", "")) for f in backing):
        flags.append("the passages describe a deal or a plan, not the current situation")
    return Support(entity, domains, flags)

