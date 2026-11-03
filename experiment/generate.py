"""C: seed로 재현 가능한 normal/peak 입력. 표준 라이브러리만 필요하다.

normal: 서로 다른 출발/도착층을 균등 추출.
peak: 확률 peak_probability로 1층→상층, 나머지는 normal.
두 시나리오 모두 도착 간격은 0..arrival_max초 정수이다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

SCENARIOS = ("normal", "peak")


def generate_requests(n: int, seed: int = 0, scenario: str = "normal", *,
                      num_floors: int = 20, arrival_max: int = 10,
                      peak_probability: float = 0.8) -> list[dict]:
    if not isinstance(n, int) or n < 0:
        raise ValueError("n must be a non-negative integer")
    if not isinstance(num_floors, int) or num_floors < 2:
        raise ValueError("num_floors must be an integer >= 2")
    if not isinstance(arrival_max, int) or arrival_max < 0:
        raise ValueError("arrival_max must be a non-negative integer")
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    if not 0 <= peak_probability <= 1:
        raise ValueError("peak_probability must be between 0 and 1")
    rng = random.Random(seed)
    time, requests = 0, []
    for i in range(n):
        time += rng.randint(0, arrival_max)
        if scenario == "peak" and rng.random() < peak_probability:
            origin, dest = 1, rng.randint(2, num_floors)
        else:
            origin, dest = rng.sample(range(1, num_floors + 1), 2)
        requests.append({"id": i, "time": time, "origin": origin, "dest": dest})
    return requests


def generate_instance(n: int, seed: int = 0, scenario: str = "normal", *,
                      num_floors: int = 20, num_elevators: int = 3,
                      initial_floors: list[int] | None = None,
                      floor_time: int = 2, stop_time: int = 5,
                      arrival_max: int = 10, peak_probability: float = 0.8) -> dict:
    requests = generate_requests(n, seed, scenario, num_floors=num_floors,
                                 arrival_max=arrival_max,
                                 peak_probability=peak_probability)
    if not isinstance(num_elevators, int) or not 1 <= num_elevators <= num_floors:
        raise ValueError("num_elevators must be between 1 and num_floors")
    if not isinstance(floor_time, int) or floor_time < 1:
        raise ValueError("floor_time must be a positive integer")
    if not isinstance(stop_time, int) or stop_time < 1:
        raise ValueError("stop_time must be a positive integer")
    if initial_floors is None:
        # 기본 20층/3대일 때 [1, 10, 20]. 한 대면 1층.
        initial_floors = ([1] if num_elevators == 1 else
                          [1 + i * (num_floors - 1) // (num_elevators - 1)
                           for i in range(num_elevators)])
    if (len(initial_floors) != num_elevators or
            any(type(f) is not int or not 1 <= f <= num_floors for f in initial_floors) or
            len(set(initial_floors)) != num_elevators):
        raise ValueError("initial_floors must contain one distinct valid floor per elevator")
    return {
        "config": {"num_floors": num_floors, "floor_time": floor_time, "stop_time": stop_time},
        "elevators": [{"id": i, "floor": f} for i, f in enumerate(initial_floors)],
        "requests": requests,
        "metadata": {"scenario": scenario, "seed": seed, "n": n,
                     "arrival_max": arrival_max, "peak_probability": peak_probability},
    }


def add_generation_arguments(parser: argparse.ArgumentParser) -> None:
    """generate/run이 동일한 입력 옵션과 기본값을 사용한다."""
    parser.add_argument("--num-floors", type=int, default=20)
    parser.add_argument("--num-elevators", type=int, default=3)
    parser.add_argument("--initial-floors", type=int, nargs="+")
    parser.add_argument("--floor-time", type=int, default=2)
    parser.add_argument("--stop-time", type=int, default=5)
    parser.add_argument("--arrival-max", type=int, default=10)
    parser.add_argument("--peak-probability", type=float, default=0.8)


def generation_options(args: argparse.Namespace) -> dict:
    return {key: getattr(args, key) for key in (
        "num_floors", "num_elevators", "initial_floors", "floor_time",
        "stop_time", "arrival_max", "peak_probability")}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--output", type=Path, help="생략하면 JSON을 화면에 출력")
    add_generation_arguments(parser)
    args = parser.parse_args(argv)
    try:
        instance = generate_instance(args.n, args.seed, args.scenario, **generation_options(args))
    except ValueError as exc:
        parser.error(str(exc))
    content = json.dumps(instance, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
        print(args.output)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
