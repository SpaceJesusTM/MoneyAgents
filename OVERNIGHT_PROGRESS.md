# Overnight Progress

Session started 2026-10-10 ~23:40 local. Branch `3-prototype-webswarm-subagents`. Nothing pushed.

## Current status

- **Stage:** D (baseline benchmark running), with stage E code (optimization arms) written and unit-tested.
- **Last verified working command:** `.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q` (99 passed)
- **Last successful real-model + live-web runs:** ATOM (54 s, correct), WIDE on the NVIDIA question (579 s, 10 agents, 6 cited pages), DEEP (365 s, investigate / verify / re-investigate).
- **Baseline frozen?** yes: commit `6458038`, local tag `webswarm-baseline-v1`, config `webswarm_baseline/configs/baseline.json`.
  Code added after the freeze is opt-in (`extract_mode=lines`) or logging-only; defaults are unchanged.

## Completed

- [x] Read the three project docs, `CLAUDEPROMPT.md`, and the existing prototype
- [x] Read the WebSwarm paper and its reference code; read the Jev announcement, docs and REST contract
- [x] Preflight: Ollama 0.40.0, `qwen3.5:4b-q4_K_M` installed, 42 GB free disk, no API keys in the environment
- [x] Baseline package `webswarm_baseline/` (ATOM, WIDE, DEEP, ENTITY_COLLECT, incremental collection, budgets, traces)
- [x] Keyless live web search and guarded page fetching, PDF reading, record/replay cassettes
- [x] Tests: 99 passing (deterministic helpers, orchestration with a scripted model, Jev contract, deciders, grader)
- [x] Live ATOM, WIDE and DEEP runs; three rounds of fixes from what they showed
- [x] Baseline frozen (commit + tag)
- [x] Jev REST adapter + contract tests against a local stub + labeled mock
- [x] Local optimization code: rules decider, local typed-decision backend (logprobs), finish-first scheduler, line-reference extraction, web probing, experience sharing
- [x] Benchmark suite (9 tasks), grader, comparison and decision-ceiling tooling
- [ ] Baseline benchmark (running)
- [ ] Live smoke test of each optimization arm
- [ ] Comparison benchmark (baseline vs arms, interleaved)
- [ ] `BASELINE_RESULTS.md`, `OPTIMIZATION_RESULTS.md`, final handoff

## Architecture decisions so far (details will go in DESIGN_DECISIONS.md)

1. **New package `webswarm_baseline/`**; `one_shot_webswarm_prototype/` is untouched.
2. **One LangGraph lifecycle for every agent node** (`route -> atom` or `route -> plan -> dispatch -> collect -> review -> synthesize`). Each node runs it in its own thread; `dispatch` starts child threads running the same graph, which is the recursion.
3. **Incremental consumption is our extension, not WebSwarm's.** The reference code (`webswarm/verbs/wide_agent/dispatch.py`) runs a batch in a thread pool and returns to the manager only when the whole batch is done. Here `collect` returns on the first arrival (`review_policy=incremental`); `review_policy=batch` reproduces the reference behaviour for comparison.
4. **Bounded decisions are separated from generative work** behind a `Decider` interface (route, next atom action, review, verify-or-not, redundancy), so Jev, a small local model, or rules can replace the main model for those without touching research code.
5. **Evidence is checked by code, not by the model.** A finding is stored only if its supporting quote really occurs in the retrieved page. The final answer is audited programmatically: citations must exist, and each figure is looked up in the cited source's text.
6. **Ollama native HTTP API**, thinking off, temperature 0, fixed seed, JSON-schema-constrained outputs with bounded string lengths.
7. **Record/replay with replayed latency** so experiment arms can share web responses without the cached arm looking faster.

## Measurements that shape the plan

| Fact (measured on this Mac) | Value | Consequence |
|---|---|---|
| 4B model generation speed | ~27 tok/s idle, ~18 tok/s under sustained load | output tokens are the largest cost |
| 4B model prompt ingestion | ~320 tok/s idle, ~190 tok/s under load | prompts kept short (page excerpt capped at 3200 chars) |
| Two concurrent requests to Ollama | no speedup (served one after the other) | model concurrency fixed at 1; only web I/O overlaps |
| Share of wall-clock spent in model calls, 14-agent run | ~100% (722 s of 722 s) | web latency is hidden by concurrency; only fewer/shorter model calls save time |
| Routing calls in that run | 14 calls, 41 s, ~6% of model time | faster routing alone cannot save much; routing *accuracy* decides how much work is spawned |
| Sustained-load slowdown (fanless laptop) | ~35% | wall-clock comparisons need token counts alongside, and interleaved run order |

## Results so far (live model + live web)

| Run | Outcome | Time | Notes |
|---|---|---|---|
| ATOM: NVIDIA FY2025 data-center revenue | **Correct**: $115.2B, +142%, cited to NVIDIA's CFO commentary PDF; 4/4 figures found in the cited source | 54 s | 8 model calls, 1 search, 2 pages |
| WIDE: NVIDIA data-center growth factors (first attempt, before prompt fixes) | Ran end to end but **poor**: the model over-decomposed (3 WIDE levels, 14 nodes) and invented over-specific sub-questions; 6 of 14 agents found nothing | 657 s to answer | 84 model calls, 7 failed (runaway JSON), 24 searches (several returning 0) |

## Problems found in live testing and what was done

| Problem | Fix | Test |
|---|---|---|
| Passage selection dropped the paragraph holding the answer (heading split from its text; table headers out-scored prose) | Heading-aware windows, phrase scoring, table cleanup, calendar words ignored | `test_select_passages_keeps_the_relevant_part_with_its_heading` |
| A page with no verifiable finding still became a citable source | Source is registered only once a quote-verified finding exists | `test_invented_quotes_are_dropped...` |
| 7 model calls failed: the model wrote a runaway "thought" until the token limit cut the JSON | Every free-text schema field has `maxLength` (enforced by Ollama's grammar) | `test_schema_strings_are_bounded` |
| Cancelled agents kept making model calls for ~65 s after the answer was ready | No model calls after cancellation; partial findings returned as-is | `test_cancelled_agents_make_no_further_model_calls` |
| Long keyword queries returned 0 results | One automatic retry with a simplified query; prompt asks for 4-9 plain keywords | `test_empty_search_is_retried_once_with_a_simpler_query` |
| Over-decomposition and invented specifics in sub-objectives | Routing and planning prompts rewritten with examples and "do not invent specifics" | live re-run in progress |

## Blockers and fallbacks

| Blocker | Workaround | Live-tested? | User action needed |
|---|---|---|---|
| No `TYPESAFE_API_KEY` (Jev) | Planned: real REST adapter + contract tests against a local stub + clearly labeled mock | not yet | Add key to `.env` to run the real service |
| Ollama serialises concurrent requests | Model concurrency left at 1 (not changing global Ollama settings) | measured | Optional: set `OLLAMA_NUM_PARALLEL` yourself to test parallel inference |

## Resources

- Models downloaded: `qwen3.5:2b-q4_K_M` (1.95 GB) for the small-decider experiment. 1 of 2 allowed.
- Python packages added to `.venv`: ddgs, trafilatura, pypdf, pytest (+ their dependencies), ~97 MB.
- Total new downloads so far: ~2.05 GB (target < 15 GB).
- Memory: 4B model uses 3.3 GB at 8K context; no swap pressure observed.

## Resume here

1. If the baseline benchmark did not finish: `.venv/bin/python -m experiments.bench.run_bench --name baseline_v1 --arms baseline --order arm` (it resumes; finished rows are skipped).
2. Smoke-test arms on one task: `.venv/bin/python -m experiments.bench.run_bench --name smoke --arms rules local_s1_4b lines_extract --tasks A1`.
3. Router agreement for the typed routers: `.venv/bin/python -m experiments.bench.eval_routing local_s1_4b local_s1_2b`.
4. Comparison: `.venv/bin/python -m experiments.bench.run_bench --name compare_v1 --arms baseline rules local_s1_4b lines_extract batch_review probing finish_first pdf_8mb`.
5. Tables: `.venv/bin/python -m experiments.bench.compare compare_v1` and `.venv/bin/python -m experiments.bench.decision_ceiling baseline_v1`.
6. Write `BASELINE_RESULTS.md` and `OPTIMIZATION_RESULTS.md` from the result files; copy representative runs to `examples/`.
