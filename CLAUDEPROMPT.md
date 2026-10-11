# Money Agents — WebSwarm-Inspired Local Subagent Prototype

## 1. Context

This work is an early prototype for the **Money Agents** project. The purpose is not to build the final Money Agents architecture yet. The immediate goal is to investigate whether ideas from the WebSwarm paper are useful for a future multi-agent financial research system, especially when orchestration is performed using a **local LLM**.

Primary reference:

**WebSwarm: Recursive Multi-Agent Orchestration for Deep-and-Wide Web Search**  
Xiaoshuai Song et al., 2026  
arXiv:2607.08662

Paper: https://arxiv.org/abs/2607.08662

The implementation should remain experimental and modular. We want to learn from the prototype before committing to a final architecture.

---

# 2. What WebSwarm Is Trying to Solve

WebSwarm focuses on complex web research tasks requiring both:

- **Depth** — following multi-step dependencies, clues, constraints, and verification chains.
- **Width** — gathering information across many entities, dimensions, sources, or candidates.

The paper argues that a single ReAct-style search agent becomes constrained by one long search trajectory and limited context.

It also argues that many existing multi-agent approaches still have three important weaknesses:

1. They often decompose the task mainly at the beginning rather than allowing the decomposition to grow recursively.
2. They often use one fixed collaboration pattern across all subtasks.
3. Their decomposition may be based on the wording of the question rather than on how information is actually organized on the web.

WebSwarm's key idea is therefore **progressive recursive delegation**.

Instead of deciding the complete task tree in advance, the system constructs and modifies the search tree while the investigation is happening.

---

# 3. Core WebSwarm Architecture

A WebSwarm search node is essentially defined by:

```text
(local objective, search mode)
```

The **local objective** specifies what that node needs to solve.

The **search mode** specifies how that objective should be investigated.

A node can gather evidence, create child nodes, receive results from those children, and then decide whether it should:

- continue investigating,
- create additional delegations,
- revise its search direction,
- aggregate the evidence,
- or return a result to its parent.

This produces a dynamically constructed delegation tree rather than a predetermined workflow.

Conceptually:

```text
Root objective
      |
      v
Search node
      |
      +-- investigate
      |
      +-- delegate child objective
      |       |
      |       +-- possibly delegate again
      |
      +-- receive child evidence
      |
      +-- continue / revise / finish
      |
      v
Return result upward
```

The important architectural property is the combination of:

**top-down delegation + bottom-up evidence feedback.**

---

# 4. WebSwarm's Four Search Modes

The paper defines four modes.

## ATOM

Used for narrow factual search.

An atom node behaves approximately like a ReAct search agent: it searches, reads pages, gathers evidence, and answers its local objective.

```text
focused objective
      |
    search
      |
    inspect
      |
    search
      |
    answer
```

## DEEP

Used for problems involving unknown-target identification or multiple constraints.

WebSwarm's actual `deep` mode is more specific than simply "recursive search." It uses an iterative **search-and-verification** structure. Searchers propose candidates/evidence and verifier agents independently check whether those candidates satisfy the required constraints.

## WIDE

Used when information needs to be gathered across multiple known entities or dimensions.

It performs parallel divide-and-conquer and then aggregates the results.

Importantly, children of a wide node do not have to be atoms. They can themselves be `deep`, `wide`, or `entity_collect`, which allows depth and breadth to become nested.

## ENTITY_COLLECT

Used when the required set of entities is **not known beforehand**.

Multiple search paths attempt to discover candidate entities. Their results are then merged, deduplicated, and low-confidence candidates are verified.

Example:

```text
"Find the important companies involved in X"
```

where the list of relevant companies is itself something the system must discover.

---

# 5. Other Important WebSwarm Mechanisms

## Web Probing

Before certain wide expansions, WebSwarm performs a lightweight preliminary investigation of how the relevant information is organized online.

The purpose is to avoid decomposing a problem purely based on its wording.

For example, the system may discover that the required information is:

- concentrated in a few aggregate pages,
- separated by company,
- separated by year,
- organized around events,
- or distributed across some other useful dimension.

This structure then influences how child nodes are created.

This is especially interesting for Money Agents.

The WebSwarm ablation results suggest that removing web probing affected accuracy relatively little compared with its effect on **web-tool usage**. Without probing, the system made substantially more web-tool calls on some benchmarks.

Therefore, one future research question for Money Agents is whether lightweight probing can reduce:

- search/tool calls,
- latency,
- API usage,
- duplicated retrieval,
- and potentially cost,

without meaningfully hurting answer quality.

## Sibling Experience Sharing

When a wide node produces many similar child tasks, WebSwarm initially runs a small subset as scouts.

Useful search strategies, source patterns, and failure lessons from those agents can then guide later sibling agents.

This attempts to prevent many parallel agents from independently rediscovering the same search strategy.

---

# 6. Why This Matters for Money Agents

Financial research frequently has both depth and width.

For example:

```text
Investigate the major risks to Company X
```

might initially produce:

```text
Company X risks
├── demand
├── competition
├── supply
└── financial position
```

While investigating supply, an agent may discover a previously unknown dependency:

```text
supply
└── advanced packaging constraint
      ├── supplier capacity
      └── geographic concentration
```

Those deeper questions may not have been obvious from the original prompt.

This is why progressive recursive delegation could be useful for Money Agents: the investigation can expand **in response to evidence**, rather than requiring a planner to anticipate the complete research structure beforehand.

However, we do not yet know whether this architecture is necessary or whether smaller/local models are capable of controlling it reliably.

That is what this prototype should help investigate.

---

# 7. Goal of This Prototype

The goal is **not to reproduce WebSwarm**.

The goal is to build a small experimental environment that captures enough of its central idea to answer:

> Can a local LLM make useful WebSwarm-inspired delegation and task-decomposition decisions?

The local LLM will be run through **LM Studio**.

LangGraph is likely to be used as the orchestration/state framework, but the implementation should prioritize clarity and experimentation over forcing everything into a complicated framework.

The prototype should make it easy to observe what the model is doing.

---

# 8. Initial Simplification

For the first prototype, we will experiment with three conceptual decisions:

```text
ATOM
DEEP
WIDE
```

For our prototype these initially mean approximately:

### ATOM — handle locally

The objective appears sufficiently narrow that additional subagents are unnecessary.

This tests whether the model can recognize when **not to spawn agents**.

### DEEP — investigate further

The objective contains dependencies, uncertainty, constraints, or unanswered questions that justify further investigation.

This is where deeper delegation may occur.

### WIDE — divide across parallel objectives

The problem naturally separates across known entities, dimensions, cases, or categories that can be investigated independently.

This is where multiple child objectives may be produced.

---

# 9. Important Difference From the Paper

These definitions are intentionally simplified for experimentation.

They should **not** be described as an exact reproduction of WebSwarm's search modes.

In particular:

- WebSwarm's `atom` is specifically a ReAct-style web searcher.
- WebSwarm's `deep` uses a more specific serial search-and-verification protocol.
- WebSwarm's `wide` implements parallel divide-and-conquer and can recursively contain different node modes.
- WebSwarm's `entity_collect` uses multi-path discovery, merging, deduplication, and verification.

Initially, our prototype is primarily interested in whether a local model can distinguish among the structural choices:

```text
solve / don't expand
        vs.
go deeper
        vs.
split outward
```

If this works, we can move progressively closer to the actual WebSwarm protocols.

---

# 10. Why ENTITY_COLLECT Is Not Part of the First Prototype

`entity_collect` introduces another research problem: discovering an unknown set of entities.

That introduces additional concerns such as:

- recall,
- candidate discovery,
- deduplication,
- confidence,
- merging,
- and verification.

Those could make it difficult to diagnose whether a failure comes from recursive orchestration or from entity-discovery quality.

Therefore it should be considered a later extension rather than part of the initial experiment.

It may eventually be highly relevant to financial research, particularly for discovering unknown:

- suppliers,
- competitors,
- counterparties,
- companies exposed to an event,
- industry participants,
- risks,
- or related entities.

---

# 11. Development Stages

## Stage 1 — Reproducible Local Development Environment

Set up the repository so another team member can clone the branch and reproduce the environment easily.

The project currently uses:

- Python virtual environment (`.venv`)
- `requirements.txt`
- `.env`
- `.env.example`
- `.gitignore`
- source directory
- tests directory

LM Studio-specific configuration should remain configurable rather than being scattered or hard-coded throughout the project.

The project should eventually have straightforward setup/run instructions in the README.

---

## Stage 2 — Local LLM Connectivity

Connect Python to an LLM running through LM Studio's local API.

At this stage, simply verify:

```text
Money Agents prototype
        |
        v
LM Studio API
        |
        v
Local model
```

No agents or recursion are necessary yet.

The point is simply to establish a reliable local inference layer that later components can use.

---

## Stage 3 — Objective Classification / Routing

Give the local model an objective and investigate whether it can make sensible high-level decisions such as:

```text
ATOM
DEEP
WIDE
```

The output should be observable and preferably structured enough that downstream orchestration can use it reliably.

At this point we want to experiment with different types of prompts/tasks and understand where the model succeeds or fails.

Examples of questions:

- Does it over-decompose simple questions?
- Does it mistake broad problems for deep ones?
- Can it identify naturally parallel problems?
- How sensitive is the decision to prompt wording?
- Does the chosen local model have sufficient reasoning capability for orchestration?

---

## Stage 4 — Generate Local Objectives

Once routing is reasonably stable, allow appropriate decisions to generate child objectives.

The quality of these child objectives is important.

We should inspect whether they are:

- distinct,
- relevant,
- sufficiently self-contained,
- collectively useful,
- non-redundant,
- and appropriately scoped.

A failure such as:

```text
Parent:
Analyze NVIDIA growth.

Children:
- Analyze NVIDIA.
- Analyze NVIDIA growth.
- Investigate NVIDIA revenue.
```

would indicate poor decomposition.

A more useful decomposition could look like:

```text
Parent:
Analyze NVIDIA data-center growth.

Children:
- hyperscaler demand
- accelerator supply constraints
- competitive dynamics
- customer concentration
```

The goal is not to prescribe the correct decomposition beforehand, but to evaluate whether meaningful structures emerge.

---

## Stage 5 — Recursive Delegation

Allow child objectives to make similar decisions themselves.

This creates the core experimental delegation tree:

```text
ROOT
├── child
│   ├── grandchild
│   └── grandchild
├── child
└── child
    └── grandchild
```

The tree should be dynamic rather than completely planned at the root.

This is the main architectural idea we want to take from WebSwarm.

Recursion must have explicit limits so a poor model decision cannot generate uncontrolled expansion.

Relevant controls may include concepts such as:

- maximum depth,
- maximum children per node,
- maximum nodes per run,
- execution/token budgets,
- and stopping conditions.

The precise implementation can evolve during experimentation.

---

## Stage 6 — Bottom-Up Results

Eventually, child nodes should return results/evidence to their parent.

Parents should be able to use those results to decide whether to:

```text
finish
continue
delegate again
revise direction
aggregate
```

This is important because WebSwarm is not simply:

```text
plan tree → execute tree → summarize
```

The search structure can evolve based on intermediate evidence.

That evidence-driven continuation is something we ultimately want to experiment with.

---

## Stage 7 — Add Search

Only once the delegation mechanism is understandable should actual search tooling be introduced.

At that point, an `ATOM`-style node can move closer to the paper's ReAct search agent:

```text
objective
   ↓
decide what information is missing
   ↓
search
   ↓
observe evidence
   ↓
possibly search/read again
   ↓
answer
```

This will let us test whether recursive delegation provides benefits when agents are actually gathering external evidence rather than only reasoning over prompts.

---

## Stage 8 — Move Closer to WebSwarm

If the basic architecture is promising, later experiments can introduce more faithful WebSwarm components individually.

Possible extensions include:

### More faithful DEEP mode

Experiment with separate search and verification behavior rather than treating deep as generic recursion.

### Web probing

Probe the structure of available information before wide decomposition.

This is particularly interesting because reducing tool calls may be an important Money Agents objective.

### Sibling experience sharing

Allow similar child nodes to benefit from strategies discovered by earlier siblings.

### ENTITY_COLLECT

Introduce open-set entity discovery where relevant.

These should be added separately so we can understand the contribution of each feature rather than introducing the entire WebSwarm architecture simultaneously.

---

# 12. What We Should Observe

This prototype should prioritize **observability**.

For each run, we should eventually be able to understand:

```text
Original objective

Decision made at each node

Why the model chose that direction

Child objectives generated

Delegation tree

Maximum depth

Number of agents/nodes created

Model calls

Tool calls, once tools exist

Execution time

Potentially token usage

Final result
```

The exact logging format does not need to be finalized immediately.

The important thing is that recursive behavior should not become a black box.

---

# 13. Primary Experimental Questions

The prototype should help us investigate:

### Delegation quality

Can a local LLM determine when another agent is actually useful?

### Stopping behavior

Can it avoid unnecessary agent creation?

This may be as important as its ability to spawn agents.

### Decomposition quality

Are generated objectives meaningful and non-redundant?

### Depth vs. breadth

Can it distinguish between problems requiring deeper investigation and problems naturally divisible into parallel work?

### Recursive stability

At what depth does decomposition quality begin to deteriorate?

### Local-model capability

Is a local model sufficiently capable to act as the orchestration model?

It does not necessarily need to be the strongest eventual research model if it can reliably make orchestration decisions.

### Efficiency

How many model/tool calls are required?

Can smarter decomposition reduce unnecessary computation?

This will become particularly important once web probing is tested.

---

# 14. What We Are NOT Trying to Do Yet

Do not prematurely turn this prototype into the final Money Agents system.

The initial work does **not** need:

- full financial analysis functionality,
- portfolio integration,
- multiple model routing,
- RAG/vector databases,
- embeddings,
- production deployment,
- every WebSwarm mode,
- benchmark reproduction,
- complex user interfaces,
- WebSwarm sibling experience sharing,
- WebSwarm web probing immediately,
- or exact reproduction of the paper.

These can be considered later if justified by what we learn.

---

# 15. This Week's Target

The most useful result for this week would be a small experimental sandbox where:

1. A local model can be called through LM Studio.
2. It receives research objectives.
3. It makes WebSwarm-inspired structural decisions.
4. It can generate useful local child objectives.
5. Some form of recursive spawning/delegation can be demonstrated.
6. The resulting delegation structure can be inspected.
7. Several example tasks can be run to identify obvious strengths and failure modes.

Actual web search is useful if there is time, but understanding the **delegation mechanism itself is the priority**.

The weekly outcome should answer something more meaningful than:

> "We managed to spawn multiple agents."

Ideally, we should instead be able to say something like:

> "We tested whether a local LLM can dynamically construct WebSwarm-inspired delegation trees, observed where ATOM/DEEP/WIDE decisions work or fail, and identified what needs to change before connecting this architecture to real web/financial research."

---

# 16. Longer-Term Connection to Money Agents

If this experiment works, a future Money Agents research system could potentially use:

```text
User financial research question
            |
            v
Local orchestration agent
            |
      progressive delegation
            |
      +-----+-----+
      |           |
   research    research
      |           |
      +---- deeper branches as evidence requires
            |
            v
       evidence synthesis
```

The local model could potentially handle relatively inexpensive orchestration while specialized or stronger models handle tasks where they are actually needed.

That is only a hypothesis at this stage.

The purpose of this prototype is to gather evidence about whether that architecture is worth pursuing.

---

# 17. Guiding Principle

When implementing this prototype, favor:

**simple, observable experiments over architectural complexity.**

The objective is to understand WebSwarm-style recursive delegation with local models, not to build an impressive but difficult-to-evaluate agent framework.

When an implementation choice is unclear, prefer the design that makes it easier to answer:

> Why did this node spawn, what objective did it give its children, what happened, and was that delegation actually useful?