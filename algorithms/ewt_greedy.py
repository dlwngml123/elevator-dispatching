"""EWT Greedy: 새 요청을 엘리베이터마다 넣어보고 시뮬레이션해서 가장 좋은 곳에 배정

- 요청은 도착 순서대로 처리하고, 후보를 평가할 때는 현재 요청까지의 prefix(requests[:i+1])만
  시뮬레이션한다. 아직 도착하지 않은 미래 요청은 넘기지 않으므로 온라인이다 (C7: 현재 요청의
  목적층은 예상 대기시간 계산에 쓴다).
- objective="total" (기본, 노션 6장 제안 채택): 배정된 승객 전체의 평균 대기시간이 가장 작은 엘리베이터
  objective="new": 새 승객의 예상 대기시간이 가장 작은 엘리베이터 (Proposal 원래 정의, 비교용)
- 동점: 전체 평균 → 새 승객 대기시간 → id 작은 순
- 시간복잡도: 시뮬레이션 N·M회 (시뮬레이션 1회 비용은 요청 수와 총 시간에 비례)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator import simulate


def ewt_greedy(config, elevators, requests, objective="total"):
    if objective not in ("total", "new"):
        raise ValueError("objective는 'total' 또는 'new'")
    assignment = []
    for i in range(len(requests)):          # 요청은 도착 시각 순으로 들어온다
        req_id = requests[i]["id"]
        seen = requests[:i + 1]             # 지금까지 도착한 요청만 (미래 요청은 모름)
        best_key, best_car = None, None
        for car in sorted(e["id"] for e in elevators):
            trial = assignment + [car]
            waits = simulate(config, elevators, seen, trial)["wait_times"]
            total = sum(waits.values())  # 승객 수가 같으므로 합 비교 = 평균 비교
            new = waits[req_id]
            key = (total, new, car) if objective == "total" else (new, car)
            if best_key is None or key < best_key:
                best_key, best_car = key, car
        assignment.append(best_car)
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
