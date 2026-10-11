# Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).

_config: rules_plus | model: qwen3.5:4b-q4_K_M | decider: rules | web: replay_or_record | status: ok | confidence: high_

## Answer

NVIDIA achieved the highest gross margins among the three companies, with a GAAP margin of 75.0% and a Non-GAAP margin of 75.5% for fiscal year 2025 [S3]. AMD reported significantly lower margins in fiscal year 2024, standing at 49% GAAP and 53% Non-GAAP [S1], though its fourth quarter reached record highs of 51% and 54%, respectively [S1]. Intel posted the lowest margins of the group for fiscal year 2024, with a GAAP margin of 32.7% and a Non-GAAP margin of 36.0% [S2]; however, both metrics improved in its fourth quarter to 39.2% and 42.1% [S2].

While AMD's full-year margins were lower than NVIDIA's, they exceeded Intel's full-year figures. All three companies experienced year-over-year declines in their GAAP gross margins for the respective fiscal years cited: NVIDIA increased by 2.3 percentage points [S3], while AMD and Intel decreased by unspecified amounts and 7.3 percentage points, respectively [S1][S2].

Uncertainty:
No evidence was found regarding any discrepancies or conflicting data between the sources provided for these specific companies and fiscal years.

## Sources cited

[S3] PDF CFO Commentary on Fourth Quarter and Fiscal 2025 Results - https://s201.q4cdn.com/141608511/files/doc_financials/2025/Q425/Q4FY25-CFO-Commentary.pdf (retrieved 2026-10-11)
[S1] AMD Reports Fourth-Quarter and Full-Year 2024 Financial Results - AMD Newsroom - https://newsroom.amd.com/news/amd-reports-fourth-quarter-and-full-year-2024-fina/ (retrieved 2026-10-11)
[S2] Intel Reports Fourth-Quarter and Full-Year 2024 Financial Results | Nasdaq - https://www.nasdaq.com/press-release/intel-reports-fourth-quarter-and-full-year-2024-financial-results-2025-01-30 (retrieved 2026-10-11)

## Grounding audit (programmatic, no model involved)

- citations: 3 (3 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 15; found in the cited source: 15; found elsewhere in retrieved evidence: 0; not found in any retrieved text: 0
- sentences with figures but no citation: 0

## Agent tree

```
[WIDE] Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).  (#0, ok, 162s, confidence high)
│   why: comparison, enumeration, or 'main factors' pattern
│   ! synthesis had no citations; asked again
├── [ATOM] NVIDIA gross margin performance for fiscal year 2025  (#1, ok, 112s, confidence high)
│       why: no multi-part or unknown-target pattern
├── [ATOM] AMD gross margin performance for fiscal year 2024  (#2, ok, 71s, confidence high)
│       why: no multi-part or unknown-target pattern
└── [ATOM] Intel gross margin performance for fiscal year 2024  (#3, ok, 103s, confidence high)
        why: no multi-part or unknown-target pattern
```

## Statistics

```
  answer_seconds: 162.5
  wall_seconds: 162.5
  time_to_first_search_result: 6.974
  time_to_first_evidence: 20.91
  time_to_first_page_evidence: 20.91
  llm_calls: 10
  llm_calls_by_kind: {'plan': 1, 'extract': 4, 'answer': 3, 'synthesize': 2}
  llm_failed_calls: 0
  llm_seconds: 159.65
  llm_queue_wait_seconds: 166.77
  prompt_tokens: 8520
  output_tokens: 1557
  llm_prompt_eval_seconds: 48.01
  llm_generation_seconds: 102.4
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:rules': 4, 'review:rules': 3}
  searches: 3
  fetches: 4
  web_calls: 7
  fetch_failures: 0
  search_failures: 0
  web_seconds: 10.21
  web_run_cache_hits: 0
  web_from_cassette: 7
  nodes: 4
  nodes_by_mode: {'WIDE': 1, 'ATOM': 3}
  nodes_by_role: {'research': 4}
  nodes_by_status: {'ok': 4}
  max_depth: 1
  findings: 8
  findings_from_pages: 8
  findings_rejected: 4
  sources: 3
  source_domains: ['nasdaq.com', 'newsroom.amd.com', 's201.q4cdn.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 0
    pages_read_with_no_accepted_finding: 1
    nodes_with_no_evidence: 0
    nodes_cancelled: 0
  interventions: 1
  budget_hits: []
```
