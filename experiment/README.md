# C 파트 사용법

Python 3.10 이상. 저장소 루트(`simulator.py`가 있는 폴더)에서 실행한다.
실험 실행·테스트는 표준 라이브러리만 사용하고, 그래프에는 matplotlib이 필요하다.

```bash
python3 -m pip install matplotlib
python3 -m unittest discover -s tests -v
python3 -m unittest experiment.test_c -v
```

## GitHub 브랜치 안내

- `feature/part-c`: 최신 `main`에 C 담당 코드·테스트·이 설명서만 추가한 브랜치.
  B 알고리즘은 별도 브랜치에 있으므로, 전체 실험은 B 파트를 통합한 뒤 실행한다.
- `integration/abc`: 최신 A의 `main` + B의 `feature/part-b` + C를 통합한 실행·검증용 브랜치.
  소규모 예시 결과와 PNG 그래프도 포함한다. 바로 실행하려면 이 브랜치를 사용한다.
- 기존 `main`, `feature/part-b`의 커밋과 담당 파일은 그대로 유지한다.

아래의 테스트·실험 명령은 **A/B/C가 모두 있는 통합본 기준**이다.
현재 예시 결과는 seed 3개로 실행한 기능 검증이며, 30개 seed 최종 실험은 별도 진행한다.

## 파일과 원본 기준

- `algorithms/exhaustive.py`: 모든 배정의 정확 최적해. `exhaustive`와 `algorithm`은 같은 함수다.
- `experiment/generate.py`: normal/peak 입력 생성, 단일 입력 JSON 저장.
- `experiment/run.py`: Nearest-Car, EWT Greedy, Local Search, Exhaustive 비교, CSV 저장.
- `experiment/plot.py`: 시나리오별 평균/최대 대기시간, 실행 시간, optimality gap 그래프.
- `experiment/test_c.py`: C 파트 검증 테스트 15개.

통합본은 업로드된 `elevator-dispatching-main.zip`의 모든 파일에
`elevator-dispatching-feature-part-b (1).zip`의 B 알고리즘 세 개와 `tests/`만 추가했다.
A의 `simulator.py`, README, round-robin 및 B의 파일 내용은 변경하지 않았다.
B ZIP의 구버전 `simulator.py`/README를 A 파일 위에 덮어쓰지 않았다.

`elevator-dispatching-C-only.zip`은 C 코드·테스트·이 설명서만 포함한다.
팀 저장소에 적용할 때는 그 ZIP의 `algorithms/`, `experiment/`를 저장소 루트에 복사한다.
`elevator-dispatching-C-complete.zip`은 실행 가능한 A+B+C 통합본과 예시 결과를 포함한다.

## 빠른 실행

```bash
# 독립 실행 예시
python3 algorithms/exhaustive.py

# normal/peak × N=4,6,10 × seed=0,1,2
python3 -m experiment.run --n 4 6 10 --seeds 0 1 2 --max-assignments 1000 --output results/demo.csv
python3 -m experiment.plot results/demo.csv --output-dir results/plots

# 단일 입력만 생성
python3 -m experiment.generate --n 6 --seed 42 --scenario peak --output results/input.json
```

`python3 experiment/run.py ...`, `python3 experiment/plot.py ...`,
`python3 experiment/generate.py ...` 형식도 지원한다. `--help`로 옵션을 볼 수 있다.

```python
from algorithms.exhaustive import exhaustive  # 또는 algorithm
from experiment.generate import generate_instance
from experiment.run import compare_instance
from simulator import simulate

instance = generate_instance(6, seed=42, scenario="normal")
config, elevators, requests = (instance[k] for k in ("config", "elevators", "requests"))
assignment = exhaustive(config, elevators, requests)
print(simulate(config, elevators, requests, assignment, step="tick"))
rows = compare_instance(instance, max_assignments=1000)
```

모든 배정 함수는 `함수(config, elevators, requests) -> list[int]`로 호출한다.
B의 함수 이름/기본 옵션은 그대로 유지한다. 반환값의 i번째 원소는 요청 i의 엘리베이터 id다.

## 입력과 탐색 범위

기본 환경은 20층, 엘리베이터 3대, 초기 위치 `[1, 10, 20]`, 한 층 이동 2초,
정차 5초, 정원 제한 없음이다. 두 시나리오의 도착 간격은 모두 **0~10초 정수 균등 추출**이며,
첫 요청도 추출한 간격 뒤에 도착한다. 같은 초에 여러 요청이 도착할 수 있다.

- normal: 서로 다른 출발층·목적층을 균등 추출한다.
- peak: 요청마다 80% 확률로 1층→상층, 나머지 20%는 normal과 같이 추출한다.
  따라서 실제 1층 상행 비율은 표본에 따라 달라지고, normal 추출에서도 1층 상행이 나올 수 있다.
  여기서 peak는 교통 방향의 집중을 의미하며, 도착 간격 자체를 줄이지 않는다.

이는 B 테스트의 입력 생성 방식과 같은 기본 규칙이다. 각 입력은 지역 난수 생성기
`random.Random(seed)`를 사용한다. 같은 환경/시나리오/N/seed는 같은 요청을 만든다.
한 입력의 동일한 요청과 초기 위치를 네 알고리즘에 각각 전달한다.

옵션 예시:

```bash
python3 -m experiment.run --n 4 6 --seeds 10 11 12 --num-floors 12 --num-elevators 2 --initial-floors 1 12 --arrival-max 5 --peak-probability 0.9 --output results/custom.csv
```

`exhaustive()` 자체는 제한/가지치기/조기 종료 없이 M^N개 모두를 평가한다.
비교 우선순위는 `(avg_wait, max_wait, assignment)`의 오름차순이다.
빈 요청은 빈 배정 하나를 평가해 `[]`를 반환한다.
시간 비용은 `M^N × 시뮬레이션 1회 비용`, 탐색의 추가 저장 공간은 O(N)이다.

실험 runner만 `--max-assignments`(기본 10000)로 탐색 범위를 제한한다.
3대/N=6은 729개, N=8은 6561개, N=10은 59049개다.
위 demo 명령의 한도 1000에서는 N=4,6을 정확히 탐색하고 N=10은 건너뛴다.
한도를 넘긴 exhaustive 행은 `status=skipped`, `skip_reason=assignment_limit`로 남긴다.
나머지 세 알고리즘은 계속 실행한다. skip은 시간 제한이나 중간 최적값 반환이 아니다.

## 결과와 측정 의미

`--output results/demo.csv`를 지정하면 다음을 저장한다.

- `demo.csv`: 입력/seed/알고리즘별 원시 결과와 배정표.
- `demo_summary.csv`: 시나리오/N/알고리즘별 seed 평균·표본 표준편차·유효값 개수·skip 개수.
- `demo_inputs/*.json`: 실제로 비교에 사용한 모든 입력.
- `demo_manifest.json`: 실행 옵션, Python 버전, 측정/gap 정의.
- plot 실행 시 `plots/`: 두 시나리오 × 네 지표 = PNG 8장.

주요 CSV 열:

| 열 | 의미 |
|---|---|
| `avg_wait`, `max_wait` | 해당 입력의 평균/최대 대기시간(초) |
| `runtime_sec` | 배정 함수 한 번의 계산 시간(초). 함수 내부 시뮬레이션은 포함 |
| `evaluation_sec` | 반환된 배정의 최종 채점 시간(별도 측정) |
| `information` | Nearest-Car/EWT는 online, Local Search/Exhaustive는 offline |
| `optimal_avg_wait` | 동일 입력의 전수탐색 최적 평균 대기시간 |
| `absolute_gap` | `avg_wait - optimal_avg_wait`(초) |
| `optimality_gap` | `(avg_wait - optimal_avg_wait) / optimal_avg_wait` 비율 |
| `gap_status` | `available`, `baseline_unavailable`, `zero_optimum` |
| `assignment` | 요청 id 순 배정표(JSON 문자열) |

gap=0.25는 25%다. 그래프에서는 %로 변환한다. 최적 평균이 0이고 해당 평균도 0이면
gap=0, 해당 평균이 양수이면 상대 gap을 빈칸(`zero_optimum`)으로 두고 절대 gap만 남긴다.
전수탐색을 건너뛴 입력은 모든 알고리즘의 최적값/gap을 빈칸으로 둔다.
빈칸이나 skip을 0으로 평균 내거나 그래프에 표시하지 않는다.

모든 알고리즘 내부 및 최종 채점은 **step="tick"** 환경이다. B는 기존 기본값 tick을 사용하고,
C는 명시적으로 tick을 지정한다. 입력 생성·복사·CSV 저장·최종 채점은 `runtime_sec`에 포함하지 않는다.
Local Search의 EWT 초기해 생성 시간은 함수 안에서 실행하므로 포함한다.
실행 순서는 seed에 따라 회전한다. 각 seed당 각 알고리즘을 한 번 측정한다.
첨부 demo는 기능 확인용 소규모 실행 결과이며, 짧은 계산 시간은 실행 환경에 따라 변동한다.
온라인/오프라인의 정보 차이를 함께 고려해 결과를 해석한다.

그래프의 점은 seed 평균, 오차 막대는 표본 표준편차다. 실행 시간은 로그축이며,
표준편차 때문에 하단이 0 이하가 되면 로그축 표시를 위해 하단만 양수로 제한한다.
하나의 CSV에는 한 가지 공통 실험 환경만 넣는다. 다른 환경을 섞거나 동일 seed 행을
중복하면 plot은 오류를 내어 잘못된 평균을 방지한다.

## 실행 확인 결과

- 기존 A/B 테스트: 21개 통과.
- C 테스트: 15개 통과. 전수탐색 전체 후보/동률/빈 입력/입력 보존,
  생성 규칙/재현성, tick 유지, 탐색 한도, gap 0 처리, CSV·요약·입력 저장을 검증했다.
- demo: 입력 18개, 결과 72행 중 정상 66행/전수탐색 skip 6행, 그래프 8장 생성.
- A/B 파일은 ZIP 원본과 바이트 단위로 일치하는지 최종 확인했다.

C 코드는 생성형 AI(Codex)의 도움으로 작성하고 위 실행 검증을 수행했다.
