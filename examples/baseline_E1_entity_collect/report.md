# Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?

_config: baseline | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: ok | confidence: high_

## Answer

- Micron: Only non-Korean supplier qualified for HBM3E; business growing over 100% year-on-year. [S2, S5, S6] (3 of 3 search paths)
- SK Hynix: Holds 50-55% global HBM market share; leads manufacturer leaderboard for HBM. [S2, S3, S4, S5] (3 of 3 search paths)
- Samsung: Trails on HBM3E but racing on HBM4; part of top supplier set. [S2, S4, S5] (2 of 3 search paths)
- Samsung Electronics: Signed MOU with AMD for HBM4 supply; passed NVIDIA qualification for HBM3E. [S1] (1 of 3 search paths; independent check: survived [S7, S8, S9])

**Gaps reported by the system:** acronym/alias variants of the same entity may be listed separately

## Sources cited

[S2] Samsung and SK Hynix Lock In AI Chip Supply Through 2030 With $950B in US Deals - https://www.techtimes.com/articles/321554/20260725/samsung-sk-hynix-lock-ai-chip-supply-through-2030-950b-us-deals.htm (retrieved 2026-10-11)
[S5] Top HBM Memory Companies in 2026: SK hynix, Samsung, Micron - https://www.sourcebyspec.com/news/top-hbm-memory-companies-in-2026-sk-hynix-samsung-micron.html (retrieved 2026-10-11) (search snippet only; page not read)
[S6] NVIDIA&#x27;s HBM bottleneck - why Blackwell shipments depend on three Korean fabs · QuantAbundance - https://quantabundance.com/articles/nvda-hbm-bottleneck (retrieved 2026-10-11)
[S3] HBM Memory Market Share 2026: SK Hynix Holds 50-55%, Samsung ... - https://www.sourcebyspec.com/news/hbm-memory-market-share-2026-sk-hynix-holds-50-55-samsung-and-micron-chase-hbm4.html (retrieved 2026-10-11) (search snippet only; page not read)
[S4] HBM Market Share 2026: SK hynix vs Samsung vs Micron - presenc.ai - https://presenc.ai/research/hbm-market-share-samsung-skhynix-micron-2026 (retrieved 2026-10-11) (search snippet only; page not read)
[S1] HBM Pricing &amp; Market Share 2026: SK Hynix, Samsung - https://siliconanalysts.com/tools/hbm-analysis (retrieved 2026-10-11)
[S7] HBM | DRAM | Samsung Semiconductor Global - https://semiconductor.samsung.com/dram/hbm/ (retrieved 2026-10-11) (search snippet only; page not read)
[S8] The Perfect Harmony Created by Samsung HBM: Powering the AI Era - https://semiconductor.samsung.com/news-events/tech-blog/the-perfect-harmony-created-by-samsung-hbm-powering-the-ai-era/ (retrieved 2026-10-11) (search snippet only; page not read)
[S9] Samsung Elec to supply HBM4 chips to OpenAI, South Korean paper says - https://www.reuters.com/world/asia-pacific/samsung-elec-supply-hbm4-chips-openai-south-korean-paper-says-2026-03-19/ (retrieved 2026-10-11) (search snippet only; page not read)

## Grounding audit (programmatic, no model involved)

- citations: 9 (3 read pages, 6 snippet-only); unknown ids removed: 0
- figures in the answer: 3; found in the cited source: 0; found elsewhere in retrieved evidence: 3; not found in any retrieved text: 0
- sentences with figures but no citation: 2

## Agent tree

```
[ENTITY_COLLECT] Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?  (#0, ok, 251s, confidence high)
│   why: The answer is a list of entities that must be discovered.
├── [ATOM/collector] Find the official suppliers of High-Bandwidth Memory (HBM) for NVIDIA Blackwell and AMD MI300 architectures announced during Q4 2025 semiconductor supply chain reports.  (#1, ok, 185s, confidence medium)
│       ! search returned nothing; retried as 'NVIDIA Blackwell HBM supplier Q4 2025 AMD'
│       ! repeated/empty query; read the next unread result instead
│       ! asked to read result 1, which is not an unread result; read 2 instead
├── [ATOM/collector] Find recent news coverage from late 2025 detailing which memory manufacturers are securing multi-year contracts with major AI accelerator makers to meet 2026 data center demand.  (#2, ok, 162s, confidence medium)
│       ! search returned nothing; retried as 'memory manufacturers multi-year contracts AI accelerators 2026'
├── [ATOM/collector] Find the current market-share rankings for HBM3e and HBM4 modules published by industry analysts in early 2026, specifically focusing on tier-1 suppliers dominating the AI chip ecosystem.  (#3, ok, 172s, confidence medium)
│       ! no page evidence; used search snippets (3 findings)
└── [ATOM/verifier] "Samsung Electronics" belongs in the answer to: Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?  (#4, ok, 56s, verdict survived)
        ! search returned nothing; retried as 'Samsung Electronics manufacturer high-bandwidth memory AI accelerator'
        ! no page evidence; used search snippets (3 findings)
```

## Statistics

```
  answer_seconds: 251.2
  wall_seconds: 251.2
  time_to_first_search_result: 19.913
  time_to_first_evidence: 80.523
  time_to_first_page_evidence: 80.523
  llm_calls: 27
  llm_calls_by_kind: {'route': 1, 'entity_plan': 1, 'act': 16, 'extract': 3, 'snippet_extract': 2, 'answer': 4}
  llm_failed_calls: 0
  llm_seconds: 241.93
  llm_queue_wait_seconds: 309.12
  prompt_tokens: 16312
  output_tokens: 2997
  llm_prompt_eval_seconds: 73.56
  llm_generation_seconds: 151.48
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 1}
  searches: 13
  fetches: 6
  web_calls: 19
  fetch_failures: 3
  search_failures: 0
  web_seconds: 35.3
  web_run_cache_hits: 0
  web_from_cassette: 0
  nodes: 5
  nodes_by_mode: {'ENTITY_COLLECT': 1, 'ATOM': 4}
  nodes_by_role: {'research': 1, 'collector': 3, 'verifier': 1}
  nodes_by_status: {'ok': 5}
  max_depth: 1
  findings: 15
  findings_from_pages: 9
  findings_rejected: 0
  sources: 9
  source_domains: ['presenc.ai', 'quantabundance.com', 'reuters.com', 'semiconductor.samsung.com', 'siliconanalysts.com', 'sourcebyspec.com', 'techtimes.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 0
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 0
    pages_read_with_no_accepted_finding: 0
    nodes_with_no_evidence: 0
    nodes_cancelled: 0
  interventions: 7
  budget_hits: []
```
