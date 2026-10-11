# One-shot WebSwarm-inspired delegation prototype

An isolated, throwaway experiment. It tests one question from [`../CLAUDEPROMPT.md`](../CLAUDEPROMPT.md):

> Can a local LLM (served by LM Studio) dynamically build a useful WebSwarm-inspired research/delegation tree?

Given a research objective, the local model decides for each node whether it is:

| Mode | Meaning here (simplified; see CLAUDEPROMPT.md §8–9) |
|------|------------------------------------------------------|
| `ATOM` | handle locally: no sub-agents |
| `DEEP` | drill into a dependency, unknown or uncertainty (usually 1–2 ordered children) |
| `WIDE` | split into independent parallel parts that are combined afterwards |

Children go through the same decision, so the tree grows recursively until every branch is `ATOM` or a safety limit stops it. You can then optionally run a bottom-up pass: leaves answer from model knowledge, and parents synthesize their children's answers.

This covers Stages 3–5 of CLAUDEPROMPT.md (routing, child objectives, recursive delegation) and a crude version of Stage 6 (bottom-up results). It has no search (Stage 7) and no WebSwarm-specific protocols (Stage 8).

## Files

| File | What it holds |
|------|---------------|
| `swarm.py` | **The core logic.** LangGraph graph, `RoutingDecision` schema, safety limits, bottom-up synthesis |
| `prompts.py` | Every prompt. Prompt wording is an experimental variable, so edit it here |
| `llm.py` | LM Studio client (`ChatOpenAI` → OpenAI-compatible API), call logging, and the scripted `MockLLM` |
| `config.py` | Reads the env vars and defines `Limits` |
| `render.py` | ASCII tree, stats, and JSON/TXT trace files |
| `run.py` | Command-line interface |
| `examples.txt` | Objectives chosen to probe ATOM, WIDE and DEEP judgement |
| `runs/` | Output traces (git-ignored) |

## How it works

```
START → route ──(frontier not empty)──► route        one tree node per step, breadth-first
             └─(frontier empty)──────► synthesize → END   post-order answers (skip with --no-synthesis)
```

1. The root objective becomes node `#0` and goes into the frontier.
2. `route` pops one node and sends it to the model with the root question, the path from the root (ancestor objectives and modes), sibling objectives, and the current depth and max depth. The model returns structured JSON: `{reasoning, mode, children}`.
3. The harness validates the decision. **Every override is recorded in the node's `notes`**:
   - an `ATOM` decision that includes children has them dropped;
   - at `max_depth`, `DEEP`/`WIDE` is forced to `ATOM`;
   - a child that exactly duplicates (after normalization) its parent, an ancestor or a sibling is dropped;
   - children beyond `max_children` are dropped, and so are children past the `max_nodes` budget;
   - `DEEP`/`WIDE` with no usable children becomes `ATOM`;
   - `WIDE` with one child is flagged but not changed.
4. Accepted children are added to the frontier, and the loop repeats. Each node is routed exactly once, so routing calls equal the node count, which is at most `max_nodes`. Termination is guaranteed.
5. `synthesize` (optional) answers leaves with `ATOM_SYSTEM`, then answers each parent with `SYNTH_SYSTEM` over its children's answers.

The tree shows both `mode` (what was executed) and `model said X` (what the model chose) wherever the two differ.

## LM Studio setup

1. Install LM Studio and download an instruction-tuned model. Mid-size models (e.g. ~7B–30B Qwen / Llama / Mistral / Gemma) are a reasonable starting point. Models that support structured output work best.
2. Load the model, then open the **Developer** tab and start the local server (default `http://localhost:1234`).
3. Copy the model identifier shown there. You can also get it with `curl http://localhost:1234/v1/models`.

## Environment variables

The prototype reads the repo's existing `MoneyAgents/.env` (template: `.env.example`).

| Variable | Default | Notes |
|----------|---------|-------|
| `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | |
| `LM_STUDIO_API_KEY` | `lm-studio` | LM Studio ignores it, but the client requires a value |
| `LM_STUDIO_MODEL` | — | **Required**; the placeholder `REPLACE_WITH_MODEL_ID` is rejected |
| `WEBSWARM_TEMPERATURE` | `0.2` | optional |
| `WEBSWARM_TIMEOUT` | `300` | seconds per call (local models can be slow) |
| `WEBSWARM_STRUCTURED_METHOD` | `json_schema` | Set to `prompt` if the model or server can't do `response_format: json_schema`; it then asks for JSON in the prompt and parses it |

## Running

No new dependencies are needed. The prototype uses `langgraph`, `langchain-openai`, `pydantic` and `python-dotenv`, all already in `../requirements.txt`. Run these from `MoneyAgents/`:

```bash
# default objective (the NVIDIA data-center question)
.venv/bin/python one_shot_webswarm_prototype/run.py

# your own objective, tighter limits, tree only (fast: one model call per node)
.venv/bin/python one_shot_webswarm_prototype/run.py \
  "What are the main factors that could affect NVIDIA's data-center revenue growth over the next 12 months?" \
  --max-depth 2 --max-children 4 --max-nodes 15 --no-synthesis

# run the example set and get a summary table
.venv/bin/python one_shot_webswarm_prototype/run.py --batch one_shot_webswarm_prototype/examples.txt --no-synthesis

# test the plumbing without LM Studio (scripted fake model; output is meaningless)
.venv/bin/python one_shot_webswarm_prototype/run.py --mock
```

Flags: `--max-depth` (default 3), `--max-children` (4), `--max-nodes` (25), `--no-synthesis`, `--hide-reasoning`, `--mock`, `--out DIR`.

### Output

- **Live log** with one block per routing decision: node id, depth, parent, mode, objective, `why:`, new children, and `!` notes.
- **Final tree**:
  ```
  [WIDE] What are the main factors ... (#0)
  │   why: ...
  ├── [ATOM] ... (#1)
  └── [DEEP] ... (#2)
      │   why: ...
      └── [ATOM] ... (#5, model said WIDE)
              ! max depth 2 reached; WIDE forced to ATOM
  ```
- **Stats**: node count, modes executed vs. modes chosen by the model, max depth, leaves, interventions, LLM calls by kind, failed calls, seconds, and tokens (when LM Studio reports them).
- **Trace files** `runs/<timestamp>_<slug>.json` (every node, every LLM call) and `.txt` (tree, stats, root answer).

## Simplifications and limitations

- **No search.** `ATOM` leaves answer from the model's own knowledge. Facts, numbers and dates in the answers are unverified and may be stale or hallucinated. The tree structure is the thing to study, not the answers.
- **Not WebSwarm's modes.** `DEEP` here is generic "drill down"; it has none of WebSwarm's search-and-verify loop. `WIDE` children run sequentially, not in parallel. There is no `entity_collect`, web probing or sibling experience sharing.
- **Plan-then-answer, not evidence-driven.** The whole tree is built top-down before any answers exist. Parents never see child evidence before deciding, and they cannot re-delegate or revise. This is exactly the pattern CLAUDEPROMPT.md says WebSwarm is *not* (Stage 6 is only half done). `DEEP` children also don't receive their earlier siblings' answers.
- **Breadth-first budget.** When `max_nodes` runs out, deeper branches are cut first.
- **Redundancy check is lexical.** Only exact duplicates (after normalization) are caught. Paraphrased duplicates get through, and spotting them is part of what you are meant to evaluate by eye.
- **One model for everything**, one routing call per node, and one retry on malformed JSON (a second failure falls back to `ATOM` with a note).
- **Prompts are first drafts.** Routing will be sensitive to the wording in `prompts.py`. The model also sees `max_depth`, which may bias it towards stopping.
