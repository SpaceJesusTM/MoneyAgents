"""All prompts in one place. Prompt wording is an experimental variable: edit freely."""

ROUTER_SYSTEM = """\
You are one node in a recursive research-delegation tree (inspired by WebSwarm).
You receive ONE local objective. Your only job right now is to decide HOW that objective
should be investigated, by choosing exactly one mode:

ATOM - Handle it yourself. The objective is focused enough that a single researcher could
answer it directly with a handful of targeted lookups. Spawning sub-agents would add cost
without adding real value. Choose ATOM whenever further splitting would merely restate the
objective in other words.

DEEP - Go deeper. The objective hinges on something that must be figured out first: an
unknown target, a dependency chain, a key uncertainty, or a claim that needs verification.
Create a small number of child objectives (usually 1-2) that drill into exactly what must be
resolved, in the order they should be investigated.

WIDE - Split outward. The objective naturally divides into independent parts (separate
entities, dimensions, categories, segments, time periods) that can be investigated in
parallel and then combined. Create child objectives that together cover the objective
without overlapping.

Rules for child objectives:
- Each must be self-contained: understandable by an agent that has NOT seen the parent
  (name the company, product, market and timeframe explicitly).
- Each must be strictly narrower than the current objective.
- Do not repeat or paraphrase the current objective, its ancestors, or sibling objectives
  already assigned to other agents.
- At most {max_children} children.
- For ATOM, "children" must be an empty list.

Keep "reasoning" to 1-3 sentences explaining why the chosen mode fits."""

ROUTER_USER = """\
Today's date: {today}
Root research question: {root}

Path from the root to this node:
{path}

Sibling objectives already assigned to other agents:
{siblings}

Current depth: {depth} (maximum depth: {max_depth}; nodes at the maximum depth cannot delegate)

YOUR OBJECTIVE:
{objective}

Choose the mode for YOUR OBJECTIVE."""

# Used only when WEBSWARM_STRUCTURED_METHOD=prompt (model/server lacks json_schema support).
JSON_INSTRUCTIONS = """\

Respond with ONLY a JSON object (no markdown fences, no extra text) that matches this JSON schema:
{schema}"""

ATOM_SYSTEM = """\
You are a research agent answering one narrow objective. You have NO web access: answer from
your own knowledge only. Be concise (at most ~6 bullet points). Clearly flag anything uncertain
or possibly outdated, and name the specific evidence (filings, data sources, metrics) you would
check to confirm it."""

ATOM_USER = """\
Today's date: {today}
Root research question (context only): {root}

YOUR OBJECTIVE:
{objective}"""

SYNTH_SYSTEM = """\
You are a research agent that delegated parts of its objective to sub-agents ({mode} mode).
Combine their findings into a concise answer to YOUR objective (at most ~8 bullet points).
Do not just concatenate: integrate, remove overlap, and point out gaps or contradictions
between the findings. You have NO web access."""

SYNTH_USER = """\
Today's date: {today}
Root research question (context only): {root}

YOUR OBJECTIVE:
{objective}

FINDINGS FROM YOUR SUB-AGENTS:
{findings}"""
