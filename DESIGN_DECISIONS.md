# Design decisions

Decision log for the WebSwarm-inspired baseline (`webswarm_baseline/`) and the optimization
experiments (`experiments/`). Each entry says what was chosen, why, what it costs, and where the
idea comes from: **[paper]** means WebSwarm describes or implements it, **[extension]** means it is
ours, **[measured]** means the choice follows from a measurement on this machine.

## Sources

| Ref | Source | What was actually read |
|---|---|---|
| WS-paper | Song et al., *WebSwarm: Recursive Multi-Agent Orchestration for Deep-and-Wide Web Search*, 2026, https://arxiv.org/abs/2607.08662 | abstract page and the HTML full text (sections 3.2-3.3, tables 1-4, appendix A) |
| WS-code | https://github.com/songxiaoshuai/WebSwarm (MIT) | `system_prompt.py`, `guidance/web_probing.py`, `guidance/subtask_experience.py`, `verbs/wide_agent/dispatch.py`, `verbs/deep_agent/deep_node.py`, README |
| Jev-blog | TypeSafe, *Introducing System One Models & Jev*, 9 Oct 2026, https://typesafe.ai/blog/introducing-system-one-models-and-jev | whole post |
| Jev-docs | https://docs.typesafe.ai (introduction, quickstart, API reference, Choice, Noul) | request/response contract, error codes |
| S1-adapter | https://github.com/typesafe-ai/system-one-adapter-python (MIT) | README |

No WebSwarm code was copied. Two of its prompt ideas were re-expressed: the three topology labels
for web probing, and the verifier verdict labels.

### What the sources demonstrate, and what they do not

**WebSwarm demonstrates** (with GLM-4.5 and other large hosted models): progressive recursive
delegation beats single-agent ReAct and several multi-agent baselines on BrowseComp-Plus,
WideSearch, DeepWideSearch and GISA. Its ablation (table 3) shows that removing web probing left
item F1 about the same (+0.5) while web-tool calls rose 63-75%, and that removing experience
sharing cost about 3 F1 points. Its own limitations section says the method needs **more** model
calls and web requests than a single agent, at higher cost and latency.

**WebSwarm does not demonstrate**: anything about small local models (its weakest reported backbone
is Qwen3-32B, and results there are much lower); anything about wall-clock latency (only tool-call
counts are reported); financial research; or managers acting on partial results. In the reference
code a WIDE batch runs in a thread pool and the manager receives results only when the whole batch
has finished (`dispatch.py`, `_run_batch`).

**The Jev post claims** 70-500 ms end-to-end responses, typed outputs with calibrated
probabilities, and large speed and cost advantages over frontier LLMs on "System One-shaped"
queries. The evidence is the vendor's own evaluation on four workflows it wrote, measured from its
own laptops, with reference answers from two LLMs; the post itself says the gains shown are "on
the higher end of real world gains". Calibration is asserted, not shown. **Nothing in the post is
about research agents or routing in a multi-agent tree.** Using Jev for the bounded decisions of
this system is our hypothesis.

## Decisions

### D1. A new package, with the old prototype untouched
`webswarm_baseline/` is self-contained; `one_shot_webswarm_prototype/` is not imported or edited.
Experiments live in `experiments/` and are loaded lazily, so the baseline has no dependency on
experiment code.

### D2. LangGraph for the agent lifecycle, plain Python for the rest [project preference]
One compiled `StateGraph` describes the lifecycle of any node (`route`, then either `atom` or
`plan -> dispatch -> collect -> review -> synthesize`). That is where a graph helps: the manager
loop has real branching (add work, keep waiting, or finish), and one graph serves WIDE, DEEP and
ENTITY_COLLECT with different policies. The ATOM loop, threading, queues, budgets and web access
are ordinary Python because a graph would only obscure them. Recursion is each child thread
invoking the same compiled graph.
*Cost:* queues and thread handles live beside the graph state rather than in it, so LangGraph
checkpointing cannot resume a run mid-flight.

### D3. Threads, with one model slot [measured]
Each node is a thread; a shared gate limits concurrent model calls. Two simultaneous requests to
Ollama on this machine took exactly as long as two sequential ones, so the gate is set to 1 and
only web I/O overlaps. Changing `OLLAMA_NUM_PARALLEL` is a global setting and was left alone.
*Consequence, measured in the first full run:* the model was busy for 722 of 722 seconds. Web
latency is completely hidden behind model time, so reducing web calls does not shorten a run
unless it also removes model calls.

### D4. Managers consume results as they arrive [extension]
`collect` returns on the first child result (plus anything else already queued) and `review` then
decides to wait, add follow-up work, or finish and cancel the rest. This is the "incremental
consumption" extension the project asked about. `review_policy=batch` waits for the whole batch,
which is how the reference implementation behaves, and is kept as a comparison arm.
*Caveat:* with one model slot, "as they arrive" is limited by the queue. Results from sibling
agents tend to arrive close together because the agents take turns on the model.

### D5. Bounded decisions sit behind a `Decider` interface [extension, motivated by Jev-docs]
Routing, the next ATOM action, stop-or-continue at review, verify-or-not, and redundancy are
choices among a few options. They are separated from generative work (queries, sub-objectives,
findings, answers) so that the same research code runs with the main model, deterministic rules, a
small local model, or Jev making those choices. A decider may answer "no opinion", which sends the
decision back to the generative path; that is how a typed decider hands off when new text is
needed (a new query, a follow-up objective).

### D6. Typed decisions mirror Jev's primitives exactly [Jev-docs]
`experiments/deciders/primitives.py` defines `Choice`, `Noul` and `Score` with the same fields as
the documented REST API, and `to_wire()` emits the documented JSON. The Jev backend therefore
sends these objects unchanged, and the local backend answers the same questions with one output
token and logprob-derived probabilities. Swapping backends does not change what is asked.

### D7. Evidence is verified by code [extension]
The 4B model invents plausible quotes. Every extracted finding must carry a quote, and the quote
must occur in the retrieved text (exact match, or at least 85% of its word trigrams for five words
or more) or the finding is dropped. Sources are registered only when a finding from them is
accepted. The final answer is audited without a model: citations must exist and each figure is
searched for in the cited source's text. WebSwarm instead trusts a model-written page summary.
*Cost:* quotes roughly double the output tokens of an extraction call.

### D8. Agents can only open URLs returned by search [security]
The `read` action takes a result number, not a URL. A page cannot steer an agent to an arbitrary
address, which removes one prompt-injection and exfiltration path. Fetching still validates
scheme, port and resolved address on every redirect hop.

### D9. Short prompts and bounded outputs [measured]
The 4B model ingests about 320 prompt tokens/s and writes about 27 tokens/s when cool (about 190
and 18 under sustained load on this fanless laptop). So: page excerpts are capped at 3200
characters chosen by a lexical relevance pass; every schema string has a `maxLength`; thinking
mode is off. `maxLength` was added after 7 calls in one run failed because the model wrote a
"thought" until the token limit cut the JSON in half.

### D10. Record and replay web responses, including their latency [extension]
Arms issue different queries, so strict replay is impossible. Instead each task has a cassette:
the first run to make a request records the response and how long it took, and later runs get the
same response after sleeping for that long. Shared requests are identical across arms and a cached
arm gains no speed advantage. Requests an arm makes that nobody made before go to the live web.

### D11. A soft deadline before the hard one [measured]
In the second full run the hard deadline cut off two of four branches seconds before they
finished, and the answer was written from the other two. Now at 70% of the time budget agents stop
gathering and write up what they have, so the remaining time goes to synthesis.

### D12. Routing prompt tuned on a small labelled set [measured]
The first routing prompt agreed with the intended mode on 72% of 32 labelled objectives, never
chose DEEP, and over-delegated 3 of 9 sub-objectives. After adding the parent objective, clearer
mode definitions and a "when unsure, ATOM" rule: 88%, DEEP 3/6, over-delegation 1/9. The labels are
the author's, and the prompt was tuned on the same set, so these figures are optimistic.

### D13. Web probing is a cheap version of the paper's [paper, simplified]
WebSwarm's probe is a full agent that searches and reads pages. Here it is one search and one
model call that classifies the result snippets as `centralized`, `centralized_with_gaps` or
`distributed`, names hub results, and suggests an axis. Hub results are passed to the children as
pre-loaded search results so they can read without searching first.

### D14. Experience sharing without a model call [paper, simplified]
Scouts run first (2, as in the paper). Tips for the remaining siblings are read from the scouts'
traces by code: domains that produced verified findings, domains that failed to load, and a query
that led to evidence. The paper uses a model call to summarise the traces.

### D15. Two models at most, both small
Research and baseline decisions use `qwen3.5:4b-q4_K_M` (already installed). `qwen3.5:2b-q4_K_M`
(1.95 GB) was downloaded for the small-decision-model arm. No 9B model was downloaded: at the
measured speeds a 9B model would roughly double every run, and the night was better spent on more
arms than on a second backbone.

### D16. Jev is integrated but not exercised against the real service
There is no `TYPESAFE_API_KEY` in this environment, and Jev is a paid API that would receive
research text. The REST adapter is implemented from the public documentation and tested over real
HTTP against a local stub that enforces the documented contract. The adapter refuses to start
without a key **and** an explicit `allow_external_calls=true`. No timing or accuracy number in this
repository describes Jev.
