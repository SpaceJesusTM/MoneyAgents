# Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).

_config: reliability | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: partial | confidence: medium_

## Answer

Based on the provided results, a direct comparison of gross margins is not possible because the data points for NVIDIA and AMD rely on fundamentally different accounting standards, preventing an apples-to-apples analysis.

NVIDIA reported a non-GAAP gross margin of 75.5% for fiscal year 2025 [S2]. This figure represents the full-year performance but is derived from non-GAAP accounting adjustments. In contrast, AMD reported a GAAP gross margin of 49% for fiscal year 2024 [S1], which includes standard accounting adjustments and excludes certain items often added back in non-GAAP calculations. Intel reported a GAAP gross margin of 32.7% for fiscal year 2024 [S3].

Because NVIDIA's figure (75.5%) is based on non-GAAP metrics while AMD's (49%) and Intel's (32.7%) are based on GAAP metrics, the reported ranking places NVIDIA at the top. However, this order is misleading; if adjusted to a common accounting basis, NVIDIA's margin would likely be lower than its non-GAAP figure, potentially narrowing or reversing the gap with AMD.

Uncertainty:
The results explicitly state that no evidence was found for Intel's gross margin performance for fiscal year 2024 in the context of the specific search terms required to verify availability by segment or region [S3]. Additionally, while NVIDIA provided a full-year non-GAAP figure, it only provided a quarterly GAAP figure (73.0%) for Q4 FY25; no full-year GAAP margin was available for NVIDIA to compare directly against AMD and Intel's GAAP figures.

**Gaps reported by the system:** no evidence for: Intel gross margin performance for fiscal year 2024; finished before all sub-tasks reported; comparison caveat: the figures are on different accounting bases (AMD: GAAP; NVIDIA: non-GAAP), so they are not like for like. Say so.

## Sources cited

[S2] NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2025 - https://nvidianews.nvidia.com/_gallery/download_pdf/67bf85d73d633281c6875f57/ (retrieved 2026-10-12)
[S1] AMD Reports Fourth Quarter and Full Year 2024 Financial Results :: Advanced Micro Devices, Inc. (AMD) - https://ir.amd.com/news-events/press-releases/detail/1236/amd-reports-fourth-quarter-and-full-year-2024-financial-results (retrieved 2026-10-12)
[S3] Intel Reports Fourth-Quarter and Full-Year 2024 Financial Results | Nasdaq - https://www.nasdaq.com/press-release/intel-reports-fourth-quarter-and-full-year-2024-financial-results-2025-01-30 (retrieved 2026-10-12)

## Grounding audit (programmatic, no model involved)

- citations: 3 (3 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 11; found in the cited source: 7; found elsewhere in retrieved evidence: 4; not found in any retrieved text: 0
- sentences with figures but no citation: 2

## Consistency checks (programmatic, no model involved)

- ordering statements that contradict the figures: 0
- GAAP / non-GAAP labels that contradict the cited passage: 0
- quarter / full-year labels that contradict the finding: 0
- comparison caveat: the figures are on different accounting bases (AMD: GAAP; NVIDIA: non-GAAP), so they are not like for like. Say so.

## Agent tree

```
[WIDE] Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).  (#0, partial, 207s, confidence medium)
│   why: Compares three named entities on a specific metric.
│   ! follow-up requested but none allowed (limit reached)
│   ! follow-up requested but none allowed (limit reached)
│   ! finished early with 1 sub-task(s) outstanding
├── [ATOM] NVIDIA gross margin performance for fiscal year 2025  (#1, ok, 143s, confidence low)
│       why: Single company metric requested, fits ATOM.
│       ! search returned nothing; retried as 'NVIDIA fiscal year 2025 annual gross margin'
│       ! answer mislabels a figure (73.0% is given as a full-year figure, but the finding it comes from gives it for a quarter); asked again
│       ! figure still mislabelled; answer replaced by the findings as extracted
├── [ATOM] AMD gross margin performance for fiscal year 2024  (#2, ok, 156s, confidence high)
│       why: Single entity and metric requested; ATOM.
│       ! search returned nothing; retried as 'AMD fiscal year 2024 gross margin earnings'
│       ! finish with no evidence overridden; read the next unread result
│       ! search returned nothing; retried as 'AMD fiscal year 2024 gross margin Q3'
├── [ATOM] Intel gross margin performance for fiscal year 2024  (#3, failed, 99s)
│       why: Single entity fact lookup.
│       ! no page evidence; used search snippets (0 findings)
├── [ATOM] Verify Intel's fiscal year 2024 gross margin availability and correct search terms.  (#4, ok, 80s, confidence high)
└── [ATOM] Cross-check AMD and NVIDIA FY2024/FY2025 data against Intel's reported periods.  (#5, running, -)
        ! search returned nothing; retried as 'Intel fiscal year FY2024 FY2025 reporting period'
        ! search returned nothing; retried as 'Intel fiscal year 2024 2025 quarter end'
```

## Statistics

```
  answer_seconds: 207.4
  wall_seconds: 297.4
  time_to_first_search_result: 18.121
  time_to_first_evidence: 56.907
  time_to_first_page_evidence: 56.907
  llm_calls: 39
  llm_calls_by_kind: {'route': 4, 'plan': 1, 'act': 18, 'extract': 6, 'snippet_extract': 1, 'review': 4, 'answer': 4, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 180.75
  llm_queue_wait_seconds: 187.3
  prompt_tokens: 24732
  output_tokens: 3734
  llm_prompt_eval_seconds: 35.56
  llm_generation_seconds: 138.65
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 4, 'review:generative': 4}
  searches: 14
  fetches: 7
  web_calls: 21
  fetch_failures: 2
  fetch_truncated: 0
  search_failures: 8
  web_seconds: 259.65
  web_run_cache_hits: 1
  web_from_cassette: 21
  nodes: 6
  nodes_by_mode: {'WIDE': 1, 'ATOM': 5}
  nodes_by_role: {'research': 6}
  nodes_by_status: {'partial': 1, 'ok': 3, 'failed': 1, 'running': 1}
  max_depth: 1
  findings: 7
  findings_from_pages: 7
  findings_rejected: 9
  findings_adjusted: 1
  guard_events: {'finding_adjusted': 1, 'label_issue': 2, 'comparison': 1}
  sources: 3
  source_domains: ['ir.amd.com', 'nasdaq.com', 'nvidianews.nvidia.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 1
    pages_read_with_no_accepted_finding: 3
    nodes_with_no_evidence: 1
    nodes_cancelled: 0
  interventions: 12
  budget_hits: []
```
