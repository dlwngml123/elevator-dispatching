"""EWT Greedy: 새 요청을 엘리베이터마다 넣어보고 시뮬레이션해서 가장 좋은 곳에 배정

- 요청은 도착 순서대로, 그 시점까지 배정된 요청 + 새 요청 하나만 넣고 시뮬레이션한다 (온라인).
  아직 안 온 요청은 None이라 시뮬레이터가 무시한다.
- objective="total" (기본, 노션 6장 제안 채택): 배정된 승객 전체의 평균 대기시간이 가장 작은 엘리베이터
  objective="new": 새 승객의 예상 대기시간이 가장 작은 엘리베이터 (Proposal 원래 정의, 비교용)
- 동점: 전체 평균 → 새 승객 대기시간 → id 작은 순
- 시간복잡도: 시뮬레이션 N·M회 (시뮬레이션 1회 비용은 요청 수와 총 시간에 비례)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import simulate

from algorithms.nearest_car import arrival_order


def ewt_greedy(config, elevators, requests, objective="total"):
    if objective not in ("total", "new"):
        raise ValueError("objective는 'total' 또는 'new'")
    assignment = [None] * len(requests)
    for i in arrival_order(requests):
        req_id = requests[i]["id"]
        best_key, best_car = None, None
        for car in sorted(e["id"] for e in elevators):
            trial = assignment.copy()
            trial[i] = car
            waits = simulate(config, elevators, requests, trial)["wait_times"]
            total = sum(waits.values())  # 승객 수가 같으므로 합 비교 = 평균 비교
            new = waits[req_id]
            key = (total, new, car) if objective == "total" else (new, car)
            if best_key is None or key < best_key:
                best_key, best_car = key, car
        assignment[i] = best_car
    return assignment


if __name__ == "__main__":
    # 사용 예: 알고리즘을 부르고, 결과를 시뮬레이터로 평가한다
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from simulator import simulate

    config = {"num_floors": 20, "floor_time": 2, "stop_time": 5}
    elevators = [{"id": 0, "floor": 1}, {"id": 1, "floor": 10}, {"id": 2, "floor": 20}]
    requests = [
        {"id": 0, "time": 0, "origin": 5, "dest": 9},
        {"id": 1, "time": 3, "origin": 7, "dest": 2},
        {"id": 2, "time": 6, "origin": 15, "dest": 18},
    ]
    assignment = ewt_greedy(config, elevators, requests)
    print("assignment:", assignment)
    print(simulate(config, elevators, requests, assignment))
