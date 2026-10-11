# What are the main factors that could affect NVIDIA's data-center revenue growth over the next 12 months?

_config: baseline | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: ok | confidence: medium_

## Answer

NVIDIA's data-center revenue growth over the next 12 months will likely be driven by sustained high pricing due to supply constraints and a maturing secondary market, while facing significant competitive pressure from custom silicon and AMD. Official GPU prices for H100, H200, and B200 units remain elevated between $25,000 and $45,000, with rack-level systems like the GB300 NVL72 priced at $3.7M–$4M [S1]. However, specific discounting strategies or percentages for Q3-Q4 2026 could not be established; only on-demand hourly rates and purchase bands were reported [S1].

Revenue growth is supported by strong enterprise AI adoption trends, with global generative AI spending reaching $644 billion in 2025 and the average number of production models per enterprise rising to 4.2 [S3]. Conversely, NVIDIA's market share has declined from 87% in 2024 to 70–75% in 2026 due to faster growth in custom silicon (15–20% market share) and contested AMD figures [S4][S6][S8]. Supply chain constraints, including extended lead times for power semiconductors and pressure on advanced packaging, continue to impact availability [S2].

Uncertainty:
No direct evidence links secondary market volumes ($121B) or specific discounting strategies to official revenue projections. Additionally, precise enterprise adoption rates specifically for NVIDIA chips were not found, only general model counts. The exact dollar amount of revenue lost due to supply constraints or competitive pressure could not be quantified.

## Sources cited

[S1] NVIDIA Data Center GPU Pricing: H100 to GB200 Cost Guide | GPUSmith - https://gpusmith.com/articles/en/nvidia-data-center-gpu-pricing-guide (retrieved 2026-10-11)
[S3] Enterprise AI Adoption Statistics 2026: 50+ Data Points on Business AI Integration - https://content-site-lovat.vercel.app/articles/enterprise-ai-adoption-statistics-2026.html (retrieved 2026-10-11)
[S4] AI Chip Market Share 2026: Nvidia, AMD, Custom Silicon - https://alatirok.com/ai-chip-market-share-2026/ (retrieved 2026-10-11)
[S6] AMD Statistics 2026: Revenue, Market Share, AI Growth &amp; Data Center Dominance - Axis Intelligence - https://axis-intelligence.com/amd-statistics/ (retrieved 2026-10-11)
[S8] AMD vs NVIDIA AI GPU Market Share 2026: MI350X vs B200 - https://siliconanalysts.com/analysis/amd-vs-nvidia-ai-gpu-market-share-2026 (retrieved 2026-10-11)
[S2] Semiconductor Shortages Are Accelerating in 2026 - https://randtech.com/semiconductor-shortages-2026-supply-chain/ (retrieved 2026-10-11)

## Grounding audit (programmatic, no model involved)

- citations: 6 (6 read pages, 0 snippet-only); unknown ids removed: 0
- figures in the answer: 17; found in the cited source: 15; found elsewhere in retrieved evidence: 2; not found in any retrieved text: 0
- sentences with figures but no citation: 2

## Agent tree

```
[WIDE] What are the main factors that could affect NVIDIA's data-center revenue growth over the next 12 months?  (#0, ok, 698s, confidence medium)
│   why: Multiple independent factors need separate research.
│   ! follow-up requested but none allowed (limit reached)
│   ! follow-up requested but none allowed (limit reached)
├── [ATOM] NVIDIA data-center GPU pricing trends and discounting strategies  (#1, ok, 196s, confidence medium)
│       why: Focuses on specific pricing and discounting mechanisms for a single entity.
├── [ATOM] Enterprise AI adoption rates and cloud provider demand for NVIDIA chips  (#2, ok, 205s, confidence medium)
│       why: Focuses on one specific factor (enterprise AI adoption) affecting a single entity (NVIDIA).
│       ! repeated/empty query; read the next unread result instead
├── [DEEP] Competitive pressure from AMD and custom silicon on NVIDIA's market share  (#3, ok, 657s, verdict refuted)
│   │   why: Objective asks to identify specific unnamed entities causing a specific effect.
│   ├── [ATOM] What is the current market share impact of AMD and custom silicon on NVIDIA?  (#5, ok, 212s, confidence high)
│   ├── [ATOM] What is the precise market share percentage of AMD in the 2026 data-center AI accelerator market?  (#8, ok, 203s, confidence low)
│   ├── [ATOM] What is the specific market share percentage of AMD in the 2026 data-center AI accelerator market?  (#9, ok, 84s, confidence medium)
│   └── [ATOM/verifier] AMD holds an estimated 6 to 8 percent share of the 2026 data-center AI accelerator market by revenue.  (#10, ok, 76s, verdict refuted)
├── [ATOM] Supply chain constraints and chip availability impacting revenue  (#4, ok, 221s, confidence high)
│       why: Specific factor analysis fits ATOM definition.
├── [ATOM] Investigate specific discounting percentages and strategies for NVIDIA H100/H200/B200 GPUs in Q3-Q4 2026.  (#6, ok, 211s, confidence low)
└── [ATOM] Analyze how secondary market dynamics influence official pricing and revenue projections.  (#7, ok, 221s, confidence medium)
```

## Statistics

```
  answer_seconds: 697.6
  wall_seconds: 697.6
  time_to_first_search_result: 28.484
  time_to_first_evidence: 77.847
  time_to_first_page_evidence: 77.847
  llm_calls: 75
  llm_calls_by_kind: {'route': 5, 'plan': 1, 'act': 36, 'deep_step': 4, 'extract': 13, 'answer': 9, 'review': 5, 'synthesize': 2}
  llm_failed_calls: 1
  llm_seconds: 690.63
  llm_queue_wait_seconds: 1112.92
  prompt_tokens: 53244
  output_tokens: 7979
  llm_prompt_eval_seconds: 236.54
  llm_generation_seconds: 402.65
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 5, 'deep_step:generative': 4, 'review:generative': 5}
  searches: 23
  fetches: 8
  web_calls: 31
  fetch_failures: 0
  search_failures: 0
  web_seconds: 49.38
  web_run_cache_hits: 4
  web_from_cassette: 0
  nodes: 11
  nodes_by_mode: {'WIDE': 1, 'ATOM': 9, 'DEEP': 1}
  nodes_by_role: {'research': 10, 'verifier': 1}
  nodes_by_status: {'ok': 11}
  max_depth: 2
  findings: 36
  findings_from_pages: 36
  findings_rejected: 0
  sources: 8
  source_domains: ['alatirok.com', 'axis-intelligence.com', 'content-site-lovat.vercel.app', 'gpusmith.com', 'jefferies.com', 'randtech.com', 'scribd.com', 'siliconanalysts.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 1
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 4
    pages_read_with_no_accepted_finding: 0
    nodes_with_no_evidence: 0
    nodes_cancelled: 0
  interventions: 3
  budget_hits: ['wrap_up']
```
