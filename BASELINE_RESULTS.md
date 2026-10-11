# Baseline results

Results for the frozen baseline: commit `6458038`, local tag `webswarm-baseline-v1`, config
`webswarm_baseline/configs/baseline.json`.

Everything in this file was measured with the **real local model and the live web** on
2026-10-11, on a MacBook Air M4 (24 GB), Ollama 0.40.0, `qwen3.5:4b-q4_K_M` (4.2B parameters,
Q4_K_M), thinking off, temperature 0, seed 7, 8K context, one model call at a time. Search was the
keyless `ddgs` metasearch. Nothing here comes from a mock.

Raw data: `experiments/results/baseline_v1/results.jsonl`. Six full runs (report, tree, trace) are
in `examples/`.

## Verdict

The baseline is a working, bounded, source-grounded recursive research system. It is **not yet a
trustworthy analyst**: on 9 tasks it produced 4 answers I would accept, 3 that are partly right,
and 2 that are wrong or unhelpful. The mechanics are sound (recursion, evidence flow, follow-ups,
verification, budgets, citations). The quality limits come from the 4B model and from what a
keyless search engine surfaces.

## Benchmark: 9 tasks, one run each

Automatic scores are explained in `experiments/bench/grade.py`. "Read" is my judgement after
reading each answer against the gold facts and the retrieved sources.

| Task | Question (short) | Time | Agents | Model calls | Web calls | Auto quality | Read |
|---|---|---:|---:|---:|---:|---:|---|
| A1 | NVIDIA FY2025 data-center revenue and growth | 42 s | 1 | 7 | 3 | 1.00 | **Correct.** $115.2B, +142%, cited to NVIDIA's own CFO commentary PDF. |
| A2 | Apple FY2024 services revenue | 38 s | 1 | 7 | 4 | 0.25 | **Failed, honestly.** Said the annual figure was not found. Also stated a Q4 figure ($23.1B) that is in no retrieved text; the audit flagged it. |
| W1 | Gross margins: NVIDIA, AMD, Intel | 388 s | 6 | 44 | 20 | 0.89 | **Partly right.** AMD 49% correct; NVIDIA 75.5% is the non-GAAP figure labelled GAAP; Intel not found and said so. |
| W2 | Revenue: Microsoft, Alphabet, Amazon | 154 s | 4 | 26 | 10 | 0.83 | **Figures right, conclusion wrong.** All three numbers correct, then the synthesis ranked Alphabet ($350B) above Amazon ($638B). |
| D1 | Which packaging supplier constrains NVIDIA, and how fast can it grow | 241 s | 5 | 31 | 15 | 0.67 | **Wrong emphasis.** Named Amkor (a July 2026 deal in the news) as the primary supplier. The retrieved sources themselves describe that deal as relief for TSMC's CoWoS bottleneck. No growth figure found, and it said so. |
| D2 | Who makes Apple's iPhone processors, and in which US state is it building fabs | 44 s | 1 | 7 | 4 | 0.75 | **Wrong.** Answered "Intel Foundry" from one page, with no verification. Arizona is right. |
| M1 | Factors affecting NVIDIA data-center revenue growth | 698 s | 11 | 75 | 31 | 0.80 | **Useful but thin on sources.** Covers pricing, demand, competition, supply with 6 cited pages; misses export controls and guidance; sources are analysis blogs, not filings. |
| M2 | Drivers and risks for AMD's data-center business | 703 s | 12 | 83 | 42 | 1.00 | **Useful.** Covers revenue, supply, competition, customers, tariffs; cites AMD's newsroom among others. Some claims rest on low-authority sites. |
| E1 | Which companies make HBM | 251 s | 5 | 27 | 19 | 1.00 | **Correct.** SK hynix, Samsung, Micron, each with support counts. Samsung appears twice ("Samsung" and "Samsung Electronics"). |

Totals: 2,559 s to answer all nine (42.6 min), 307 model calls, 197,439 prompt tokens, 28,336
output tokens, 148 web calls (searches plus page fetches). Mean automatic quality 0.80.

Time to first source-grounded evidence ranged from 23 s (single agent) to 119 s (12 agents).
Maximum tree depth reached was 2.

### What the automatic scores miss

The W2 ranking error and the W1 GAAP/non-GAAP mislabel both score well automatically, because the
grader matches figures and cannot check reasoning built on them. Automatic quality is a consistent
yardstick across arms. It is not a correctness guarantee.

## Where the time goes

Model calls took 2,499 s of the 2,559 s (97.7%). Web requests took 230 s in total but overlap with
model calls, so they add almost nothing to wall-clock time.

| Call kind | Calls | Seconds | Share of model time |
|---|---:|---:|---:|
| Extract findings from a page | 39 | 730 | 29.2% |
| ATOM step that wrote a search query | 82 | 432 | 17.3% |
| Write an agent's answer | 36 | 323 | 12.9% |
| ATOM step that chose a result to read | 59 | 291 | 11.6% |
| Extract from snippets (fallback) | 11 | 186 | 7.4% |
| Synthesis | 7 | 134 | 5.4% |
| Review that wrote follow-ups | 14 | 121 | 4.8% |
| Routing | 27 | 99 | 4.0% |
| DEEP step that wrote a question or claim | 8 | 45 | 1.8% |
| Review with no follow-up | 8 | 44 | 1.8% |
| Planning (WIDE, ENTITY_COLLECT) | 6 | 39 | 1.6% |
| ATOM step whose output was discarded and repaired | 5 | 33 | 1.3% |
| ATOM step that chose to finish | 5 | 22 | 0.9% |

Generation is the larger half: 1,419 s writing 28K output tokens against 890 s reading 197K prompt
tokens.

**Bounded decisions (routing, which result to read, finish, review with no follow-up) are 457 s,
18.3% of model time, across 99 decisions.** That is the most any faster decider could remove if it
made the same choices. Routing alone is 4.0%. See `OPTIMIZATION_RESULTS.md` for what this means
for Jev.

## Delegation behaviour

| Observation | Evidence |
|---|---|
| Evidence-driven follow-ups happen | 14 reviews asked for follow-up work and 7 follow-up agents were started (the rest hit the per-manager limit of 2). In M1 the root added "discounting percentages for H100/H200/B200" and "secondary market dynamics" after the pricing agent reported; in W1 it added "Retrieve Intel's GAAP gross margin" after the Intel agent came back empty. |
| Follow-ups are often re-tries, not new leads | The W1 follow-ups repeat the failed sub-objective in different words. The review prompt says not to do this; the 4B model does it anyway. |
| DEEP verification works when the claim is a statement | In M1 the DEEP child sent the claim "AMD holds an estimated 6 to 8 percent share..." to an independent verifier, which returned `refuted`. In D1 the model sent a non-claim ("The provided findings do not contain specific capacity figures...") and the verifier returned `survived`, which gave a muddled answer a "verified" label. WebSwarm's reference code refuses to verify non-existence claims; this baseline does not. Of the 3 verifiers that ran in the benchmark, 2 returned `survived` and 1 `refuted`. |
| DEEP repeats itself | M1's DEEP child asked for AMD's "precise market share percentage" and then its "specific market share percentage". Exact-duplicate detection does not catch paraphrases. |
| Over-delegation is partly controlled | After prompt tuning the router agrees with the intended mode on 88% of 32 labelled objectives and over-delegates 1 of 9 sub-objectives. M2 still nested a second WIDE with 5 children. |
| Routing misses DEEP | D2 (a two-hop question) was routed ATOM, answered from one page, and was wrong. The router picks DEEP for 3 of 6 labelled DEEP objectives. |
| Redundant work is modest | Across 9 runs: 3 near-duplicate objective pairs, 5 URLs read by more than one agent, 6 page reads that produced no accepted finding, 2 agents with no evidence. |
| The wrap-up deadline was used | M1 and M2 reached 70% of the 900 s budget; agents wrote up and the root synthesized every branch. No run hit the hard deadline. |

## Grounding

| Measure | Result |
|---|---|
| Citations to non-existent sources in final answers | 0 in 9 runs |
| Figures in final answers | 67 |
| ...found in the source cited in the same sentence | 49 (73%) |
| ...found elsewhere in retrieved text | 16 (24%) |
| ...found in no retrieved text | 2 (3%): A2's $23.1B, and one figure in W2 |
| Extracted findings rejected because the quote was not on the page | 8 (all in W1) |
| Page fetches that failed | 26 of 58 (HTTP 403 from finance sites, script-rendered pages, one oversized PDF) |
| Sources cited as "search snippet only" | 21 of 44 citations. When pages cannot be read the system falls back to snippets and says so in the report. |

Two limits of these checks showed up:

- **A quote check does not tie the claim to the quote.** In A2 the model attached an invented
  figure to a real sentence. The quote passed; the final audit caught the figure.
- **A figure check does not tie the figure to the metric.** In W1 a real 75.5% (non-GAAP) was
  reported as GAAP.

## Failures and their causes

| Failure | Cause | Status |
|---|---|---|
| A2: annual figure not found | Apple's financial-statements PDF is 4.9 MB; the 3 MB response cap truncated it and the parser returned nothing. The full file contains "Services 96,169". | Baseline left as frozen. The `pdf_8mb` arm re-runs A2 with an 8 MB cap. |
| D1: Amkor instead of TSMC | Search results were dominated by recent news of an NVIDIA-Amkor deal; the model took "supplier in a new deal" for "the constraint". The verifier was then handed a statement about missing data rather than the candidate answer, and passed it. | Model/search limitation, plus a missing guard: verification should refuse non-existence claims. |
| D2: Intel Foundry | Routed ATOM, one source, no verification. | Routing limitation; DEEP would have verified. |
| W1: Intel margin missing | Intel's investor pages and several aggregators returned 403 or no text; snippets did not contain the figure. | Search/fetch limitation. |
| W2: wrong ranking | Synthesis reasoning error by the 4B model. | Model limitation. |

## Earlier live runs (before the freeze)

These shaped the baseline and are recorded for honesty about how it got here.

| Run | Outcome | What changed afterwards |
|---|---|---|
| ATOM, first attempt | Said the annual data-center figure was missing, though the page had it | Passage selection rewritten (the relevant paragraph had been dropped) |
| NVIDIA question, attempt 1 | 14 agents, 657 s, 7 failed model calls, 6 agents with no evidence; invented sub-questions such as "Intel's 4nm capacity for NVIDIA H100" | Bounded JSON strings, planning prompt with an example and "do not invent specifics", query simplification, clean cancellation |
| NVIDIA question, attempt 2 | 14 agents, hit the 900 s deadline; answer used 2 of 4 branches | Routing prompt with lineage and examples; soft wrap-up deadline; node budget |
| NVIDIA question, attempt 3 | 10 agents, 579 s, 6 cited pages, no failed calls | Follow-ups forced to single lookups; failed sub-tasks kept out of citation position |
| DEEP question | 5 agents, 365 s; investigate, verify, re-investigate | Verify step phrased as a question is treated as investigate |

## Validation status

| Component | Status |
|---|---|
| ATOM, WIDE, DEEP, ENTITY_COLLECT | Live end to end (real model, live web) |
| Recursive spawning to depth 2 | Live |
| Incremental review and evidence-driven follow-ups | Live |
| Independent verification in DEEP and ENTITY_COLLECT | Live |
| Budgets: nodes, wrap-up deadline | Hit live and handled |
| Budgets: model calls, web calls, hard deadline, depth | Tested with the scripted model only (never reached live at default settings, except the hard deadline in pre-freeze attempt 2) |
| Quote verification, citation stripping, answer audit | Live, plus unit tests |
| SSRF guard, robots.txt | Unit-tested with literal addresses; robots.txt honoured live. No hostile page was encountered, so prompt-injection handling is untested against a real attack. |
| Record/replay cassettes | Recorded live in this benchmark; replay unit-tested and used live in the comparison runs |
| Web probing, experience sharing | Scripted tests only at the time of the baseline freeze; see `OPTIMIZATION_RESULTS.md` for live results |
| Peak memory | Not instrumented. The 4B model occupies 3.3 GB at 8K context; no memory pressure was observed. |

## Reproduce

```bash
.venv/bin/python -m experiments.bench.run_bench --name my_baseline --arms baseline --order arm
.venv/bin/python -m experiments.bench.compare my_baseline
.venv/bin/python -m experiments.bench.decision_ceiling my_baseline
```

Live answers will differ from these: search results change daily, and the model's outputs depend
on what it retrieves.
