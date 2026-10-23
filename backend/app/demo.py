from datetime import datetime, timedelta, timezone

from .database import FloorRepository
from .models import OccupancyObservation


DEMO_STEPS = [
    [("T1", True, 0.97), ("T3", True, 0.94), ("T5", True, 0.91)],
    [("T2", True, 0.95), ("T6", True, 0.93)],
    [("T3", False, 0.96)],
    [("T1", False, 0.98), ("T4", True, 0.90)],
]


class DemoController:
    def __init__(self):
        self.step = 0

    def advance(self, repository: FloorRepository):
        now = datetime.now(timezone.utc)
        for table_id, occupied, confidence in DEMO_STEPS[self.step % len(DEMO_STEPS)]:
            observed_at = (now - timedelta(minutes=52)).isoformat() if self.step == 0 and table_id == "T1" else now.isoformat()
            repository.observe(OccupancyObservation(table_id=table_id, occupied=occupied, confidence=confidence, observed_at=observed_at, source="synthetic-demo"))
        self.step += 1
        return repository.snapshot(now.isoformat())

    def reset(self, repository: FloorRepository):
        self.step = 0
        repository.reset_demo()
        return repository.snapshot()

