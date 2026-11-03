"""C 검증: python3 -m unittest experiment.test_c -v (저장소 루트에서 실행)."""
from copy import deepcopy
from itertools import product
import csv
import importlib
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from algorithms.exhaustive import algorithm, exhaustive
from experiment.generate import generate_instance, generate_requests
from experiment.plot import aggregate, load_results
from experiment.run import ALGORITHMS, compare_instance, summarize
from simulator import SimulationError, Simulator, simulate

ROOT = Path(__file__).resolve().parents[1]
EXHAUSTIVE_MODULE = importlib.import_module("algorithms.exhaustive")


class TestExhaustive(unittest.TestCase):
    def test_matches_independent_integer_total_oracle(self):
        for scenario in ("normal", "peak"):
            for seed in range(4):
                case = generate_instance(4, seed, scenario, num_floors=7, num_elevators=2)
                config, cars, requests = (case[k] for k in ("config", "elevators", "requests"))
                before = deepcopy(case)
                def key(assignment):
                    waits = list(simulate(config, cars, requests, list(assignment))["wait_times"].values())
                    return sum(waits), max(waits), assignment
                expected = min(product(range(2), repeat=4), key=key)
                self.assertEqual(exhaustive(config, cars, requests), list(expected))
                self.assertEqual(case, before)

    def test_evaluates_every_candidate_even_when_first_has_zero_wait(self):
        case = generate_instance(3, num_elevators=2)
        with patch.object(EXHAUSTIVE_MODULE, "simulate", return_value={"avg_wait": 0, "max_wait": 0}) as spy:
            result = exhaustive(case["config"], case["elevators"], case["requests"])
        self.assertEqual(result, [0, 0, 0])
        self.assertEqual(spy.call_count, 8)
        self.assertEqual([tuple(c.args[3]) for c in spy.call_args_list], list(product(range(2), repeat=3)))
        self.assertTrue(all(c.kwargs["step"] == "tick" for c in spy.call_args_list))

    def test_tie_breaking_average_then_max_then_lexicographic(self):
        case = generate_instance(2, num_elevators=2)
        # 00은 평균이 같지만 최대가 나쁘다. 01/10 동률은 사전식 순서로 01.
        scores = {(0, 0): (1, 2), (0, 1): (1, 1), (1, 0): (1, 1), (1, 1): (2, 0)}
        def score(config, cars, requests, assignment, **kwargs):
            avg, maximum = scores[tuple(assignment)]
            return {"avg_wait": avg, "max_wait": maximum}
        with patch.object(EXHAUSTIVE_MODULE, "simulate", side_effect=score):
            self.assertEqual(algorithm(case["config"], case["elevators"], case["requests"]), [0, 1])

    def test_empty_single_car_and_unsorted_cars(self):
        case = generate_instance(0)
        self.assertEqual(algorithm(case["config"], case["elevators"], []), [])
        one = generate_instance(4, num_elevators=1)
        self.assertEqual(exhaustive(one["config"], one["elevators"], one["requests"]), [0] * 4)
        config = {"num_floors": 5}
        cars = [{"id": 1, "floor": 5}, {"id": 0, "floor": 1}]
        requests = [{"id": 0, "time": 0, "origin": 3, "dest": 4}]
        self.assertEqual(exhaustive(config, cars, requests), [0])

    def test_invalid_input_uses_simulator_validation(self):
        with self.assertRaises(SimulationError):
            exhaustive({}, [], [])
        with self.assertRaises(SimulationError):
            exhaustive({}, [{"id": 1, "floor": 1}], [])
        with self.assertRaises(SimulationError):
            exhaustive({}, [{"id": 0, "floor": 1}],
                       [{"id": 0, "time": 0, "origin": 2, "dest": 2}])


class TestGeneration(unittest.TestCase):
    def test_reproducibility_bounds_and_no_global_random_effect(self):
        state = random.getstate()
        for scenario in ("normal", "peak"):
            a = generate_instance(100, 17, scenario)
            self.assertEqual(a, generate_instance(100, 17, scenario))
            self.assertNotEqual(a["requests"], generate_instance(100, 18, scenario)["requests"])
            previous = 0
            for i, request in enumerate(a["requests"]):
                self.assertEqual(request["id"], i)
                self.assertTrue(0 <= request["time"] - previous <= 10)
                self.assertTrue(1 <= request["origin"] <= 20 and 1 <= request["dest"] <= 20)
                self.assertNotEqual(request["origin"], request["dest"])
                previous = request["time"]
        self.assertEqual(random.getstate(), state)

    def test_peak_probability_and_simultaneous_requests(self):
        requests = generate_requests(50, scenario="peak", peak_probability=1, arrival_max=0)
        self.assertTrue(all(r["origin"] == 1 and r["dest"] > 1 and r["time"] == 0 for r in requests))
        self.assertEqual([e["floor"] for e in generate_instance(0)["elevators"]], [1, 10, 20])

    def test_bad_parameters(self):
        for options in ({"n": -1}, {"n": 0, "num_floors": 1}, {"n": 0, "scenario": "bad"},
                        {"n": 0, "arrival_max": -1}, {"n": 0, "peak_probability": 2},
                        {"n": 0, "num_elevators": 0}, {"n": 0, "num_elevators": 21},
                        {"n": 0, "initial_floors": [1, 1, 20]}, {"n": 0, "floor_time": 0},
                        {"n": 0, "stop_time": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                generate_instance(**options)


class TestExperiments(unittest.TestCase):
    def test_feasible_quality_gap_tick_and_nonmutation(self):
        case = generate_instance(4, 5)
        before = deepcopy(case)
        steps = []
        original = Simulator.__init__
        def observed_init(sim, *args, **kwargs):
            steps.append(kwargs.get("step", "tick"))
            original(sim, *args, **kwargs)
        with patch.object(Simulator, "__init__", observed_init):
            rows = compare_instance(case)
        self.assertEqual(set(steps), {"tick"})
        self.assertEqual(case, before)
        by_name = {r["algorithm"]: r for r in rows}
        optimum = by_name["exhaustive"]["avg_wait"]
        self.assertLessEqual(optimum, by_name["local_search"]["avg_wait"])
        self.assertLessEqual(by_name["local_search"]["avg_wait"], by_name["ewt_greedy"]["avg_wait"])
        for row in rows:
            self.assertEqual(row["status"], "ok")
            self.assertEqual(row["optimal_avg_wait"], optimum)
            self.assertGreater(row["runtime_sec"], 0)
            self.assertGreaterEqual(row["absolute_gap"], 0)
            self.assertGreaterEqual(row["optimality_gap"], 0)
            self.assertEqual(row["gap_status"], "available")

    def test_limit_boundary_and_missing_baseline(self):
        case = generate_instance(3, num_elevators=2)
        self.assertEqual(compare_instance(case, max_assignments=8)[-1]["status"], "ok")
        rows = compare_instance(case, max_assignments=7)
        self.assertEqual(rows[-1]["status"], "skipped")
        self.assertEqual(rows[-1]["skip_reason"], "assignment_limit")
        self.assertIsNone(rows[-1]["runtime_sec"])
        self.assertTrue(all(r["optimality_gap"] is None for r in rows))
        self.assertTrue(all(r["gap_status"] == "baseline_unavailable" for r in rows))
        with self.assertRaises(ValueError):
            compare_instance(case, max_assignments=0)

    def test_zero_optimum_handling(self):
        case = generate_instance(1, num_elevators=2)
        case["requests"] = [{"id": 0, "time": 0, "origin": 1, "dest": 2}]
        rows = compare_instance(case)
        self.assertTrue(all(r["optimality_gap"] == 0 for r in rows))
        with patch.dict(ALGORITHMS, {"nearest_car": lambda *args: [1]}):
            row = compare_instance(case)[0]
        self.assertEqual(row["optimal_avg_wait"], 0)
        self.assertGreater(row["absolute_gap"], 0)
        self.assertIsNone(row["optimality_gap"])
        self.assertEqual(row["gap_status"], "zero_optimum")

    def test_empty_requests(self):
        rows = compare_instance(generate_instance(0))
        self.assertTrue(all(r["avg_wait"] == 0 and json.loads(r["assignment"]) == [] for r in rows))

    def test_summary_statistics_and_skipped_values(self):
        a = compare_instance(generate_instance(2, 0), max_assignments=1)
        b = compare_instance(generate_instance(2, 1), max_assignments=1)
        summary = summarize(a + b)
        nearest = next(r for r in summary if r["algorithm"] == "nearest_car")
        self.assertEqual(nearest["runs"], 2)
        self.assertAlmostEqual(nearest["avg_wait_mean"], (a[0]["avg_wait"] + b[0]["avg_wait"]) / 2)
        self.assertEqual(nearest["optimality_gap_count"], 0)
        skipped = next(r for r in summary if r["algorithm"] == "exhaustive")
        self.assertEqual(skipped["skipped"], 2)
        self.assertIsNone(skipped["runtime_sec_mean"])

    def test_plot_aggregation_omits_missing_and_converts_to_percent(self):
        rows = [dict(scenario="normal", algorithm="exhaustive", status="skipped", n="3", optimality_gap=""),
                dict(scenario="normal", algorithm="exhaustive", status="ok", n="2", optimality_gap="0.5"),
                dict(scenario="normal", algorithm="exhaustive", status="ok", n="2", optimality_gap="0.1")]
        data = aggregate(rows, "normal", "exhaustive", "optimality_gap")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0][0:2], (2, 30.0))
        self.assertAlmostEqual(data[0][2], 28.284271247461902)

    def test_cli_json_csv_summary_and_saved_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            target = folder / "case.json"
            subprocess.run([sys.executable, str(ROOT / "experiment/generate.py"), "--n", "2",
                            "--output", str(target)], cwd=ROOT, check=True, capture_output=True)
            self.assertEqual(json.loads(target.read_text()), generate_instance(2))
            result = folder / "results.csv"
            subprocess.run([sys.executable, "-m", "experiment.run", "--n", "2", "3",
                            "--seeds", "0", "1", "--max-assignments", "9", "--output", str(result)],
                           cwd=ROOT, check=True, capture_output=True)
            rows = load_results(result)
            self.assertEqual(len(rows), 32)
            self.assertEqual(sum(r["status"] == "skipped" for r in rows), 4)
            self.assertEqual(len(list((folder / "results_inputs").glob("*.json"))), 8)
            self.assertTrue((folder / "results_manifest.json").is_file())
            with (folder / "results_summary.csv").open() as stream:
                self.assertEqual(len(list(csv.DictReader(stream))), 16)
            for row in rows:
                if row["n"] == "3":
                    self.assertEqual(row["optimality_gap"], "")
            # 동일 seed가 중복되면 그래프를 잘못 평균내지 않고 오류를 낸다.
            with result.open("a", newline="") as stream:
                csv.DictWriter(stream, fieldnames=list(rows[0])).writerow(rows[0])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_results(result)


if __name__ == "__main__":
    unittest.main()
