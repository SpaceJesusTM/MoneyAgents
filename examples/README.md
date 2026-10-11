# Example runs

Saved live runs (real local model, real web content). Each folder has `report.md` (answer, sources,
grounding audit, agent tree, statistics), `run.json` (config, manifest, every node, source and
finding) and `trace.jsonl` (every decision, model call and web call, timestamped).

| Folder | What it shows |
|---|---|
| `baseline_A1_atom_correct` | A single agent answering a factual question correctly from a primary-source PDF |
| `baseline_A2_atom_failure_caught_by_audit` | An honest "not found", plus an invented figure that the programmatic audit flags |
| `baseline_W1_wide_with_follow_ups` | WIDE over three companies, with follow-up agents added after a child came back empty |
| `baseline_D1_deep_with_verifier` | DEEP: investigate, decide, verify. Also a failure: it names the wrong supplier and the verifier passes a non-claim |
| `baseline_M1_nvidia_mixed_wide_deep` | The NVIDIA data-center question: 11 agents, a nested DEEP child whose claim an independent verifier refutes |
| `baseline_E1_entity_collect` | ENTITY_COLLECT: three discovery paths, merged list with support counts, one name independently checked |
| `optimized_W1_rules_plus_correct_and_cited` | The same comparison in under half the time with all six margin figures right and cited to primary sources (rules decider, line extraction, citation retry). One sentence of its commentary contradicts itself. |
| `optimized_M2_rules_plus_fast` | An open-ended question in 103 s against the baseline's 718 s, with 5 agents instead of 12 |
| `optimized_M1_typed_2b_decisions` | Typed one-token decisions from the 2B model steering the 4B researcher |
| `failed_W2_rules_v1_dropped_siblings` | The first rules version dropping two of three companies as "redundant": a fast wrong control decision |
