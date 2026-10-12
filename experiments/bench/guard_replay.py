"""Replay the deterministic guards over runs that were recorded before the guards existed.

    .venv/bin/python -m experiments.bench.guard_replay

No model and no network: it reads saved runs (examples/*/run.json, tracked; and
experiments/results/*/runs/*/run.json, local only) and, for page text, the local web recordings
under experiments/bench/cassettes/. It answers "what would each guard have done on those runs?":

  - verify_guard   which claims that were sent to a verifier would have been refused
  - claim_checks   which stored findings would have been rejected or changed
  - numeric_guard  which final answers contain an ordering statement their figures contradict

Writes experiments/results/regrade_v2/guard_replay.md. This shows where the guards fire and where
they stay quiet. It cannot show what the model would have written next; only a live run can.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from webswarm_baseline import guards
from webswarm_baseline.config import REPO_ROOT
from webswarm_baseline.textutil import clean_page_text

from .run_bench import CASSETTES, RESULTS, load_tasks

OUT = RESULTS / "regrade_v2" / "guard_replay.md"


def saved_runs() -> list[tuple[str, dict]]:
    seen, out = set(), []
    paths = sorted(RESULTS.glob("*/runs/*/run.json")) + sorted((REPO_ROOT / "examples").glob("*/run.json"))
    for p in paths:
        if p.parent.parent.parent.name.startswith(("smoke", "reliability")):
            continue          # only runs recorded before the guards existed
        run = json.loads(p.read_text())
        key = (run["question"], run["config"]["name"], (run.get("manifest") or {}).get("created"))
        if key not in seen:
            seen.add(key)
            out.append((str(p.parent.relative_to(REPO_ROOT)), run))
    return out


def page_texts() -> dict[str, str]:
    texts = {}
    for p in CASSETTES.glob("*/fetch_*.json"):
        e = json.loads(p.read_text())
        if (e["response"].get("text") or ""):
            texts.setdefault(e["key"], clean_page_text(e["response"]["text"]))
    return texts


def main() -> None:
    runs, texts = saved_runs(), page_texts()
    task_of = {t["question"]: t["id"] for t in load_tasks().values()}
    md = ["# Guards replayed over recorded runs", "",
          f"{len(runs)} saved runs (recorded before the guards existed), page text for {len(texts)} recorded pages. "
          "No model, no network. See the module docstring of `experiments/bench/guard_replay.py` for what this "
          "can and cannot show.", ""]

    # ---- verify_guard
    claims = [(where, run, n) for where, run in runs for n in run["nodes"] if n["role"] == "verifier"]
    refused = [(w, r, n) for w, r, n in claims if not guards.verifiable_part(n["objective"])]
    verdicts = Counter((n.get("result") or {}).get("verdict") or "none" for _, _, n in refused)
    md += ["## verify_guard", "",
           f"Claims sent to a verifier: **{len(claims)}**. Claims the guard would have refused because they only "
           f"describe missing information: **{len(refused)}**. Verdicts those claims received at the time: "
           f"{dict(verdicts)}.", "",
           "| Task | Config | Verdict then | Claim that was sent |", "|---|---|---|---|"]
    for _, run, n in refused:
        md.append(f"| {task_of.get(run['question'], '?')} | `{run['config']['name']}` | "
                  f"{(n.get('result') or {}).get('verdict')} | {n['objective'][:150]}... |")
    kept = [n["objective"] for _, _, n in claims if guards.verifiable_part(n["objective"])]
    md += ["", f"The other {len(kept)} claims would have been sent as they were (after dropping any clause that "
               "reports a gap). Examples:", ""] + [f"- {c[:140]}" for c in sorted(set(kept))[:6]] + [""]

    # ---- claim_checks
    total = checked = 0
    outcome, examples = Counter(), []
    for where, run in runs:
        src = {s["id"]: s for s in run["evidence"]["sources"]}
        for f in run["evidence"]["findings"]:
            total += 1
            s = src[f["source_id"]]
            text = texts.get(s["url"]) if s["kind"] == "page" else f"{s['title']} {f['quote']}"
            if text is None:
                outcome["page text not recorded locally"] += 1
                continue
            checked += 1
            c = guards.check_claim(f["claim"], f["quote"], text)
            kind = "kept unchanged" if c.ok and not c.reason else \
                ("rejected: " + ("basis label contradicts the passage" if "labelled" in c.reason else
                                 "figure not in the source text")) if not c.ok else \
                ("changed: " + ("unsupported clause dropped" if "dropped" in c.reason else "") +
                 (" + " if "dropped" in c.reason and "removed" in c.reason else "") +
                 ("basis label removed" if "removed" in c.reason else ""))
            outcome[kind] += 1
            if kind != "kept unchanged":
                examples.append((task_of.get(run["question"], "?"), run["config"]["name"], kind, f["claim"], c))
    md += ["## claim_checks", "", f"Stored findings: **{total}**; checked against their source text: **{checked}**.", "",
           "| Outcome | Findings |", "|---|---:|"] + [f"| {k} | {v} |" for k, v in outcome.most_common()]
    md += ["", "Distinct findings the checks would have rejected or changed (first 30):", "",
           "| Task | Outcome | Claim as stored | Reason / claim after |", "|---|---|---|---|"]
    shown = set()
    for task, cfg, kind, claim, c in examples:
        if claim in shown or len(shown) >= 30:
            continue
        shown.add(claim)
        after = c.reason if not c.ok else f"{c.reason} -> {c.claim}"
        md.append(f"| {task} | {kind} | {claim[:170]} | {after[:230]} |")
    md.append("")

    # ---- numeric_guard
    flagged = [(run, i) for _, run in runs for i in guards.ordering_issues(run["outcome"]["answer"])]
    md += ["## numeric_guard (ordering check on final answers)", "",
           f"Final answers: **{len(runs)}**; answers with an ordering statement contradicted by figures: "
           f"**{len({id(r) for r, _ in flagged})}**.", "", "| Task | Config | What the check found |", "|---|---|---|"]
    md += [f"| {task_of.get(r['question'], '?')} | `{r['config']['name']}` | {i['detail']} |" for r, i in flagged]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(md) + "\n")
    print(f"{len(runs)} runs replayed -> {OUT}")


if __name__ == "__main__":
    main()
