"""C: 모든 M**N 배정을 tick 시뮬레이터로 평가하는 오프라인 정확 해법.

평균 대기시간 → 최대 대기시간 → 배정표의 사전식 순서로 최소화한다.
시뮬레이션 M**N회, 후보 생성용 추가 공간 O(N). 실행 범위 제한은 실험
runner에서 담당하며 이 함수는 후보를 생략하거나 조기 종료하지 않는다.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator import Simulator, simulate


def exhaustive(config, elevators, requests) -> list[int]:
    # 빈 요청에서도 A와 같은 입력 검증을 수행한다. 입력 객체는 변경하지 않는다.
    Simulator(config, elevators, requests, step="tick")
    best_key = None
    best_assignment = None
    for assignment in product(range(len(elevators)), repeat=len(requests)):
        result = simulate(config, elevators, requests, list(assignment), step="tick")
        key = (result["avg_wait"], result["max_wait"], assignment)
        if best_key is None or key < best_key:
            best_key, best_assignment = key, assignment
    # M >= 1은 Simulator가 검증한다. N == 0일 때도 빈 배정 1개를 평가한다.
    return list(best_assignment)


algorithm = exhaustive


if __name__ == "__main__":
    config = {"num_floors": 20, "floor_time": 2, "stop_time": 5}
    elevators = [{"id": 0, "floor": 1}, {"id": 1, "floor": 10}, {"id": 2, "floor": 20}]
    requests = [
        {"id": 0, "time": 0, "origin": 5, "dest": 9},
        {"id": 1, "time": 3, "origin": 7, "dest": 2},
        {"id": 2, "time": 6, "origin": 15, "dest": 18},
    ]
    assignment = exhaustive(config, elevators, requests)
    print("assignment:", assignment)
    print(simulate(config, elevators, requests, assignment, step="tick"))
