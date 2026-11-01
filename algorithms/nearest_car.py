"""Nearest-Car: 요청이 들어온 순간 가장 가까운 엘리베이터에 배정 (전통 방식)

- 요청은 도착 순서대로, 그 시점까지 배정된 요청만 보고 결정한다 (온라인).
- 위치는 노션 5장 옵션 1: 시뮬레이터가 주는 시각별 위치, 이동 중이면 마지막으로 떠난 층.
- 거리만 보고 방향·작업량은 보지 않는다. 거리가 같으면 id가 작은 엘리베이터.
- 시뮬레이터의 점진 모드(advance_to → state → assign)를 써서 시뮬레이션을 한 번만 돌린다.
- 시간복잡도: 시뮬레이션 1회 + 요청마다 엘리베이터 M대 비교 = O(T + N·M)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import Simulator


def nearest_car(config, elevators, requests):
    sim = Simulator(config, elevators, requests)
    assignment = [None] * len(requests)
    for i, req in enumerate(requests):          # 요청은 도착 시각 순으로 들어온다
        sim.advance_to(req["time"])             # 요청 i가 도착하기 직전까지 진행
        states = sim.state()
        best = min(states, key=lambda s: (abs(s["floor"] - req["origin"]), s["id"]))
        assignment[i] = best["id"]
        sim.assign(i, best["id"])
    return assignment


if __name__ == "__main__":
    # 사용 예: 알고리즘을 부르고, 결과를 시뮬레이터로 평가한다
    from simulator import simulate

    config = {"num_floors": 20, "floor_time": 2, "stop_time": 5}
    elevators = [{"id": 0, "floor": 1}, {"id": 1, "floor": 10}, {"id": 2, "floor": 20}]
    requests = [
        {"id": 0, "time": 0, "origin": 5, "dest": 9},
        {"id": 1, "time": 3, "origin": 7, "dest": 2},
        {"id": 2, "time": 6, "origin": 15, "dest": 18},
    ]
    assignment = nearest_car(config, elevators, requests)
    print("assignment:", assignment)
    print(simulate(config, elevators, requests, assignment))
