# model_compare_v1

| Task | Arm | Model | v1 / v2 | Status, confidence | Model calls | Prompt / output tokens | Time to answer | Model work | Searches: replayed / live / unanswered | Pages: replayed / live / unanswered | Limits hit |
|---|---|---|---|---|---:|---|---:|---:|---|---|---|
| A1 | `reliability` | 4b | 1.0 / 1.0 | ok, high | 7 | 4623 / 509 | 42.8 s | 36 s | 1 / 0 / 0 | 1 / 0 / 0 | - |
| A1 | `reliability_9b` | 9b | 1.0 / 1.0 | ok, high | 8 | 5250 / 464 | 144.0 s | 128 s | 0 / 1 / 0 | 1 / 1 / 0 | - |
| W1 | `reliability` | 4b | 0.889 / 0.889 | partial, medium | 47 | 33206 / 5401 | 520.2 s | 511 s | 5 / 4 / 1 | 6 / 0 / 0 | - |
| W1 | `reliability_9b` | 9b | 0.556 / 0.556 | partial, high | 27 | 17372 / 3215 | 972.0 s | 583 s | 0 / 3 / 0 | 3 / 1 / 0 | max_seconds, wrap_up |
| W2 | `reliability` | 4b | 1.0 / 1.0 | ok, medium | 43 | 24748 / 3027 | 390.3 s | 378 s | 2 / 5 / 3 | 4 / 2 / 0 | - |
| W2 | `reliability_9b` | 9b | 0.889 / 0.889 | ok, high | 30 | 17487 / 1784 | 384.4 s | 376 s | 0 / 3 / 0 | 6 / 1 / 0 | - |
| D1 | `reliability` | 4b | 0.667 / 0.0 | partial, medium | 31 | 18769 / 2642 | 347.8 s | 316 s | 4 / 6 / 0 | 2 / 0 / 0 | - |
| D1 | `reliability_9b` | 9b | 0.0 / 0.0 | failed, low | 10 | 6013 / 396 | 125.1 s | 119 s | 0 / 2 / 0 | 0 / 2 / 0 | - |
| D2 | `reliability` | 4b | 0.75 / 0.75 | ok, high | 7 | 4119 / 440 | 63.3 s | 55 s | 3 / 0 / 0 | 1 / 0 / 0 | - |
| D2 | `reliability_9b` | 9b | 1.0 / 1.0 | ok, high | 18 | 9967 / 2054 | 346.4 s | 334 s | 0 / 2 / 0 | 0 / 3 / 0 | - |

## Memory (sampled every 5 s; swap is system-wide)

| Arm | Minutes sampled | Runner peak | Swap start / peak / end (MB) | Pageouts | Swapouts | Lowest free memory |
|---|---:|---:|---|---:|---:|---:|
| 4b | 21.3 | 4231 MB | 31924 / 38409 / 38409 | 518 | 1764060 | 26% |
| 9b | 18.5 | 6640 MB | 38290 / 42770 / 42607 | 741 | 1870352 | 22% |
| 9b_part2 | 14.1 | 6801 MB | 42733 / 47199 / 47199 | 403 | 2028292 | 22% |
