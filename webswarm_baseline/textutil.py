"""Small deterministic text helpers: tokenising, passage selection, quote and number checks."""
from __future__ import annotations

import math
import re
from urllib.parse import urlsplit

_WORD = re.compile(r"[a-z0-9][a-z0-9.\-']*")
_STOP = frozenset("""a an and are as at be been but by can could did do does for from had has have how if in
into is it its may might more most not of on or over than that the their them then there these they this
those to was were what when where which while who whom whose why will with would about after also any
between both during each other such per via vs versus main key major current recent latest find identify
determine research report describe explain give list provide state including include support claims
sources source next last year years months month quarter""".split())


def norm(text: str) -> str:
    """Lowercase, straighten quotes/dashes, collapse whitespace."""
    text = (text or "").lower()
    text = text.translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                                         " ": " ", " ": " "}))
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return _WORD.findall(norm(text))


def content_terms(text: str) -> list[str]:
    """Distinct informative terms, in order of first appearance."""
    seen, out = set(), []
    for t in tokens(text):
        t = t.strip(".-'")
        if len(t) < 2 or t in _STOP or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def objective_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def overlap(a: str, b: str) -> float:
    """Jaccard overlap of content terms; a cheap lexical similarity in [0, 1]."""
    ta, tb = set(content_terms(a)), set(content_terms(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_MONTHS = frozenset("january february march april may june july august september october november december "
                    "jan feb mar apr jun jul aug sep sept oct nov dec".split())
_TABLE_GAP = re.compile(r"(?:\|\s*){2,}")


def clean_page_text(text: str) -> str:
    """Collapse empty table cells and blank runs so the character budget buys content, not markup."""
    lines = []
    for line in (text or "").splitlines():
        line = _TABLE_GAP.sub(" | ", line).strip(" |\t")
        line = re.sub(r"[ \t]{2,}", " ", line)
        if line and not re.fullmatch(r"[\-|: ]+", line):
            lines.append(line)
    return "\n".join(lines)


def _is_heading(line: str) -> bool:
    return len(line) <= 60 and not line.endswith((".", ":", ";", ",")) and not line.startswith(("-", "|", "*"))


def _windows(text: str, size: int = 600) -> list[str]:
    """Split into ~`size`-character windows on line boundaries, keeping a heading with what follows it."""
    out: list[str] = []
    buf: list[str] = []
    used = 0

    def flush():
        nonlocal buf, used
        if buf:
            out.append("\n".join(buf))
        buf, used = [], 0

    for line in text.splitlines():
        while len(line) > size * 1.4:      # one huge paragraph: cut near a sentence end
            cut = line.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 3 else size
            flush()
            out.append(line[:cut])
            line = line[cut:].lstrip()
        if buf and (used + len(line) > size or (_is_heading(line) and used > size // 3)):
            carry = []
            if not _is_heading(line) and buf and _is_heading(buf[-1]) and len(buf) > 1:
                carry = [buf.pop()]        # do not leave a heading stranded at the end of a window
            flush()
            buf, used = carry, sum(len(c) for c in carry)
        buf.append(line)
        used += len(line) + 1
    flush()
    return out


def select_passages(text: str, focus: str, max_chars: int) -> str:
    """Pick the parts of a page most related to `focus`, keeping original order.

    Long filings and articles do not fit a small context window, and prompt tokens are the main
    latency cost on a local model, so the extractor is shown a relevance-selected excerpt.
    Scoring is lexical: rarer focus terms count more, adjacent focus terms appearing together
    ("data center") count extra, and calendar words/small numbers are ignored because they match
    every table header in a financial document.
    """
    text = clean_page_text(text)
    if len(text) <= max_chars:
        return text
    windows = _windows(text)
    terms = [t for t in content_terms(focus) if t not in _MONTHS and not (t.isdigit() and len(t) < 4)]
    if not terms or not windows:
        return text[:max_chars]
    ordered = [t.strip(".-'") for t in tokens(focus)]
    phrases = {f"{a} {b}" for a, b in zip(ordered, ordered[1:]) if a in terms and b in terms}
    wnorm = [norm(w) for w in windows]
    wtoks = [set(t.strip(".-'") for t in tokens(w)) for w in windows]
    n = len(windows)
    idf = {t: math.log(1 + n / (1 + sum(1 for s in wtoks if t in s))) for t in terms}
    scored = []
    for i, w in enumerate(windows):
        s = sum(idf[t] * (0.5 if t.isdigit() else 1.0) for t in terms if t in wtoks[i])
        s += sum(1.5 for ph in phrases if ph in wnorm[i])
        if s > 0 and re.search(r"\d", w):
            s *= 1.15  # figures matter in financial research
        s /= 1 + max(0, len(w) - 700) / 1400      # do not let one oversized window win on bulk
        if i == 0:
            s += 0.5   # the lead usually says what the document is
        scored.append((s, i))
    chosen, used = set(), 0
    for s, i in sorted(scored, key=lambda x: (-x[0], x[1])):
        if s <= 0 and chosen:
            break
        if used + len(windows[i]) > max_chars:
            continue
        chosen.add(i)
        used += len(windows[i]) + 7
    if not chosen:
        return text[:max_chars]
    out, prev = [], None
    for i in sorted(chosen):
        if prev is not None and i != prev + 1:
            out.append("[...]")
        out.append(windows[i])
        prev = i
    return "\n".join(out)


_KEY_FIGURE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:%|percent|billion|million|"
                         r"trillion|thousand|bn\b|mn\b|bps|basis points)|\d[\d,]*\.\d+", re.I)


def key_figures(text: str) -> list[str]:
    """Substantive figures in a claim: money, percentages, magnitudes, decimals. Dates, years and bare
    counts are left out, because a claim may restate its period ("fiscal 2025") from context."""
    out = []
    for m in _KEY_FIGURE.finditer(text or ""):
        out += numbers_in(re.match(r"\$?\s?[\d,.]+", m.group(0)).group(0).replace(" ", "") + "%")
    return list(dict.fromkeys(out))


def number_lines(excerpt: str, max_len: int = 320) -> list[str]:
    """Split an excerpt into citable lines (long paragraphs are cut at sentence ends).

    PDF text arrives hard-wrapped mid-sentence, so a line that does not end a sentence is joined
    with a following line that starts in lower case before the lines are numbered."""
    merged: list[str] = []
    for line in excerpt.splitlines():
        line = line.strip()
        if not line:
            continue
        if (merged and merged[-1] != "[...]" and line != "[...]" and line[0].islower() and "|" not in line
                and not merged[-1].endswith((".", "!", "?", ":", ";")) and len(merged[-1]) + len(line) < max_len):
            merged[-1] += " " + line
        else:
            merged.append(line)
    out: list[str] = []
    for line in merged:
        if line == "[...]":
            continue
        while len(line) > max_len:
            cut = line.rfind(". ", 0, max_len)
            cut = cut + 1 if cut > max_len // 3 else max_len
            out.append(line[:cut].strip())
            line = line[cut:].strip()
        if line:
            out.append(line)
    return out


def quote_in_text(quote: str, text: str) -> bool:
    """True if `quote` really occurs in `text` (exactly, or with small whitespace/markup drift).

    Used to reject findings whose supporting quote the model invented.
    """
    q, t = norm(quote).strip(" .\"'"), norm(text)
    if len(q) < 8:
        return False
    if q in t:
        return True
    qt = tokens(q)
    if len(qt) < 5:
        return False
    tt = tokens(t)
    grams = {tuple(tt[i:i + 3]) for i in range(len(tt) - 2)}
    qgrams = [tuple(qt[i:i + 3]) for i in range(len(qt) - 2)]
    hit = sum(1 for g in qgrams if g in grams)
    return hit / len(qgrams) >= 0.85


_NUM = re.compile(r"(?<![A-Za-z0-9])\$?\d[\d,]*(?:\.\d+)?%?")


def numbers_in(text: str) -> list[str]:
    """Normalised numeric tokens ('$115.2 billion' -> '115.2', '12%' -> '12', '1,000' -> '1000').

    Source ids like [S3] and bare small ordinals are skipped.
    """
    text = re.sub(r"\[[SF]\d+(?:\s*,\s*[SF]\d+)*\]", " ", text or "")
    out = []
    for m in _NUM.finditer(text):
        raw = m.group(0)
        n = raw.replace("$", "").replace(",", "").rstrip("%").rstrip(".")
        if not n or not re.search(r"\d", n):
            continue
        if "." in n:
            n = n.rstrip("0").rstrip(".") or "0"
        if len(n) == 1 and "%" not in raw and "$" not in raw:
            continue  # "3 factors", "2 sources": not a claim about the world
        out.append(n)
    return out
