"""C: 동일 입력의 네 알고리즘 비교. 모든 시뮬레이션은 tick 환경.

runtime_sec는 배정 함수 호출만 측정한다(그 안의 시뮬레이션 포함).
결과 채점은 타이머 밖에서 수행하고 evaluation_sec에 별도 기록한다.
입력 생성, 파일 저장, 최적값과 gap 계산은 runtime_sec에 포함하지 않는다.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import json
from pathlib import Path
from statistics import mean, stdev
import sys
from time import perf_counter

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from algorithms.ewt_greedy import ewt_greedy
from algorithms.exhaustive import exhaustive
from algorithms.local_search import local_search
from algorithms.nearest_car import nearest_car
from experiment.generate import (SCENARIOS, add_generation_arguments,
                                 generate_instance, generation_options)
from simulator import simulate

ALGORITHMS = {"nearest_car": nearest_car, "ewt_greedy": ewt_greedy,
              "local_search": local_search, "exhaustive": exhaustive}
FIELDS = ["scenario", "seed", "n", "num_elevators", "num_floors", "floor_time",
          "stop_time", "initial_floors", "arrival_max", "peak_probability", "step",
          "algorithm", "information", "status", "skip_reason", "candidate_count",
          "max_assignments", "avg_wait", "max_wait", "runtime_sec", "evaluation_sec",
          "optimal_avg_wait", "absolute_gap", "optimality_gap", "gap_status", "assignment"]
METRICS = ("avg_wait", "max_wait", "runtime_sec", "optimality_gap")


def compare_instance(instance: dict, *, max_assignments: int = 10_000) -> list[dict]:
    """한 입력 비교. 한도는 exhaustive에만 적용하며 나머지는 모두 실행한다."""
    if type(max_assignments) is not int or max_assignments < 1:
        raise ValueError("max_assignments must be a positive integer")
    config, elevators, requests = (instance[key] for key in ("config", "elevators", "requests"))
    n, m = len(requests), len(elevators)
    metadata = instance["metadata"]
    base = {"scenario": metadata["scenario"], "seed": metadata["seed"], "n": n,
            "num_elevators": m, **config,
            "initial_floors": json.dumps([e["floor"] for e in elevators]),
            "arrival_max": metadata["arrival_max"],
            "peak_probability": metadata["peak_probability"], "step": "tick",
            "candidate_count": m ** n, "max_assignments": max_assignments}
    rows = []
    # Seed 반복마다 실행 순서를 회전하여 항상 같은 알고리즘이 먼저 실행되는 것을 피한다.
    names = list(ALGORITHMS)
    offset = metadata["seed"] % len(names)
    for name in names[offset:] + names[:offset]:
        row = dict.fromkeys(FIELDS)
        row.update(base, algorithm=name,
                   information="offline" if name in ("local_search", "exhaustive") else "online")
        if name == "exhaustive" and m ** n > max_assignments:
            row.update(status="skipped", skip_reason="assignment_limit",
                       gap_status="baseline_unavailable")
        else:
            # 함수에 전달하는 복사 비용은 계산 시간에서 제외한다.
            inputs = deepcopy((config, elevators, requests))
            start = perf_counter()
            assignment = ALGORITHMS[name](*inputs)
            runtime = perf_counter() - start
            if (not isinstance(assignment, list) or len(assignment) != n or
                    any(type(a) is not int or not 0 <= a < m for a in assignment)):
                raise ValueError(f"{name} returned an invalid assignment: {assignment!r}")
            start = perf_counter()
            result = simulate(config, elevators, requests, assignment, step="tick")
            evaluation = perf_counter() - start
            row.update(status="ok", avg_wait=result["avg_wait"], max_wait=result["max_wait"],
                       runtime_sec=runtime, evaluation_sec=evaluation,
                       assignment=json.dumps(assignment))
        rows.append(row)
    optimum = next((r["avg_wait"] for r in rows
                    if r["algorithm"] == "exhaustive" and r["status"] == "ok"), None)
    for row in rows:
        if row["status"] != "ok":
            continue
        if optimum is None:
            row["gap_status"] = "baseline_unavailable"
        else:
            gap = row["avg_wait"] - optimum
            if gap < 0:
                raise AssertionError("an algorithm beat the exhaustive optimum")
            row.update(optimal_avg_wait=optimum, absolute_gap=gap)
            if optimum > 0:
                row.update(optimality_gap=gap / optimum, gap_status="available")
            elif gap == 0:
                row.update(optimality_gap=0.0, gap_status="available")
            else:
                # 0으로 나누는 상대 gap은 정의되지 않으므로 빈칸. 절대 gap은 유지.
                row["gap_status"] = "zero_optimum"
    return sorted(rows, key=lambda r: list(ALGORITHMS).index(r["algorithm"]))


def summarize(rows: list[dict]) -> list[dict]:
    groups = {}
    for row in rows:
        key = (row["scenario"], row["n"], row["num_elevators"], row["algorithm"])
        groups.setdefault(key, []).append(row)
    summary = []
    for key, group in sorted(groups.items()):
        good = [r for r in group if r["status"] == "ok"]
        item = dict(zip(("scenario", "n", "num_elevators", "algorithm"), key))
        item.update(runs=len(good), skipped=len(group) - len(good))
        for metric in METRICS:
            values = [r[metric] for r in good if r[metric] is not None]
            item[f"{metric}_count"] = len(values)
            item[f"{metric}_mean"] = mean(values) if values else None
            item[f"{metric}_std"] = stdev(values) if len(values) > 1 else (0.0 if values else None)
        summary.append(item)
    return summary


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, nargs="+", default=[4, 6, 8, 20])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--scenarios", choices=SCENARIOS, nargs="+", default=list(SCENARIOS))
    parser.add_argument("--max-assignments", type=int, default=10_000,
                        help="전수탐색 후보 한도(기본 10000); 초과 시 skipped 행 기록")
    parser.add_argument("--output", type=Path, default=Path("results/results.csv"))
    add_generation_arguments(parser)
    args = parser.parse_args(argv)
    if args.max_assignments < 1 or any(n < 0 for n in args.n):
        parser.error("n must be non-negative and max-assignments must be positive")
    options = generation_options(args)
    try:
        generate_instance(0, **options)  # 실행 전에 공통 옵션을 검증한다.
    except ValueError as exc:
        parser.error(str(exc))
    rows = []
    input_dir = args.output.parent / f"{args.output.stem}_inputs"
    input_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output.with_name(f"{args.output.stem}_summary.csv")
    manifest_path = args.output.with_name(f"{args.output.stem}_manifest.json")
    manifest_path.write_text(json.dumps({
        "python": sys.version, "step": "tick", "generation": options,
        "n": args.n, "seeds": args.seeds, "scenarios": args.scenarios,
        "max_assignments": args.max_assignments,
        "runtime_definition": "algorithm call only; internal simulation included; final scoring excluded",
        "gap_definition": "(avg_wait - optimal_avg_wait) / optimal_avg_wait; ratio, not percent",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for scenario in dict.fromkeys(args.scenarios):
        for n in dict.fromkeys(args.n):
            for seed in dict.fromkeys(args.seeds):
                instance = generate_instance(n, seed, scenario, **options)
                (input_dir / f"{scenario}_n{n}_seed{seed}.json").write_text(
                    json.dumps(instance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"{scenario} N={n} seed={seed} (M^N={options['num_elevators'] ** n})", flush=True)
                rows.extend(compare_instance(instance, max_assignments=args.max_assignments))
                # 입력 하나가 끝날 때마다 저장하여 긴 실험의 중간 결과도 보존한다.
                write_csv(args.output, rows, FIELDS)
                summary = summarize(rows)
                write_csv(summary_path, summary, list(summary[0]))
    print(f"결과: {args.output}\n요약: {summary_path}\n입력: {input_dir}")


if __name__ == "__main__":
    main()
