"""Local Search (선택): EWT Greedy 결과에서 요청을 하나씩 다른 엘리베이터로 옮겨보며 개선

- 전체 요청 목록을 보고 배정표를 고치므로 오프라인이다 (Exhaustive처럼 미래를 안다).
  발표에서는 "미래를 아는 쪽: Exhaustive(정확) vs Local Search(빠른 근사)"로 설명한다.
- 이웃: 요청 하나의 엘리베이터만 바꾼 배정. 한 요청의 배정을 바꿔 전체 대기시간 합이 줄면
  현재 해에 바로 반영하고, 그 해를 기준으로 다음 요청·엘리베이터를 계속 탐색한다.
- 모든 요청·엘리베이터를 한 바퀴 돌 동안 개선이 없거나 max_passes에 닿으면 멈춘다.
- 시간복잡도: EWT(N·M회) + 바퀴당 시뮬레이션 N·(M-1)회
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import simulate

from algorithms.ewt_greedy import ewt_greedy


def _total_wait(config, elevators, requests, assignment):
    return sum(simulate(config, elevators, requests, assignment)["wait_times"].values())


def local_search(config, elevators, requests, max_passes=50):
    assignment = ewt_greedy(config, elevators, requests)
    best = _total_wait(config, elevators, requests, assignment)
    cars = sorted(e["id"] for e in elevators)
    for _ in range(max_passes):
        improved = False
        for i in range(len(requests)):
            for car in cars:
                if car == assignment[i]:
                    continue
                trial = assignment.copy()
                trial[i] = car
                total = _total_wait(config, elevators, requests, trial)
                if total < best:
                    assignment, best, improved = trial, total, True
        if not improved:
            break
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
    assignment = local_search(config, elevators, requests)
    print("assignment:", assignment)
    print(simulate(config, elevators, requests, assignment))
