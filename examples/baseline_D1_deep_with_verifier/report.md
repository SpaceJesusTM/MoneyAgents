# Which supplier's advanced-packaging capacity most constrains shipments of NVIDIA's latest AI accelerators, and how fast can that capacity grow?

_config: baseline | model: qwen3.5:4b-q4_K_M | decider: generative | web: replay_or_record | status: ok | confidence: high_

## Answer

Amkor is the primary supplier of advanced-packaging technology for NVIDIA's latest AI accelerators, confirmed by a $1.5 billion deal signed in late July 2026 to expand U.S. production in Arizona [S1][S4]. This partnership involves jointly developing packaging and testing technologies to integrate different chip types into single packages [S1].

However, the specific advanced-packaging capacity figures (in units per year) and the projected annual growth rate for this deal could not be established. Despite multiple sub-objectives seeking these quantitative metrics, all provided sources explicitly state that such data is missing. The findings only confirm the financial value of the agreement, its location, and its timing [S2][S3][S5][S6][S7]. There are no conflicting results regarding capacity numbers; rather, there is a consistent absence of this information across all cited documents.

Uncertainty:
The research could not determine Amkor's current maximum advanced-packaging capacity for NVIDIA chips nor its projected annual growth rate. The available evidence confirms the existence and value of the partnership but lacks the specific production volume data required to answer how fast that capacity can grow.

## Sources cited

[S1] Amkor, Nvidia&#x27;s Packaging Pick, Tackles Hidden AI Chip Bottleneck - Seoul Economic Daily - https://en.sedaily.com/international/2026/07/24/amkor-nvidias-packaging-pick-tackles-hidden-ai-chip (retrieved 2026-10-11)
[S4] NVIDIA Locks $1.5B Amkor Advanced Packaging Capacity: AI ... - https://www.seadivi.asia/nvidia-amkor-advanced-packaging-deal-analysis (retrieved 2026-10-11) (search snippet only; page not read)
[S2] Amkor Technology Announces Strategic Partnership with NVIDIA to Expand Advanced Packaging and Test for Next-Generation AI Infrastructure | Amkor Technology - https://ir.amkor.com/news-releases/news-release-details/amkor-technology-announces-strategic-partnership-nvidia-expand (retrieved 2026-10-11)
[S3] Nvidia, Amkor strike $1.5 billion chip packaging deal | Reuters - https://www.reuters.com/world/asia-pacific/nvidia-amkor-strike-15-billion-chip-packaging-deal-2026-07-23/ (retrieved 2026-10-11) (search snippet only; page not read)
[S5] Amkor Technology Announces Strategic Partnership with NVIDIA ... - https://secure.businesswire.com/news/home/20260723873230/en/Amkor-Technology-Announces-Strategic-Partnership-with-NVIDIA-to-Expand-Advanced-Packaging-and-Test-for-Next-Generation-AI-Infrastructure (retrieved 2026-10-11) (search snippet only; page not read)
[S6] Nvidia signs $1.5 billion deal with Amkor Technology to boost U.S ... - https://thebuildout.ai/intel/9a939572-818f-418e-ac8d-ed56acdff437 (retrieved 2026-10-11) (search snippet only; page not read)
[S7] Amkor inks $1.5B deal with Nvidia to expand Arizona chip packaging capacity - https://www.bizjournals.com/phoenix/news/2026/07/23/nvidia-amkor-chip-packaging-agreement.html (retrieved 2026-10-11) (search snippet only; page not read)

## Grounding audit (programmatic, no model involved)

- citations: 7 (2 read pages, 5 snippet-only); unknown ids removed: 0
- figures in the answer: 2; found in the cited source: 0; found elsewhere in retrieved evidence: 2; not found in any retrieved text: 0
- sentences with figures but no citation: 1

## Agent tree

```
[DEEP] Which supplier's advanced-packaging capacity most constrains shipments of NVIDIA's latest AI accelerators, and how fast can that capacity grow?  (#0, ok, 241s, verdict survived)
│   why: Identifies specific unnamed entity (supplier) and dependent metric (growth speed).
│   ! no investigate rounds left (or repeated step); moving to verification
│   ! verification sent before finishing
├── [ATOM] Who is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips?  (#1, ok, 39s, confidence high)
├── [ATOM] What is the current maximum advanced-packaging capacity of Amkor for NVIDIA chips, and what is the projected annual growth rate?  (#2, ok, 49s, confidence low)
│       ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging capacity annual growth'
│       ! repeated/empty query; read the next unread result instead
├── [ATOM] What are the specific advanced-packaging capacity figures (in units per year) and projected annual growth rate for Amkor's $1.5 billion deal with NVIDIA?  (#3, ok, 57s, confidence low)
│       ! search returned nothing; retried as 'Amkor NVIDIA advanced packaging capacity per year'
│       ! no page evidence; used search snippets (3 findings)
└── [ATOM/verifier] The provided findings do not contain specific advanced-packaging capacity figures (units per year) or a projected annual growth rate for Amkor's $1.5 billion deal with NVIDIA. The text confirms the deal value, location (Arizona), and timing (late July 2026) but lacks quantitative production data or growth projections.  (#4, ok, 54s, verdict survived)
        ! no page evidence; used search snippets (3 findings)
```

## Statistics

```
  answer_seconds: 240.6
  wall_seconds: 240.6
  time_to_first_search_result: 13.151
  time_to_first_evidence: 31.555
  time_to_first_page_evidence: 31.555
  llm_calls: 31
  llm_calls_by_kind: {'route': 1, 'deep_step': 4, 'act': 16, 'extract': 3, 'answer': 4, 'snippet_extract': 2, 'synthesize': 1}
  llm_failed_calls: 0
  llm_seconds: 212.05
  llm_queue_wait_seconds: 0
  prompt_tokens: 19145
  output_tokens: 2663
  llm_prompt_eval_seconds: 73.02
  llm_generation_seconds: 119.37
  decision_calls: 0
  decision_seconds: 0
  decision_prompt_tokens: None
  decisions: {'route:generative': 1, 'deep_step:generative': 4}
  searches: 9
  fetches: 6
  web_calls: 15
  fetch_failures: 4
  search_failures: 0
  web_seconds: 30.51
  web_run_cache_hits: 2
  web_from_cassette: 0
  nodes: 5
  nodes_by_mode: {'DEEP': 1, 'ATOM': 4}
  nodes_by_role: {'research': 4, 'verifier': 1}
  nodes_by_status: {'ok': 5}
  max_depth: 1
  findings: 12
  findings_from_pages: 6
  findings_rejected: 0
  sources: 7
  source_domains: ['bizjournals.com', 'en.sedaily.com', 'ir.amkor.com', 'reuters.com', 'seadivi.asia', 'secure.businesswire.com', 'thebuildout.ai']
  redundancy:
    objectives_dropped_as_duplicate: 0
    near_duplicate_objective_pairs: 0
    repeated_queries: 0
    urls_read_by_more_than_one_agent: 1
    pages_read_with_no_accepted_finding: 1
    nodes_with_no_evidence: 0
    nodes_cancelled: 0
  interventions: 7
  budget_hits: []
```
