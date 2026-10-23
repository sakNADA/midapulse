from enum import Enum

from pydantic import BaseModel, Field


class TableState(str, Enum):
    available_clean = "available_clean"
    occupied = "occupied"
    attention_due = "attention_due"
    vacated_needs_cleaning = "vacated_needs_cleaning"
    cleaning = "cleaning"
    out_of_service = "out_of_service"


class TableStatus(BaseModel):
    id: str
    label: str
    seats: int
    zone_x: int
    zone_y: int
    state: TableState
    occupied_since: str | None
    state_changed_at: str
    last_confidence: float
    attention_after_minutes: int
    assigned_server: str | None
    elapsed_minutes: int = 0


class OccupancyObservation(BaseModel):
    table_id: str
    occupied: bool
    confidence: float = Field(ge=0, le=1)
    observed_at: str | None = None
    source: str = Field(default="edge-camera", max_length=60)


class Alert(BaseModel):
    id: int
    table_id: str
    alert_type: str
    priority: str
    message: str
    status: str
    created_at: str
    acknowledged_by: str | None


class AlertAcknowledgement(BaseModel):
    server: str = Field(min_length=2, max_length=80)


class CleaningAction(BaseModel):
    staff: str = Field(min_length=2, max_length=80)
    action: str = Field(pattern=r"^(start|complete)$")


class Event(BaseModel):
    id: int
    table_id: str
    event_type: str
    detail: str
    source: str
    created_at: str


class FloorSnapshot(BaseModel):
    generated_at: str
    tables: list[TableStatus]
    alerts: list[Alert]
    metrics: dict[str, int]

