"""C: 저장된 30개 seed 최종 데이터의 검증·요약·그래프 재생성.

시뮬레이터와 알고리즘을 다시 최적화하거나 계산 시간을 재측정하지 않는다.
CSV에 저장된 배정표의 대기시간만 다시 채점한다.
사용: python3 -m experiment.report_final [results/final_30seeds]
"""
from pathlib import Path
from collections import Counter, defaultdict
from statistics import mean, stdev
import csv
import hashlib
import json
import math
import subprocess
import sys
import argparse

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiment.generate import generate_instance
from experiment.plot import create_plots, load_results, LABELS
from experiment.run import summarize
from simulator import simulate

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('folder', nargs='?', type=Path, default=Path('results/final_30seeds'))
folder = parser.parse_args().folder
environment = json.loads((folder / 'environment.json').read_text())
assert environment['exit_code'] == 0
for path, digest in environment['source_sha256'].items():
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
rows = load_results(folder / 'results.csv')
ns = environment['design']['n']
seeds = environment['design']['seeds']
assert len(rows) == 2 * len(ns) * len(seeds) * 4 == 1920
groups = defaultdict(dict)
for row in rows:
    groups[(row['scenario'], int(row['n']), int(row['seed']))][row['algorithm']] = row
assert len(groups) == 480
expected = {(scenario, n, seed) for scenario in ['normal', 'peak'] for n in ns for seed in seeds}
assert set(groups) == expected
rechecked = 0
gap_states = Counter()
for (scenario, n, seed), algorithms in groups.items():
    assert set(algorithms) == set(LABELS)
    case = json.loads((folder / 'results_inputs' / f'{scenario}_n{n}_seed{seed}.json').read_text())
    assert case == generate_instance(n, seed, scenario)
    for name, row in algorithms.items():
        assert row['step'] == 'tick'
        assert int(row['candidate_count']) == 3 ** n
        gap_states[row['gap_status']] += 1
        if name == 'exhaustive' and n > 10:
            assert row['status'] == 'skipped' and row['skip_reason'] == 'assignment_limit'
            assert row['runtime_sec'] == row['avg_wait'] == row['optimality_gap'] == ''
            continue
        assert row['status'] == 'ok'
        assignment = json.loads(row['assignment'])
        assert len(assignment) == n and all(type(a) is int and 0 <= a < 3 for a in assignment)
        result = simulate(case['config'], case['elevators'], case['requests'], assignment, step='tick')
        assert len(result['wait_times']) == n
        assert math.isclose(result['avg_wait'], float(row['avg_wait']), rel_tol=1e-12)
        assert result['max_wait'] == int(row['max_wait'])
        assert float(row['runtime_sec']) > 0 and float(row['evaluation_sec']) > 0
        rechecked += 1
        if n <= 10:
            optimum = float(algorithms['exhaustive']['avg_wait'])
            gap = float(row['avg_wait']) - optimum
            assert gap >= 0 and float(row['optimal_avg_wait']) == optimum
            assert math.isclose(float(row['absolute_gap']), gap, abs_tol=1e-12)
            if optimum > 0:
                assert math.isclose(float(row['optimality_gap']), gap / optimum, abs_tol=1e-12)
            elif gap == 0:
                assert float(row['optimality_gap']) == 0
            else:
                assert row['gap_status'] == 'zero_optimum' and row['optimality_gap'] == ''
        else:
            assert row['optimal_avg_wait'] == row['absolute_gap'] == row['optimality_gap'] == ''
    assert float(algorithms['local_search']['avg_wait']) <= float(algorithms['ewt_greedy']['avg_wait'])
assert rechecked == 1740
assert sum(r['status'] == 'skipped' for r in rows) == 180
typed = []
for raw in rows:
    row = raw.copy()
    row['n'], row['num_elevators'] = int(row['n']), int(row['num_elevators'])
    for metric in ['avg_wait', 'max_wait', 'runtime_sec', 'optimality_gap']:
        row[metric] = float(row[metric]) if row[metric] else None
    typed.append(row)
rebuilt = summarize(typed)
stored = list(csv.DictReader((folder / 'results_summary.csv').open()))
assert len(stored) == len(rebuilt) == 64
for a, b in zip(rebuilt, stored):
    for key, value in a.items():
        if value is None:
            assert b[key] == ''
        elif isinstance(value, (float, int)):
            assert math.isclose(float(b[key]), value, rel_tol=1e-12, abs_tol=1e-12), key
        else:
            assert b[key] == value
verification = {'source_hashes_unchanged': True, 'input_instances_verified': 480,
                'raw_rows_verified': 1920, 'assignments_rescored': rechecked,
                'exhaustive_exact_runs': 300, 'exhaustive_skipped_runs': 180,
                'summary_rows_recomputed': 64, 'gap_status_counts': dict(gap_states),
                'local_search_never_worse_than_ewt': True,
                'test_results_before_benchmark': environment['tests']}
(folder / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
paths = create_plots(folder / 'results.csv', folder / 'plots')
import matplotlib.pyplot as plt
for scenario in ['normal', 'peak']:
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for name, label in LABELS.items():
        data = [r for r in rebuilt if r['scenario'] == scenario and r['algorithm'] == name and r['n'] <= 10]
        x = [r['n'] for r in data]
        y = [r['runtime_sec_mean'] for r in data]
        errors = [r['runtime_sec_std'] for r in data]
        yerr = [[min(e, v * .99) for e, v in zip(errors, y)], errors]
        ax.errorbar(x, y, yerr=yerr, marker='o', capsize=3, label=label)
    ax.set(title=f'{scenario.capitalize()} | M=3 | tick | 30 seeds', xlabel='Number of requests (N)',
           ylabel='Algorithm runtime (s, log scale)', yscale='log')
    ax.set_xticks([2, 4, 6, 8, 10])
    ax.grid(True, alpha=.25)
    ax.legend(fontsize=8)
    fig.text(.5, .02, 'Mean +/- sample SD across seeds; final scoring excluded.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, 1))
    path = folder / 'plots' / f'{scenario}_runtime_small.png'
    fig.savefig(path, dpi=180)
    plt.close(fig)
    paths.append(path)

# gap은 정확 최적값이 있는 N만 표시하여 큰 입력의 빈 영역을 만들지 않는다.
for scenario in ['normal', 'peak']:
    fig, ax = plt.subplots(figsize=(8.4, 5.2))
    for name, label in LABELS.items():
        data = [r for r in rebuilt if r['scenario'] == scenario and r['algorithm'] == name
                and r['optimality_gap_count'] > 0]
        ax.errorbar([r['n'] for r in data], [100*r['optimality_gap_mean'] for r in data],
                    yerr=[100*r['optimality_gap_std'] for r in data],
                    marker='o', capsize=3, label=label)
    ax.set(title=f'{scenario.capitalize()} | M=3 | tick | 30 seeds',
           xlabel='Number of requests (N)', ylabel='Optimality gap (%)', ylim=(0, None))
    ax.set_xticks([2, 4, 6, 8, 10])
    ax.grid(True, alpha=.25)
    ax.legend(fontsize=8)
    fig.text(.5, .02, 'Mean +/- sample SD; only inputs with an exact optimum are shown.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .04, 1, 1))
    fig.savefig(folder / 'plots' / f'{scenario}_optimality_gap.png', dpi=180)
    plt.close(fig)

summary = {(r['scenario'], r['n'], r['algorithm']): r for r in rebuilt}
names = {'nearest_car': 'Nearest-Car', 'ewt_greedy': 'EWT Greedy', 'local_search': 'Local Search', 'exhaustive': 'Exhaustive'}
def table(scenario, n):
    lines = ['| 알고리즘 | 평균 대기시간(s) | 최대 대기시간(s) | 계산 시간(s) | 상대 gap 평균(%) |',
             '|---|---:|---:|---:|---:|']
    for name in LABELS:
        r = summary[(scenario, n, name)]
        if not r['runs']:
            lines.append(f'| {names[name]} | 생략 | 생략 | 생략 | — |')
            continue
        gap = f"{100*r['optimality_gap_mean']:.2f} (유효 {r['optimality_gap_count']}/30)" if r['optimality_gap_mean'] is not None else '—'
        lines.append(f"| {names[name]} | {r['avg_wait_mean']:.3f} ± {r['avg_wait_std']:.3f} | {r['max_wait_mean']:.3f} ± {r['max_wait_std']:.3f} | {r['runtime_sec_mean']:.6f} ± {r['runtime_sec_std']:.6f} | {gap} |")
    return '\n'.join(lines)

pilot = [r for r in csv.DictReader((folder / 'pilot.csv').open()) if r['algorithm'] == 'exhaustive']
pilot_table = '\n'.join(['| 시나리오 | N | 후보 수 | 전수탐색 시간(s) |', '|---|---:|---:|---:|'] +
                        [f"| {r['scenario']} | {r['n']} | {int(r['candidate_count']):,} | {float(r['runtime_sec']):.3f} |" for r in pilot])
findings = []
for scenario in ['normal', 'peak']:
    ex = summary[(scenario, 10, 'exhaustive')]
    ewt = summary[(scenario, 10, 'ewt_greedy')]
    ls = summary[(scenario, 10, 'local_search')]
    nc = summary[(scenario, 10, 'nearest_car')]
    findings.append(f"- {scenario}, N=10: 평균 대기시간은 Exhaustive {ex['avg_wait_mean']:.3f}초, Local Search {ls['avg_wait_mean']:.3f}초, EWT {ewt['avg_wait_mean']:.3f}초, Nearest-Car {nc['avg_wait_mean']:.3f}초였다.")
    findings.append(f"- {scenario}, N=10: Exhaustive/EWT의 평균 계산 시간 비율은 약 {ex['runtime_sec_mean']/ewt['runtime_sec_mean']:,.0f}배였다. 온라인/오프라인의 정보 수준 차이를 함께 해석해야 한다.")

command = 'python3 -m experiment.run --n 2 4 6 8 10 20 30 50 --seeds ' + ' '.join(map(str, seeds)) + ' --max-assignments 59049 --output results/reproduced_30seeds/results.csv'
report = f'''# normal/peak별 30개 seed 최종 실험

실행일: 2026-11-04 (Asia/Seoul). 테스트 42개를 통과한 코드로 시나리오별, N별 30개 seed를 순차 실행했다.
입력 480개, 결과 1,920행 중 정상 측정 1,740행과 전수탐색 생략 180행을 저장했다.
저장된 입력 480개를 seed로 재생성해 일치를 확인했고, 정상 배정표 1,740개를 다시 tick 채점해 CSV와 일치함을 확인했다.

## 코드 및 팀원 검토 반영

- `main` 기준: `{environment['main_commit_at_start']}`.
- 실제 검증·측정 기준: B의 `feature/part-b-2`, `{environment['source_commit']}`.
- B의 추가 변경은 테스트 보강뿐이며 Simulator·알고리즘·입력 생성·실험 실행·기본 그래프 코드는 main과 동일하다.
- A/B 기존 테스트 27개와 C 테스트 15개, 총 42개가 통과했다. Simulator·알고리즘 원본은 변경하지 않았다.
- 실행에 사용한 소스의 SHA-256과 환경은 [environment.json](environment.json), 결과 대조 기록은 [verification.json](verification.json)에 있다.

## 실험 조건

| 항목 | 조건 |
|---|---|
| 컴퓨터 | Apple M3, 16 GiB 메모리, 물리/논리 코어 각 8개 |
| 소프트웨어 | Python 3.12.4, matplotlib 3.10.3, {environment['machine']['platform']} |
| 운행 | 20층, 3대, 초기 위치 1·10·20층, 이동 2초, 정차 5초, 정원 제한 없음, 승하차 추가 시간 0초 |
| 시뮬레이션 | 모든 알고리즘 내부와 결과 채점은 tick |
| 입력 크기 N | 2, 4, 6, 8, 10, 20, 30, 50 |
| 시나리오 및 반복 | normal/peak 각각, 각 N마다 seed 0~29의 30개 입력 |
| 전수탐색 | N≤10에서 모든 3^N 후보 평가; 한도 59,049개 |
| 큰 입력 | N=20·30·50은 Nearest-Car·EWT·Local Search 측정, Exhaustive는 `assignment_limit`으로 생략 |
| 시간 측정 | 배정 함수만 측정. 내부 시뮬레이션 포함, 최종 채점·입력 복사·파일 저장 제외 |
| 실행 방식 | 알고리즘을 병렬 실행하지 않고, seed에 따라 실행 순서 회전. 각 입력의 함수 호출은 1회 측정 |

normal은 서로 다른 두 층을 균등 추출한다. peak는 80% 확률로 1층→상층, 나머지는 normal과 같이 추출한다.
따라서 실제 로비 상행 비율이 정확히 80%로 고정되지는 않는다. 도착 간격은 두 시나리오 모두 0~10초 정수 균등 추출이다.
이 값들은 실험용 가정이며 산업 통계값으로 사용하지 않는다.

## N=10: 네 알고리즘 비교

아래 값은 각 지표의 seed 평균 ± 표본 표준편차다. 최대 대기시간 열은 각 입력의 최대 대기시간을 30개 seed에 걸쳐 평균 낸 값이다.

### normal

{table('normal', 10)}

### peak

{table('peak', 10)}

상대 gap은 입력별 `(알고리즘 평균 대기시간 - 최적 평균 대기시간) / 최적 평균 대기시간`의 유효값 평균이다.
seed별 평균 대기시간을 먼저 합쳐서 계산한 비율과는 다르다. 최적=0·알고리즘=0이면 0,
최적=0·알고리즘>0이면 상대 gap은 빈칸이고 절대 gap은 유지한다. 유효 개수는 요약 CSV에도 저장했다.

## N=50: 큰 입력 비교

### normal

{table('normal', 50)}

### peak

{table('peak', 50)}

최적값을 측정하지 않은 큰 입력은 gap을 계산하지 않았다. 모든 N의 평균·표준편차는 [results_summary.csv](results_summary.csv)에 있다.

## 관찰 결과

{chr(10).join(findings)}
- 전체 480개 입력에서 Local Search의 평균 대기시간이 EWT보다 커진 경우는 없었다.
- 평균 대기시간 개선이 최대 대기시간 개선을 보장하지는 않았다. peak N=50에서 Local Search의 최대 대기시간 평균은 {summary[('peak', 50, 'local_search')]['max_wait_mean']:.3f}초로 EWT의 {summary[('peak', 50, 'ewt_greedy')]['max_wait_mean']:.3f}초보다 컸다. Local Search는 평균을 개선하는 목적 함수이므로 이 결과도 그대로 제시한다.
- Exhaustive의 최적성은 고정된 운행 규칙 아래 배정 공간에 대한 것이다. 운행 규칙이나 승객 처리 순서를 추가로 최적화한 결과가 아니다.

## 탐색 범위를 정하기 위한 별도 예비 측정

공식 30개 seed 실험 전에 각 조건의 seed=0 한 건을 측정했다. 이 예비 수치는 최종 평균·그래프에 섞지 않았다.

{pilot_table}

N=12도 한 입력의 정확 탐색은 완료했지만, 전체 60개 입력의 비용을 고려해 본 실험은 N≤10으로 범위를 정했다.
큰 N의 생략은 후보 한도 정책이며, 실제 시간 초과나 계산 불가능을 실증한 결과로 표현하지 않는다.

## 결과 파일과 그래프

- [results.csv](results.csv): 모든 원시 결과, 배정표, 대기시간, 계산 시간, gap, skip 이유.
- [results_summary.csv](results_summary.csv): 64개 조건의 seed 평균·표본 표준편차·유효 개수.
- `results_inputs/`: 비교에 사용한 JSON 입력 480개.
- [run.log](run.log): 실행 진행 기록.
- [pilot.csv](pilot.csv): seed=0의 별도 예비 측정.
- `plots/`: 시나리오별 평균·최대 대기시간, 계산 시간, gap 그래프 8장과 작은 입력 계산 시간 확대 그래프 2장.
- gap 그래프는 정확 최적값을 측정한 N≤10만 표시한다.

![normal 평균 대기시간](plots/normal_avg_wait.png)
![peak 평균 대기시간](plots/peak_avg_wait.png)
![normal 계산 시간 확대](plots/normal_runtime_small.png)
![peak 계산 시간 확대](plots/peak_runtime_small.png)

## 재현 방법

저장소 루트에서 같은 소스 버전을 사용한다. 아래 명령은 기존 결과를 보존하도록 다른 폴더에 저장한다.

```bash
{command}
python3 -m experiment.plot results/reproduced_30seeds/results.csv --output-dir results/reproduced_30seeds/plots
```

환경과 명령 원문은 environment.json에 기록했다. 입력과 대기시간은 동일 조건에서 재현되며, 계산 시간은 실행 환경에 따라 달라진다.
첨부된 최종 데이터의 재검증과 그래프 10장·이 보고서 재생성은 `python3 -m experiment.report_final`로 실행한다.
해당 코드는 [experiment/report_final.py](../../experiment/report_final.py)에 있다. 이 명령은 최적화 알고리즘의 계산 시간을 다시 측정하지 않는다.
표준편차는 서로 다른 seed 간 변동으로, 동일 입력의 반복 시간 측정에 대한 오차 범위가 아니다.
Codex가 실행 중인 사용자 컴퓨터에서 측정했으며 다른 프로그램의 종료나 백그라운드 부하를 통제하지 않았다.
그래프의 계산 시간은 로그축이고, 오차 막대 하단이 0 이하일 때 표시 가능한 양수 범위로 제한했다.

C 코드·결과 정리·보고서는 생성형 AI(Codex)의 도움으로 작성하고 위 검증을 수행했다.
'''
(folder / 'README.md').write_text(report)
print(json.dumps(verification, ensure_ascii=False, indent=2))
print('\n'.join(findings))
print('plots generated:', len(paths))
