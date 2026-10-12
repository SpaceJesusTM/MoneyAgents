# Optimization experiments

Everything here is opt-in. The baseline in `../webswarm_baseline/` never imports this directory
unless a config asks for a non-default decider.

## What can be switched

| Switch | Values | What changes |
|---|---|---|
| `decider` | `generative` (baseline), `rules`, `local_s1`, `jev`, `mock_jev` | who makes bounded decisions: mode, next ATOM action, review verdict, verify-or-not, redundancy |
| `verify_policy` | `always` (baseline), `decider`, `never` | whether DEEP always sends a verifier or lets the decider judge |
| `extract_mode` | `quote` (baseline), `lines` | copy a supporting quote, or cite a numbered line |
| `cite_retry` | `false` (baseline), `true` | if a synthesis comes back with no citations, ask once more, then fall back to the cited sub-results |
| `scheduler` | `fifo` (baseline), `finish_first` | which queued model call gets the single model slot next |
| `review_policy` | `incremental` (baseline), `batch` | review each arriving result, or wait for the whole batch |
| `web_probing` | `false` (baseline), `true` | probe how the information is organised before WIDE planning |
| `experience_sharing` | `false` (baseline), `true` | scouts first, then pass tips to remaining siblings |
| `verify_guard`, `claim_checks`, `numeric_guard` | `false` (baseline), `true` | reliability guards, not optimizations: see `../webswarm_baseline/README.md` and `../RELIABILITY_IMPROVEMENTS.md` |
| `oversize_policy`, `max_pdf_bytes` | `truncate` / `0` (baseline), `fail` / bytes | explicit failure for responses over the size limit; separate bounded limit for PDFs |

Try any of them on one question:

```bash
.venv/bin/python -m webswarm_baseline.run "your question" --set decider=rules --set verify_policy=decider
.venv/bin/python -m webswarm_baseline.run "your question" --set decider=local_s1 --set verify_policy=decider
.venv/bin/python -m webswarm_baseline.run "your question" --set extract_mode=lines --set scheduler=finish_first
```

## Deciders

| Name | What it is | Validation status |
|---|---|---|
| `rules` | Regex and counting heuristics for every bounded decision; no model call for control | Live-tested with the real model and web |
| `local_s1` | Each decision is a typed question (`Choice`/`Noul`) answered by a local Ollama model with **one output token**; probabilities come from that token's logprobs. Option `model` picks the model (default: the main 4B model; `qwen3.5:2b-q4_K_M` for the small one). | Live-tested with the real model and web |
| `jev` | The same typed questions sent to TypeSafe's Jev over its REST API | **Implemented, tested only against a local stub. Never run against the real service.** |
| `mock_jev` | An in-process fake that speaks the Jev wire format and answers with word overlap | Plumbing only. Its decisions and timings mean nothing about Jev. |

### Running Jev for real

Needs an account and a key from https://console.typesafe.ai/keys. Jev is a paid API
($0.042 per million input tokens at the time of writing), and the text of research objectives,
search-result snippets and finding summaries would be sent to it.

```bash
echo 'TYPESAFE_API_KEY=...' >> .env          # .env is git-ignored; never commit the key
set -a; source .env; set +a
.venv/bin/python -m webswarm_baseline.run "your question" \
    --set decider=jev --set verify_policy=decider --set decider_options.allow_external_calls=true
```

The adapter refuses to start unless the key is present **and** `allow_external_calls` is true. To
benchmark it, add an arm to `bench/arms.json` with those three overrides and run it alongside
`baseline` and `local_s1_4b`; the decision events in the traces will then carry real Jev latencies.

What the stub tests cover (`tests/test_jev_contract.py`): the request body and `Authorization`
header match the documentation; the documented example response parses; 401 and 422 are surfaced
without retries; 429 and 529 are retried with backoff; the key never appears in traces or errors;
a full (scripted) research run completes with every decision going through the HTTP adapter.

What they cannot cover: whether the real service accepts these requests, how fast it answers, or
how good its decisions are.

## Benchmark

```bash
# the baseline alone (records web responses to bench/cassettes/, git-ignored)
.venv/bin/python -m experiments.bench.run_bench --name baseline_v1 --arms baseline --order arm

# arms interleaved per task (arm names are in bench/arms.json)
.venv/bin/python -m experiments.bench.run_bench --name my_compare \
    --arms baseline rules_plus local_s1_2b finish_first

# tables
.venv/bin/python -m experiments.bench.compare my_compare
.venv/bin/python -m experiments.bench.decision_ceiling baseline_v1     # how much any fast decider could save
.venv/bin/python -m experiments.bench.eval_routing                     # router agreement with intended modes
```

| File | Role |
|---|---|
| `bench/tasks.json` | 9 tasks: 2 ATOM, 2 WIDE, 2 DEEP, 2 mixed, 1 ENTITY_COLLECT; gold facts for the 7 stable ones |
| `bench/arms.json` | each arm = frozen baseline config + a few overrides |
| `bench/run_bench.py` | runner: per-task cassettes, interleaved order, resumable |
| `bench/grade.py` | automatic grading (v1): gold-fact recall, coverage, grounding. Unchanged; all recorded scores are v1 |
| `bench/grade_v2.py` | stricter grading (v2): no credit for "not found", for a figure under the wrong accounting basis, or for a ranking the figures contradict |
| `bench/regrade.py` | re-grades every recorded run with v2 into `results/regrade_v2/` without touching the recorded results |
| `bench/guard_replay.py` | replays the reliability guards over recorded runs: what each would have refused, rejected or flagged |
| `bench/heldout_tasks.json` | held-out set: 12 questions with gold facts and scoring rules fixed before any run (`run_bench --suite heldout_tasks.json`). Do not tune on it |
| `bench/model_table.py` | table for runs that differ only in the model, with evidence provenance and memory |
| `bench/memwatch.py` | samples swap, free memory, pageouts and the model runner's size during a run |
| `bench/compare.py` | per-arm, paired, and per-task tables |
| `bench/decision_ceiling.py` | splits baseline model time into generative vs bounded-decision work |
| `bench/eval_routing.py`, `bench/routing_cases.json` | router agreement on 32 labelled objectives |
| `results/<set>/results.jsonl` | one graded row per run (tracked); full traces under `results/<set>/runs/` (git-ignored) |

### How comparisons are kept fair

- Every arm is the frozen baseline config plus stated overrides; same model, seed, temperature 0, budgets.
- Web responses are shared through a per-task cassette. A replayed response is delayed by its
  recorded latency, so an arm that hits the cache is not faster for it.
- Arms are interleaved per task with rotating order, because this fanless laptop slows down by
  about a third under sustained load.
- Each row also records `ref_model_seconds`: prompt and output tokens divided by fixed reference
  speeds (300 and 25 tokens/s). It measures model work independent of how hot the machine was.
- The quality tolerance was fixed before any arm was compared (`bench/grade.py`): within 0.05 of
  the baseline's mean quality and no gold fact lost.

### Two graders

`grade.py` (v1) is what every table in `../OPTIMIZATION_RESULTS.md` uses, and it is unchanged. It
matches gold figures anywhere in the answer, so a right figure with a wrong label or a wrong ranking
scores well. `grade_v2.py` removes that credit (rules R1 to R4 in its docstring). New benchmark rows
carry both: the v1 fields as before, and a `v2` block. Recorded runs are re-graded into a separate
folder:

```bash
.venv/bin/python -m experiments.bench.regrade          # -> results/regrade_v2/summary.md
.venv/bin/python -m experiments.bench.guard_replay     # -> results/regrade_v2/guard_replay.md
```

### Limits of the grading

Grading is pattern matching and a number audit. It cannot recognise a correct paraphrase it has no
pattern for, and it cannot see a wrong claim sitting next to a right one. Tasks are few (9) and
each arm ran each task once or twice, so small differences are noise. Read the answers in
`results/<set>/runs/*/report.md` before trusting a close call.
