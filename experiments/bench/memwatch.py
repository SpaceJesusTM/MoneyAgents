"""Sample memory while a benchmark runs: swap in use, free memory, pageouts and the model runner's size.

    .venv/bin/python -m experiments.bench.memwatch experiments/results/<set>/memory_<arm>.csv &

One row every 5 seconds until killed. Read-only: `sysctl`, `vm_stat`, `memory_pressure`, `ps`.
The machine's swap total is system-wide, so other applications show up in it too; the columns that
isolate the benchmark are the change in swap and pageouts over a run and the runner's own size.
"""
from __future__ import annotations

import csv
import re
import subprocess
import sys
import time


def sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return ""


def sample() -> dict:
    swap = re.search(r"used = ([\d.]+)M", sh("sysctl", "-n", "vm.swapusage"))
    vm = sh("vm_stat")
    num = lambda name: int((re.search(name + r":\s+(\d+)", vm) or [0, 0])[1])   # noqa: E731
    free = re.search(r"free percentage: (\d+)%", sh("memory_pressure"))
    rss = 0
    for line in sh("ps", "-axo", "rss=,command=").splitlines():
        if "llama-server" in line or "ollama runner" in line:
            rss += int(line.split()[0])
    loaded = [ln.split()[0] for ln in sh("ollama", "ps").splitlines()[1:] if ln.strip()]
    return {"time": time.strftime("%H:%M:%S"), "swap_used_mb": float(swap.group(1)) if swap else None,
            "free_pct": int(free.group(1)) if free else None, "pageouts": num("Pageouts"),
            "swapouts": num("Swapouts"), "runner_rss_mb": round(rss / 1024), "loaded": "+".join(loaded)}


def main() -> None:
    path = sys.argv[1]
    with open(path, "w", newline="") as fh:
        w = None
        while True:
            row = sample()
            if w is None:
                w = csv.DictWriter(fh, fieldnames=list(row))
                w.writeheader()
            w.writerow(row)
            fh.flush()
            time.sleep(5)


if __name__ == "__main__":
    main()
