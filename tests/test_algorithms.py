"""B 알고리즘 테스트: Nearest-Car, EWT Greedy, Local Search"""

import itertools
import random
import unittest

from _path import CONFIG, cars, req
from simulator import simulate, state_at

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

    def test_tie_goes_to_smaller_id(self):
        # 3층·7층 엘리베이터, 5층 요청 → 거리 2로 같음 → id 작은 E0
        self.assertEqual(nearest_car(CONFIG, cars(3, 7), [req(0, 0, 5, 9)]), [0])

    def test_moving_car_uses_last_departed_floor(self):
        # E0는 2층에서 P0를 태우고 올라가는 중(t=10에 3층을 떠나 4층으로 가는 중), E1은 1층 IDLE
        # t=10 2층 요청: E0 위치를 마지막으로 떠난 3층으로 보면 거리 1 = E1 거리 1 → 동점 → E0
        # (다음 층 4층으로 보면 거리 2라 E1이 뽑힘)
        elevators = cars(1, 1)
        requests = [req(0, 0, 2, 20), req(1, 10, 2, 20)]
        state = state_at(CONFIG, elevators, requests, [0, None], 10)[0]
        self.assertEqual((state["floor"], state["status"]), (3, "MOVING"))
        self.assertEqual(nearest_car(CONFIG, elevators, requests), [0, 0])

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
    """Nearest-Car와 EWT는 그 시점까지의 정보만 쓴다: 뒤에 요청이 붙거나 바뀌어도 앞 배정이 안 바뀐다"""

    def test_prefix_unchanged(self):
        for seed in range(5):
            full = random_requests(8, seed)
            for algo in (nearest_car, ewt_greedy):
                whole = algo(CONFIG, ELEVATORS, full)
                for k in (3, 5):
                    self.assertEqual(algo(CONFIG, ELEVATORS, full[:k]), whole[:k],
                                     f"{algo.__name__} seed={seed} k={k}")

    def test_future_requests_do_not_affect_earlier_assignment(self):
        # 앞 5개는 같고 뒤 3개의 출발층·목적층만 다른 두 목록 → 앞 5개 배정은 같아야 함
        for seed in range(5):
            a = random_requests(8, seed)
            b = random_requests(8, seed + 100)
            mixed = a[:5] + [req(5 + i, a[5]["time"] + i, r["origin"], r["dest"]) for i, r in enumerate(b[5:])]
            for algo in (nearest_car, ewt_greedy):
                self.assertEqual(algo(CONFIG, ELEVATORS, a)[:5], algo(CONFIG, ELEVATORS, mixed)[:5],
                                 f"{algo.__name__} seed={seed}")


class TestEwtObjective(unittest.TestCase):
    def test_default_is_total_average_not_new_passenger(self):
        # experiment.generate normal n=3 seed=31 인스턴스: 두 기준이 다른 배정을 냄
        requests = [req(0, 0, 16, 4), req(1, 6, 5, 2), req(2, 8, 4, 18)]
        by_total = ewt_greedy(CONFIG, ELEVATORS, requests)
        by_new = ewt_greedy(CONFIG, ELEVATORS, requests, objective="new")
        self.assertEqual(by_total, [2, 0, 1])
        self.assertEqual(by_new, [2, 0, 0])
        self.assertEqual(ewt_greedy(CONFIG, ELEVATORS, requests, objective="total"), by_total)
        # 전체 평균 기준이 실제로 평균을 더 낮춘다 (9.33초 vs 27.33초)
        self.assertLess(total_wait(requests, by_total), total_wait(requests, by_new))


class TestLocalSearchOffline(unittest.TestCase):
    def test_starts_from_ewt_and_revises_earlier_assignment(self):
        # experiment.generate normal n=3 seed=17 인스턴스: EWT는 [1,1,1](평균 13초),
        # Local Search는 뒤 요청까지 보고 요청 0을 E2로 옮겨 [2,1,1](평균 9.33초) → 오프라인
        requests = [req(0, 8, 14, 10), req(1, 13, 10, 6), req(2, 21, 9, 4)]
        ewt = ewt_greedy(CONFIG, ELEVATORS, requests)
        ls = local_search(CONFIG, ELEVATORS, requests)
        self.assertEqual(ewt, [1, 1, 1])
        self.assertEqual(ls, [2, 1, 1])
        self.assertLess(total_wait(requests, ls), total_wait(requests, ewt))

    def test_never_worse_than_ewt(self):
        for seed in range(10):
            for peak in (False, True):
                requests = random_requests(8, seed, peak)
                self.assertLessEqual(total_wait(requests, local_search(CONFIG, ELEVATORS, requests)),
                                     total_wait(requests, ewt_greedy(CONFIG, ELEVATORS, requests)))


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
