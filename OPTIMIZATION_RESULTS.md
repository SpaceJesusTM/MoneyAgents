# Optimization results

Baseline versus optimized arms on the 9-task benchmark. Every number in the result tables was
measured on 2026-10-11 with the **real local model (`qwen3.5:4b-q4_K_M`) and real web content**
(live, or replayed from a recording made live the same night with its original latency).

**No number in this file describes Jev.** The Jev adapter was not run against the real service.
Where Jev appears, the text says whether it is a contract test against a local stub or arithmetic
on TypeSafe's published latency.

Raw rows: `experiments/results/compare_v1/results.jsonl` (round 1) and
`experiments/results/compare_v2/results.jsonl` (round 2).

ROUND2_PLACEHOLDER_SUMMARY

## Method

- Each arm is the frozen baseline config plus the overrides in `experiments/bench/arms.json`.
  Same model, seed, temperature 0, budgets and tasks.
- Arms were interleaved per task, with the order rotated, and each round includes its own baseline
  rows, so an arm is always compared with a baseline that ran minutes earlier on the same code.
- Web responses were shared through per-task recordings. A replayed response is delayed by the
  latency it originally took.
- **Quality rule, fixed before any arm was compared:** an arm preserves quality if its mean
  automatic quality is within 0.05 of the baseline's on the same tasks and it loses no gold fact
  that the baseline found.
- Two time measures. *Time to answer* is wall-clock until the root's answer is ready. *Reference
  model time* is prompt tokens / 300 + output tokens / 25, which does not depend on how hot the
  laptop was.

### How noisy is the measurement?

The baseline ran each task three times across the night (once alone, once in each round).

| | Result |
|---|---|
| Automatic quality | identical across repeats on every task |
| Model calls and reference model time | identical on 7 of 9 tasks, within 5% on the other two |
| Wall-clock time to answer | varied by 2% to 20% between repeats of the same task |

So the baseline is close to deterministic in what it does (temperature 0, fixed seed, replayed web)
and noisy only in how long the same work takes, because the fanless laptop slows down by up to a
third when warm. Differences in reference model time are real. Differences in wall-clock time
under about 20% on a single task are not.

## Finding 1: faster decisions can save at most 18%. Different decisions saved up to 68%.

Splitting the baseline's model time by what each call was for
(`experiments/bench/decision_ceiling.py`):

| | Share of baseline model time |
|---|---:|
| Generative work: queries, findings, answers, plans, synthesis | 80.4% |
| Bounded decisions: routing, which result to read, finish, review with no follow-up | **18.3%** (99 decisions, 4.6 s each) |
| ...of which routing | 4.0% |
| Output that was discarded and repaired | 1.3% |

A decider that made the same 99 choices in zero time would shorten the baseline by 18.3% and no
more. Routing alone is worth 4%.

Round 1 then showed where the larger savings come from:

| Arm | Time to answer, 9 tasks | vs baseline | Model calls | Decision calls (time) | Agents spawned | Gold facts found (of 16) |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | 2,638 s | 1.00 | 303 | 0 | 46 | 11 |
| Typed decisions, 4B model | 1,968 s | 0.75 | 133 | 161 (415 s) | 33 | 10 |
| Typed decisions, 2B model | 1,233 s | 0.47 | 102 | 141 (144 s) | 27 | 11 |
| Rules, first version | 836 s | 0.32 | 65 | 0 | 31 | 9 |

The 4B typed-decision arm spent **415 s deciding, about as much as the baseline's 457 s**, because
a one-token answer still has to read a prompt of roughly 390 tokens (2.6 s per decision on this
machine). It was 25% faster anyway. The saving came from what it decided: it spawned 33 agents
instead of 46 and made 133 generative calls instead of 303. On the two open-ended questions (M1,
M2) every optimized arm built a 5-agent tree where the baseline built 11 and 12, because they did
not nest a second manager or add follow-up agents.

That is the answer to "does faster routing make research faster?" on this system: **barely. What
the router and the stop rule decide matters several times more than how quickly they decide.**

## Jev

### Status

| Item | Status |
|---|---|
| REST adapter (`experiments/deciders/jev.py`) | Implemented from the public docs: `POST https://api.typesafe.ai/v1/systemone`, bearer key, `state` / `model` / `questions`, `choice` / `noul` / `score` answers, retry on 429 and 529 |
| Contract tests | 12 tests over real HTTP against a local stub that enforces the documented request shape, auth header and error codes. All pass. |
| Decision points wired to it | Routing, ATOM stop, which result to read, review finish, review follow-up gate, verify-or-skip, redundancy. Same typed questions the local backend answers. |
| End-to-end run through the adapter | Scripted model + stub server: every decision in a full research run went through the HTTP adapter |
| Run against the real Jev service | **Not done.** No `TYPESAFE_API_KEY` in this environment. Jev is paid ($0.042 per million input tokens) and research text would leave the machine, so the adapter also requires an explicit opt-in. |
| Mock (`mock_jev`) | Answers by word overlap. Plumbing only. Not benchmarked, and its output must not be read as Jev's. |

To run it: put `TYPESAFE_API_KEY` in `.env`, export it, and run
`.venv/bin/python -m experiments.bench.run_bench --name jev_v1 --arms baseline local_s1_4b local_s1_2b jev`.

### What the measurements say Jev could and could not do here

These follow from local measurements plus TypeSafe's stated latency (70 to 500 ms per request).
They are projections, clearly not measurements.

1. **If Jev only made the baseline's decisions faster**, with the same outcomes, the ceiling is the
   18.3% above. At 70 to 500 ms for each of 99 decisions that is a saving of 16% to 18% of model
   time.
2. **In the typed-decision design**, the local 4B model spent 415 s on 161 decisions. Replacing
   those with 70 to 500 ms requests would take 11 to 80 s, bringing that arm from 0.75 to roughly
   0.59 to 0.62 of baseline time, if Jev chose as the 4B model did. Batching the two ATOM questions
   into one request, which the adapter does for Jev, would lower the request count further.
3. **The 2B local model already captures most of that**: 144 s for its decisions, 0.47 of baseline
   overall. Its lower total comes mostly from making different choices, not from being faster.
4. **Decision quality is the open question, and the larger one.** On the 32-objective routing set
   the typed 4B router agreed with the intended mode 84% of the time and the 2B router 72%; neither
   recognised more than 2 of 6 DEEP objectives. Jev's accuracy on these decisions is unknown. A
   decider that routed two-hop questions to DEEP would have fixed D2, which every model-based arm
   got wrong or half right. That would be worth more than its latency.
5. **Jev cannot replace the 80% that is generative.** It does not write queries, extract findings
   or write answers.

## Round 1: who makes the bounded decisions

Paired with the baseline on all 9 tasks.

| Arm | Time ratio (median of per-task ratios) | Reference model-time ratio | First-evidence ratio | Mean quality (arm / baseline) | Gold facts lost / gained | Preserves quality by the pre-set rule? |
|---|---:|---:|---:|---:|---|---|
| Typed decisions, 4B (`local_s1_4b`) | 0.86 | 0.76 | 0.86 | 0.79 / 0.80 | lost 2, gained 1 | No (lost facts) |
| Typed decisions, 2B (`local_s1_2b`) | 0.60 | 0.70 | 0.54 | 0.80 / 0.80 | lost 1, gained 1 | No (lost a fact) |
| Rules, first version (`rules`) | 0.42 | 0.43 | 0.66 | 0.69 / 0.80 | lost 3, gained 1 | No |

Per task, time to answer in seconds / automatic quality / agents:

| Task | Baseline | Typed 4B | Typed 2B | Rules (first version) |
|---|---|---|---|---|
| A1 NVIDIA revenue | 41 / 1.00 / 1 | 30 / 1.00 / 1 | 25 / 1.00 / 1 | 23 / 1.00 / 1 |
| A2 Apple services | 36 / 0.25 / 1 | 39 / 0.25 / 1 | 31 / 0.25 / 1 | 16 / 0.00 / 1 |
| W1 three gross margins | 367 / 0.89 / 6 | 424 / 1.00 / 6 | 194 / 0.56 / 4 | 154 / 0.89 / 3 |
| W2 three revenues | 157 / 0.83 / 4 | 135 / 0.89 / 4 | 94 / 0.89 / 4 | 18 / 0.00 / 3 |
| D1 packaging constraint | 268 / 0.67 / 5 | 327 / 0.67 / 5 | 247 / 0.67 / 5 | 113 / 0.50 / 4 |
| D2 iPhone chip maker | 47 / 0.75 / 1 | 37 / 0.50 / 1 | 38 / 1.00 / 1 | 70 / 1.00 / 3 |
| M1 NVIDIA factors | 706 / 0.80 / 11 | 342 / 0.80 / 5 | 275 / 0.80 / 5 | 189 / 0.80 / 5 |
| M2 AMD drivers and risks | 718 / 1.00 / 12 | 373 / 1.00 / 5 | 266 / 1.00 / 5 | 106 / 1.00 / 5 |
| E1 HBM makers | 260 / 1.00 / 5 | 262 / 1.00 / 5 | 62 / 1.00 / 1 | 148 / 1.00 / 6 |

Baseline cells are the mean of that round's baseline run and the standalone baseline run.

### Reading the answers

- **The "lost fact" on W2 for both typed arms is a precision loss, not an error.** They wrote
  "over $245 billion" for Microsoft where the baseline wrote "$245.12 billion". The gold pattern,
  set in advance, requires the decimal. I did not loosen it after the fact.
- **D2 separates the arms.** Baseline: "Intel Foundry" (wrong). Typed 4B: "Broadcom ... Fort
  Collins, Colorado" (worse). Typed 2B and rules: TSMC and Arizona (right). Rules got there by
  routing the question DEEP and sending a verifier; typed 2B by picking a better page. One task
  cannot rank deciders, but it shows the range.
- **Typed 4B found Intel's gross margin on W1**, which the baseline never did, by reading three
  more pages (9 extractions against 6). Its stop rule asked for more evidence there, which cost
  time and bought the fact.
- **Typed 2B wrote an uncited synthesis on W1** (grounding 0): the 4B model's synthesis, working
  from fewer sub-results, dropped the citations.
- **The open-ended questions (M1, M2) kept the same automatic quality with less than half the
  agents.** The typed arms' answers cite as many sources as the baseline's (7 to 8 against 7 to 9)
  at similar length; the rules arm's M2 answer is shorter, with 3 citations. Every arm, baseline
  included, missed the same two dimensions on M1 (export controls, company guidance), because the
  root's plan is a generative call that all arms share. The baseline's extra agents were two
  follow-ups per run, mostly returning low-confidence or "not found" results, and in M2 a nested
  second manager with five children.

### Typed decisions from the same 4B model (`local_s1_4b`)

*What changed:* routing, stop, read-which, review and verify-or-skip became one-token typed
questions with probabilities from logprobs. Our hypothesis, shaped like Jev's interface.
*Tested:* live. *Result:* 0.76 of baseline model work, same mean quality, mixed per task.
*Why it is not faster per decision:* 2.6 s per decision, dominated by reading the prompt.
*Verdict:* **revise.** The interface is right; the same 4B model is the wrong engine for it.

### Typed decisions from a 2B model (`local_s1_2b`)

*What changed:* the same questions answered by `qwen3.5:2b-q4_K_M`; research stays on the 4B model.
*Tested:* live. *Result:* 1.0 s per decision, 0.70 of baseline model work, 0.47 of total time, same
mean quality, one precision loss, one uncited synthesis, and it never chose ENTITY_COLLECT (it
answered E1 as a single lookup and happened to find all three names).
*Verdict:* **keep as the default decider candidate**, with the routing weakness noted. Both models
fit in memory together (3.3 GB + about 2 GB).

### Rules, first version (`rules`)

*What changed:* regex routing, lexical result scoring with a source prior, a coverage-based stop
rule, no follow-ups, verification skipped when two independent sites agree, word-overlap
redundancy. *Tested:* live. *Result:* 0.43 of baseline model work and the fastest first evidence,
but it **failed W2 outright**: the redundancy rule treated "Alphabet's total annual revenue" as a
duplicate of "Microsoft's total annual revenue" and dropped it, and likewise dropped one company on
W1. A fast wrong control decision. *Verdict:* **discard this version**; see the fixed version in
round 2.

## Round 2: other mechanisms, and the fixed rules

Paired with the baseline rows of the same round. Task M2 was left out of round 2 to save time, so
"8 tasks" means all but M2. Mechanisms that can only act under a WIDE root ran on the tasks where
they can act.

| Arm | Tasks | Total time vs baseline | Reference model time vs baseline | Model calls (arm / baseline) | Web calls | Agents | Mean quality (arm / baseline) | Gold facts found (arm / baseline) | Preserves quality by the pre-set rule? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Rules, fixed (`rules_fixed`) | 8 | 0.45 | 0.44 | 65 / 220 | 60 / 105 | 28 / 34 | 0.72 / 0.77 | 11 / 11 | No (lost 2, gained 2; one uncited synthesis) |
| Rules + line extraction + finish-first (`rules_lines`) | 8 | 0.38 | 0.36 | 66 / 220 | 62 / 105 | 29 / 34 | 0.68 / 0.77 | 11 / 11 | No (same, two uncited syntheses) |
| Line-reference extraction (`lines_extract`) | 8 | 0.89 | 0.87 | 207 / 220 | 102 / 105 | 32 / 34 | 0.67 / 0.77 | 10 / 11 | No (lost 2 on A1, gained 1) |
| Batch review (`batch_review`) | 3 | 0.93 | 0.91 | 124 / 141 | 56 / 60 | 19 / 21 | 0.82 / 0.84 | 6 / 5 | Yes |
| Web probing (`probing`) | 3 | 0.65 | 0.61 | 95 / 141 | 45 / 60 | 14 / 21 | 0.81 / 0.84 | 5 / 5 | No (lost 1, gained 1; coverage down on M1) |
| Finish-first scheduling (`finish_first`) | 4 | 1.08 | 1.04 | 168 / 168 | 82 / 79 | 26 / 26 | 0.91 / 0.88 | 9 / 8 | Yes |

Per task, time to answer in seconds / automatic quality / agents:

| Task | Baseline | Rules fixed | Rules + lines | Line extraction | Batch review | Probing | Finish-first |
|---|---|---|---|---|---|---|---|
| A1 | 46 / 1.00 / 1 | 26 / 1.00 / 1 | 24 / 1.00 / 1 | 44 / 0.50 / 1 | | | |
| A2 | 41 / 0.25 / 1 | 18 / 0.00 / 1 | 17 / 0.00 / 1 | 35 / 0.00 / 1 | | | |
| W1 | 343 / 0.89 / 6 | 211 / 0.67 / 4 | 120 / 0.67 / 4 | 252 / 0.67 / 4 | 363 / 0.83 / 6 | 249 / 1.00 / 4 | 434 / 1.00 / 6 |
| W2 | 135 / 0.83 / 4 | 64 / 0.78 / 4 | 41 / 0.78 / 4 | 166 / 0.83 / 4 | 143 / 0.83 / 4 | 221 / 0.78 / 5 | 151 / 0.83 / 4 |
| D1 | 274 / 0.67 / 5 | 116 / 0.50 / 4 | 152 / 0.67 / 5 | 223 / 0.67 / 5 | | | |
| D2 | 50 / 0.75 / 1 | 64 / 1.00 / 3 | 64 / 0.50 / 3 | 35 / 0.75 / 1 | | | |
| M1 | 719 / 0.80 / 11 | 188 / 0.80 / 5 | 157 / 0.80 / 5 | 690 / 0.90 / 11 | 610 / 0.80 / 9 | 309 / 0.65 / 5 | 735 / 0.80 / 11 |
| E1 | 255 / 1.00 / 5 | 154 / 1.00 / 6 | 130 / 1.00 / 6 | 216 / 1.00 / 5 | | | 250 / 1.00 / 5 |

On A2 no arm found the fact. The baseline's 0.25 there is grounding credit for an answer that says
"not found" and adds an invented figure; the 0.00 arms returned no answer at all. Do not read that
row as the baseline being better.

### Rules, fixed (`rules_fixed`)

*What changed:* the redundancy rule now also requires two objectives to name the same entities.
*Tested:* live. *Result:* **0.44 of baseline model work with the same number of gold facts (11 of
16)**, but not the same facts. It found Intel's margin (W1) and TSMC (D2), which the baseline
missed, and lost Microsoft's and Alphabet's revenue (W2): its keyword query for Microsoft returned
nothing and the rule gives up there instead of asking the model for another query, and the pages
it picked for Alphabet could not be read. W1's facts were all correct but the synthesis came back
without citations. First evidence arrived in 20 s (median) against 44 s.
*Verdict:* **keep as the fast mode, not as the default.** It is the cheapest arm by a wide margin
and its routing is the best measured, but it gives up after an empty search, and with no
follow-ups it cannot recover from a branch that found nothing.

### Line-reference extraction (`lines_extract`)

*What changed:* the page is shown as numbered lines; the model cites a line number instead of
copying a quote, and every money, percentage or decimal figure in a claim must appear on the cited
line or the one next to it. Our hypothesis. *Tested:* live.
*Result per extraction call:* output 230 to 133 tokens (-42%), prompt 1,019 to 1,188 tokens (+17%),
17.5 to 14.1 s (-19%). 15 claims were rejected for carrying a figure that was not on the cited
line; the baseline's quote check rejected 9 for a different reason and would have let those 15
through. *Result per run:* 0.87 of baseline model work.
*Quality, mixed:* its W1 answer has all three companies with GAAP and non-GAAP labelled correctly,
where the baseline misses Intel and mislabels NVIDIA's, and it had the best M1 coverage (4 of 5
dimensions against 3).
It also **lost A1**, a task every other arm gets right: the extractor cited quarterly lines and
never the line holding the full-year figure. And its W1 synthesis dropped the citations.
*Verdict:* **revise.** The stricter claim check is worth keeping. The A1 miss needs a look at how
the numbered excerpt changes what the 4B model attends to.

### Batch review (`batch_review`)

*What changed:* the manager waits for the whole batch before reviewing, as WebSwarm's reference
code does, instead of reviewing each arrival. *Tested:* live, 3 tasks.
*Result:* 0.91 of baseline model work, same quality. Reviews dropped from 13 to 4 across the three
tasks, and on M1 the tree shrank from 11 agents to 9 because one review asks for follow-ups once
instead of several reviews asking repeatedly.
*What this says about incremental consumption:* on this hardware, reviewing each arrival cost about
9% more model work and bought no measurable quality. With one model slot, sibling results arrive
close together, so there is little "early" evidence to act on, and the 4B model used the extra
reviews mostly to request follow-ups rather than to stop early. A manager finished early in 2 of
88 benchmark runs, never in a baseline run, and in one of those two (probing, W2) it cancelled the
agent that was about to find Amazon's figure.
*Verdict:* incremental review is **not a win here**. It should pay off when children finish far
apart (parallel inference, or mixed fast and slow branches); that is untested.

### Web probing (`probing`)

*What changed:* one search and one model call classify how the information is organised before a
WIDE plan (paper, simplified). *Tested:* live, 3 tasks.
*Result:* 0.61 of baseline model work and 25% fewer web calls (45 against 60), which is the
direction the paper reports (fewer tool calls at similar accuracy). But the mechanism here was
blunt: the probe called all three tasks `centralized` or `centralized_with_gaps`, which caps the
plan at 2 or 3 children. That helped W1 (4 agents, all three margins found, quality 1.00) and hurt
the other two: on W2 the manager finished early and cancelled the Amazon agent, and on M1, an open-ended multi-factor question that is not
centralized in any useful sense, the 5-agent tree dropped the competition dimension and the answer
carried two figures found in no retrieved text.
*Verdict:* **revise.** The saving is real, but it comes from planning fewer children, and a 4B
model judging topology from ten snippets is not reliable enough to decide that. Three tasks is too
few to say more.

### Finish-first scheduling (`finish_first`)

*What changed:* when several agents are waiting for the single model slot, calls that complete a
node (answers, synthesis, extraction) go ahead of calls that start new work. Our hypothesis.
*Tested:* live, 4 tasks.
*Result:* total time and model work unchanged (1.08 and 1.04, inside the noise), as expected,
since the same calls are made in a different order. What moved is when evidence becomes available:

| Task | First child result reaches the root: baseline | finish-first |
|---|---:|---:|
| W1 | 168 s | 120 s |
| W2 | 79 s | 52 s |
| M1 | 221 s | 102 s |
| E1 | 175 s | 147 s |

Time to first source-grounded finding moved the same way (median 77 s to 60 s).
*Verdict:* **keep.** It costs nothing and delivers the first usable branch 16% to 54% sooner. That
matters for time-sensitive use and is a precondition for incremental review to be worth anything.

### Page size cap (`pdf_8mb`), a robustness check

*Why:* the baseline could not answer A2 because Apple's financial-statements PDF is 4.9 MB and the
3 MB response cap truncated it. *Tested:* partly.
- At the fetch level the fix works: with `max_page_bytes=8000000` the same URL returns 8,956
  characters of text including the line "Services 24,972 22,314 96,169 85,200".
- End to end it is **inconclusive**. Replaying from the recording cannot test it (recordings are
  keyed by URL, so the replay returns the truncated fetch). A live re-run without the recording got
  different search results that night and the agent never opened the PDF, so both the baseline and
  the 8 MB run again answered "not found".
*Verdict:* raise the cap (it is one config value), and treat A2 as still unsolved until a run shows
otherwise.



## Router agreement on labelled objectives

32 objectives labelled with the intended mode (`experiments/bench/routing_cases.json`), real local
model, `experiments/bench/eval_routing.py`.

| Router | Agreement | ATOM | WIDE | DEEP | ENTITY_COLLECT | Over-delegated sub-objectives | Median time per decision |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rules | 97% | 15/15 | 6/7 | 6/6 | 4/4 | 0 of 9 | under 1 ms |
| Generative, 4B (baseline) | 88% | 14/15 | 7/7 | 3/6 | 4/4 | 1 of 9 | 3.6 s |
| Typed one-token, 4B | 84% | 15/15 | 6/7 | 2/6 | 4/4 | 0 of 9 | 2.1 s |
| Typed one-token, 2B | 72% | 15/15 | 6/7 | 2/6 | 0/4 | 0 of 9 | 0.9 s |

Caveats, all of which make these figures optimistic: the labels are mine; the prompts were tuned
on this same set; and the rules were edited after seeing their own errors on it (84% before, 97%
after), so the rules' lead here is the least trustworthy number in the table. Before tuning, the
generative router scored 72% and the typed routers 56% (4B) and 47% (2B), both sending nearly
every sub-objective to WIDE. Typed routing needed the same worked examples as the generative
prompt, and needed the parent's wording removed from its input, before it was usable.

## Not benchmarked

| Mechanism | Status |
|---|---|
| Jev | Adapter and contract tests only. See above. |
| Larger backbone (9B) | Not downloaded. At the measured speeds it would roughly double every run. |
| Parallel model inference | Not tried. Ollama serialises requests here and changing `OLLAMA_NUM_PARALLEL` is a global setting. |

ROUND2_PLACEHOLDER_TAIL
