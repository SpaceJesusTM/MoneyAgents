# What are the main drivers and risks for AMD's data center business over the next year?

_config: rules_plus | model: qwen3.5:4b-q4_K_M | decider: rules | web: replay_or_record | status: partial | confidence: high_

## Answer

AMD's data center business is experiencing explosive growth driven by strong customer adoption, but faces severe supply chain constraints that limit near-term expansion. In Q1 2026 alone, revenue hit $5.78 billion, a 57% year-over-year increase, projecting an annualized run-rate of roughly $23.1 billion [S1]. This growth is underpinned by high customer uptake across the EPYC and MI300 series. However, manufacturing capacity remains the primary risk; both product lines face fully booked CoWoS packaging queues lasting 52–78 weeks due to TSMC's near-monopolistic position in high-performance computing [S2]. With TSMC holding approximately 70% of the market share and Samsung only 7%, supply bottlenecks are structural rather than cyclical [S3]. Furthermore, geopolitical tensions could exacerbate these issues by increasing wafer costs by 25–40% if US onshore capacity is developed [S2].

Uncertainty: The provided results contain no evidence regarding the competitive landscape or market share dynamics between AMD and NVIDIA in enterprise AI, nor do they address regulatory policies or trade tariffs impacting global chip exports. Consequently, it cannot be established how direct competition with NVIDIA influences AMD's specific growth trajectory or what export restrictions might alter revenue projections over the next year.

**Gaps reported by the system:** no evidence for: Competitive landscape and market share dynamics between AMD and NVIDIA in enterp; Regulatory policies and trade tariffs impacting AMD's global data center chip ex

## Sources cited

[S1] AMD Statistics 2026: Revenue, Market Share, AI Growth &amp; Data Center Dominance - Axis Intelligence - https://axis-intelligence.com/amd-statistics/ (retrieved 2026-10-11)
[S2] Supply Chain Analysis - Semiconductor Market Intelligence - https://siliconanalysts.com/analysis/topic/supply-chain (retrieved 2026-10-11)
[S3] Semiconductors in 2026: Why supply chains are a major bottleneck - https://www.moodys.com/web/en/us/insights/corporations/semiconductors-in-2026-why-supply-chains-are-a-major-bottleneck.html (retrieved 2026-10-11)

## Grounding audit (programmatic, no model involved)

- citations: 3 (3 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 10; found in the cited source: 10; found elsewhere in retrieved evidence: 0; not found in any retrieved text: 0
- sentences with figures but no citation: 0

## Agent tree

```
[WIDE] What are the main drivers and risks for AMD's data center business over the next year?  (#0, partial, 103s, confidence high)
│   why: comparison, enumeration, or 'main factors' pattern
├── [ATOM] AMD data center revenue growth trends and customer adoption rates in recent quarters  (#1, ok, 49s, confidence high)
│       why: no multi-part or unknown-target pattern
├── [ATOM] Competitive landscape and market share dynamics between AMD and NVIDIA in enterprise AI  (#2, failed, 7s)
│       why: no multi-part or unknown-target pattern
│       ! search returned nothing; retried as 'competitive landscape market share dynamics amd nvidia'
├── [ATOM] Supply chain constraints and semiconductor manufacturing capacity for AMD EPYC and MI300 series  (#3, ok, 71s, confidence high)
│       why: no multi-part or unknown-target pattern
└── [ATOM] Regulatory policies and trade tariffs impacting AMD's global data center chip exports  (#4, failed, 7s)
        why: no multi-part or unknown-target pattern
        ! search returned nothing; retried as 'regulatory policies trade tariffs impacting amd s'
```

## Statistics

```
  answer_seconds: 103.3
  wall_seconds: 103.3
  time_to_first_search_result: 12.563
  time_to_first_evidence: 30.599
  time_to_first_page_evidence: 30.599
  llm_calls: 7
  llm_calls_by_kind: {'plan': 1, 'extract': 3, 'answer': 2, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 100.2
  llm_queue_wait_seconds: 45.59
  prompt_tokens: 4639
  output_tokens: 1120
  llm_prompt_eval_seconds: 26.23
  llm_generation_seconds: 67.89
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:rules': 5, 'review:rules': 4}
  searches: 6
  fetches: 4
  web_calls: 10
  fetch_failures: 1
  search_failures: 0
  web_seconds: 19.86
  web_run_cache_hits: 0
  web_from_cassette: 10
  nodes: 5
  nodes_by_mode: {'WIDE': 1, 'ATOM': 4}
  nodes_by_role: {'research': 5}
  nodes_by_status: {'partial': 1, 'ok': 2, 'failed': 2}
  max_depth: 1
  findings: 7
  findings_from_pages: 7
  findings_rejected: 1
  sources: 3
  source_domains: ['axis-intelligence.com', 'moodys.com', 'siliconanalysts.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 0
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 0
    pages_read_with_no_accepted_finding: 0
    nodes_with_no_evidence: 2
    nodes_cancelled: 0
  interventions: 2
  budget_hits: []
```
