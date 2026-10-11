# Money Agents — WebSwarm Evaluation and Optimization Protocol

**Companion to:** `WEBSWARM_BASELINE_AND_OPTIMIZATION_PLAN.md`  
**Purpose:** Ensure that speed improvements are real, quality-preserving where possible, and directly comparable to a validated baseline.

## 1. Evaluation questions

1. Can the baseline gather and cite correct evidence for financial research questions?
2. Does progressive delegation discover valuable follow-up questions, or mostly create redundant work?
3. Can results inform subsequent research before every branch completes (if supported by the implementation)?
4. Which components dominate end-to-end latency: inference, routing, web search, page reading, verification, queueing, or synthesis?
5. Do changes such as web probing, smaller/local routers, Jev-style typed decisions, caching, or smarter stopping reduce **end-to-end time or tool usage** without harming grounded answer quality?
6. Is any latency gain just an artifact of provider responses, cache warm-up, source variation, or weaker verification?

## 2. Baseline and variant definitions

Freeze a baseline after live validation, even if the baseline remains imperfect. Keep its code/configuration available for repeat runs. Save a baseline run manifest, model tag/quantization, model/server version, exact prompt templates, search provider, date/time, budgets, machine/resource notes, and revision/commit hash when available.

Recommended experimental arms:

| Arm | Description | Why it matters |
|---|---|---|
| A — Baseline | Ollama generative model controls research and orchestration | Reference quality/time |
| B — Web probing | Probing enabled vs disabled, otherwise same config | Search efficiency ablation |
| C — Local lightweight router | Small local model or cheap classifier for bounded decisions | No-key speed alternative |
| D — Jev decision adapter | Live Jev handles selected typed choices if authorized | Test actual external decision latency |
| E — Rules / targeted optimizations | Deterministic heuristics, dedupe, caching, adaptive stopping, etc. | Check whether novelty is necessary |

Avoid stacking several changes before measuring any one of them. If combined variants are tested, also include isolated ablations so their effects remain interpretable.

## 3. Benchmark task suite

Start with **8–12 bounded queries**, including at least:

- 1–2 **ATOM** tasks: facts from official company filings or earnings releases with directly verifiable answers.
- 2 **DEEP** tasks: multi-hop causal or constraint research requiring a follow-up investigation.
- 2 **WIDE** tasks: compare companies/entities or research multiple independent dimensions.
- 2 mixed **DEEP/WIDE** tasks: e.g., drivers and risks of a company revenue segment, requiring both coverage and follow-up.
- Optional **ENTITY_COLLECT** task: discover, deduplicate, and source-check an unknown set of entities.

Use finance topics realistically connected to Money Agents, but avoid making all tasks about NVIDIA or depending on one live news cycle. For each task, specify objective, date/as-of constraints, authoritative source candidates, and how an evaluator could check the answer.

Separate tasks into:

- **Stable / reproducible:** past filings, historical figures, known source documents, locally recorded search fixtures.
- **Live / dynamic:** current reporting, recent developments. Treat results as exploratory; log run timestamps and source variance.

Tests should assess the actual answer **and** intermediate research behavior, not merely whether a plausible task tree appears.

## 4. Metrics

### Quality (primary acceptance gate)

- **Claim support / groundedness:** Are important claims backed by actual retrieved sources?
- **Factual correctness:** Are key figures, dates, company names, comparisons, and conclusions correct relative to verifiable references?
- **Coverage:** Were major requested dimensions addressed?
- **Citation validity:** Do cited URLs actually support the attached claims? Are retrieval failures/blocked sources disclosed?
- **Uncertainty and conflict handling:** Were contradictory or incomplete findings handled honestly?
- **Delegation relevance:** Did spawned subtasks add useful evidence, or were they redundant?

A concise manual rubric (e.g., 0–2 on each dimension) is adequate initially. Save notes and examples of mistakes; avoid overtrusting model self-grades. Define an acceptable quality-loss tolerance *before* selecting a “winner.”

### Efficiency

- **End-to-end wall-clock time** and, when feasible, p50/p95 across repeated bounded runs.
- **Time to first useful/source-grounded evidence** (different from final completion time).
- **LLM calls**, output/input tokens where reported, and time spent waiting/generating.
- **Search queries, fetches, web-tool calls**, retries and failures; count all calls, including probing.
- **Agents spawned**, maximum depth, cancelled/duplicate branches.
- **Peak memory / swap pressure**, actual model size, and warm/cold start conditions where measurable.
- **Cloud usage / cost** only if a provider is explicitly authorized; distinguish estimated and billed values.

Measure full-workflow speedups rather than inferring savings from sub-second routing decisions. A router that saves milliseconds but triggers many redundant searches can be slower overall.

## 5. Trace schema (suggested, not mandatory)

Each run should preserve enough data to debug and replay:

```text
run_id, task_id, timestamp, code_revision, config, model, search_provider
node_id, parent_id, objective, mode, created_at, started_at, finished_at
routing_decision, decision_reason_summary, child_objectives, overrides
sources[{url, title, retrieved_at, claim_ids}], evidence_summaries
llm_calls, web_calls, retries, errors, budget_usage
completion_status, final_answer, citations, quality_notes, timing_breakdown
```

Do **not** store private secrets or unrestricted hidden reasoning traces. A concise model-authored decision explanation is sufficient. Keep noisy generated logs out of Git by default; save small representative traces for evaluation.

## 6. Comparison procedure

1. **Smoke test** all arms with mock/fixture clients. These validate plumbing only.
2. **Validate live baseline** on at least one multi-step query with real Ollama + web search and real URLs. If unavailable, mark baseline *not live-validated*.
3. **Freeze baseline** config/revision and save a manifest.
4. Run the same selected tasks with comparable search settings, tool budgets, model parameters, and source corpus where possible. Use recorded evidence fixtures for controlled comparisons, plus live runs for ecological validity.
5. If affordable, repeat promising experiments to distinguish consistent effects from run-to-run variance. Randomize task order where feasible; note caches and hot models.
6. Save a table of results and failure notes. Include unsuccessful and timed-out runs, not just successes.
7. Reject misleading improvements that get speed by skipping required evidence, citations, or verification; document the quality/latency tradeoff explicitly.

### Example results table to populate

| Variant | Tasks/live | Quality | Median time | Time-to-first-evidence | Web calls | Model calls | Issues |
|---|---:|---:|---:|---:|---:|---:|---|
| Baseline | — | — | — | — | — | — | Not measured |
| + probing | — | — | — | — | — | — | Not measured |
| + small router | — | — | — | — | — | — | Not measured |
| + Jev | — | — | — | — | — | — | Requires real provider access |

## 7. Jev experiment rules

Reference: https://typesafe.ai/blog/introducing-system-one-models-and-jev

Jev is proposed for **typed/bounded decisions**, not free-form research writing. Candidate tasks include: branch priority, stop/continue, verification required/not required, relevance scoring, and possibly mode selection. Generative tasks such as child-objective writing, evidence synthesis, and financial reasoning remain with a capable local LLM.

- **Implement the real Jev integration interface**, with configuration and explicit authorization for live external calls.
- If no key/provider access: create a **mock to validate interface behavior** and preserve a complete blocker note; **do not count mock latency/quality as Jev results**.
- Independently implement a genuine **local decision-model or rule-based variant** so the optimization stage is still testable overnight.
- Compare *decision accuracy and confidence* where observable, alongside *total task latency and grounded answer quality*. A fast wrong control decision is not a win.
- Check the official, current API contract at implementation time. Do not guess endpoint details or use unofficial paid gateways without approval.

## 8. Required findings to report

For each completed experiment, explain:

- What changed and why (paper-informed vs local hypothesis).
- What was actually tested (mock/fixture/live).
- Impact on answer quality, full-run latency, model calls and web-tool calls.
- Memory/provider constraints, measurement uncertainty, and failure examples.
- Whether the variant should be kept, revised, or discarded in Money Agents.

**Research priority:** optimize **quality–latency–cost jointly**. In future time-sensitive financial workflows, time to *decision-critical evidence* might be especially important; this prototype does **not** authorize trade execution or establish a safe trade-readiness threshold.
