"""테스트 공통 설정: 저장소 루트를 경로에 넣고, 입력을 만드는 도우미를 둔다."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIG = {"num_floors": 20, "floor_time": 2, "stop_time": 5}


def req(rid, time, origin, dest):
    return {"id": rid, "time": time, "origin": origin, "dest": dest}


def cars(*floors):
    return [{"id": i, "floor": f} for i, f in enumerate(floors)]
