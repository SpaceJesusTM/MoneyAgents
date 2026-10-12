# Next pass: retrieval reliability, 4B versus 9B, evidence checks, held-out set

Mac-only pass on 2026-10-12, following `RELIABILITY_IMPROVEMENTS.md`. Real local models and the live
web throughout; nothing here comes from a mock unless it says so.

## What this pass found

1. **The search timeouts were a local DNS fault, and they are fixed in-process.** The resolver drops
   IPv6 lookups and the machine has no IPv6 route, so every connection waited 2 to 5 seconds and the
   search library's 10-second limit expired. Failed searches are no longer written into recordings.
2. **The 9B model was right more often by reading (3 of 5 against 1 of 5), but the comparison does
   not show that the model is the reason.** Every 9B search was answered live today, because the 9B
   model writes different queries from the recorded ones. On the one task where the gap was decisive
   (D2), the 4B model also answers correctly when it too gets today's live search. The 9B model costs
   about twice the time per token and ran out of the 15-minute budget on one task.
3. **The evidence-check prototype did not earn its place.** It fixed one held-out two-hop question,
   left D1 wrong, and turned a correct D2 answer into a hedge. It stays opt-in and is not recommended.
4. **On three held-out questions the 4B configuration got none fully right.** The development tasks
   flatter the system.
5. **Replays are only exact on the day they were recorded**, because every prompt carries the date.
   A pinned date (`as_of`) restores exact replay; with it the frozen baseline still reproduces.
6. **The automatic graders gave full marks to three answers that are wrong or evasive.** Every
   correctness statement below is from reading the answer against the gold facts.

Tests: **234 pass** (191 before this pass, 43 new). The frozen baseline, `reliability_v1` and all
earlier recorded results are unchanged.

## 1. Retrieval: diagnosis and fixes

### Diagnosis

`python -m webswarm_baseline.netcheck` (new, read-only) checks the four places a search can fail.
Output on this machine today:

```
IPv6 route: NO
Name lookups (seconds; IPv4 only / IPv4 and IPv6):
  html.duckduckgo.com      0.01 / 5.01
  search.brave.com         0.02 / 5.01
  www.mojeek.com           0.02 / 5.01
  search.yahoo.com         0.27 / 5.01
Plain HTTPS request to each search host, over IPv4:
  duckduckgo  HTTP 200 in 0.62 s
  brave       HTTP 429 in 0.12 s  <- challenge / refusal
  mojeek      HTTP 403 in 0.29 s  <- challenge / refusal
  yahoo       HTTP 500 in 0.09 s
ddgs:
  auto, as installed           0 results in 70.2 s  [timeout]
  duckduckgo, via IPv4 tunnel  3 results in 0.8 s
  brave, via IPv4 tunnel       0 results in 0.1 s  [empty]
  auto, via IPv4 tunnel        3 results in 2.5 s
DDGSProvider (used by the agents): 3 results in 1.2 s
```

| Possible cause | Verdict | Evidence |
|---|---|---|
| Local network | **Yes, the root cause** | `dig` for an AAAA record times out at both local resolvers (100.100.100.100 and the router) and answers in 9 ms at 1.1.1.1; A records answer in 4 ms. There is no IPv6 route. Any lookup that asks for both families waits out the timeout |
| Provider outage | No | Every provider answers over IPv4 in under a second |
| Rate limiting | **Yes, secondary** | Brave returns HTTP 429 and Mojeek 403 to a plain request; DuckDuckGo served a challenge page (HTTP 202) to one request. The search library reports all of these as "No results found" |
| Internal errors | **Yes, three in our code** | (a) failed searches were recorded and replayed; (b) "no results" was trusted even when it hid a timeout or a rate-limit page; (c) there was no overall deadline, so one failed search took 100 to 145 s |

### Fixes

| Fix | Detail |
|---|---|
| Unanswered requests are never recorded | Timeouts, dropped connections and rate limits say nothing about the web. Empty result lists, HTTP 403 and oversized pages are answers and are still recorded. Applies to searches and to page fetches |
| "No results" is checked before it is trusted | On an empty result a control query that always has results is tried (at most once every two minutes). If that is empty too, the provider is not answering and the search counts as failed |
| Failures are classified | `timeout`, `network`, `rate_limited`, `provider`, `internal`, `unavailable`; shown in traces and statistics |
| Bounded retries, a deadline, a breaker | Two tries, 25 s per provider call, and after three failed searches in a row search is treated as unavailable for 90 s, so a dead provider costs seconds |
| IPv4-only lookups when there is no IPv6 route | For our own fetches and the SSRF check. The search library resolves names itself, so it is sent through an in-process tunnel that resolves over IPv4. The tunnel only opens port 443 to hosts the SSRF guard accepts. No system setting is changed |
| Agents tell a failed search from an empty one | A failed search is noted as a retrieval failure, the query is not reworded, and the reported gap says so instead of "nothing found" |
| Evidence provenance per run | `web_provenance`: searches and pages replayed, answered live, or not answered |

**Replay is preserved.** Strict replay returns exactly what was recorded, including a failure recorded
by an older version. In record-and-replay mode such a recorded failure is asked again instead of being
trusted. No historical recording was edited. (The 39 failed-search entries deleted yesterday were ones
that day's own runs had written; none remained before today's change.)

**Tests** (`webswarm_baseline/tests/test_search_reliability.py`, 25 tests): a failed search is not
recorded and is asked again; an empty result is recorded and replayed without the network; an empty
result from a provider that is not answering is a failure; retry then success; retries are bounded;
the breaker opens and closes; a legacy recorded failure in both replay modes; error classification
including the real "no results after 10 s" case; the per-call deadline; the tunnel's refusals; a
dropped fetch is not recorded but a 403 is; an agent reports a retrieval failure and does not reword;
the pinned date.

### A second replay problem found along the way

Two baseline replays differed from the recorded baseline today. Cause: every prompt begins "Today:
<date>", the date had changed, and with it the model wrote one search query with an extra word, which
was not in the recording. `as_of` (new, empty by default) pins the date shown to the model.

| Baseline replay on the finished code | Result against the recorded baseline |
|---|---|
| A1, D2 with the real date (2026-10-12) | Identical: calls, tokens, answer text |
| W2, D1 with the real date | **Different** (a query changed, then live searches) |
| W2, D1 with `as_of=2026-10-11` | Identical: calls, tokens, answer text, all searches replayed |

So the frozen baseline is unchanged by this pass, and any future replay of a recording should pin
the date it was recorded on. Every run in the comparison below used the real date (2026-10-12) for
both models.

## 2. 4B versus 9B

`qwen3.5:9b-q4_K_M` (6.6 GB) was downloaded; it is the only download. Both arms are the
`reliability_v1` configuration and differ only in `model`: same prompts, thinking off, temperature 0,
seed 7, 8K context, same budgets, same recordings directory. Configs: `configs/reliability_v1.json`
and `configs/reliability_v1_9b.json`. The 4B arm ran first, was unloaded, then the 9B arm ran.
Raw rows and memory samples: `experiments/results/model_compare_v1/`.

### Correctness, by reading each answer against the gold facts

Scale fixed in `heldout_tasks.json`: CORRECT 2 = every requested fact right and correctly labelled,
1 = some right and none wrong, 0 = a requested fact wrong or the main fact missing.

| Task | 4B | 9B | Was the evidence the same? |
|---|---|---|---|
| A1 NVIDIA data-center revenue | **2.** $115.2 billion, +142% | **2.** Same | No: 9B's one search was live. Both read NVIDIA's own release |
| W1 three gross margins | **1.** NVIDIA 75.5% non-GAAP and AMD 49% GAAP right and labelled. Intel missing, with the false remark that Intel "did not report" a full-year margin. Contradicts itself about NVIDIA | **1.** AMD 49% / 53% and Intel 32.7% / 36.0% right, both bases labelled. NVIDIA missing: its sub-agent took 908 s and the run hit the time limit. **No citations** | No: 4B 5 replayed, 4 live, 1 unanswered; 9B 3 live |
| W2 three revenues | **1.** All three figures right, then refuses to rank them and wrongly doubts Alphabet's figure | **2.** Amazon $638 billion, Alphabet $350.0 billion, Microsoft "over $245 billion", ranked correctly, cited to the companies | No: 4B 2 replayed, 5 live, **3 unanswered** (rate limited); 9B 3 live |
| D1 packaging constraint | **0.** Amkor. The verifier, now able to search, confirmed it from the same deal news | **0.** No answer. It read a page titled "NVIDIA Packaging Bottleneck" and extracted nothing, then repeated its step | No: 4B 4 replayed, 6 live; 9B 2 live |
| D2 iPhone chip maker | **0.** Intel Foundry, high confidence | **2.** TSMC, Arizona, verified | **No, and it decides the result.** 4B replayed yesterday's searches; 9B's were live today |
| Fully correct | 1 of 5 | 3 of 5 | |

**The D2 control.** The same 4B configuration with no recording, so that its searches were live today
too (`model_compare_v1_live`): "TSMC manufactures the processors designed by Apple for the iPhone ...
building advanced chip factories in Arizona". Correct, 7 model calls, 54 s. With today's search
results the 4B model gets D2 right. With yesterday's it gets it wrong. The model is not what changed.

### Cost

| Task | Model calls 4B / 9B | Prompt + output tokens 4B / 9B | Time to answer 4B / 9B | Limits hit |
|---|---|---|---|---|
| A1 | 7 / 8 | 5,132 / 5,714 | 43 s / 144 s | |
| W1 | 47 / 27 | 38,607 / 20,587 | 520 s / 972 s | 9B: time limit |
| W2 | 43 / 30 | 27,775 / 19,271 | 390 s / 384 s | |
| D1 | 31 / 10 | 21,411 / 6,409 | 348 s / 125 s | |
| D2 | 7 / 18 | 4,559 / 12,021 | 63 s / 346 s | |
| Total | 135 / 93 | 97,484 / 64,002 | 1,364 s / 1,972 s | |

| Speed | 4B | 9B | Ratio |
|---|---:|---:|---:|
| Output tokens per second, machine cool (single call) | about 27 | 14.5 | 1.9x slower |
| Prompt tokens per second, machine cool | about 320 | 170 | 1.9x slower |
| Output tokens per second during these runs | 16.7 | 8.9 | 1.9x slower |
| Model time per call during these runs | 9.6 s | 16.6 s | 1.7x |
| Model load | not measured | 6.8 s | |

Wall-clock times are not a clean comparison. The laptop was warm for both arms, and from about
03:12 another session's job (a different project) was connected to the same Ollama server, during
the 9B W1 run; that run's model calls queued for a combined 1,513 s.

### Memory

Sampled every 5 s (`memwatch.py`). Swap is system-wide and includes every other application.

| | 4B arm | 9B arm |
|---|---|---|
| Model runner peak size | 4.2 GB | 6.8 GB |
| Lowest free memory | 26% | 22% |
| System swap in use, start to end of arm | 31.9 to 38.4 GB over 21 min | 38.3 to 47.2 GB over 33 min |
| Swap in use after the model was unloaded | not sampled | 30.5 GB |
| Crashes, failed model calls | none | none |

The machine already had 28 GB of swap in use before the session began. Swap grew at about the same
rate under both models (0.30 and 0.27 GB per minute) and fell back once the 9B model was unloaded.
I cannot attribute the swapping to the 9B model; I can say that it ran, fully on the GPU, without
failing, on a machine that was short of memory before it started.

## 3. Does the 9B model materially improve research quality?

**Not established.** What the five tasks support:

- It answered more of them correctly by reading (3 against 1), and it made no confident wrong claim
  where the 4B model made two.
- The comparison is not evidence-controlled on any task. None of the 9B model's 11 searches could be
  replayed, because it words its queries differently. On D2 that alone accounts for the difference.
  On W2 the 4B run had three searches refused by the provider.
- It is about 1.9 times slower per token, it exceeded the 15-minute budget on a three-company
  comparison, and that answer came back without citations.
- On D1 it failed differently, not better: no answer at all, after reading a relevant page.
- One run per task, five tasks.

Two things it did that could be real model differences, to test under controlled evidence: it routed
D2 as a two-hop question where the 4B model treats it as a single lookup, and it kept "iPhone" in its
D2 search query where the 4B model dropped it.

Under the brief's stop rule: one timeout and roughly double latency, no swapping attributable to the
model. I ran all five tasks and did not extend the experiment (no repeats, no scaled time budget).

## 4. Evidence and verification changes

### Why D1 says Amkor and D2 said Intel Foundry

From the recorded evidence of the baseline runs:

| | D1 | D2 |
|---|---|---|
| What the search returned | Five results, all about one event: the $1.5 billion NVIDIA-Amkor deal of July 2026. None mentions TSMC or CoWoS | Apple's US manufacturing news; then one blog post, "Why Apple Is Using Intel Foundry" |
| What the page said | "Nvidia signed a ... packaging deal ... with Amkor" | "Intel Foundry **will** manufacture Apple-designed chips at US facilities" |
| What the model claimed | "Amkor is the **primary supplier**" | "Intel Foundry **manufactures** the processors ... **for the iPhone**" |
| The right answer was in view | In a later result snippet: "TSMC remains the primary provider of CoWoS capacity" | In the same blog's snippet: "Apple's near-total dependence on TSMC" |
| Rewording before the search | "most constrains shipments" became "primary supplier" in the first step | "iPhone" was dropped from the query |

Common pattern: one site, reporting a deal or a plan, and no quoted passage that states the
relationship the question asked about. And, as section 2 shows for D2, which sites come back depends
on the day.

### What was prototyped (opt-in, `configs/evidence_v1.json`)

| Switch | Behaviour |
|---|---|
| `identify_guard` | "Which X ..., and <something that depends on it>?" is worked as DEEP whatever the router said. Its first step is the first half of the question, word for word, chosen by rule |
| `support_check` | The entity named in answer to "which / who" must be named by quoted passages from two sites, and not only by reports of a deal or plan. Otherwise: low confidence, a stated gap, and a DEEP manager verifies that step first. No extra model call for a single lookup |

The two-part rule fires on 3 of the 6 objectives labelled DEEP in the 32-objective routing set and on
none of the other 26. (Same author for labels and rule.)

### Results (4B model, by reading)

| Run | Evidence | Answer | Reading |
|---|---|---|---|
| D2, `reliability` | replayed, Oct 11 | Intel Foundry, **high** confidence, 7 calls | wrong |
| D2, `reliability` + `support_check` only | same, replayed | Intel Foundry, **low** confidence, "rests on one source (aprenderhub.com)", 7 calls | wrong, but flagged at no cost |
| D2, `reliability` | live, Oct 12 | TSMC, Arizona, 7 calls | correct |
| D2, `evidence` | live, Oct 12 | "it cannot be definitively established ... TSMC holds an exclusive agreement through 2026 and Intel is acting as a manufacturer", 30 calls | **worse**: a hedge where the plain configuration was right |
| D1, `reliability` | mostly replayed | Amkor, 31 calls | wrong |
| D1, `evidence` | live | "SK Hynix ... most constrains", confidence high, 32 calls. Mentions that TSMC is fully booked | wrong, differently |
| H8 (held-out), `reliability` | live | Microsoft, CEO "Bobby Kotick", high confidence, 8 calls | wrong second hop |
| H8 (held-out), `evidence` | live | Microsoft, Satya Nadella, 13 October 2023, low confidence, 27 calls | **correct** |

**Verdict: do not adopt.** One clean result: `support_check` alone turns a confident wrong answer into
a flagged one on identical evidence, for free. `identify_guard` fixed the held-out two-hop question
and cost 3.4 times the model calls. Against that, D1 is still wrong and D2 became worse than doing
nothing. Three weaknesses showed up:

- A verifier that searches the same web as the proposer confirms the same news. In D1 the claim
  "Amkor is the primary supplier" came back `survived`.
- The claim handed to the verifier can be a patchwork of clauses when the answer is hedged (D2).
- The entity detector took "High" (from "High Bandwidth Memory") as the named entity in D1.

Regression tests (`test_evidence_checks.py`, 18 tests) cover the rules, the real D1 and D2 findings,
and the engine paths with a scripted model. They do not show a real model reaching the right answer.

## 5. Held-out evaluation

`experiments/bench/heldout_tasks.json`: 12 questions (5 single-fact numerical, 2 comparisons, 3
two-hop, 2 entity collections), with gold facts and the scoring rules written and committed before
any run. Every gold fact also appeared in live search snippets today; for six questions, and one of the two
facts in a seventh, that was only with a query that named the expected fact, which is weaker (recorded
per question).

**Bounded subset run: 3 of 12, 4B `reliability`, live search.** The other nine are ready and not run.

| Question | Answer | CORRECT |
|---|---|---|
| H1 Google Cloud revenue, full year 2024 (gold $43.2 billion) | "$12.0 billion", high confidence. That is the fourth-quarter figure; the quoted sentence gave no period and the model wrote "full year" at extraction. No guard caught it | 0 |
| H8 Who acquired Activision Blizzard, and who was that company's CEO (gold Microsoft, Nadella) | Microsoft, "Bobby Kotick", high confidence. Kotick ran Activision. A two-hop question answered as one lookup | 0 |
| H12 Big Four accounting firms | Deloitte, EY, KPMG. PwC missing; one source | 1 |

None fully right. Three questions cannot rank anything, but they are the first questions this system
has answered that it was not developed on, and they are worse than the development tasks. Two of the
three failures are the same kinds seen in development: a quarter presented as a year (now at the
extraction step, where no check exists), and a two-hop question routed as a lookup.

## Where the automatic graders failed today

| Answer | v1 / v2 | Reading |
|---|---|---|
| W2, 4B: figures right, refuses to rank | 1.00 / 1.00 | incomplete |
| D1, `evidence`: names SK Hynix, mentions TSMC and CoWoS in passing | 1.00 / 1.00 | wrong |
| D2, `evidence`: a hedge that mentions TSMC and Arizona | 1.00 / 1.00 | not an answer |

Pattern matching credits a gold term wherever it appears. Until the grader checks which entity the
answer commits to, results need reading.

## 6. Related work and recommendations

There is no separate literature review file in the repository; `DESIGN_DECISIONS.md` is the record,
and it covers WebSwarm and Jev. For this section I re-read the STORM abstract and the GPT Researcher
and Open Deep Research READMEs today (through a summarising fetch, so quotations are second-hand);
the rest is from memory of the papers and is marked.

| System | How it splits the work | How evidence travels | Checking | How its authors evaluate it |
|---|---|---|---|---|
| **WebSwarm** (Song et al., 2026) | Recursive delegation with atom / deep / wide / entity modes; web probing; sibling experience sharing | Model-written page summaries passed up the tree | A verify agent; refuses non-existence claims | BrowseComp-Plus, WideSearch, DeepWideSearch, GISA with large hosted models. Reports more calls and latency than a single agent |
| **Open Deep Research** (LangChain) | A supervisor hands sub-topics to parallel researchers with separate contexts (from memory of its 2025 write-up) | Researchers compress findings; one model writes the report at the end. Separate models for summarising, research, compression and writing (README) | None described | Deep Research Bench, 100 tasks, LLM judge. RACE 0.4309 with default models, 0.4943 with GPT-5 as researcher (README) |
| **GPT Researcher** | A planner writes research questions; execution agents crawl in parallel; "deep research" explores a tree with set depth and breadth (README) | Each source summarised and source-tracked; a filter keeps relevant passages before the model sees them. The README now names Jev as the default filter | None described | Its own test on 28 tasks: relevant passages kept 73% (Jev), 51% (keyword), 46% (embeddings). The project's own measurement |
| **STORM** (Shao et al., NAACL 2024) | Finds perspectives on a topic, simulates question-asking conversations grounded in sources, builds an outline, then writes | Collected references attached to the outline | Citation quality measured, not enforced (from memory) | FreshWiki. Wikipedia editors judged more articles organized (+25 points) and broad (+10) than a retrieval baseline; they flagged source bias and over-association of unrelated facts |
| **This system** | WebSwarm's modes on a 4B local model, with managers that act on partial results | Findings with verbatim quotes checked by code; prose answers passed up | Quote check, opt-in guards, independent verifier | 9 development tasks, 12 held-out (3 run), read by hand |

Three recommendations, in priority order. None is implemented.

**1. Evaluate on a fixed corpus, with a pinned date.**
*Why:* this pass could not tell a model effect from a retrieval effect. The same model answered D2
wrongly on Monday's search results and correctly on Tuesday's; a baseline replay changed because the
date did. *Grounding:* WebSwarm's main benchmark, BrowseComp-Plus, fixes the document collection for
exactly this reason; GPT Researcher's own filter test replays the same scraped sources.
*Concretely:* per task, index every page and result already in the recordings (plus gold-source
pages) and let all arms search that index offline with BM25; keep live runs as a separate check.
`as_of` is the first piece. Small: the recordings and passage scorer exist.

**2. Pass typed findings up the tree and write once.**
*Why:* the errors that survived every guard were introduced when prose was rewritten: a quarter became
a year at extraction (H1), correct sub-results became "75.5% in Q4" at synthesis (yesterday's W1),
three correct figures became a refusal to rank (today's W2). The most reliable outputs yesterday were
the ones code produced: sorted figures, findings returned as extracted. *Grounding:* Open Deep
Research separates research from writing and writes the report in one final step from compressed
findings; STORM fixes the outline before writing. *Concretely:* a finding becomes a record (entity,
metric, value, unit, period, basis, source, quote); managers merge records; comparisons are computed;
one model call writes the final text from the table.

**3. Gate "which entity" answers on the relationship, not on a second search.**
*Why:* D1, D2 and H8 are the same failure, and today's prototype shows a second agent searching the
same web does not fix it. What was missing each time was a passage stating the relationship that was
asked about. *Grounding:* WebSwarm's deep mode and STORM's multi-perspective questioning both widen
what is retrieved before committing; GPT Researcher puts a relevance judge between retrieval and the
model, and reports that a typed System One model does that job better than embeddings.
*Concretely:* decompose two-part questions by rule (done here, opt-in); before naming an entity,
require a quoted passage for which a typed yes/no judge agrees "this states that E has relation R",
from two unrelated sites, with one search worded to exclude the leading candidate. This is also the
most promising use of Jev in this project: the baseline analysis found that bounded decisions are 18%
of run time, so the gain from a typed judge is in evidence quality, not routing speed. Untested.

## 7. Remaining issues

| Issue | Status |
|---|---|
| Model comparison is not evidence-controlled | Needs recommendation 1. Until then, no claim that 9B is better |
| 9B exceeded the time budget on W1 and returned an uncited answer | Not re-run with a longer budget |
| 9B extracted nothing from a relevant page (D1) | Not investigated |
| Rate limiting by Brave, Mojeek and sometimes DuckDuckGo | Handled as failures, not fixed. 6 of today's 78 live searches went unanswered |
| A quarter written as a full year at extraction (H1) | No check exists at that step |
| Evidence-check prototype | Not recommended; three weaknesses listed in section 4 |
| Graders credit a gold term anywhere in the answer | Not fixed; see the table above |
| Nine held-out questions | Not run |
| Replays need the recording's date | `as_of` added; the benchmark runner does not set it automatically |
| D1 | Still wrong in every configuration |
| Machine | 28 GB of swap in use before the session; another session shared the model server during part of the 9B arm |

## What was and was not validated

| | Status |
|---|---|
| Search fixes | 25 scripted tests; live: `netcheck`, and today's 24 runs made 72 searches that were answered live and 6 that were not; the unanswered ones were reported as failures and none was recorded |
| Baseline unchanged | Live: A1, D2, W2, D1 reproduce the recorded baseline exactly (W2 and D1 with the date pinned) |
| 4B versus 9B | Live, one run per task, five tasks, same day and date. Not evidence-controlled |
| D2 live control | Live, one run |
| Evidence checks | 18 scripted tests; live: D1, D2, H8, one run each, and one replayed run of `support_check` alone |
| Held-out set | 3 of 12 questions live with one configuration; gold facts corroborated in search snippets, not re-read in the primary documents |
| Memory | Sampled system-wide; not isolated from other applications |
| Related work | STORM abstract and two READMEs re-read today through a summarising fetch; other statements from memory |

## Reproduce

```bash
# tests (no model, no network; about 13 s)
.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q

# why is search failing?
.venv/bin/python -m webswarm_baseline.netcheck

# the frozen baseline still replays (pin the date the recordings were made)
.venv/bin/python -m experiments.bench.run_bench --name my_baseline_check --arms baseline --tasks A1 D2 W2 D1 --set as_of=2026-10-11

# 4B versus 9B (run one arm at a time so only one model is loaded), then the table
.venv/bin/python -m experiments.bench.run_bench --name my_models --arms reliability --tasks A1 W1 W2 D1 D2 --order arm
ollama stop qwen3.5:4b-q4_K_M
.venv/bin/python -m experiments.bench.run_bench --name my_models --arms reliability_9b --tasks A1 W1 W2 D1 D2 --order arm
ollama stop qwen3.5:9b-q4_K_M
.venv/bin/python -m experiments.bench.model_table my_models
.venv/bin/python -m experiments.bench.memwatch memory.csv &      # optional: sample memory during a run

# the live control for D2 (no recording)
.venv/bin/python -m experiments.bench.run_bench --name my_live --arms reliability --tasks D2 --no-cassette

# evidence checks
.venv/bin/python -m experiments.bench.run_bench --name my_evidence --arms evidence --tasks D2 D1
.venv/bin/python -m experiments.bench.run_bench --name my_support --arms reliability --tasks D2 --set support_check=true --set as_of=2026-10-11

# held-out set (12 questions; H1, H8 and H12 were run)
.venv/bin/python -m experiments.bench.run_bench --name my_heldout --suite heldout_tasks.json --arms reliability

# one question with either model
.venv/bin/python -m webswarm_baseline.run "your question" --config webswarm_baseline/configs/reliability_v1.json
.venv/bin/python -m webswarm_baseline.run "your question" --config webswarm_baseline/configs/reliability_v1_9b.json
```

Result sets from this pass: `experiments/results/model_compare_v1`, `model_compare_v1_live`,
`evidence_v1`, `evidence_v1_support_only`, `heldout_v1`, `np_baseline_check`. Live searches made by
any configuration are added to the local recordings; no earlier recording was changed.
