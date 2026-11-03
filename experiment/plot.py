"""C: results.csv에서 시나리오별 seed 평균 ± 표본 표준편차 그래프 생성.

실행/생성은 표준 라이브러리, 그래프만 matplotlib이 필요하다.
건너뛴 전수탐색이나 최적값 없는 gap을 0으로 채우지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
from pathlib import Path
from statistics import mean, stdev
import tempfile

LABELS = {"nearest_car": "Nearest-Car (online)", "ewt_greedy": "EWT (online)",
          "local_search": "Local Search (offline)", "exhaustive": "Exhaustive (offline)"}
METRICS = {"avg_wait": "Average waiting time (s)", "max_wait": "Maximum waiting time (s)",
           "runtime_sec": "Algorithm runtime (s, log scale)",
           "optimality_gap": "Optimality gap (%)"}


def load_results(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"scenario", "seed", "n", "num_elevators", "algorithm", "status", *METRICS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {sorted(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("CSV has no experiment rows")
    # 서로 다른 실험 설정을 평균 내는 일을 방지한다.
    config_fields = ("num_elevators", "num_floors", "floor_time", "stop_time", "step",
                     "initial_floors", "arrival_max", "peak_probability")
    configurations = {tuple(r.get(key, "") for key in config_fields) for r in rows}
    if len(configurations) != 1:
        raise ValueError("plot one configuration per CSV (floors, elevators, timing, arrival model)")
    if {r.get("step", "tick") for r in rows} != {"tick"}:
        raise ValueError("expected tick experiment results")
    keys = [(r["scenario"], r["n"], r["seed"], r["algorithm"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate scenario/n/seed/algorithm rows")
    return rows


def aggregate(rows: list[dict], scenario: str, algorithm: str, metric: str) -> list[tuple]:
    groups = {}
    for row in rows:
        if (row["scenario"] != scenario or row["algorithm"] != algorithm or
                row["status"] != "ok" or row[metric] in (None, "")):
            continue
        value = float(row[metric])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid {metric}: {value}")
        if metric == "optimality_gap":
            value *= 100  # CSV에는 비율, 그래프에는 %
        groups.setdefault(int(row["n"]), []).append(value)
    return [(n, mean(values), stdev(values) if len(values) > 1 else 0.0)
            for n, values in sorted(groups.items())]


def create_plots(csv_path: Path, output_dir: Path) -> list[Path]:
    rows = load_results(csv_path)
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "elevator-dispatching-mpl"))
    os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "elevator-dispatching-cache"))
    Path(os.environ["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("그래프에는 matplotlib이 필요합니다: python3 -m pip install matplotlib") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for scenario in sorted({r["scenario"] for r in rows}):
        if scenario not in ("normal", "peak"):
            raise ValueError(f"unknown scenario: {scenario!r}")
        ns = sorted({int(r["n"]) for r in rows if r["scenario"] == scenario})
        m = rows[0]["num_elevators"]
        for metric, ylabel in METRICS.items():
            fig, ax = plt.subplots(figsize=(8.4, 5.2))
            try:
                plotted = False
                for name, label in LABELS.items():
                    data = aggregate(rows, scenario, name, metric)
                    if not data:
                        continue
                    x, y, err = zip(*data)
                    if metric == "runtime_sec":
                        if any(v <= 0 for v in y):
                            raise ValueError("runtime_sec must be positive for a logarithmic plot")
                        # 0 이하의 오차 막대는 로그축에 표시할 수 없어 하단만 제한한다.
                        yerr = [[min(e, v * 0.99) for v, e in zip(y, err)], list(err)]
                    else:
                        yerr = err
                    ax.errorbar(x, y, yerr=yerr, marker="o", capsize=3, label=label)
                    plotted = True
                ax.set(title=f"{scenario.capitalize()} | M={m} | tick | mean +/- sample SD",
                       xlabel="Number of requests (N)", ylabel=ylabel)
                ax.set_xticks(ns)
                if metric == "runtime_sec":
                    ax.set_yscale("log")
                else:
                    ax.set_ylim(bottom=0)
                if plotted:
                    ax.legend(fontsize=8)
                else:
                    ax.text(0.5, 0.5, "No optimum baseline available", ha="center", va="center",
                            transform=ax.transAxes)
                ax.grid(True, alpha=0.25)
                fig.text(0.5, 0.02, "Unavailable measurements are omitted; gap uses only exact optima.",
                         ha="center", fontsize=8)
                fig.tight_layout(rect=(0, 0.04, 1, 1))
                path = output_dir / f"{scenario}_{metric}.png"
                fig.savefig(path, dpi=160)
                paths.append(path)
            finally:
                plt.close(fig)
    return paths


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path("results/results.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/plots"))
    args = parser.parse_args(argv)
    try:
        paths = create_plots(args.csv, args.output_dir)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
