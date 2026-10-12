# Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).

_config: reliability | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: partial | confidence: high_

## Answer

NVIDIA's GAAP gross margin for fiscal year 2025 was 73.0%, while AMD's GAAP gross margin for fiscal year 2024 was 49% [S1, S2]. Intel reported a GAAP gross margin of 32.7% for fiscal year 2024 [S3].

The primary comparison relies on GAAP figures because they represent standardized accounting measures across all three companies, whereas non-GAAP margins vary by company and exclude specific adjustments that make direct cross-company comparison difficult. NVIDIA's margin is significantly higher than both AMD and Intel, driven largely by its data center segment performance. AMD showed a slight year-over-year increase in Q4 2024 to 51%, whereas Intel reported decreases for both GAAP and Non-GAAP margins compared to the prior year [S1, S3].

Uncertainty: The search results did not specify the exact search terms used to retrieve Intel's data, nor did they provide a breakdown of gross margin availability by product segment or region. Additionally, while evidence was found for NVIDIA and AMD, no specific evidence was located regarding Intel's gross margin performance trends beyond the aggregate fiscal year figure; however, the available data confirms the 32.7% GAAP figure exists.

**Gaps reported by the system:** no evidence for: Intel gross margin performance for fiscal year 2024; finished before all sub-tasks reported

## Sources cited

[S1] AMD Reports Fourth Quarter and Full Year 2024 Financial Results :: Advanced Micro Devices, Inc. (AMD) - https://ir.amd.com/news-events/press-releases/detail/1236/amd-reports-fourth-quarter-and-full-year-2024-financial-results (retrieved 2026-10-11)
[S2] NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2025 - https://nvidianews.nvidia.com/_gallery/download_pdf/67bf85d73d633281c6875f57/ (retrieved 2026-10-11)
[S3] Intel Reports Fourth-Quarter and Full-Year 2024 Financial Results | Nasdaq - https://www.nasdaq.com/press-release/intel-reports-fourth-quarter-and-full-year-2024-financial-results-2025-01-30 (retrieved 2026-10-11)

## Grounding audit (programmatic, no model involved)

- citations: 3 (3 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 9; found in the cited source: 8; found elsewhere in retrieved evidence: 1; not found in any retrieved text: 0
- sentences with figures but no citation: 1

## Consistency checks (programmatic, no model involved)

- ordering statements that contradict the figures: 0
- GAAP / non-GAAP labels that contradict the cited passage: 0

## Agent tree

```
[WIDE] Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).  (#0, partial, 422s, confidence high)
│   why: Compares three named entities on a specific metric.
│   ! follow-up requested but none allowed (limit reached)
│   ! finished early with 1 sub-task(s) outstanding
├── [ATOM] NVIDIA gross margin performance for fiscal year 2025  (#1, ok, 359s, confidence high)
│       why: Single company metric requested, fits ATOM.
│       ! search returned nothing; retried as 'NVIDIA fiscal year 2025 annual gross margin'
├── [ATOM] AMD gross margin performance for fiscal year 2024  (#2, ok, 399s, confidence high)
│       why: Single entity and metric requested; ATOM.
│       ! search returned nothing; retried as 'AMD fiscal year 2024 gross margin earnings'
│       ! finish with no evidence overridden; read the next unread result
│       ! search returned nothing; retried as 'AMD fiscal year 2024 gross margin Q3'
├── [ATOM] Intel gross margin performance for fiscal year 2024  (#3, failed, 188s)
│       why: Single entity fact lookup.
│       ! no page evidence; used search snippets (0 findings)
├── [ATOM] Verify Intel's fiscal year 2024 gross margin availability and correct search terms.  (#4, ok, 168s, confidence high)
└── [ATOM] Cross-check AMD and NVIDIA FY2024/FY2025 data against Intel's reported periods.  (#5, cancelled, 234s)
        ! search returned nothing; retried as 'Intel fiscal year FY2024 FY2025 reporting period'
        ! research cut short: Cancelled
```

## Statistics

```
  answer_seconds: 422.3
  wall_seconds: 438.9
  time_to_first_search_result: 21.264
  time_to_first_evidence: 83.265
  time_to_first_page_evidence: 83.265
  llm_calls: 37
  llm_calls_by_kind: {'route': 4, 'plan': 1, 'act': 17, 'extract': 6, 'snippet_extract': 1, 'review': 4, 'answer': 3, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 273.27
  llm_queue_wait_seconds: 287.08
  prompt_tokens: 23620
  output_tokens: 3384
  llm_prompt_eval_seconds: 86.25
  llm_generation_seconds: 163.77
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 4, 'review:generative': 4}
  searches: 13
  fetches: 7
  web_calls: 20
  fetch_failures: 2
  fetch_truncated: 0
  search_failures: 7
  web_seconds: 831.48
  web_run_cache_hits: 1
  web_from_cassette: 13
  nodes: 6
  nodes_by_mode: {'WIDE': 1, 'ATOM': 5}
  nodes_by_role: {'research': 6}
  nodes_by_status: {'partial': 1, 'ok': 3, 'failed': 1, 'cancelled': 1}
  max_depth: 1
  findings: 7
  findings_from_pages: 7
  findings_rejected: 9
  findings_adjusted: 1
  guard_events: {'finding_adjusted': 1, 'comparison': 1}
  sources: 3
  source_domains: ['ir.amd.com', 'nasdaq.com', 'nvidianews.nvidia.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 1
    pages_read_with_no_accepted_finding: 3
    nodes_with_no_evidence: 1
    nodes_cancelled: 1
  interventions: 9
  budget_hits: []
```
