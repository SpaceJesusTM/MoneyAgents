### Per-arm summary (each arm on the tasks it ran)

| Arm | Runs | Quality | Fact recall | Coverage | Grounding | Median time (s) | Median first evidence (s) | Model calls | Decision calls | Web calls | Agents | Ref. model time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 8 | 0.77 | 0.59 | 0.90 | 0.88 | 194.9 | 44.5 | 27.5 | 0 | 13.1 | 4.2 | 159.6 |
| rules_fixed | 8 | 0.72 | 0.62 | 0.90 | 0.69 | 90.2 | 20.1 | 8.1 | 0 | 7.5 | 3.5 | 70.2 |
| rules_lines | 8 | 0.68 | 0.62 | 0.90 | 0.62 | 91.7 | 18.9 | 8.2 | 0 | 7.8 | 3.6 | 57.3 |
| lines_extract | 8 | 0.67 | 0.50 | 0.95 | 0.69 | 190.8 | 57.6 | 25.9 | 0 | 12.8 | 4 | 139.4 |
| batch_review | 3 | 0.82 | 1.00 | 0.87 | 0.67 | 362.9 | 70.9 | 41.3 | 0 | 18.7 | 6.3 | 251.2 |
| probing | 3 | 0.81 | 0.83 | 0.82 | 0.83 | 249.3 | 63.1 | 31.7 | 0 | 15 | 4.7 | 167.7 |
| finish_first | 4 | 0.91 | 1.00 | 0.87 | 0.88 | 341.6 | 59.6 | 42 | 0 | 20.5 | 6.5 | 262.4 |

### Paired comparison with the baseline

Paired against `baseline` on shared tasks. Time and model-time ratios below 1.00 mean faster.

| Arm | Shared tasks | Time ratio (median) | Ref. model-time ratio | First-evidence ratio | Model calls | Web calls | Quality (arm / base) | Gold facts lost | Preserves quality? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| rules_fixed | 8 | 0.52 | 0.47 | 0.56 | 8.1 / 27.5 | 7.5 / 13.1 | 0.72 / 0.77 | 2 | NO |
| rules_lines | 8 | 0.46 | 0.39 | 0.31 | 8.2 / 27.5 | 7.8 / 13.1 | 0.68 / 0.77 | 2 | NO |
| lines_extract | 8 | 0.84 | 0.86 | 0.91 | 25.9 / 27.5 | 12.8 / 13.1 | 0.67 / 0.77 | 2 | NO |
| batch_review | 3 | 1.06 | 0.95 | 0.99 | 41.3 / 47 | 18.7 / 20 | 0.82 / 0.84 | 0 | yes |
| probing | 3 | 0.73 | 0.64 | 1.13 | 31.7 / 47 | 15 / 20 | 0.81 / 0.84 | 1 | NO |
| finish_first | 4 | 1.07 | 1.00 | 0.82 | 42 / 42 | 20.5 / 19.8 | 0.91 / 0.88 | 0 | yes |

### Baseline run-to-run spread

(only one baseline run per task: no run-to-run spread available)

### Per task

Each cell: time to answer (s) / quality / agents. `!` marks a budget limit hit.

| Task | baseline | rules_fixed | rules_lines | lines_extract | batch_review | probing | finish_first |
|---|---|---|---|---|---|---|---|
| A1 | 46 / 1.00 / 1 | 26 / 1.00 / 1 | 24 / 1.00 / 1 | 44 / 0.50 / 1 |  |  |  |
| A2 | 41 / 0.25 / 1 | 18 / 0.00 / 1 | 17 / 0.00 / 1 | 35 / 0.00 / 1 |  |  |  |
| W1 | 343 / 0.89 / 6 | 211 / 0.67 / 4 | 120 / 0.67 / 4 | 252 / 0.67 / 4 | 363 / 0.83 / 6 | 249 / 1.00 / 4 | 434 / 1.00 / 6 |
| W2 | 135 / 0.83 / 4 | 64 / 0.78 / 4 | 41 / 0.78 / 4 | 166 / 0.83 / 4 | 143 / 0.83 / 4 | 221 / 0.78 / 5 | 151 / 0.83 / 4 |
| D1 | 274 / 0.67 / 5 | 116 / 0.50 / 4 | 152 / 0.67 / 5 | 223 / 0.67 / 5 |  |  |  |
| D2 | 50 / 0.75 / 1 | 64 / 1.00 / 3 | 64 / 0.50 / 3 | 35 / 0.75 / 1 |  |  |  |
| M1 | 719 / 0.80 / 11 | 188 / 0.80 / 5 | 157 / 0.80 / 5 | 690 / 0.90 / 11 | 610 / 0.80 / 9 | 309 / 0.65 / 5 | 735 / 0.80 / 11 |
| E1 | 255 / 1.00 / 5 | 154 / 1.00 / 6 | 130 / 1.00 / 6 | 216 / 1.00 / 5 |  |  | 250 / 1.00 / 5 |
