# Elevator Dispatching: Exhaustive Search vs. Greedy-based Dispatching

팀 B2 알고리즘 프로젝트. 집합 제어(Collective Control) 규칙으로 움직이는 엘리베이터 여러 대에
시간에 따라 들어오는 요청을 배정하고, 평균 대기시간과 계산 시간의 trade-off를 측정한다.

## 구조와 담당

```
elevator-dispatching/
├── simulator.py            A  공통 시뮬레이터
├── algorithms/
│   ├── round_robin.py      A  인터페이스 예시 (비교 대상 아님)
│   ├── nearest_car.py      B
│   ├── ewt_greedy.py       B
│   ├── local_search.py     B
│   └── exhaustive.py       C
├── experiment/             C  입력 생성, 실행, 그래프
└── tests/                  B  손계산 테스트
```

각자 자기 담당 파일만 수정한다. 올리기 전에 최신 버전을 먼저 받는다(`git pull`).

## 환경

Python 3.10 이상. `simulator.py`는 표준 라이브러리만 사용한다.

## 시뮬레이터 (A)

배정표를 받아 엘리베이터를 움직여 보고, 요청별 대기시간을 돌려주는 채점기다.
모든 알고리즘은 같은 시뮬레이터로 평가한다.

### 입력

```python
config = {"num_floors": 20, "floor_time": 2, "stop_time": 5}   # 20층, 한 층 2초, 정차 5초
elevators = [{"id": 0, "floor": 1}, {"id": 1, "floor": 10}, {"id": 2, "floor": 20}]
requests = [                                                     # 도착 시각 순
    {"id": 0, "time": 0, "origin": 5,  "dest": 9},
    {"id": 1, "time": 3, "origin": 7,  "dest": 2},
    {"id": 2, "time": 6, "origin": 15, "dest": 18},
]
```

- 층 번호는 1부터, 엘리베이터·요청 id는 0부터 빈칸 없이 순서대로, 시간은 정수 초.
- 출발층 = 목적층, 범위 밖 층, 시각 역순, id 어긋남은 오류(`SimulationError`)를 낸다.
- 배정의 엘리베이터 id는 0..M-1 정수 또는 `None`. `Simulator.assign()`도 같은 기준으로 검사한다.

### 사용법

```python
from simulator import simulate, state_at, Simulator

# 1) 배정표 채점. assignment[i] = 요청 i를 맡는 엘리베이터 id
simulate(config, elevators, requests, [0, 1, 2])
# {'wait_times': {0: 8, 1: 6, 2: 10}, 'avg_wait': 8.0, 'max_wait': 10}

# 2) 일부만 배정: None인 요청은 무시 (EWT가 "지금까지 배정 + 새 요청"을 시뮬레이션할 때)
simulate(config, elevators, requests, [0, 1, None])
# {'wait_times': {0: 8, 1: 6}, 'avg_wait': 7.0, 'max_wait': 8}

# 3) 사건 기록 보기 (손계산과 비교할 때)
for line in simulate(config, elevators, requests, [0, 1, 2], trace=True)["trace"]:
    print(line)
# t=   8 E0 5층 P0 탑승 (대기 8초) ...

# 4) 시각 t의 일을 처리하기 직전의 엘리베이터 상태 (Nearest-Car)
state_at(config, elevators, requests, [0, 1, 2], 9)
# [{'id': 0, 'floor': 5, 'direction': 'UP', 'status': 'STOPPED', 'load': 1}, ...]
# 이동 중(MOVING)이면 floor는 마지막으로 떠난 층이다.

# 5) 시간을 흘리며 하나씩 배정 (온라인 알고리즘)
sim = Simulator(config, elevators, requests)
for i, req in enumerate(requests):
    sim.advance_to(req["time"])   # 요청 i가 도착하기 직전까지 진행
    states = sim.state()          # 그 순간 엘리베이터 상태
    sim.assign(i, 0)              # 요청 i를 고른 엘리베이터에 배정 (예시는 0번)
sim.run()                         # 끝까지 돌려 simulate와 같은 형식의 결과 반환
```

| 반환값 | 뜻 |
|---|---|
| `wait_times` | 요청별 대기시간(초) = 탑승 시각 − 도착 시각 |
| `avg_wait` | 평균 대기시간 (주 목적) |
| `max_wait` | 최대 대기시간 (공정성) |

**종료 조건:** 본 프로젝트는 승객 대기시간을 측정하므로, 배정된 승객이 모두 탑승하면 시뮬레이션을 종료한다.
대기시간은 탑승 시각으로 정해지므로 결과는 같고, 마지막 하차까지는 계산하지 않는다.

### 알고리즘 형식 (B, C)

모든 알고리즘은 같은 모양의 함수 하나다. 예시는 `algorithms/round_robin.py`.

```python
def algorithm(config, elevators, requests) -> list[int]:
    ...   # assignment[i] = 요청 i를 맡는 엘리베이터 id
```

```bash
python algorithms/round_robin.py    # 예시 실행
```

### 운행 규칙

방향 문서 3장의 운행 규칙 1~5와 가정값(약 20층, 엘리베이터 3대·서로 다른 초기 위치,
한 층 2초, 정차 1회 5초, 정원 제한 없음, 재배정 없음, 1초 단위 시뮬레이션)을 따른다.
층수와 엘리베이터 대수·초기 위치는 입력으로 받으므로 시뮬레이터 코드에 고정되어 있지 않다.

승객은 자기에게 배정된 엘리베이터만 탄다. 방향 전환은 시간이 들지 않는다.
방향 문서만으로 정해지지 않아 팀이 합의한 세부 규칙은 다음과 같다 (10/30).

| 번호 | 규칙 |
|---|---|
| C1 | 정차 중 같은 층에 같은 방향 승객이 오면 바로 태우고, 정차 시간은 늘리지 않음 |
| C2 | 엘리베이터가 서 있는 층에서 승객이 오면 대기 0초로 태우고 정차 5초 후 출발 |
| C3 | 같은 층의 하차와 탑승은 정차 1회로 처리 |
| C4 | 정차한 층에서 앞쪽 할 일이 없으면 같은 정차 안에서 방향을 바꿔 그 층 반대 방향 승객도 태움 |
| C5 | 같은 초에 승객 도착과 엘리베이터 도착이 겹치면 승객을 먼저 받음 |
| C6 | 엘리베이터는 요청이 도착한 시각에 일을 받음 (미리 마중 없음) |
| C7 | 요청 시 출발층·목적층이 모두 주어지고 EWT는 목적층을 예상 대기시간 계산에 쓸 수 있으나, 탑승 전에는 목적층을 정차할 곳으로 추가하지 않음 |
| C8 | 층 사이에서는 판단하지 않고 층에 도착할 때만 판단 |
| C9 | IDLE 상태에서 할 일이 여러 곳이면 같은 층 승객 > 가장 가까운 할 일 > 먼저 온 요청 순으로 출발 방향을 정함 (`_choose_direction`) |

### 옵션

| 쓰는 법 | 뜻 | 기본값 |
|---|---|---|
| `simulate(..., trace=True)` | 사건 기록을 함께 돌려줌 | `False` |
| `simulate(..., step="event")` | 일이 없는 초를 건너뛰는 가속 모드. 결과는 1초 단위와 같음 (검증용) | `"tick"` |
| `config["capacity"]` | 정원 제한 | `None` (제한 없음) |
| `config["transfer_time"]` | 승객 1명당 승하차 추가 시간(초) | `0` |

**최종 실험 규칙:** Computation Time을 공정하게 비교하기 위해, 최종 실험에서는 모든 알고리즘이 기본값인 1초 단위(`tick`)를 쓴다.
알고리즘 코드에서 `step="event"`를 지정하지 않는다. (가속 모드는 약 10% 빨라서 섞어 쓰면 비교가 불공정해진다.)

## 실험과 결과

(C 작성 예정)

## 생성형 AI 사용

`simulator.py`, `algorithms/round_robin.py`와 이 README의 시뮬레이터 부분은 생성형 AI(Claude) 보조로 작성했으며,
담당자(A)가 검토 중이다.
