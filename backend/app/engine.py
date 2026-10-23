from datetime import datetime, timezone

from .models import TableState


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def elapsed_minutes(start: str | None, now: str) -> int:
    if not start:
        return 0
    return max(0, int((parse_time(now) - parse_time(start)).total_seconds() // 60))


def occupancy_transition(current: TableState, occupied: bool) -> TableState:
    if current == TableState.out_of_service:
        return current
    if occupied:
        if current in {TableState.available_clean, TableState.vacated_needs_cleaning, TableState.cleaning}:
            return TableState.occupied
        return current
    if current in {TableState.occupied, TableState.attention_due}:
        return TableState.vacated_needs_cleaning
    return current


def timer_transition(current: TableState, minutes: int, threshold: int) -> TableState:
    if current == TableState.occupied and minutes >= threshold:
        return TableState.attention_due
    return current

