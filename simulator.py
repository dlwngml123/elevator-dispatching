"""Elevator dispatching simulator (Part A).

집합 제어(collective control) 규칙으로 엘리베이터 여러 대를 움직이고,
주어진 배정(assignment)에 대한 승객 대기시간을 계산한다.

공개 인터페이스
    simulate(config, elevators, requests, assignment, *, trace=False, step="tick") -> dict
    state_at(config, elevators, requests, assignment, t) -> list[dict]
    Simulator  : 시간을 조금씩 진행하면서 배정을 추가할 수 있는 점진 모드
                 (Nearest-Car 같은 온라인 알고리즘용)

운행 규칙 ("알고리즘 프로젝트 방향" 문서 3장)
    1. 진행 방향 유지: UP이면 위쪽 할 일을 아래부터 순서대로 처리 (DOWN은 반대)
    2. 탑승 조건: 승객 방향과 엘리베이터 방향이 같을 때만 탑승, 다르면 돌아올 때 태움
    3. 방향 전환: 진행 방향 앞쪽에 할 일이 없을 때만
    4. 대기: 할 일이 없으면 IDLE, 새 할 일이 생기면 그 방향으로 출발
    5. 도착 시각: 승객은 도착 시각 이후에만 탑승 가능
    가정값: 약 20층, 엘리베이터 3대(서로 다른 초기 위치), 한 층 이동 2초, 정차 1회 5초,
            정원 제한 없음, 재배정 없음
    층수·엘리베이터 대수·초기 위치는 입력(config, elevators)으로 받으므로 코드에 고정되어 있지 않다.
    구현: 1초 단위 시간 시뮬레이션

방향 문서 규칙에서 도출되는 동작
    - "할 일"은 탑승층과 하차층 모두 (3장 "할 일 목록(탑승층, 하차층)"). 그래서 반대 방향
      승객의 탑승층도 앞쪽 할 일이다 (규칙 1).
    - 탑승 시각 = 엘리베이터가 그 층에 도착한 시각 (7장 예시 "1→5층 8초 → t=8 P1 탑승").
    - 방향 전환은 시간이 들지 않는다 (7장 예시: t=26 전환, 9→7층 4초 → t=30).
    - 승객은 자기에게 배정된 엘리베이터만 탄다 (출력 = 요청별 배정, 재배정 없음).
    - 같은 층의 여러 승객은 한 번 정차로 태운다 (7장 확인 항목 "같은 층에 승객 2명").

방향 문서만으로 정해지지 않아 정한 세부 규칙 (설계 문서 4번, 10/30 팀 합의로 확정)
    C1 정차 중 도착한 같은 방향 승객은 즉시 태우고, 정차 종료 시각은 그대로 둔다 (_reveal).
    C2 같은 층에 IDLE로 있을 때 그 층 승객이 오면 승객 방향으로 정하고 정차 5초를 적용한다.
    C3 같은 층의 하차와 탑승은 한 번 정차로 처리한다 (_stop).
    C4 정차한 층에서 앞쪽 할 일이 없으면 같은 정차 안에서 방향을 바꿔 반대 방향 승객도 태운다.
    C5 같은 시각에는 요청을 먼저 공개하고 엘리베이터가 판단한다 (_process).
    C6 엘리베이터는 요청의 도착 시각에 할 일을 받는다 (미리 마중 없음).
    C7 요청 시 출발층·목적층이 모두 주어진다. EWT 같은 알고리즘은 목적층을 예상 대기시간
       계산에 쓸 수 있지만, 시뮬레이터는 승객이 실제로 탄 뒤에만 목적층을 정차할 곳으로
       추가한다 (_board).
    C8 층 사이에서는 멈추거나 돌아서지 않고, 층에 도착할 때만 판단한다 (_decide).
    C9 IDLE에서 할 일이 여러 곳이면: 같은 층 승객 > 가장 가까운 할 일 > 먼저 온 요청 (_choose_direction).

표준 라이브러리만 사용한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

UP, DOWN, IDLE = 1, -1, 0
DIR_NAME = {UP: "UP", DOWN: "DOWN", IDLE: "IDLE"}

DEFAULT_CONFIG = {
    "num_floors": 20,
    "floor_time": 2,      # 한 층 이동 (초)
    "stop_time": 5,       # 정차 1회 (초)
    "capacity": None,     # 탑승 인원 제한. None = 제한 없음
    "transfer_time": 0,   # 승객 1명당 승하차 추가 시간 (초). 0 = 고정 정차 시간
}


@dataclass(slots=True)
class Elevator:
    """엘리베이터 한 대의 상태. 판단 로직은 Simulator가 가진다."""

    id: int
    floor: int                      # 현재 층. 이동 중이면 마지막으로 떠난 층
    direction: int = IDLE           # UP / DOWN / IDLE
    status: str = "IDLE"            # "IDLE" / "MOVING" / "STOPPED"
    next_time: int | None = None    # 다음 판단 시각 (층 도착 또는 정차 종료)
    pickups: dict = field(default_factory=dict)   # 층 -> [요청 id, ...] (태우러 갈 곳)
    dropoffs: dict = field(default_factory=dict)  # 층 -> [요청 id, ...] (내려줄 곳)
    load: int = 0                   # 현재 탑승 인원


class SimulationError(Exception):
    """입력이 잘못됐거나 시뮬레이션이 진행되지 않을 때."""


class Simulator:
    """집합 제어 시뮬레이터.

    step="tick"  : 1초씩 진행한다 (기본, 방향 문서의 구현 방식)
    step="event" : 아무 일도 없는 초는 건너뛰고 다음 사건 시각으로 바로 간다 (가속 옵션).
                   결과는 tick과 항상 같다 (테스트로 확인).
    """

    def __init__(self, config, elevators, requests, assignment=None, *,
                 trace=False, step="tick"):
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.num_floors = int(cfg["num_floors"])
        self.floor_time = int(cfg["floor_time"])
        self.stop_time = int(cfg["stop_time"])
        self.capacity = cfg["capacity"]
        self.transfer_time = int(cfg["transfer_time"])
        if step not in ("event", "tick"):
            raise SimulationError(f"step must be 'event' or 'tick', got {step!r}")
        self.step = step

        _validate(self.num_floors, elevators, requests)
        n = len(requests)
        self.n = n
        self.r_time = [r["time"] for r in requests]
        self.r_origin = [r["origin"] for r in requests]
        self.r_dest = [r["dest"] for r in requests]
        self.r_dir = [UP if r["dest"] > r["origin"] else DOWN for r in requests]

        if assignment is None:
            assignment = [None] * n
        if len(assignment) != n:
            raise SimulationError("assignment length must equal number of requests")
        m = len(elevators)
        for i, a in enumerate(assignment):
            if a is not None and not (0 <= a < m):
                raise SimulationError(f"assignment[{i}]={a} is not an elevator id")
        self.assignment = list(assignment)

        self.elevs = [Elevator(e["id"], e["floor"])
                      for e in sorted(elevators, key=lambda e: e["id"])]
        self.t = 0                        # 현재 시각
        self.clock = 0                    # 다음에 처리할 초 (이보다 이른 시각은 모두 처리됨)
        self.next_req = 0                 # 아직 공개되지 않은 첫 요청
        self.board_time = [None] * n
        self.alight_time = [None] * n
        self.boarded = 0
        self.trace = [] if trace else None

    # ------------------------------------------------------------------ 진행
    def assign(self, i, elevator_id):
        """아직 공개되지 않은 요청 i의 배정을 정한다 (점진 모드)."""
        if i < self.next_req:
            raise SimulationError(f"request {i} was already revealed at t={self.r_time[i]}")
        self.assignment[i] = elevator_id

    def advance_to(self, t):
        """시각 t 직전까지(t 미만의 시각만) 처리한다."""
        while self.clock < t:
            if self.step == "tick":
                self._process(self.clock)          # 1초씩
            else:
                nt = self._next_event_time()       # 일이 있는 다음 시각으로 건너뜀
                if nt is None or nt >= t:
                    break
                self._process(nt)
        self.clock = max(self.clock, t)
        self.t = max(self.t, t)

    def run(self):
        """배정된 승객이 모두 탈 때까지 진행한다."""
        target = sum(1 for a in self.assignment if a is not None)
        guard = 0
        while self.boarded < target:
            nt = self._next_event_time()
            if nt is None:
                raise SimulationError("no more events but some passengers never boarded")
            if self.step == "tick":
                self._process(self.clock)          # 이 1초 동안 일어나는 일 (없으면 그냥 지나감)
            else:
                self._process(nt)
            guard += 1
            if guard > 10_000_000:
                raise SimulationError("simulation did not finish")
        return self.result()

    def result(self):
        waits = {i: self.board_time[i] - self.r_time[i]
                 for i in range(self.n)
                 if self.assignment[i] is not None and self.board_time[i] is not None}
        if waits:
            avg = sum(waits.values()) / len(waits)
            mx = max(waits.values())
        else:
            avg, mx = 0.0, 0
        out = {"wait_times": waits, "avg_wait": avg, "max_wait": mx}
        if self.trace is not None:
            out["trace"] = list(self.trace)
        return out

    def state(self):
        """현재 시각의 엘리베이터 상태 (Nearest-Car 등이 사용)."""
        return [{"id": e.id, "floor": e.floor, "direction": DIR_NAME[e.direction],
                 "status": e.status, "load": e.load} for e in self.elevs]

    # ------------------------------------------------------------ 내부: 사건
    def _next_event_time(self):
        best = self.r_time[self.next_req] if self.next_req < self.n else None
        for e in self.elevs:
            if e.next_time is not None and (best is None or e.next_time < best):
                best = e.next_time
        return best

    def _process(self, t):
        """시각 t에 일어나는 일을 처리한다."""
        self.t = t
        self.clock = t + 1
        # 1) 시각 t에 도착한 요청을 id 순서로 공개 (id 순서는 방향 문서 6장, 요청 먼저는 C5)
        while self.next_req < self.n and self.r_time[self.next_req] == t:
            self._reveal(self.next_req, t)
            self.next_req += 1
        # 2) 시각 t에 판단할 엘리베이터를 id 순서로 처리
        for e in self.elevs:
            if e.next_time == t:
                self._decide(e, t)

    def _reveal(self, i, t):
        a = self.assignment[i]
        if a is None:
            return
        e = self.elevs[a]
        f, d = self.r_origin[i], self.r_dir[i]
        self._log(t, f"P{i} 도착 {f}층 -> {self.r_dest[i]}층, E{a} 배정")
        # C1: 그 층에 정차 중이고 탈 수 있으면 바로 탑승, 정차 종료 시각은 그대로
        if e.status == "STOPPED" and e.floor == f and self._has_room(e):
            if e.direction == d or not self._has_ahead(e, e.direction):
                if e.direction != d:
                    e.direction = d
                self._board(e, i, t)
                return
        e.pickups.setdefault(f, []).append(i)
        if e.status == "IDLE":
            e.next_time = t          # 같은 시각에 바로 판단

    def _decide(self, e, t):
        if e.status == "MOVING":
            e.floor += e.direction
            if not 1 <= e.floor <= self.num_floors:
                raise SimulationError(f"E{e.id} left the building (floor {e.floor})")
        for _ in range(4):            # 방향 전환은 최대 한 번이면 충분하다
            d = e.direction
            if d == IDLE:
                if not e.pickups and not e.dropoffs:
                    self._go_idle(e, t)
                    return
                e.direction = self._choose_direction(e)
                self._log(t, f"E{e.id} {e.floor}층 IDLE -> {DIR_NAME[e.direction]}")
                continue
            if self._should_stop(e):
                self._stop(e, t)
                return
            if self._has_ahead(e, d):
                e.status = "MOVING"
                e.next_time = t + self.floor_time
                return
            if e.pickups or e.dropoffs:
                e.direction = -d       # 앞쪽에 할 일이 없으면 방향 전환
                self._log(t, f"E{e.id} {e.floor}층 방향 전환 -> {DIR_NAME[e.direction]}")
                continue
            self._go_idle(e, t)
            return
        raise SimulationError(f"E{e.id} could not decide at t={t}")

    # ------------------------------------------------------------ 내부: 규칙
    def _choose_direction(self, e):
        """C9: IDLE에서 출발 방향: 같은 층 승객 > 가장 가까운 할 일 > 먼저 온 요청."""
        here = e.pickups.get(e.floor)
        if here:
            return self.r_dir[min(here)]
        best = None
        for f, rids in e.pickups.items():
            key = (abs(f - e.floor), min(rids))
            if best is None or key < best[0]:
                best = (key, f)
        for f, rids in e.dropoffs.items():
            key = (abs(f - e.floor), min(rids))
            if best is None or key < best[0]:
                best = (key, f)
        return UP if best[1] > e.floor else DOWN

    def _has_ahead(self, e, d):
        if d == IDLE:
            return False
        f = e.floor
        for g in e.dropoffs:
            if (g - f) * d > 0:
                return True
        for g in e.pickups:
            if (g - f) * d > 0:
                return True
        return False

    def _has_room(self, e):
        return self.capacity is None or e.load < self.capacity

    def _should_stop(self, e):
        f = e.floor
        if f in e.dropoffs:
            return True
        here = e.pickups.get(f)
        if here and self._has_room(e):
            d = e.direction
            for i in here:
                if self.r_dir[i] == d:
                    return True
        return False

    def _stop(self, e, t):
        f = e.floor
        moved = 0
        for i in e.dropoffs.pop(f, []):
            self.alight_time[i] = t
            e.load -= 1
            moved += 1
            self._log(t, f"E{e.id} {f}층 P{i} 하차")
        moved += self._board_here(e, e.direction, t)
        # C4: 앞쪽 할 일이 없으면 같은 정차 안에서 방향을 바꿔 반대 방향 승객도 태운다
        if not self._has_ahead(e, e.direction) and e.pickups.get(f):
            e.direction = -e.direction
            self._log(t, f"E{e.id} {f}층 정차 중 방향 전환 -> {DIR_NAME[e.direction]}")
            moved += self._board_here(e, e.direction, t)
        e.status = "STOPPED"
        e.next_time = t + self.stop_time + self.transfer_time * moved

    def _board_here(self, e, d, t):
        here = e.pickups.get(e.floor)
        if not here:
            return 0
        keep, count = [], 0
        for i in sorted(here):
            if self.r_dir[i] == d and self._has_room(e):
                self._board(e, i, t)
                count += 1
            else:
                keep.append(i)
        if keep:
            e.pickups[e.floor] = keep
        else:
            del e.pickups[e.floor]
        return count

    def _board(self, e, i, t):
        self.board_time[i] = t
        self.boarded += 1
        e.load += 1
        e.dropoffs.setdefault(self.r_dest[i], []).append(i)   # C7: 탑승한 뒤에만 목적층을 정차할 곳으로 추가
        self._log(t, f"E{e.id} {e.floor}층 P{i} 탑승 (대기 {t - self.r_time[i]}초)")

    def _go_idle(self, e, t):
        if e.status != "IDLE":
            self._log(t, f"E{e.id} {e.floor}층 IDLE")
        e.direction = IDLE
        e.status = "IDLE"
        e.next_time = None

    def _log(self, t, msg):
        if self.trace is not None:
            self.trace.append(f"t={t:>4} {msg}")


# ---------------------------------------------------------------- 공개 함수
def simulate(config, elevators, requests, assignment, *, trace=False, step="tick"):
    """assignment에서 None인 요청은 무시한다 (아직 배정 안 된 요청).

    반환: {"wait_times": {요청id: 대기시간}, "avg_wait": 평균, "max_wait": 최대}
          trace=True면 "trace": [사건 기록 문자열] 추가
    """
    return Simulator(config, elevators, requests, assignment,
                     trace=trace, step=step).run()


def state_at(config, elevators, requests, assignment, t):
    """시각 t의 사건을 처리하기 직전의 엘리베이터 상태.

    t 미만에 도착한 요청만 반영한다. 이동 중이면 floor는 마지막으로 떠난 층이다.
    """
    sim = Simulator(config, elevators, requests, assignment)
    sim.advance_to(t)
    return sim.state()


def _validate(num_floors, elevators, requests):
    if num_floors < 2:
        raise SimulationError("num_floors must be at least 2")
    if not elevators:
        raise SimulationError("need at least one elevator")
    ids = sorted(e["id"] for e in elevators)
    if ids != list(range(len(elevators))):
        raise SimulationError("elevator ids must be 0..M-1")
    for e in elevators:
        if not 1 <= e["floor"] <= num_floors:
            raise SimulationError(f"elevator {e['id']} floor {e['floor']} out of range")
    prev = None
    for i, r in enumerate(requests):
        if r["id"] != i:
            raise SimulationError(f"request ids must be 0..N-1 in order (index {i})")
        if not (1 <= r["origin"] <= num_floors and 1 <= r["dest"] <= num_floors):
            raise SimulationError(f"request {i} floor out of range")
        if r["origin"] == r["dest"]:
            raise SimulationError(f"request {i} has origin == dest")
        if not isinstance(r["time"], int) or r["time"] < 0:
            raise SimulationError(f"request {i} time must be a non-negative int")
        if prev is not None and r["time"] < prev:
            raise SimulationError("requests must be sorted by time")
        prev = r["time"]
