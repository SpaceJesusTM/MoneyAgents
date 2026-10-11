### Per-arm summary (each arm on the tasks it ran)

| Arm | Runs | Quality | Fact recall | Coverage | Grounding | Median time (s) | Median first evidence (s) | Model calls | Decision calls | Web calls | Agents | Ref. model time (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 18 | 0.80 | 0.59 | 0.92 | 0.89 | 245.9 | 58.3 | 33.9 | 0 | 16.3 | 5.1 | 197.6 |
| rules | 9 | 0.69 | 0.52 | 0.72 | 0.72 | 106.4 | 24.6 | 7.2 | 0 | 7.1 | 3.4 | 63.6 |
| local_s1_4b | 9 | 0.79 | 0.52 | 0.92 | 0.94 | 261.8 | 41.0 | 14.8 | 17.9 | 11 | 3.7 | 138.7 |
| local_s1_2b | 9 | 0.80 | 0.62 | 0.92 | 0.83 | 94.0 | 32.5 | 11.3 | 15.7 | 9 | 3 | 109.4 |
| pdf_8mb | 1 | 0.25 | 0.00 | - | 0.50 | 38.0 | 22.8 | 7 | 0 | 4 | 1 | 34.4 |

### Paired comparison with the baseline

Paired against `baseline` on shared tasks. Time and model-time ratios below 1.00 mean faster.

| Arm | Shared tasks | Time ratio (median) | Ref. model-time ratio | First-evidence ratio | Model calls | Web calls | Quality (arm / base) | Gold facts lost | Preserves quality? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| rules | 9 | 0.42 | 0.43 | 0.66 | 7.2 / 33.9 | 7.1 / 16.3 | 0.69 / 0.80 | 3 | NO |
| local_s1_4b | 9 | 0.86 | 0.76 | 0.86 | 14.8 / 33.9 | 11 / 16.3 | 0.79 / 0.80 | 2 | NO |
| local_s1_2b | 9 | 0.60 | 0.70 | 0.54 | 11.3 / 33.9 | 9 / 16.3 | 0.80 / 0.80 | 1 | NO |
| pdf_8mb | 1 | 1.07 | 1.00 | 1.03 | 7 / 7 | 4 / 4 | 0.25 / 0.25 | 0 | yes |

### Baseline run-to-run spread

- A1: 2 baseline runs, time 40-42 s (spread 5%), ref. model time 36-36 s, quality 1.0-1.0
- A2: 2 baseline runs, time 33-38 s (spread 12%), ref. model time 34-34 s, quality 0.25-0.25
- W1: 2 baseline runs, time 346-388 s (spread 12%), ref. model time 244-244 s, quality 0.889-0.889
- W2: 2 baseline runs, time 154-160 s (spread 4%), ref. model time 114-114 s, quality 0.833-0.833
- D1: 2 baseline runs, time 241-295 s (spread 20%), ref. model time 170-170 s, quality 0.667-0.667
- D2: 2 baseline runs, time 44-49 s (spread 11%), ref. model time 31-31 s, quality 0.75-0.75
- M1: 2 baseline runs, time 698-715 s (spread 2%), ref. model time 475-497 s, quality 0.8-0.8
- M2: 2 baseline runs, time 703-732 s (spread 4%), ref. model time 485-490 s, quality 1.0-1.0
- E1: 2 baseline runs, time 251-268 s (spread 7%), ref. model time 174-174 s, quality 1.0-1.0

### Per task

Each cell: time to answer (s) / quality / agents. `!` marks a budget limit hit.

| Task | baseline | rules | local_s1_4b | local_s1_2b | pdf_8mb |
|---|---|---|---|---|---|
| A1 | 41 / 1.00 / 1 | 23 / 1.00 / 1 | 30 / 1.00 / 1 | 25 / 1.00 / 1 |  |
| A2 | 36 / 0.25 / 1 | 16 / 0.00 / 1 | 39 / 0.25 / 1 | 31 / 0.25 / 1 | 38 / 0.25 / 1 |
| W1 | 367 / 0.89 / 6 | 154 / 0.89 / 3 | 424 / 1.00 / 6 | 194 / 0.56 / 4 |  |
| W2 | 157 / 0.83 / 4 | 18 / 0.00 / 3 | 135 / 0.89 / 4 | 94 / 0.89 / 4 |  |
| D1 | 268 / 0.67 / 5 | 113 / 0.50 / 4 | 327 / 0.67 / 5 | 247 / 0.67 / 5 |  |
| D2 | 47 / 0.75 / 1 | 70 / 1.00 / 3 | 37 / 0.50 / 1 | 38 / 1.00 / 1 |  |
| M1 | 706 / 0.80 / 11 | 189 / 0.80 / 5 | 342 / 0.80 / 5 | 275 / 0.80 / 5 |  |
| M2 | 718 / 1.00 / 12 | 106 / 1.00 / 5 | 373 / 1.00 / 5 | 266 / 1.00 / 5 |  |
| E1 | 260 / 1.00 / 5 | 148 / 1.00 / 6 | 262 / 1.00 / 5 | 62 / 1.00 / 1 |  |
