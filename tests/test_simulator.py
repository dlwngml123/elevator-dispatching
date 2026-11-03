"""손계산 예시 (시뮬레이터 검증용, B 작성)

한 층 2초, 정차 5초. 기대값은 노션 2~4장 규칙대로 손으로 계산했다.
시뮬레이터 결과가 다르면 시뮬레이터 버그이거나 규칙 해석이 다른 것이다.
"""

import unittest

from _path import CONFIG, cars, req
from simulator import simulate


def waits(elevators, requests, assignment):
    return simulate(CONFIG, elevators, requests, assignment)["wait_times"]


class TestHandCalculated(unittest.TestCase):
    # ----- 방향 문서 7장 목록 -----
    def test_one_passenger_one_car(self):
        # 1층 → 4층 3층 이동 = 6초
        self.assertEqual(waits(cars(1), [req(0, 0, 4, 6)], [0]), {0: 6})

    def test_opposite_direction_passenger(self):
        # 방향 문서 7장 예시: P1 8초, P2 30초, 평균 19초 (7층에서 P2를 태우면 버그)
        result = simulate(CONFIG, cars(1), [req(0, 0, 5, 9), req(1, 0, 7, 2)], [0, 0])
        self.assertEqual(result["wait_times"], {0: 8, 1: 30})
        self.assertEqual(result["avg_wait"], 19)

    def test_passenger_arrives_later(self):
        # 규칙 5 + C6: t=10에 요청 → 그때 출발, 1→3층 4초 → 대기 4초 (미리 가 있으면 0초)
        self.assertEqual(waits(cars(1), [req(0, 10, 3, 5)], [0]), {0: 4})

    def test_two_passengers_same_floor_one_stop(self):
        # 5층 두 명 t=8 같이 탑승, 정차 1회 → 8층 t=19, 9층 t=26, 10층 t=33
        # 5층에서 두 번 서면 P2가 38초가 됨
        requests = [req(0, 0, 5, 8), req(1, 0, 5, 9), req(2, 0, 10, 12)]
        self.assertEqual(waits(cars(1), requests, [0, 0, 0]), {0: 8, 1: 8, 2: 33})

    def test_two_cars_independent(self):
        requests = [req(0, 0, 3, 5), req(1, 0, 18, 15)]
        self.assertEqual(waits(cars(1, 20), requests, [0, 1]), {0: 4, 1: 4})

    # ----- 노션 3장 -----
    def test_case_a_turn_at_pickup_floor(self):
        # 1층 IDLE, 7층 하행 한 명 → 7층 도착 → 위쪽 없음 → DOWN 전환 → 탑승, 대기 12초
        self.assertEqual(waits(cars(1), [req(0, 0, 7, 2)], [0]), {0: 12})

    # ----- 노션 4장 -----
    def test_c1_board_during_stop_without_extending(self):
        # 5층 정차 t=8~13 중 t=10 같은 방향 승객(P2) → 대기 0초, 출발 t=13 그대로
        # → 8층 t=19, 9층 t=26, 10층 t=33 (정차가 늘면 P1이 33초보다 커짐)
        requests = [req(0, 0, 5, 9), req(1, 0, 10, 12), req(2, 10, 5, 8)]
        self.assertEqual(waits(cars(1), requests, [0, 0, 0]), {0: 8, 1: 33, 2: 0})

    def test_c2_passenger_at_idle_car_floor(self):
        # 5층 IDLE, 5층 승객 → 대기 0초, 정차 5초 후 출발 → 8층 t=11, 정차 후 9층 t=18
        requests = [req(0, 0, 5, 8), req(1, 0, 9, 12)]
        self.assertEqual(waits(cars(5), requests, [0, 0]), {0: 0, 1: 18})

    def test_c3_alight_and_board_same_floor_one_stop(self):
        # 9층에서 P0 하차(t=21)와 같은 방향 P1 탑승을 정차 1회로 → P1 대기 21초 (두 번 서면 26초)
        requests = [req(0, 0, 5, 9), req(1, 0, 9, 15)]
        self.assertEqual(waits(cars(1), requests, [0, 0]), {0: 8, 1: 21})

    def test_c4_turn_within_same_stop(self):
        # 9층 t=21 마지막 승객 하차, 9층 하행 승객도 같은 정차에서 탑승 → 대기 21초 (정차 끝나고 태우면 26초)
        requests = [req(0, 0, 5, 9), req(1, 0, 9, 3)]
        self.assertEqual(waits(cars(1), requests, [0, 0]), {0: 8, 1: 21})

    def test_c5_request_and_arrival_same_second(self):
        # 5층 가는 길에 t=4 3층 도착. 같은 초에 3층 상행 요청 → 승객 먼저 받아 정차, P1 대기 0초
        # (엘리베이터를 먼저 처리하면 3층을 지나쳐 P1이 한참 뒤에 탐). P0는 정차 5초만큼 늦은 13초
        requests = [req(0, 0, 5, 9), req(1, 4, 3, 7)]
        self.assertEqual(waits(cars(1), requests, [0, 0]), {0: 13, 1: 0})

    def test_c7_destination_not_a_stop_before_boarding(self):
        # 10층 IDLE, 14층→9층 요청. 탑승 전 목적층 9층이 할 일이면 더 가까운 9층으로 먼저 가 버림(대기 17초)
        # 목적층은 탑승 후에만 추가되므로 14층으로 바로 올라감 → 대기 8초
        self.assertEqual(waits(cars(10), [req(0, 0, 14, 9)], [0]), {0: 8})

    def test_c8_no_decision_between_floors(self):
        # 1층에서 5층 향해 출발, t=1(1~2층 사이)에 1층 상행 요청. 층 사이에서 되돌아가면 P1 대기 1초
        # 2층 도착 후 판단 → 앞에 할 일 있어 계속 진행, 9층까지 갔다가 내려와 t=42에 1층 → 대기 41초
        requests = [req(0, 0, 5, 9), req(1, 1, 1, 3)]
        self.assertEqual(waits(cars(1), requests, [0, 0]), {0: 8, 1: 41})

    def test_c9_idle_goes_to_nearest_task(self):
        # 10층 IDLE, 7층·12층 요청 → 12층(2층 차) 먼저: P1 4초, 15층 t=15 정차 후 DOWN, 7층 t=36
        requests = [req(0, 0, 7, 2), req(1, 0, 12, 15)]
        self.assertEqual(waits(cars(10), requests, [0, 0]), {0: 36, 1: 4})

    def test_c9_tie_goes_to_earlier_request(self):
        # 10층 IDLE, 8층·12층 거리 같음 → 먼저 온 요청(id 0) → 8층 t=4, 5층 t=15 정차 후 UP, 12층 t=34
        requests = [req(0, 0, 8, 5), req(1, 0, 12, 15)]
        self.assertEqual(waits(cars(10), requests, [0, 0]), {0: 4, 1: 34})

    # ----- 노션 7장 예시 -----
    def test_notion_examples(self):
        requests = [req(0, 0, 5, 9), req(1, 3, 7, 2), req(2, 6, 15, 18)]
        elevators = cars(1, 10, 20)
        self.assertEqual(waits(elevators, requests, [0, 1, 2]), {0: 8, 1: 6, 2: 10})
        self.assertEqual(waits(elevators, requests, [0, 0, 0]), {0: 8, 1: 73, 2: 32})
        self.assertEqual(waits(elevators, requests, [0, 1, None]), {0: 8, 1: 6})


if __name__ == "__main__":
    unittest.main()
