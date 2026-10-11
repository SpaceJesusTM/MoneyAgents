# MoneyAgents
make money, make no mistakes

## WebSwarm-inspired research system

A recursive multi-agent web research baseline on a local Ollama model, plus measured optimization
experiments. Start here:

| Document | What it covers |
|---|---|
| [`webswarm_baseline/README.md`](webswarm_baseline/README.md) | Setup, run commands, architecture, differences from the WebSwarm paper |
| [`experiments/README.md`](experiments/README.md) | Optimization arms, the Jev adapter, the benchmark |
| [`BASELINE_RESULTS.md`](BASELINE_RESULTS.md) | What the baseline did on 9 live tasks, including its failures |
| [`OPTIMIZATION_RESULTS.md`](OPTIMIZATION_RESULTS.md) | Baseline versus optimized arms |
| [`DESIGN_DECISIONS.md`](DESIGN_DECISIONS.md) | Decision log with sources |
| [`OVERNIGHT_PROGRESS.md`](OVERNIGHT_PROGRESS.md) | Build log, blockers, how to resume |
| [`examples/`](examples/) | Six saved live runs: report, agent tree, full trace |

```bash
.venv/bin/pip install -r requirements.txt -r webswarm_baseline/requirements.txt
ollama pull qwen3.5:4b-q4_K_M
.venv/bin/python -m webswarm_baseline.run "What was NVIDIA's data center revenue for fiscal year 2025?"
.venv/bin/python -m pytest webswarm_baseline/tests experiments/tests -q
```

The earlier structural prototype is unchanged in `one_shot_webswarm_prototype/`.
