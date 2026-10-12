# Reliability improvements

A focused follow-up to the baseline and optimization work, done on 2026-10-11. It addresses four
failures recorded in `BASELINE_RESULTS.md`: a DEEP verifier that "verified" a statement about
missing data (D1), a non-GAAP figure reported as GAAP (W1), a wrong ranking of correct figures
(W2), and a 4.9 MB filing that was silently truncated (A2). It also adds a stricter grader.

**Everything is opt-in.** The frozen baseline behaves exactly as it was measured, and no recorded
result was changed. The patched version is one config file:

```bash
.venv/bin/python -m webswarm_baseline.run "your question" --config webswarm_baseline/configs/reliability_v1.json
```

## Summary

| Objective | Original failure | Status | Shown live? |
|---|---|---|---|
| 1. DEEP verification | D1: "The provided findings do not contain ... capacity figures" was sent to the verifier, came back `survived`, and the answer was labelled verified, high confidence | **Fixed, opt-in** (`verify_guard`). The wrong answer itself (Amkor, not TSMC) is not fixed | The refusal and the downgraded answer: yes, one run. A verifier completing a check under the guard: no, scripted only, because web search was down |
| 2. Numerical correctness | W2: Alphabet ($350 billion) ranked above Amazon ($638 billion) | **Fixed, opt-in** (`numeric_guard`) | Yes, two identical runs: ranking right on the first draft |
| | W1: NVIDIA's non-GAAP 75.5% reported as GAAP | **Fixed, opt-in** (`claim_checks`): gone in all six patched runs. Removing it exposed a second error, a quarterly figure reported as the fiscal-year one. That is now caught and, in the final run, removed, but it took five revisions to get there (see "W1, run by run") | Detection: yes, every run. Removal: once, on the finished code |
| 3. Oversized PDFs | A2: Apple's 4,919,216-byte filing cut at 3 MB and reported as "no extractable text" | **Fixed, opt-in** (`oversize_policy=fail`, `max_pdf_bytes`) | Yes: the filing was read and A2 answered correctly |
| 4. Tests and evaluation | The grader scored the W1 and W2 errors 0.89 and 0.83 | 82 new tests; a v2 grader; re-grade and replay tools | Not applicable (no model involved) |

Tests: **191 pass** (109 before this pass, 82 new).

## The baseline is unchanged

| Check | Result |
|---|---|
| Tag `webswarm-baseline-v1` | Still points at commit `6458038` |
| `webswarm_baseline/configs/baseline.json` | Not edited. Every new switch defaults to the old behaviour, and a test asserts the frozen config equals the defaults |
| Baseline re-run on the finished code (A1, W2, D1, replayed web) | **Identical to every recorded baseline row for those tasks**: same model calls, prompt tokens, output tokens, web calls, status, confidence, and the same answer text character for character |
| Recorded results (`experiments/results/baseline_v1`, `compare_v1..3`, `pdf_check`, `sanity`) | Not edited. Re-grading writes to a new folder; recomputing the v1 score for all 110 recorded runs gives the stored value every time |
| `BASELINE_RESULTS.md`, `OPTIMIZATION_RESULTS.md`, `OVERNIGHT_PROGRESS.md`, the ten earlier folders in `examples/` | Not edited. `examples/` gained five new folders and a section in its README |
| `one_shot_webswarm_prototype/` | Not edited |

One thing the baseline path does gain: when a response is cut off, the fetch record and trace now
carry `truncated: true`. That is a label only; what the baseline does with the content is the same.

## What changed

All checks are deterministic code in `webswarm_baseline/guards.py` (regular expressions and
arithmetic, no model). The only extra model calls are single retries after a check has failed.
First-attempt prompts are untouched, with one exception noted under `numeric_guard`.

### 1. `verify_guard`: what a verifier may be asked, and when its verdict counts

**What went wrong in D1.** After three investigate steps the model asked its last question again.
The engine then picked "the most recent investigate answer" as the claim to verify. That answer
was a report of what had not been found. The verifier agreed that it had not been found, returned
`survived`, and the engine mapped `survived` to verified, high confidence.

Replaying the recorded runs shows this was systematic: of 32 claims sent to verifiers across 110
recorded runs, **6 were statements about missing information, all on D1, across four
configurations, and all 6 came back `survived`**.

**What the guard does.**

- The claim sent to a verifier is the newest statement that asserts something about the world.
  Clauses that report a gap ("do not contain", "could not be established", "no figure was
  reported", "lacks ... data") and clauses about the evidence itself ("The text confirms ...",
  "They only confirm ...") are removed. The model's own verify text gets the same treatment.
- If nothing checkable is left, no verifier is sent. The answer has no verdict and says so.
- A verdict other than `unverifiable` must cite evidence, and `survived` is not accepted when the
  verifier's own explanation only describes missing information.
- A DEEP answer whose last steps came back empty-handed is `partial`, lists what was not
  established, and cannot be `high` confidence. The same applies when the verdict rests on search
  snippets alone.

A negative fact stays checkable: "Intel does not manufacture Apple's iPhone processors" is a claim
about the world, not about the search.

**What it does not do.** It does not make D1's answer right. Every arm named Amkor because search
results were dominated by an Amkor deal; that is a retrieval and model problem. The guard stops
that answer from being presented as verified.

### 2. `claim_checks`: figures and labels must come from the source

**When a finding is extracted**, before it becomes evidence:

- **Figures.** A figure that is nowhere in the source text rejects the finding. This stops
  invented numbers (A2's "$23.1 billion" attached to a real sentence) and numbers the model
  computed itself. A trailing clause whose figure is not in or next to the quote is cut:
  "AMD's GAAP gross margin for the full year 2024 was 49%, ~~which represents an increase of 1
  percentage point compared to the previous quarter~~". Rounding and unit changes are allowed
  ("$130.5 billion" against "130,497").
- **Accounting basis.** A GAAP or non-GAAP label in the claim is compared with what the passage
  shows: a label inside the quote, a `GAAP` / `Non-GAAP` heading line above a table row, or an
  unlabelled figure followed by "On a non-GAAP basis ...". A contradiction rejects the finding.
  This is the W1 case: the quoted row sat under the `Non-GAAP` heading of NVIDIA's table. A label
  the passage does not show at all is removed and the claim says the basis was not shown.

**When an answer is written** (added during live testing, see "W1, run by run"): each figure must
keep the period, quarter or full year, and the basis of the finding it came from.

- A single agent's answer that breaks this is asked for once more with the problem named. If the
  second draft is still wrong, the written answer is dropped and the agent returns its findings as
  extracted, low confidence, with a one-line fact for its parent ("73.0% is the figure for a
  quarter, not for the full year").
- A manager's synthesis gets the same check and one retry. If the problem remains it is listed as a
  gap and the answer is `partial`.
- The final audit runs the checks once more. Anything still wrong makes the outcome `partial`, at
  most `medium` confidence, and is named in the reported gaps.

### 3. `numeric_guard`: rankings are computed, then checked

For an objective that compares named entities on one kind of figure ("compare the revenue of A, B
and C"):

- The engine picks one figure per entity from the sub-results (skipping quarterly figures when a
  year was asked for, and "up from" baselines), sorts them, and appends the sorted list to the
  synthesis prompt. **This is the one first-attempt prompt change in the pass**, about 60 tokens,
  and only for comparison objectives.
- The written answer is checked for ordering statements that contradict figures: a superlative
  with a larger figure attached to another name in the same sentence, "X is higher than Y" the
  wrong way round, or a named entity called highest or lowest against the computed order.
- On a contradiction the synthesis is asked once more with the problem named. If it is still
  wrong, the draft is kept and a labelled correction is appended ("Correction (computed from the
  figures, not written by the model): ..."). Nothing the model wrote is deleted, and the answer
  becomes `partial` and at most `medium` confidence.
- If the compared figures are on different bases (one GAAP, one non-GAAP) or periods (one quarter,
  one year), the prompt and the reported gaps say so. If an entity's sub-result gives several
  different figures, it is not ranked and the model is told to say which figure it uses.

### 4. `oversize_policy=fail`, `max_pdf_bytes`, `pdf_max_pages`: no silent truncation

The baseline stopped reading at 3 MB and parsed whatever had arrived. For a PDF that means no text
and the misleading error "no extractable text (script-rendered or empty page)". The same silent
acceptance applied to a download cut off by the time limit or a dropped connection.

With `oversize_policy=fail`:

- A response whose declared length exceeds the limit is refused **before any of its body is
  downloaded**. One with no declared length is never read past the limit.
- Any incomplete body is an explicit error and nothing from it is parsed:
  `too large: 9,400,000 bytes declared, limit 8,000,000; nothing parsed`. The agent tree shows it.
- PDFs have their own limit (`max_pdf_bytes`, 8 MB in `reliability_v1.json`); everything else
  stays at 3 MB.
- A long PDF is read up to `pdf_max_pages` (40) and the result says how much was read
  ("read 20 of 110 PDF pages").

Bounds on a PDF: 8 MB of download, 40 pages, 80,000 characters of text, 15 seconds of parsing
(checked between pages), plus pypdf's own limits on decompressed stream sizes. Up to four fetches
run at once, so up to four such files can be in memory together; peak memory was not measured.
Parsing still happens in the main process, and one pathological page cannot be interrupted. A
subprocess with a hard timeout would close that; I left it out to keep the change small.

**Recordings.** Web recordings are keyed by URL, so a truncated recording would be replayed
whatever the limit is now. With `oversize_policy=fail`, a recording of a cut-off body is either
re-fetched under a second key that names the limit (when a larger limit applies and recording is
allowed) or turned into the explicit failure. The original recording is never overwritten, so the
baseline replays exactly what it recorded.

### 5. Evaluation: a stricter grader, kept beside the old one

`experiments/bench/grade.py` (v1) is unchanged and every table in `OPTIMIZATION_RESULTS.md` still
means what it meant. `grade_v2.py` removes credit v1 should not have given:

| Rule | v1 behaviour | v2 |
|---|---|---|
| R1 | A fact or coverage point "found" in a clause that says it was not found | Not credited |
| R2 | The right figure under the wrong accounting basis | Not credited |
| R3 | Correct figures, then an ordering statement they contradict | Quality capped at 0.5 |
| R4 | No gold fact found, but citations earned grounding credit | Quality 0 |

The recorded baseline under both graders (mean over its recorded runs of each task):

| Task | v1 | v2 | Why |
|---|---:|---:|---|
| A1 | 1.00 | 1.00 | |
| A2 | 0.25 | 0.00 | "not found" plus an invented figure no longer scores |
| W1 | 0.89 | 0.78 | NVIDIA's 75.5% was called GAAP |
| W2 | 0.83 | 0.50 | wrong ranking |
| D1 | 0.67 | 0.00 | neither gold fact (TSMC, CoWoS) is in the answer |
| D2, M1, M2, E1 | 0.75, 0.80, 1.00, 1.00 | same | |

These now line up with how I judged the answers by reading them in `BASELINE_RESULTS.md`, except
D2: "Intel Foundry" is wrong, but Arizona is right and the answer is cited, so it still scores 0.75.
v2 cannot see a wrong name next to a right one, and it has no rule for a wrong period. Full tables
for all 110 recorded runs: `experiments/results/regrade_v2/summary.md`.

## Evidence without a model: replaying the guards over the recorded runs

`experiments/bench/guard_replay.py` runs the checks over the 110 runs recorded before the guards
existed. Output: `experiments/results/regrade_v2/guard_replay.md`.

| Guard | What it would have done |
|---|---|
| `verify_guard` | Refused 6 of 32 verifier claims, all on D1, all of which had come back `survived`. The other 26 would have been sent |
| `claim_checks`, at extraction | Of 1,087 stored findings: 1,047 unchanged, 20 rejected (13 for a figure not in the source, 7 for a contradicted basis label), 20 changed (14 with a clause cut, 6 with a basis label removed) |
| `claim_checks`, period labels in answers | 0 flags in 395 recorded answers |
| `numeric_guard` | Flagged 6 of 110 final answers. All 6 are the W2 ranking error, which recurred in every arm that shared the baseline's synthesis |

I read every distinct rejected or changed finding (7 and 8). All 7 rejections were justified: 4
invented figures, 2 computed by the model, and the W1 mislabel. Of the 8 changes, 7 removed a wrong
or unsupported clause or label. One left a claim that was already wrong ("NVIDIA's Data Center
segment generated $39.3 billion in total revenue for fiscal 2025" is the fourth-quarter company
total); the check did not cause that error and cannot catch it.

**Caveat on these counts.** The rules were adjusted while looking at this same recorded data. An
earlier version of the figure check would have rejected the only finding carrying Intel's gross
margin, and the period rule went through four versions before it stopped raising false alarms here.
Zero false alarms on data the rules were tuned on is weaker evidence than it sounds. One false
alarm did occur live (W1, third run) and is now a regression test.

## Live results

Real local model (`qwen3.5:4b-q4_K_M`), patched config, web replayed from the baseline's
recordings where the same request was made and live otherwise. Raw rows:
`experiments/results/reliability_v1/results.jsonl` (23 runs: 17 patched, 6 baseline). Five runs
are saved in `examples/reliability_*`.

Results on the finished code:

| Task | Baseline (recorded) v1 / v2 | Patched v1 / v2 | Model calls (baseline / patched) | What happened |
|---|---|---|---|---|
| A2 | 0.25 / 0.00 | **1.00 / 1.00** | 7 / 9 | The agent opened the same PDF first, as in the baseline. Under the 8 MB limit it downloaded (4,919,216 bytes, 4 pages) and yielded "Services ... 96,169". Answer: "Apple's Services revenue for the twelve months ended September 28, 2024 was $96,169 million", cited to apple.com. The claim check also rejected the invented "$23.1 billion" finding that the baseline had stored |
| W2 | 0.83 / 0.50 | **0.83 / 0.83** | 26 / 27 | The sorted figures were in the prompt and the first draft ranked them correctly: "Amazon ... $638 billion, followed by Alphabet at $350.0 billion, and Microsoft at $245.12 billion". No retry was needed. v1 does not move because v1 never saw the error |
| W1 | 0.89 / 0.78 | **1.00 / 1.00** | 44 / 39 | NVIDIA 75.5% non-GAAP for fiscal 2025, AMD 49% GAAP, Intel 32.7% GAAP, each with the right basis and period, and the statement that they are not like for like. It says NVIDIA's full-year GAAP margin was not found and that 73.0% is the fourth-quarter GAAP figure. One speculative sentence remains ("potentially narrowing or reversing the gap with AMD"). This is the sixth patched run of this task; see below |
| D1 | 0.67 / 0.00 | 0.67 / 0.00 | 31 / 29 | Same three investigate steps as the baseline. Then the guard acted: "the latest result only reports missing information; verifying an earlier finding instead". The verifier was sent "Amkor is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips ...". All 8 of its searches timed out, so it returned `unverifiable`. Final answer: `partial`, **low** confidence, with "not established" listed for both growth questions. Baseline: `ok`, **high** confidence, verdict `survived`. The answer text still names Amkor |
| A1 | 1.00 / 1.00 | 1.00 / 1.00 | 7 / 7 | No guard fired. Same answer as the baseline |
| D2 | 0.75 / 0.75 | 0.75 / 0.75 | 7 / 7 | No guard fired. Still "Intel Foundry" (routed as a single lookup; nothing here addresses routing) |

A2, W2, A1 and D2 were each run twice, once on an early state of the patch and once on the finished
code. Both runs of each gave the same answer and the same token counts.

### W1, run by run

I changed the code between these runs in response to what each one did. That is tuning on one
task, and it should be read that way.

| Run | State of the patch | What the answer did |
|---|---|---|
| 1 | Checks at extraction only | The GAAP-labelled 75.5% finding was rejected, as intended. The model then wrote "NVIDIA's GAAP gross margin for fiscal year 2025 was 73.0%". That is the fourth-quarter figure. A new error, and nothing flagged it |
| 2 | Plus the label check on single agents' answers | The sub-agent's mislabel was caught and its retry came back right. The top-level summary then wrote "75.5% in Q4 FY2025". Flagged by the final audit, not repaired |
| 3 | Plus the same check on manager syntheses | All figures and labels right. The retry that produced this was set off by a false alarm in the period rule, since fixed |
| 4 | False alarm fixed | The sub-agent's retry repeated the mislabel. The answer was kept at low confidence, and the summary led with 73.0% while saying one paragraph later that it was a quarterly figure |
| 5 | Plus: a failed retry returns the extracted findings instead | Sub-agent correct. The summary read the note explaining the discarded draft and attached it to the wrong figure ("75.5% ... derived from Q4 data") |
| 6 | Plus: the note is a plain fact about the figure. Finished code | All figures and labels right (the row in the table above) |

What this shows: the original failure, a non-GAAP figure called GAAP, did not recur in any of the
six runs. The error that replaced it was detected in every run once the check existed. Getting the
4B model to then write it up correctly was fragile: a change of a few words in a retry prompt or a
note changed the outcome. The deterministic fallback (run 5 onward) is what I would rely on, not the
retry. One good run on the finished code is not proof that the period problem is solved.

### Conditions that affect how to read these

- **One run per task on the finished code.** These show what the guards do on the recorded
  failures. They are not a benchmark of the patched configuration, and M1, M2 and E1 were not run.
- **Timing is not comparable with the baseline.** Another session on this machine was running jobs
  against the same Ollama server during the first batch of runs, and Ollama serves one request at
  a time. The first A2 run took 254 s for 76 s of model work. The model-call counts above are
  comparable; wall-clock times are not, so I have left them out.
- **Web search was failing all day.** Every live search timed out from about 12:35 until at least
  21:35 (a request to any host took about 5 seconds to connect). Replayed searches were
  unaffected, so runs that stayed on the baseline's path worked; any new query failed. This is why
  the D1 verifier found nothing, and it also cost the patched W1 and W2 runs some searches the
  baseline never made.
- **Two D1 attempts are invalid and are kept in the results** (`repeat` 0 and 1, quality 0, cut off
  at the 900 s limit). Cause: an early version of the patch appended a rule to the DEEP prompt,
  which changed the model's first question, which needed new searches, which timed out. I removed
  that prompt rule (the code check does the work) so that a patched run stays on the recorded path
  until a guard acts. The valid D1 run is `repeat` 2.
- **Runs after 16:50 had a longer time allowance** (`budgets.max_seconds=2700`, recorded in each
  row as `extra_overrides`), because each failed search costs about two minutes of waiting. No run
  with that allowance reached the normal 900 s limit except D1 `repeat` 2 (1,396 s, nearly all of
  it search timeouts).

## Shown live versus fixtures only

| Behaviour | Scripted tests | Replay of recorded runs | Live (real model) |
|---|---|---|---|
| Missing-information statement is not sent to a verifier; an earlier positive claim is | Yes | 6 of 6 cases identified | **Yes** (D1) |
| Answer with unresolved steps is `partial`, not high confidence | Yes | n/a | **Yes** (D1) |
| Verifier completes a check on the positive claim and its verdict is used | Yes | n/a | **No** (search outage) |
| Verdict without cited evidence is not accepted | Yes | n/a | No (did not arise) |
| No verifier sent when nothing is checkable | Yes | n/a | No (did not arise) |
| Sorted figures in the synthesis prompt; correct ranking | Yes | n/a | **Yes** (W2, twice) |
| Retry after a wrong ranking; appended correction | Yes | 6 answers would trigger it | No (first draft was right) |
| Mixed-basis warning in a comparison, and the answer saying so | Yes | n/a | **Yes** (W1) |
| Mixed-period warning in a comparison | Yes | n/a | No (did not arise) |
| GAAP label on a non-GAAP figure rejected at extraction | Yes | 7 findings | **Yes** (W1, six runs) |
| Unsupported clause cut from a claim | Yes | 14 findings | **Yes** (W1) |
| Invented figure rejected at extraction | Yes | 13 findings | **Yes** (A2) |
| Quarter presented as full year caught in an agent's answer | Yes | 0 flags in 395 answers | **Yes** (W1, five runs) |
| ...and the retry fixing it | Yes | n/a | Twice in five runs |
| ...and the fallback to extracted findings when the retry fails | Yes | n/a | **Yes** (W1, two runs) |
| Label check and retry on a manager synthesis | Yes | n/a | Once, and that once was a false alarm |
| PDF over 3 MB read under the bounded PDF limit | Yes | n/a | **Yes** (A2; also a 110-page report in W2, read to page 20 and reported as such) |
| Oversized response refused with an explicit error | Yes | n/a | No (no response exceeded 8 MB) |
| Truncated recording re-fetched under a second key, original kept | Yes | n/a | **Yes** (A2) |
| Baseline behaviour unchanged | Yes | n/a | **Yes** (A1, W2, D1 identical to the recorded rows, on the finished code) |

## Trade-offs and possible regressions

- **Fixing one error exposed another, and the repair is fragile.** See "W1, run by run". A 4B model
  asked for a figure it does not have will substitute a neighbouring one. The checks catch more of
  that than before; they do not stop the model from trying.
- **The checks cannot tell one metric from another.** A figure that is on the page, next to the
  quote, with the right basis and period, passes even if it is revenue reported as operating
  income.
- **Some true findings will be rejected or trimmed.** 3.7% of recorded findings would have been
  rejected or changed. All were justified on reading, on data the rules were tuned on.
- **An agent's answer can now be a list of extracted findings** instead of prose, when its retry
  fails. Correct, but harder to read, and it may include findings beside the point.
- **Fewer answers are labelled verified or high confidence.** That is the intent, but an arm that
  was credited for confident answers will look worse.
- **`numeric_guard` changes a first-attempt prompt.** In W2 the patched answer is right about the
  ranking but dropped the baseline's caveat that Microsoft's fiscal year and the others' calendar
  years do not line up, and it added ratios it computed itself ("42% greater", "2.6 times"; both
  correct, both flagged by the audit as not found in any source).
- **The heuristics are English financial prose only**, about 750 lines including comments. That is
  more than "lightweight" suggests; most of it is patterns for what counts as a gap statement, a
  figure, and a period label. A sentence like "There is no evidence that X" is treated as
  unverifiable even though it could be checked.
- **Larger downloads.** The A2 PDF took 11 s to fetch. Up to 8 MB per PDF and four at once.
- **Latency.** No extra model call unless a check fails; then one retry. Patched runs made between
  5 fewer and 2 more model calls than the baseline on these tasks.
- **v2 is harsher than v1 and still pattern matching.** R4 gives 0 to an answer that has no gold
  fact but is otherwise sensible. It gave 1.00 to the final W1 answer and also to W1 runs 2, 4
  and 5, each of which had a period problem: v2 has no period rule.

## Still failing or not addressed

| Item | Status |
|---|---|
| D1 names Amkor instead of TSMC | Not fixed. Retrieval and model problem |
| D2 "Intel Foundry" | Not fixed. A routing problem; out of scope |
| A verifier completing a check under the guard, live | Not shown. Needs a re-run when web search works (command below) |
| W1: NVIDIA's full-year GAAP margin (75.0%) | Not retrieved in any patched run. The final answer says so instead of substituting the quarterly figure |
| Period mixing in general | Detected on the one case seen. Repair shown once on the finished code |
| Failed searches are written to recordings and replayed as failures | Existing behaviour, found during this pass. I deleted the 39 such entries my own runs wrote today (none existed before) and left the code alone. Worth fixing before the next benchmark |
| PDF parsing in the main process | See section 4 |
| M1, M2, E1 under the patched config | Not run |

## Commands

```bash
# all tests (no model, no network; about 12 s)
.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q

# only the regression tests for the four failures
.venv/bin/python -m pytest webswarm_baseline/tests/test_reliability.py webswarm_baseline/tests/test_guards.py -q

# one question with the patched config, or with one guard
.venv/bin/python -m webswarm_baseline.run "Compare the total annual revenue of Microsoft (fiscal year 2024), Alphabet (2024) and Amazon (2024)." --config webswarm_baseline/configs/reliability_v1.json
.venv/bin/python -m webswarm_baseline.run "your question" --set verify_guard=true

# re-grade the recorded runs with v2, and replay the guards over them (writes only to experiments/results/regrade_v2/)
.venv/bin/python -m experiments.bench.regrade
.venv/bin/python -m experiments.bench.guard_replay

# the live runs reported above, and the unchanged-baseline check, into a fresh result set
.venv/bin/python -m experiments.bench.run_bench --name my_reliability --arms reliability baseline --tasks A2 W2 W1 D1 A1 D2

# the one thing not shown live: D1 with a verifier that can search. Check first that search works:
.venv/bin/python -c "from webswarm_baseline.web import DDGSProvider; print(len(DDGSProvider().search('TSMC CoWoS capacity', 3)))"
.venv/bin/python -m experiments.bench.run_bench --name my_reliability_d1 --arms reliability --tasks D1

# what changed
git log --oneline a1139d6..HEAD
git diff a1139d6 -- webswarm_baseline/swarm.py webswarm_baseline/web.py
```

Files to read first: `webswarm_baseline/guards.py` (the checks),
`webswarm_baseline/tests/test_reliability.py` (each failure reproduced, then fixed), and the saved
runs `examples/reliability_*`.
