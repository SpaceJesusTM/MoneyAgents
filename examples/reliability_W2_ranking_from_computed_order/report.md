# Compare the total annual revenue of Microsoft (fiscal year 2024), Alphabet (2024) and Amazon (2024).

_config: reliability | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: ok | confidence: high_

## Answer

Based on the sub-researcher results, Amazon generated the highest total annual revenue in 2024 at $638 billion, followed by Alphabet at $350.0 billion, and Microsoft at $245.12 billion [S2][S3][S1]. Alphabet's calendar year 2024 revenue was significantly higher than Microsoft's fiscal year 2024 revenue, which is approximately 42% greater. Amazon's revenue was more than double that of Alphabet and nearly 2.6 times that of Microsoft.

All three entities reported their respective revenues with high confidence, and no gaps or conflicting data were identified in the provided results. The comparison relies on direct figures: $638 billion for Amazon [S2], $350.0 billion for Alphabet [S3], and $245.12 billion for Microsoft [S1].

Uncertainty:
No uncertainty exists regarding the specific revenue figures or the ranking of these companies based on the provided data.

## Sources cited

[S2] Amazon.com, Inc. - https://s2.q4cdn.com/299287126/files/doc_financials/2025/ar/Amazon-2024-Annual-Report.pdf (retrieved 2026-10-11)
[S3] Alphabet Inc. 10-K FY2024 Annual Report — Revenue, Net Income, EPS - https://www.analystlens.com/stocks/googl/10k/fy2024 (retrieved 2026-10-11)
[S1] MSFT 10-K FY2024 Annual Report — Revenue, Net Income, EPS - https://www.analystlens.com/stocks/msft/10k/fy2024 (retrieved 2026-10-11)

## Grounding audit (programmatic, no model involved)

- citations: 3 (3 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 10; found in the cited source: 7; found elsewhere in retrieved evidence: 2; not found in any retrieved text: 1
- sentences with figures but no citation: 2
  - ungrounded figure `2.6` in: Amazon's revenue was more than double that of Alphabet and nearly 2.6 times that of Microsoft.

## Consistency checks (programmatic, no model involved)

- ordering statements that contradict the figures: 0
- GAAP / non-GAAP labels that contradict the cited passage: 0
- quarter / full-year labels that contradict the finding: 0

## Agent tree

```
[WIDE] Compare the total annual revenue of Microsoft (fiscal year 2024), Alphabet (2024) and Amazon (2024).  (#0, ok, 366s, confidence high)
│   why: Compares three named entities on a specific metric.
├── [ATOM] Microsoft's total annual revenue for fiscal year 2024  (#1, ok, 76s, confidence high)
│       why: Single entity fact retrieval.
├── [ATOM] Alphabet's total annual revenue for calendar year 2024  (#2, ok, 346s, confidence high)
│       why: Single entity fact retrieval.
│       ! long document, s206.q4cdn.com: read 20 of 110 PDF pages
│       ! search returned nothing; retried as 'Alphabet Inc total annual revenue 2024 dollars'
└── [ATOM] Amazon's total annual revenue for calendar year 2024  (#3, ok, 94s, confidence high)
        why: Single entity fact retrieval.
        ! finish with no evidence overridden; read the next unread result
```

## Statistics

```
  answer_seconds: 365.8
  wall_seconds: 365.8
  time_to_first_search_result: 23.007
  time_to_first_evidence: 56.232
  time_to_first_page_evidence: 56.232
  llm_calls: 27
  llm_calls_by_kind: {'route': 4, 'plan': 1, 'act': 11, 'extract': 4, 'answer': 3, 'review': 3, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 131.54
  llm_queue_wait_seconds: 143.29
  prompt_tokens: 14545
  output_tokens: 1520
  llm_prompt_eval_seconds: 62.73
  llm_generation_seconds: 60.3
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 4, 'review:generative': 3}
  searches: 5
  fetches: 6
  web_calls: 11
  fetch_failures: 2
  fetch_truncated: 0
  search_failures: 2
  web_seconds: 277.87
  web_run_cache_hits: 0
  web_from_cassette: 9
  nodes: 4
  nodes_by_mode: {'WIDE': 1, 'ATOM': 3}
  nodes_by_role: {'research': 4}
  nodes_by_status: {'ok': 4}
  max_depth: 1
  findings: 4
  findings_from_pages: 4
  findings_rejected: 0
  findings_adjusted: 0
  guard_events: {'comparison': 1}
  sources: 3
  source_domains: ['analystlens.com', 's2.q4cdn.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 0
    pages_read_with_no_accepted_finding: 1
    nodes_with_no_evidence: 0
    nodes_cancelled: 0
  interventions: 3
  budget_hits: []
```
