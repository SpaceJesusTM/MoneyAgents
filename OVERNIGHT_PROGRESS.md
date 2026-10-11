# Overnight Progress

Session: 2026-10-10 23:40 to 2026-10-11 07:30 local. Branch `3-prototype-webswarm-subagents`.
All work is committed locally. Nothing was pushed.

## Current status

- **Stage:** F (compare and hand off). All planned stages are done.
- **Last verified working command:** `.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q` (109 passed)
- **Last successful real-model + live-web run:** 07:19, final sanity run. 126 live runs across the night (120 benchmark runs, 6 earlier validation runs).
- **Baseline frozen?** yes: commit `6458038`, local tag `webswarm-baseline-v1`, config `webswarm_baseline/configs/baseline.json`.
  Everything added after the freeze is opt-in; the baseline's defaults and behaviour are unchanged
  (its three benchmark passes produced identical work on 7 of 9 tasks and identical quality on all 9).

## Morning deliverables

| # | Deliverable | Where | Status |
|---|---|---|---|
| 1 | Runnable WebSwarm-inspired baseline | `webswarm_baseline/` | Live-validated |
| 2 | Configurable optimized implementation | same engine, switches in `SwarmConfig`; arms in `experiments/bench/arms.json` | Live-validated |
| 3 | Jev integration attempt | `experiments/deciders/jev.py`, `experiments/tests/test_jev_contract.py` | **Stub-tested only.** No key; not run against the real service |
| 4 | Real local optimization | rules decider, typed decisions from a 2B model, finish-first scheduling, line extraction, citation retry, probing | Live-benchmarked |
| 5 | Baseline vs optimized results | `BASELINE_RESULTS.md`, `OPTIMIZATION_RESULTS.md` | Done |
| 6 | Saved traces and examples | `examples/` (10 runs), `experiments/results/*/results.jsonl` | Done |
| 7 | Setup and run instructions | `webswarm_baseline/README.md`, `experiments/README.md`, root `README.md` | Done |
| 8 | Architecture with references | `webswarm_baseline/README.md`, `DESIGN_DECISIONS.md` | Done |
| 9 | Strengths, weaknesses, manual steps | this file, plus the two results files | Done |

## Headline results

Baseline, 9 live tasks: 2,559 s in total, 307 model calls, mean automatic quality 0.80. By reading:
4 answers acceptable, 3 partly right, 2 wrong or unhelpful.

| Arm | Time to answer vs baseline | Mean quality (arm / baseline) | Note |
|---|---:|---:|---|
| Rules decider + line extraction + citation retry | 0.38 | 0.81 / 0.80 | fastest; loses 2 gold facts, gains 2 |
| Typed decisions from a 2B model | 0.48 | 0.80 / 0.80 | loses 1 (a precision loss), gains 1 |
| Typed decisions from the same 4B model | 0.76 | 0.79 / 0.80 | no faster per decision |
| Finish-first scheduling | 1.06 | 0.91 / 0.88 | same total; first result 16-54% sooner |
| Batch review instead of incremental | 0.92 | 0.82 / 0.84 | incremental review did not pay on one model slot |
| Web probing | 0.64 | 0.81 / 0.84 | fewer agents and 25% fewer web calls, coverage cost |

No arm passes the strict quality rule set in advance (no gold fact lost), so these are trades, not
proven quality-preserving speedups. Details and caveats: `OPTIMIZATION_RESULTS.md`.

The finding that matters most: bounded decisions are 18% of the baseline's model time, so a faster
decider (Jev included) can save at most that. What the decisions *are* moved total time by 2x to 3x.

## What was validated, and how

| Component | Status |
|---|---|
| ATOM, WIDE, DEEP, ENTITY_COLLECT; recursion to depth 2; follow-ups; verification | Live (real model, live web) |
| Incremental and batch review; finish-first scheduler; web probing; line extraction; citation retry | Live, benchmarked |
| Rules decider; typed-decision decider with the 4B and 2B models | Live, benchmarked |
| Sibling experience sharing | One live run (works); not benchmarked |
| Record/replay of web responses | Live |
| Budgets: node limit, wrap-up deadline | Hit live and handled |
| Budgets: model-call, web-call, depth, hard deadline | Scripted-model tests only |
| SSRF guard | Unit tests with literal addresses. No hostile page was encountered |
| Jev REST adapter | **Local stub only** (12 contract tests over real HTTP) |
| Mock Jev | Plumbing only; one live run to confirm wiring; never benchmarked |

## Blockers and fallbacks

| Blocker | Workaround | Live-tested? | User action needed |
|---|---|---|---|
| No `TYPESAFE_API_KEY`; Jev is paid and receives research text | REST adapter from public docs, contract tests against a local stub, labeled mock, and a local typed-decision backend answering the same questions | Adapter: no. Local backend: yes | Get a key at https://console.typesafe.ai/keys, put `TYPESAFE_API_KEY=...` in `.env`, then run the command under "Next actions" |
| Ollama runs one request at a time on this machine | Model concurrency fixed at 1; only web I/O overlaps | Measured | Optional: set `OLLAMA_NUM_PARALLEL=2` yourself to test parallel inference (a global setting, so I left it alone) |
| Laptop slows by about a third when warm | Arms interleaved per task; token-based time measure reported alongside wall-clock | Measured | None |
| Finance sites block automated readers (26 of 58 fetches failed in the baseline) | Failures are reported in each answer; snippet fallback is marked as such | Live | Optional: add a keyed search or reader API as another provider in `web.py` |
| Apple's 4.9 MB PDF exceeded the 3 MB page cap | Fetch works with `max_page_bytes=8000000`; end-to-end re-run was inconclusive | Partly | Decide whether to raise the default cap |

## Known weaknesses of what was built

- The 4B model is the quality limit: wrong ranking from right figures (W2), wrong supplier from recent news (D1), one-source wrong answer (D2).
- A DEEP verifier will "pass" a statement about missing data. The reference WebSwarm code refuses such claims; this one does not yet.
- Quote and figure checks prove a number is on the page, not that it belongs to the metric named.
- The grader is pattern matching over 9 tasks with one run per arm. It finds 2x effects and broken arms; it cannot rank close ones.
- Routing prompts and rule patterns were tuned on the same 32 labelled objectives they are scored on.
- Recorded web responses stay local (git-ignored: third-party text). A fresh clone re-records from the live web and will get different answers.

## Resources

- Models downloaded: `qwen3.5:2b-q4_K_M` (1.95 GB). 1 of the 2 allowed; no model above 4.2B parameters was used.
- Python packages added to `.venv`: ddgs, trafilatura, pypdf, pytest and their dependencies, about 97 MB (`webswarm_baseline/requirements.txt`).
- Total new downloads: about 2.05 GB (target under 15 GB).
- Disk written by the project: about 11 MB (0.5 MB examples, 4.3 MB recorded web responses, 5.7 MB results and traces).
- Memory: 3.3 GB (4B) plus 1.8 GB (2B) loaded together; no swap pressure observed. Both models were unloaded at the end.
- No paid API was called. No trade or brokerage action exists anywhere in the code.

## Commits (local only)

`git log --oneline 14f89ba..HEAD` lists them. The frozen baseline is the tag `webswarm-baseline-v1`.
`one_shot_webswarm_prototype/`, `src/`, `docs/`, `CLAUDEPROMPT.md`, `requirements.txt` and `.env.example`
have no changes (`git diff 14f89ba -- <those paths>` is empty). The root `README.md` gained one
section of links.

## Next actions

1. Read `OPTIMIZATION_RESULTS.md` (bottom line first), then two or three reports in `examples/`.
2. To run Jev for real, with the key exported:
   `.venv/bin/python -m experiments.bench.run_bench --name jev_v1 --arms baseline local_s1_2b jev`
   then `.venv/bin/python -m experiments.bench.compare jev_v1`.
3. Try the untested combination that the results point to:
   `.venv/bin/python -m webswarm_baseline.run "your question" --set decider=local_s1 --set decider_options.model=qwen3.5:2b-q4_K_M --set verify_policy=decider --set cite_retry=true --set scheduler=finish_first`
4. Engineering, in order of value: stop verifying non-existence statements; make the rules decider ask the model for a new query after an empty search; raise the page cap; merge entity aliases.
5. If any of this is going to GitHub: review the diff, then push yourself. I did not push.

## Timeline

| Time | Milestone |
|---|---|
| 23:40 | Read docs, prototype, WebSwarm paper and code, Jev post and docs; preflight |
| 00:02 | First live ATOM run (wrong: passage selection dropped the answer), fixed, correct at 54 s |
| 00:17 | First live multi-agent run: mechanics work, decomposition poor; three rounds of fixes |
| 00:55 | Baseline frozen and tagged |
| 01:00 | Baseline benchmark, 9 tasks |
| 01:57 | Round 1: baseline, rules, typed decisions (4B, 2B) |
| 03:58 | Round 2: fixed rules, line extraction, batch review, probing, finish-first |
| 06:30 | Round 3: two candidate configurations; live sanity runs |
| 07:25 | Reports finalized, models unloaded |
