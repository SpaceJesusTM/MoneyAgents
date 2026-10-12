# Which supplier's advanced-packaging capacity most constrains shipments of NVIDIA's latest AI accelerators, and how fast can that capacity grow?

_config: reliability | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: partial | confidence: low_

## Answer

Amkor is the primary supplier of advanced-packaging technology for NVIDIA's latest AI accelerators, confirmed by a $1.5 billion deal signed in October 2026 to expand U.S. production [S1]. This partnership involves jointly developing packaging and testing technologies to integrate different chip types into single packages [S1].

However, the specific advanced-packaging capacity figures (in units per year) and the projected annual growth rate for this deal could not be established from the available results. While the agreement confirms a commitment to strengthen domestic manufacturing capabilities in Arizona with prepayments made by late July 2026 [S2][S3], no quantitative data regarding maximum capacity or growth projections was provided [S4][S5].

Uncertainty: The research failed to identify a specific maximum capacity limit for Amkor's NVIDIA packaging operations, nor could an annual growth rate be determined. The results only confirm the existence and value of the expansion agreement without providing the necessary metrics to answer how fast that capacity can grow.

**Gaps reported by the system:** no evidence for: Amkor is the primary supplier of advanced packaging technology for NVIDIA's late; not established: What is the current maximum advanced-packaging capacity of Amkor for NVIDIA chips, and what is the projected a; What are the specific advanced-packaging capacity figures (in units per year) and projected annual growth rate

## Sources cited

[S1] Amkor, Nvidia&#x27;s Packaging Pick, Tackles Hidden AI Chip Bottleneck - Seoul Economic Daily - https://en.sedaily.com/international/2026/07/24/amkor-nvidias-packaging-pick-tackles-hidden-ai-chip (retrieved 2026-10-11)
[S2] Amkor Technology Announces Strategic Partnership with NVIDIA to Expand Advanced Packaging and Test for Next-Generation AI Infrastructure | Amkor Technology - https://ir.amkor.com/news-releases/news-release-details/amkor-technology-announces-strategic-partnership-nvidia-expand (retrieved 2026-10-11)
[S3] Nvidia, Amkor strike $1.5 billion chip packaging deal | Reuters - https://www.reuters.com/world/asia-pacific/nvidia-amkor-strike-15-billion-chip-packaging-deal-2026-07-23/ (retrieved 2026-10-11) (search snippet only; page not read)
[S4] NVIDIA Locks $1.5B Amkor Advanced Packaging Capacity: AI ... - https://www.seadivi.asia/nvidia-amkor-advanced-packaging-deal-analysis (retrieved 2026-10-11) (search snippet only; page not read)
[S5] Amkor Technology Announces Strategic Partnership with NVIDIA ... - https://secure.businesswire.com/news/home/20260723873230/en/Amkor-Technology-Announces-Strategic-Partnership-with-NVIDIA-to-Expand-Advanced-Packaging-and-Test-for-Next-Generation-AI-Infrastructure (retrieved 2026-10-11) (search snippet only; page not read)

## Grounding audit (programmatic, no model involved)

- citations: 5 (2 read pages, 3 snippet-only); unknown ids removed: 0
- figures in the answer: 3; found in the cited source: 1; found elsewhere in retrieved evidence: 2; not found in any retrieved text: 0
- sentences with figures but no citation: 1

## Consistency checks (programmatic, no model involved)

- ordering statements that contradict the figures: 0
- GAAP / non-GAAP labels that contradict the cited passage: 0
- quarter / full-year labels that contradict the finding: 0

## Agent tree

```
[DEEP] Which supplier's advanced-packaging capacity most constrains shipments of NVIDIA's latest AI accelerators, and how fast can that capacity grow?  (#0, partial, 1396s, verdict unverifiable)
│   why: Identifies specific unnamed entity (supplier) and dependent metric (growth speed).
│   ! no investigate rounds left (or repeated step); moving to verification
│   ! the latest result only reports missing information; verifying an earlier finding instead
│   ! verification sent before finishing
├── [ATOM] Who is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips?  (#1, ok, 37s, confidence high)
├── [ATOM] What is the current maximum advanced-packaging capacity of Amkor for NVIDIA chips, and what is the projected annual growth rate?  (#2, ok, 177s, confidence low)
│       ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging capacity annual growth'
│       ! repeated/empty query; read the next unread result instead
├── [ATOM] What are the specific advanced-packaging capacity figures (in units per year) and projected annual growth rate for Amkor's $1.5 billion deal with NVIDIA?  (#3, ok, 53s, confidence low)
│       ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging capacity per year'
│       ! no page evidence; used search snippets (3 findings)
└── [ATOM/verifier] Amkor is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips, evidenced by a $1.5 billion deal signed on October 23 to expand US production. The partnership involves jointly developing packaging and testing technology to combine different chip types into single packages. Amkor previously focused on simpler packaging. it is actively advancing its capabilities through such  (#4, failed, 1048s, verdict unverifiable)
        ! search returned nothing; retried as 'Amkor NVIDIA $1.5 billion deal October 23'
        ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging deal 2024 filing'
        ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging deal SEC filing'
        ! search returned nothing; retried as 'Amkor NVIDIA contract agreement SEC filing 2024'
```

## Statistics

```
  answer_seconds: 1396.3
  wall_seconds: 1396.3
  time_to_first_search_result: 10.2
  time_to_first_evidence: 26.719
  time_to_first_page_evidence: 26.719
  llm_calls: 29
  llm_calls_by_kind: {'route': 1, 'deep_step': 4, 'act': 16, 'extract': 3, 'answer': 3, 'snippet_extract': 1, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 377.23
  llm_queue_wait_seconds: 0
  prompt_tokens: 16655
  output_tokens: 2296
  llm_prompt_eval_seconds: 67.51
  llm_generation_seconds: 95.99
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 1, 'deep_step:generative': 4}
  searches: 15
  fetches: 5
  web_calls: 20
  fetch_failures: 3
  fetch_truncated: 0
  search_failures: 8
  web_seconds: 1018.82
  web_run_cache_hits: 1
  web_from_cassette: 12
  nodes: 5
  nodes_by_mode: {'DEEP': 1, 'ATOM': 4}
  nodes_by_role: {'research': 4, 'verifier': 1}
  nodes_by_status: {'partial': 1, 'ok': 3, 'failed': 1}
  max_depth: 1
  findings: 9
  findings_from_pages: 6
  findings_rejected: 0
  findings_adjusted: 0
  guard_events: {}
  sources: 5
  source_domains: ['en.sedaily.com', 'ir.amkor.com', 'reuters.com', 'seadivi.asia', 'secure.businesswire.com']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 0
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 1
    pages_read_with_no_accepted_finding: 1
    nodes_with_no_evidence: 1
    nodes_cancelled: 0
  interventions: 11
  budget_hits: []
```
