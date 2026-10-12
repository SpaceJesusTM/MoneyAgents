# Guards replayed over recorded runs

110 saved runs (recorded before the guards existed), page text for 107 recorded pages. No model, no network. See the module docstring of `experiments/bench/guard_replay.py` for what this can and cannot show.

## verify_guard

Claims sent to a verifier: **32**. Claims the guard would have refused because they only describe missing information: **6**. Verdicts those claims received at the time: {'survived': 6}.

| Task | Config | Verdict then | Claim that was sent |
|---|---|---|---|
| D1 | `baseline` | survived | The provided findings do not contain specific advanced-packaging capacity figures (units per year) or a projected annual growth rate for Amkor's $1.5 ... |
| D1 | `baseline` | survived | The provided findings do not contain specific advanced-packaging capacity figures (units per year) or a projected annual growth rate for Amkor's $1.5 ... |
| D1 | `baseline` | survived | The provided findings do not contain specific advanced-packaging capacity figures (units per year) or a projected annual growth rate for Amkor's $1.5 ... |
| D1 | `rules_lines` | survived | The provided findings do not specify the magnitude of Amkor's advanced-packaging capacity gap for NVIDIA in wafers per month, nor do they state the pr... |
| D1 | `typed_2b_plus` | survived | The provided findings do not contain the annual growth rate of Amkor Technology's advanced packaging capacity dedicated to NVIDIA's AI accelerators. T... |
| D1 | `rules_plus` | survived | The provided findings do not specify the magnitude of Amkor's advanced-packaging capacity gap for NVIDIA in wafers per month, nor do they state the pr... |

The other 26 claims would have been sent as they were (after dropping any clause that reports a gap). Examples:

- "Micron Technology" belongs in the answer to: Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?
- "Micron" belongs in the answer to: Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?
- "Samsung Electronics" belongs in the answer to: Which companies manufacture high-bandwidth memory (HBM) chips used in AI accelerators?
- AMD and custom silicon collectively account for approximately 25% to 30% of NVIDIA's data-center GPU market share in 2026.
- AMD holds an estimated 6 to 8 percent share of the 2026 data-center AI accelerator market by revenue.
- Amkor faces no specific advanced-packaging capacity constraints for NVIDIA's AI chips because it is actively expanding its U.S. footprint in

## claim_checks

Stored findings: **1087**; checked against their source text: **1087**.

| Outcome | Findings |
|---|---:|
| kept unchanged | 1047 |
| changed: unsupported clause dropped | 14 |
| rejected: figure not in the source text | 13 |
| rejected: basis label contradicts the passage | 7 |
| changed: basis label removed | 6 |

Distinct findings the checks would have rejected or changed (first 30):

| Task | Outcome | Claim as stored | Reason / claim after |
|---|---|---|---|
| A2 | rejected: figure not in the source text | Apple's Services revenue for fiscal year 2024 (the quarter ended September 28, 2024) was $23.1 billion. | figure $23.1 billion in the claim is not in the source text |
| W1 | changed: unsupported clause dropped | AMD's GAAP gross margin for the full year 2024 was 49%, which represents an increase of 1 percentage point compared to the previous quarter. | dropped a clause whose figure(s) 1 percentage point are not in or next to the quoted passage -> AMD's GAAP gross margin for the full year 2024 was 49%. |
| W1 | rejected: basis label contradicts the passage | For fiscal year 2025, NVIDIA's GAAP gross margin was 75.5%, representing an increase of 1.7 percentage points compared to the prior year. | claim says gaap but the passage is labelled non-gaap (heading) |
| W1 | changed: basis label removed | For Q4 of fiscal year 2024 (ended Dec 28, 2024), AMD's GAAP gross margin was 51%. | removed a GAAP/non-GAAP label the quoted passage does not show -> For Q4 of fiscal year 2024 (ended Dec 28, 2024), AMD's gross margin was 51% (GAAP or non-GAAP basis not shown in the quoted passage). |
| W1 | changed: basis label removed | For Q3 of fiscal year 2024 (ended Oct 29, 2024), AMD's GAAP gross margin was 50%. | removed a GAAP/non-GAAP label the quoted passage does not show -> For Q3 of fiscal year 2024 (ended Oct 29, 2024), AMD's gross margin was 50% (GAAP or non-GAAP basis not shown in the quoted passage). |
| M1 | changed: unsupported clause dropped | AMD holds an estimated 5–7% market share of the AI accelerator market in 2026, which contradicts the claim of 6 to 8 percent. | dropped a clause whose figure(s) 8 percent are not in or next to the quoted passage -> AMD holds an estimated 5–7% market share of the AI accelerator market in 2026. |
| M2 | changed: unsupported clause dropped | According to Jon Peddie Research data for Q1 2025, the AIB market reached 9.2 million units, with NVIDIA's share rising by 8.5% compared to its previous 84%. | dropped a clause whose figure(s) 84% are not in or next to the quoted passage -> According to Jon Peddie Research data for Q1 2025, the AIB market reached 9.2 million units. |
| M2 | changed: unsupported clause dropped | AMD's Data Center revenue reached a record $6.718 billion in Q2 FY2026, representing a 107% year-over-year increase. | dropped a clause whose figure(s) 107% are not in or next to the quoted passage -> AMD's Data Center revenue reached a record $6.718 billion in Q2 FY2026. |
| M1 | changed: unsupported clause dropped | In October 2025, one company controls over 80% of the AI accelerator market, while Intel's share sits at roughly 8.7% with a downward trajectory. | dropped a clause whose figure(s) 8.7% are not in or next to the quoted passage -> In October 2025, one company controls over 80% of the AI accelerator market. |
| W2 | rejected: figure not in the source text | Amazon's net revenue for the fiscal year ending December 31, 2024, was almost $500 billion U.S. dollars. | figure $500 billion in the claim is not in or next to the quoted passage |
| W2 | rejected: figure not in the source text | Amazon's brand worth as of 2025 amounts to over $470 billion U.S. dollars. | figure $470 billion in the claim is not in the source text |
| W2 | rejected: figure not in the source text | In 2025, approximately $470 billion U.S. dollars was earned in North America compared to roughly $130 billion U.S. dollars internationally. | figure $470 billion in the claim is not in or next to the quoted passage |
| M1 | rejected: figure not in the source text | NVIDIA's market share is down approximately 7-13 percentage points from 2023 to 2026, with AMD capturing roughly 5-7% of the data center AI accelerator market by revenue. | figure 13 percentage points in the claim is not in the source text |
| M1 | rejected: figure not in the source text | The page attributes NVIDIA's loss of ~7-13% market share primarily to diversification by hyperscalers (AWS, Google, Microsoft, Meta) investing in custom silicon for cost  | figure 13% in the claim is not in the source text |
| A1 | changed: unsupported clause dropped | NVIDIA's Data Center segment generated $39.3 billion in total revenue for fiscal 2025, with the fourth quarter alone contributing $35.6 billion. | dropped a clause whose figure(s) $35.6 billion are not in or next to the quoted passage -> NVIDIA's Data Center segment generated $39.3 billion in total revenue for fiscal 2025. |

## numeric_guard (ordering check on final answers)

Final answers: **110**; answers with an ordering statement contradicted by figures: **6**.

| Task | Config | What the check found |
|---|---|---|
| W2 | `baseline` | $350 billion is called the highest but $638 billion in the same sentence is larger |
| W2 | `baseline` | $350 billion is called the highest but $638 billion in the same sentence is larger |
| W2 | `batch_review` | $350 billion is called the highest but $638 billion in the same sentence is larger |
| W2 | `finish_first` | $350 billion is called the highest but $638 billion in the same sentence is larger |
| W2 | `baseline` | $350 billion is called the highest but $638 billion in the same sentence is larger |
| W2 | `experience` | $350 billion is called the highest but $638 billion in the same sentence is larger |
