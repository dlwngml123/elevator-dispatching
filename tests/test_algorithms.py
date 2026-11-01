"""B 알고리즘 테스트: Nearest-Car, EWT Greedy, Local Search"""

import itertools
import random
import unittest

from _path import CONFIG, cars, req
from simulator import simulate

from algorithms.ewt_greedy import ewt_greedy
from algorithms.local_search import local_search
from algorithms.nearest_car import nearest_car

ELEVATORS = cars(1, 10, 20)


def random_requests(n, seed, peak=False):
    """노션 5장 가정: 도착 간격 0~10초 정수, peak는 80%가 1층에서 위로"""
    rng = random.Random(seed)
    t, requests = 0, []
    for i in range(n):
        t += rng.randint(0, 10)
        if peak and rng.random() < 0.8:
            origin, dest = 1, rng.randint(2, 20)
        else:
            origin, dest = rng.sample(range(1, 21), 2)
        requests.append(req(i, t, origin, dest))
    return requests


def total_wait(requests, assignment):
    return sum(simulate(CONFIG, ELEVATORS, requests, assignment)["wait_times"].values())


class TestNearestCar(unittest.TestCase):
    def test_notion_example(self):
        # t=0 5층: E0(1층) / t=3 7층: E1(10층) / t=6 15층: E2(20층)
        requests = [req(0, 0, 5, 9), req(1, 3, 7, 2), req(2, 6, 15, 18)]
        self.assertEqual(nearest_car(CONFIG, ELEVATORS, requests), [0, 1, 2])

    def test_weakness_ignores_workload(self):
        # S7 장면: E0는 5층에서 20층 가는 승객을 태움. t=1 6층 하행 요청은 E0가 1층 차로 가장 가깝지만
        # E0는 20층까지 갔다가 돌아와야 함 → Nearest-Car는 E0, EWT는 E1
        elevators = cars(5, 15)
        requests = [req(0, 0, 5, 20), req(1, 1, 6, 1)]
        self.assertEqual(nearest_car(CONFIG, elevators, requests), [0, 0])
        self.assertEqual(ewt_greedy(CONFIG, elevators, requests), [0, 1])
        self.assertEqual(simulate(CONFIG, elevators, requests, [0, 0])["wait_times"][1], 67)
        self.assertEqual(simulate(CONFIG, elevators, requests, [0, 1])["wait_times"][1], 18)


class TestOnline(unittest.TestCase):
    """Nearest-Car와 EWT는 그 시점까지의 정보만 쓴다: 뒤에 요청이 붙어도 앞 배정이 안 바뀐다"""

    def test_prefix_unchanged(self):
        for seed in range(5):
            full = random_requests(8, seed)
            for algo in (nearest_car, ewt_greedy):
                whole = algo(CONFIG, ELEVATORS, full)
                for k in (3, 5):
                    self.assertEqual(algo(CONFIG, ELEVATORS, full[:k]), whole[:k],
                                     f"{algo.__name__} seed={seed} k={k}")


class TestQuality(unittest.TestCase):
    def test_order_against_brute_force(self):
        # 최적(모든 3^N 배정) <= Local Search <= EWT
        for seed in range(6):
            for peak in (False, True):
                requests = random_requests(6, seed, peak)
                optimum = min(total_wait(requests, list(a))
                              for a in itertools.product(range(3), repeat=len(requests)))
                ewt = total_wait(requests, ewt_greedy(CONFIG, ELEVATORS, requests))
                ls = total_wait(requests, local_search(CONFIG, ELEVATORS, requests))
                self.assertLessEqual(optimum, ls)
                self.assertLessEqual(ls, ewt)

    def test_outputs_are_valid(self):
        requests = random_requests(10, 42)
        for algo in (nearest_car, ewt_greedy, local_search):
            assignment = algo(CONFIG, ELEVATORS, requests)
            self.assertEqual(len(assignment), len(requests))
            self.assertTrue(all(a in (0, 1, 2) for a in assignment))
        new = ewt_greedy(CONFIG, ELEVATORS, requests, objective="new")
        self.assertTrue(all(a in (0, 1, 2) for a in new))
        with self.assertRaises(ValueError):
            ewt_greedy(CONFIG, ELEVATORS, requests, objective="wrong")


if __name__ == "__main__":
    unittest.main()
