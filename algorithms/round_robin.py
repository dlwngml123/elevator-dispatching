"""Round-robin (Part A, 인터페이스 예시).

모든 알고리즘이 따라야 하는 형태를 보여주는 가장 단순한 배정.
요청 i를 엘리베이터 i % M 에 배정한다. 실험 비교 대상은 아니다.

형태
    입력: config(dict), elevators(list[dict]), requests(list[dict], 도착 시각 순)
    출력: assignment(list[int]), assignment[i] = 요청 i를 맡는 엘리베이터 id
"""


def round_robin(config, elevators, requests):
    m = len(elevators)
    return [i % m for i in range(len(requests))]


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
    ]
    assignment = round_robin(config, elevators, requests)
    print("assignment:", assignment)
    print(simulate(config, elevators, requests, assignment))
