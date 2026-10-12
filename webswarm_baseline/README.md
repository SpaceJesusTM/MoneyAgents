# WebSwarm-inspired research baseline

A recursive multi-agent web research system that runs entirely on a local Ollama model. Given a
research question it searches the live web, reads pages, extracts quote-backed findings, delegates
sub-questions to child agents, and writes a cited answer.

It is **inspired by** WebSwarm (Song et al., 2026, [arXiv:2607.08662](https://arxiv.org/abs/2607.08662),
[code](https://github.com/songxiaoshuai/WebSwarm)). It is not a reproduction, and none of the
paper's benchmark results apply to it. [What differs from the paper](#what-differs-from-the-paper)
lists the differences.

The earlier `one_shot_webswarm_prototype/` is untouched; this package does not import it.

## Setup

```bash
# from the repository root
python3 -m venv .venv                       # skip if .venv already exists
.venv/bin/pip install -r requirements.txt   # langgraph, pydantic, requests (already in the repo)
.venv/bin/pip install -r webswarm_baseline/requirements.txt   # ddgs, trafilatura, pypdf, pytest

ollama serve                                # if it is not already running
ollama pull qwen3.5:4b-q4_K_M               # 3.3 GB, the model the baseline is frozen on
```

No API keys are needed. Search uses the keyless `ddgs` metasearch package.

## Run

```bash
# a live research question (real model, real web)
.venv/bin/python -m webswarm_baseline.run "What was NVIDIA's data center revenue for fiscal year 2025?"

# the default question (NVIDIA data-center growth factors), with a tighter tree
.venv/bin/python -m webswarm_baseline.run --set budgets.max_nodes=6

# plumbing check with a SCRIPTED model and canned pages: no Ollama, no network, proves nothing about quality
.venv/bin/python -m webswarm_baseline.run --mock

# tests (scripted model; about 20 seconds)
.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q
```

Each run prints a live log and a report, and saves `runs/<timestamp>_<config>_<slug>/` with:

| File | Contents |
|---|---|
| `report.md` | answer, cited sources with URLs, grounding audit, agent tree, statistics |
| `run.json` | config, manifest (git commit, model digest, Ollama version), every node, every source and finding |
| `trace.jsonl` | one timestamped event per decision, model call, web call, finding, and child result |

Useful flags: `--set key=value` (any config field, e.g. `--set web_probing=true`,
`--set review_policy=batch`, `--set budgets.max_seconds=600`), `--config file.json`, `--verbose`,
`--quiet`, `--out DIR`.

## How it works

Every agent node runs the same LangGraph lifecycle in its own thread:

```
START -> route -+-> atom ------------------------------------------> END
                +-> plan -> dispatch -> collect -> review -+-> dispatch   (follow-up work)
                                          ^----------------+-> collect    (keep waiting)
                                                           +-> synthesize -> END
```

`dispatch` starts child threads that run this same graph, which is the recursion. A child pushes
its id onto its parent's queue when it finishes.

| Mode | What it does here |
|---|---|
| `ATOM` | A ReAct-style loop: the model picks `search`, `read` or `finish`; pages are fetched and a second call extracts findings, each with a supporting quote; a final call writes a cited answer. |
| `WIDE` | Plans independent sub-objectives, runs them concurrently, reviews results **as they arrive**, may add follow-up sub-objectives the evidence points to, then synthesizes. Children choose their own mode, so depth and breadth can nest. |
| `DEEP` | One step at a time: send a researcher, read the result, decide the next step from that evidence. Before finishing it sends an **independent verifier** that is given only the claim, not the evidence behind it, and returns `survived / weakened / refuted / unverifiable`. |
| `ENTITY_COLLECT` | Three discovery paths with different search angles, merged and de-duplicated by code; names found by only one path are sent to a verifier. |

Other mechanisms, all switchable in the config:

| Mechanism | Config | Default |
|---|---|---|
| Review as results arrive vs. wait for the whole batch | `review_policy` = `incremental` / `batch` | `incremental` |
| Web probing before WIDE planning | `web_probing` | off |
| Sibling experience sharing (scouts first, then tips to the rest) | `experience_sharing` | off |
| Who makes bounded decisions | `decider` = `generative` / `rules` / `local_s1` / `jev` / `mock_jev` | `generative` |
| Order of queued model calls | `scheduler` = `fifo` / `finish_first` | `fifo` |
| DEEP verification | `verify_policy` = `always` / `decider` / `never` | `always` |

### Evidence is checked by code, not by the model

- A finding is stored only if its supporting quote actually occurs in the retrieved page text.
  Rejected findings are logged, and a page that yields no verified finding never becomes a source.
- The model only ever writes source ids such as `[S3]`. URLs in the report come from the evidence
  store. Citations to ids that do not exist are removed and counted.
- The final answer gets a programmatic audit: every figure is looked up in the text of the source
  cited in its sentence, then in all retrieved text, and is otherwise reported as ungrounded.
- If no page yields evidence, an agent may fall back to search-result snippets. Those sources are
  marked "search snippet only; page not read" in the report.

### Reliability guards (opt-in)

Added after the baseline was frozen, in response to failures it showed. All are off in
`configs/baseline.json`, so the baseline behaves as it was measured; `configs/reliability_v1.json`
is the baseline with all of them on. They are deterministic code in `guards.py`, with no model call
except one retry of a synthesis that contradicts its figures.

| Switch | What it does | Failure it answers |
|---|---|---|
| `verify_guard` | A DEEP manager sends a verifier only a positive, checkable claim (clauses that report missing information or talk about "the findings" are removed; if nothing is left, no verifier is sent). A verdict needs cited evidence. An answer with unresolved steps is `partial` and never `high` confidence. | D1: "the findings do not contain capacity figures" came back `survived` |
| `claim_checks` | Each extracted claim is tied to its quote: a figure that is nowhere in the source rejects the finding, a trailing clause with a figure that is not next to the quote is cut, a GAAP / non-GAAP label must not contradict the passage (a label the passage does not show is removed). A written answer must keep each figure's period (quarter or full year) and basis; one retry, then the agent returns its extracted findings instead. | W1: non-GAAP 75.5% stored as GAAP, and then a quarterly figure written up as the fiscal-year one; A2: an invented figure attached to a real quote |
| `numeric_guard` | For "compare A, B and C" objectives the compared figures are picked out and sorted by code and given to the synthesis. An ordering statement that contradicts the figures triggers one retry; if it persists, a labelled computed correction is appended. Mixed bases or periods are flagged. | W2: $350 billion ranked above $638 billion |
| `oversize_policy=fail`, `max_pdf_bytes`, `pdf_max_pages` | A response cut off by the size or time limit is an explicit error (of the form "too large: N bytes declared, limit M; nothing parsed") and nothing from it is parsed. PDFs get their own, larger, still bounded limit. A PDF read only in part says so. | A2: a 4.9 MB filing truncated at 3 MB and reported as "no extractable text" |

```bash
.venv/bin/python -m webswarm_baseline.run "your question" --config webswarm_baseline/configs/reliability_v1.json
.venv/bin/python -m webswarm_baseline.run "your question" --set numeric_guard=true     # one guard at a time
```

What was verified, and what these guards do not catch: `../RELIABILITY_IMPROVEMENTS.md`.

### When search fails

A search that gets no valid answer (timeout, network error, rate limit, provider or internal error)
is a different thing from a search that is answered with nothing, and the code keeps them apart:

- It is **never written to a recording**. Empty result lists, HTTP refusals and oversized pages are
  answers and are recorded; timeouts and dropped connections are not.
- The provider's "no results" is trusted only if a control query that always has results is being
  answered too (`ddgs` says "no results" when its engines serve rate-limit pages).
- Each search has a deadline and a bounded number of tries; after several failures in a row search
  is treated as unavailable for a while, so a dead provider costs seconds, not minutes per call.
- An agent whose searches failed reports a retrieval failure, not "nothing found", and does not
  reword its query. Each run's statistics say how much of its evidence was replayed, fetched live,
  or not answered (`web_provenance`).
- Without an IPv6 route, names are resolved over IPv4 only, and `ddgs` is sent through an in-process
  IPv4-only tunnel. (On the development machine the resolver dropped IPv6 lookups, which cost
  2-5 s per connection and timed out every search.)

```bash
.venv/bin/python -m webswarm_baseline.netcheck     # which of: local network, provider outage, rate limiting, our code
```

### Evidence checks for identification questions (opt-in, prototype)

`configs/evidence_v1.json` is `reliability_v1` plus two switches, added after looking at why two
"which company ...?" questions were answered from a single page reporting a deal or a plan:

| Switch | What it does |
|---|---|
| `identify_guard` | "Which X ..., and <something that depends on it>?" is worked as DEEP whatever the router said, so the first answer is checked before the second part builds on it |
| `support_check` | The entity named in answer to "which / who" must be named by quoted passages from two sites, and not only by reports of a deal or plan. Otherwise: low confidence, a stated gap, and a DEEP manager verifies that step first. No extra model call for a single lookup |

Results and limits: `../NEXT_PASS_RESULTS.md`.

### Limits

Hard limits live in `config.Budgets`: tree depth, node count, children per batch, follow-ups,
model calls, web calls, wall-clock seconds, steps per ATOM, rounds per DEEP, retries. When a limit
is hit the affected agents stop and return what they have, the trace records which limit, and the
root still writes an answer (two model calls are held in reserve for that). At 70% of the time
budget agents stop gathering and write up, so a slow run ends with a synthesis of every branch
rather than a cut-off.

### Web safety

`web.py` fetches only `http`/`https` URLs on default ports, resolves the host and refuses
non-public addresses (loopback, private, link-local, metadata endpoints), re-checks on every
redirect hop, caps response size and time, honours `robots.txt`, and identifies itself with an
honest User-Agent. Agents can only open URLs that came back from a search, never a URL written in
a page. Page text reaches the model inside `<<<UNTRUSTED ... >>>` markers with an instruction to
treat it as data. The model has no tools beyond search, read and finish.

## Files

| File | Role |
|---|---|
| `swarm.py` | The engine: LangGraph lifecycle, the four modes, dispatch/collect/review, cancellation |
| `decisions.py` | `Decider` interface for bounded decisions, and the baseline generative decider |
| `prompts.py` | Every prompt and JSON schema |
| `web.py` | Search provider, guarded fetch, HTML/PDF text extraction, record/replay cassettes |
| `evidence.py` | Source and finding store, quote verification, citation handling, answer audit |
| `textutil.py` | Passage selection, quote matching, number extraction |
| `llm.py` | Ollama client (native HTTP API) and the scripted stand-in used by tests |
| `runtime.py` | Trace, budgets, and the model-slot gate with its scheduling policies |
| `report.py` | Statistics, tree rendering, live log, saved artifacts |
| `run.py` | CLI and the `execute()` function used by tests and benchmarks |
| `mock.py` | Scripted model and canned pages for offline tests |
| `configs/baseline.json` | The frozen baseline configuration |
| `guards.py` | Deterministic reliability checks (opt-in): unverifiable claims, figures and accounting basis, rankings |
| `configs/reliability_v1.json` | The baseline plus the reliability guards |
| `configs/reliability_v1_9b.json` | The same with the research model changed to `qwen3.5:9b-q4_K_M` (model comparison) |
| `configs/evidence_v1.json` | `reliability_v1` plus the evidence checks for identification questions |
| `netcheck.py` | Read-only diagnosis of why web search is failing |

## What differs from the paper

| Topic | WebSwarm (paper / reference code) | Here |
|---|---|---|
| Backbone | GLM-4.5 and other large hosted models, 128K-256K context, up to 200 steps per agent | A 4B local model, 8K context, 4 tool actions per ATOM |
| Tools | Serper search, Jina Reader with a model-written page summary | Keyless `ddgs` search, direct fetch, quote-verified extraction |
| Root | A single-layer planner that calls one verb at a time | The root is an ordinary node that routes itself like any other |
| Manager and child results | A WIDE batch runs in a thread pool and returns to the manager only when the whole batch is done | **Extension:** the manager reviews results as they arrive and can add work or finish early (`review_policy=batch` restores the reference behaviour) |
| DEEP | Model-driven loop over `call_search_agent` / `call_verify_agent` | Same idea, with the harness forcing one verification before finishing |
| ENTITY_COLLECT | Schema inference, model-driven table merge, split-verify-merge | Three paths, merge by normalised name in code, verify single-path names |
| Web probing | A separate agent with its own search-and-read budget, before the first-layer WIDE | One search plus one model call over the result snippets, before any WIDE plan |
| Experience sharing | A model call summarises scout traces into tips | Tips are read from the scout traces by code (useful domains, sites that failed, a query that worked) |
| Model concurrency | Parallel API calls | One generation at a time: Ollama serialises requests on this machine, so only web I/O overlaps |
| Results | Benchmarked on BrowseComp-Plus, WideSearch, DeepWideSearch, GISA | Not run on any of those |

## Known limitations

- The 4B model is the limiting factor: it over-delegates, sometimes extracts a neighbouring figure
  instead of the one asked for, and writes weak follow-up objectives. See `../BASELINE_RESULTS.md`.
- All model calls share one slot, so a run's wall-clock time is essentially its total model time.
- Quote verification proves that a quote is on the page, not that the claim follows from it.
- The number audit matches digits, so it cannot tell that a correct number is attached to the
  wrong metric. (`claim_checks` narrows this for GAAP / non-GAAP labels and for figures that are
  not in the source at all; it still cannot tell revenue from operating income.)
- Entity merging is by normalised name; an acronym and its long form are listed separately.
- The SSRF guard validates before connecting but does not pin the resolved address, so a
  DNS-rebinding attacker could in principle still redirect a request.
- Many financial sites block automated readers (HTTP 403). Those failures are reported, not hidden.
