# Recorded runs re-graded with the v2 grader

110 recorded runs from 6 result sets. The recorded results are unchanged; this file and `regrade.jsonl` are the only outputs.
Stored v1 scores that differ from a fresh v1 computation: **0** (0 means the v1 grader and the task fields it reads are as they were).

## What v2 changes

- **R1** (credit for something the answer says was not found): 5 runs
- **R2** (right figure, wrong accounting basis): 4 runs
- **R3** (ordering statement contradicted by the figures (quality capped at 0.5)): 6 runs
- **R4** (no gold fact found, yet v1 gave credit for citations (quality 0)): 22 runs

## Baseline, per task (mean over its recorded runs)

| Task | Runs | v1 quality | v2 quality | Rules that fired |
|---|---:|---:|---:|---|
| A1 | 3 | 1.00 | 1.00 | - |
| A2 | 4 | 0.25 | 0.00 | R4 |
| W1 | 3 | 0.89 | 0.78 | R2 |
| W2 | 3 | 0.83 | 0.50 | R3 |
| D1 | 3 | 0.67 | 0.00 | R4 |
| D2 | 3 | 0.75 | 0.75 | - |
| M1 | 3 | 0.80 | 0.80 | - |
| M2 | 2 | 1.00 | 1.00 | - |
| E1 | 3 | 1.00 | 1.00 | - |

## Per arm (all recorded runs of that arm)

| Arm | Runs | Mean v1 quality | Mean v2 quality | Runs changed by v2 |
|---|---:|---:|---:|---:|
| `baseline` | 27 | 0.77 | 0.61 | 13 |
| `rules` | 9 | 0.69 | 0.63 | 1 |
| `local_s1_4b` | 9 | 0.79 | 0.63 | 3 |
| `local_s1_2b` | 9 | 0.80 | 0.69 | 2 |
| `typed_2b_plus` | 9 | 0.77 | 0.63 | 3 |
| `rules_plus` | 9 | 0.81 | 0.71 | 3 |
| `rules_fixed` | 8 | 0.72 | 0.66 | 1 |
| `rules_lines` | 8 | 0.68 | 0.58 | 2 |
| `lines_extract` | 8 | 0.66 | 0.52 | 2 |
| `finish_first` | 4 | 0.91 | 0.80 | 2 |
| `batch_review` | 3 | 0.82 | 0.71 | 1 |
| `probing` | 3 | 0.81 | 0.78 | 1 |
| `pdf_8mb` | 2 | 0.25 | 0.00 | 2 |
| `experience` | 1 | 0.83 | 0.50 | 1 |
| `mock_jev` | 1 | 1.00 | 1.00 | 0 |

Arms ran different numbers and subsets of tasks, so the per-arm means are not comparable with each other; compare each arm's v1 and v2 columns.

## Every run whose score changed

| Set | Task | Arm | v1 | v2 | Why |
|---|---|---|---:|---:|---|
| baseline_v1 | A2 | `baseline` | 0.25 | 0.00 | no gold fact found |
| baseline_v1 | W1 | `baseline` | 0.89 | 0.78 | wrong basis: NVIDIA FY2025 gross margin 75.0% GAAP (75.5% non-GAAP) |
| baseline_v1 | W2 | `baseline` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
| baseline_v1 | D1 | `baseline` | 0.67 | 0.00 | no gold fact found |
| compare_v1 | A2 | `local_s1_4b` | 0.25 | 0.00 | no gold fact found |
| compare_v1 | A2 | `local_s1_2b` | 0.25 | 0.00 | no gold fact found |
| compare_v1 | A2 | `pdf_8mb` | 0.25 | 0.00 | no gold fact found |
| compare_v1 | A2 | `baseline` | 0.25 | 0.00 | no gold fact found |
| compare_v1 | W1 | `baseline` | 0.89 | 0.78 | wrong basis: NVIDIA FY2025 gross margin 75.0% GAAP (75.5% non-GAAP) |
| compare_v1 | W2 | `baseline` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
| compare_v1 | D1 | `baseline` | 0.67 | 0.00 | no gold fact found |
| compare_v1 | D1 | `rules` | 0.50 | 0.00 | no gold fact found |
| compare_v1 | D1 | `local_s1_4b` | 0.67 | 0.00 | no gold fact found |
| compare_v1 | D1 | `local_s1_2b` | 0.67 | 0.00 | no gold fact found |
| compare_v1 | D2 | `local_s1_4b` | 0.50 | 0.00 | no gold fact found |
| compare_v2 | A1 | `lines_extract` | 0.50 | 0.00 | no gold fact found |
| compare_v2 | A2 | `baseline` | 0.25 | 0.00 | no gold fact found |
| compare_v2 | W1 | `finish_first` | 1.00 | 0.89 | wrong basis: NVIDIA FY2025 gross margin 75.0% GAAP (75.5% non-GAAP) |
| compare_v2 | W1 | `baseline` | 0.89 | 0.78 | wrong basis: NVIDIA FY2025 gross margin 75.0% GAAP (75.5% non-GAAP) |
| compare_v2 | W2 | `batch_review` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
| compare_v2 | W2 | `finish_first` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
| compare_v2 | W2 | `baseline` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
| compare_v2 | D1 | `baseline` | 0.67 | 0.00 | no gold fact found |
| compare_v2 | D1 | `rules_fixed` | 0.50 | 0.00 | no gold fact found |
| compare_v2 | D1 | `rules_lines` | 0.67 | 0.00 | no gold fact found |
| compare_v2 | D1 | `lines_extract` | 0.67 | 0.00 | no gold fact found |
| compare_v2 | M1 | `rules_lines` | 0.80 | 0.70 | not-found credit: supply or manufacturing constraints |
| compare_v2 | M1 | `probing` | 0.65 | 0.55 | not-found credit: export controls / China / trade policy |
| compare_v3 | A1 | `typed_2b_plus` | 0.50 | 0.00 | no gold fact found |
| compare_v3 | D1 | `typed_2b_plus` | 0.67 | 0.00 | no gold fact found |
| compare_v3 | D1 | `rules_plus` | 0.67 | 0.00 | no gold fact found |
| compare_v3 | M1 | `rules_plus` | 0.80 | 0.70 | not-found credit: supply or manufacturing constraints |
| compare_v3 | M2 | `rules_plus` | 1.00 | 0.90 | not-found credit: competition |
| compare_v3 | M2 | `typed_2b_plus` | 1.00 | 0.90 | not-found credit: customer demand / hyperscalers |
| pdf_check | A2 | `baseline` | 0.25 | 0.00 | no gold fact found |
| pdf_check | A2 | `pdf_8mb` | 0.25 | 0.00 | no gold fact found |
| sanity | W2 | `experience` | 0.83 | 0.50 | ordering: $350 billion is called the highest but $638 billion in the same sentence is larger |
