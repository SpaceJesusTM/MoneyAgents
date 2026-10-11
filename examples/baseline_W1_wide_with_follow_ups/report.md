# Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).

_config: baseline | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: partial | confidence: medium_

## Answer

NVIDIA's GAAP gross margin for fiscal year 2025 was 75.5%, representing a 1.7 percentage point increase from the prior year [S2]. AMD's GAAP gross margin for fiscal year 2024 was 49% [S1], which included a Q3 figure of 50% and a Q4 figure of 51% [S6, S5]. Intel's specific GAAP gross margin percentage for fiscal year 2024 could not be established from the provided results. While findings confirmed that Intel's margins were negatively impacted by lower revenue, higher unit costs, and excess capacity charges [S4], and that performance exceeded guidance in Q4 [S3], no exact numerical figure was reported [S4].

Uncertainty: The research failed to retrieve the specific GAAP gross margin percentage for Intel for fiscal year 2024. Although qualitative factors affecting Intel's margins were identified, the quantitative data required to complete the comparison is missing from the available findings.

**Gaps reported by the system:** no evidence for: Intel gross margin performance for fiscal year 2024

## Sources cited

[S2] NVIDIA Announces Financial Results for Fourth Quarter and Fiscal 2025 - https://nvidianews.nvidia.com/_gallery/download_pdf/67bf85d73d633281c6875f57/ (retrieved 2026-10-11)
[S1] AMD Reports Fourth Quarter and Full Year 2024 Financial Results :: Advanced Micro Devices, Inc. (AMD) - https://ir.amd.com/news-events/press-releases/detail/1236/amd-reports-fourth-quarter-and-full-year-2024-financial-results (retrieved 2026-10-11)
[S6] AMD Reports Third Quarter 2024 Financial Results - https://ir.amd.com/news-events/press-releases/detail/1224/amd-reports-third-quarter-2024-financial-results (retrieved 2026-10-11) (search snippet only; page not read)
[S5] AMD Reports Fourth-Quarter and Full-Year 2024 Financial… - https://newsroom.amd.com/news/amd-reports-fourth-quarter-and-full-year-2024-fina/ (retrieved 2026-10-11) (search snippet only; page not read)
[S4] PDF 10-K - 01/26/2024 - Intel Corporation - https://www.intc.com/filings-reports/annual-reports/content/0000050863-24-000010/0000050863-24-000010.pdf (retrieved 2026-10-11) (search snippet only; page not read)
[S3] PDF Intel Reports Fourth-Quarter and Full-Year 2024 Financial Results - https://download.intel.com/newsroom/2025/c8e6h3a2/intel-q4-2024y-earnings.pdf (retrieved 2026-10-11) (search snippet only; page not read)

## Grounding audit (programmatic, no model involved)

- citations: 6 (2 read pages, 4 snippet-only); unknown ids removed: 0
- figures in the answer: 9; found in the cited source: 7; found elsewhere in retrieved evidence: 2; not found in any retrieved text: 0
- sentences with figures but no citation: 2

## Agent tree

```
[WIDE] Compare the gross margins of NVIDIA (fiscal year 2025), AMD (fiscal year 2024) and Intel (fiscal year 2024).  (#0, partial, 388s, confidence medium)
│   why: Compares three named entities on a specific metric.
│   ! follow-up requested but none allowed (limit reached)
│   ! follow-up requested but none allowed (limit reached)
├── [ATOM] NVIDIA gross margin performance for fiscal year 2025  (#1, ok, 195s, confidence high)
│       why: Single company metric requested, fits ATOM.
│       ! asked to read result 3, which is not an unread result; read 1 instead
├── [ATOM] AMD gross margin performance for fiscal year 2024  (#2, ok, 207s, confidence high)
│       why: Single entity and metric requested; ATOM.
│       ! search returned nothing; retried as 'AMD fiscal year 2024 gross margin earnings'
│       ! finish with no evidence overridden; read the next unread result
├── [ATOM] Intel gross margin performance for fiscal year 2024  (#3, failed, 241s)
│       why: Single entity fact lookup.
│       ! no page evidence; used search snippets (0 findings)
├── [ATOM] Determine AMD's GAAP gross margin for Q3 and Q4 of fiscal year 2024.  (#4, ok, 114s, confidence high)
│       ! no page evidence; used search snippets (2 findings)
└── [ATOM] Retrieve Intel's GAAP gross margin for fiscal year 2024.  (#5, ok, 108s, confidence low)
        ! no page evidence; used search snippets (3 findings)
```

## Statistics

```
  answer_seconds: 388.4
  wall_seconds: 388.4
  time_to_first_search_result: 24.443
  time_to_first_evidence: 105.447
  time_to_first_page_evidence: 105.447
  llm_calls: 44
  llm_calls_by_kind: {'route': 4, 'plan': 1, 'act': 20, 'extract': 6, 'answer': 4, 'review': 5, 'snippet_extract': 3, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 388.15
  llm_queue_wait_seconds: 553.33
  prompt_tokens: 28164
  output_tokens: 3764
  llm_prompt_eval_seconds: 148.34
  llm_generation_seconds: 213.06
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 4, 'review:generative': 5}
  searches: 8
  fetches: 12
  web_calls: 20
  fetch_failures: 6
  search_failures: 0
  web_seconds: 27.37
  web_run_cache_hits: 0
  web_from_cassette: 0
  nodes: 6
  nodes_by_mode: {'WIDE': 1, 'ATOM': 5}
  nodes_by_role: {'research': 6}
  nodes_by_status: {'partial': 1, 'ok': 4, 'failed': 1}
  max_depth: 1
  findings: 10
  findings_from_pages: 5
  findings_rejected: 8
  sources: 6
  source_domains: ['download.intel.com', 'intc.com', 'ir.amd.com', 'newsroom.amd.com', 'nvidianews.nvidia.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 0
    pages_read_with_no_accepted_finding: 4
    nodes_with_no_evidence: 1
    nodes_cancelled: 0
  interventions: 8
  budget_hits: []
```
