from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.database import FloorRepository
from backend.app.demo import DemoController
from backend.app.main import app
from backend.app.models import CleaningAction, OccupancyObservation, TableState


client = TestClient(app)


def test_health_exposes_privacy_mode():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["privacy_mode"] == "anonymous-events-only"


def test_occupancy_creates_explicit_state_transition():
    repo = FloorRepository(":memory:")
    table = repo.observe(OccupancyObservation(table_id="T1", occupied=True, confidence=0.95))
    assert table.state == TableState.occupied
    assert table.occupied_since is not None


def test_long_occupancy_creates_service_alert():
    repo = FloorRepository(":memory:")
    start = datetime(2026, 10, 23, 18, 0, tzinfo=timezone.utc)
    repo.observe(OccupancyObservation(table_id="T1", occupied=True, confidence=0.97, observed_at=start.isoformat()))
    snapshot = repo.snapshot((start + timedelta(minutes=46)).isoformat())
    table = next(item for item in snapshot.tables if item.id == "T1")
    assert table.state == TableState.attention_due
    assert snapshot.alerts[0].alert_type == "service_check"


def test_vacated_table_requires_cleaning_then_returns_available():
    repo = FloorRepository(":memory:")
    repo.observe(OccupancyObservation(table_id="T2", occupied=True, confidence=0.96))
    table = repo.observe(OccupancyObservation(table_id="T2", occupied=False, confidence=0.98))
    assert table.state == TableState.vacated_needs_cleaning
    assert any(alert.alert_type == "cleaning" for alert in repo.list_alerts())
    table = repo.cleaning("T2", CleaningAction(staff="Nora", action="complete"))
    assert table.state == TableState.available_clean
    assert repo.list_alerts() == []


def test_camera_observation_contains_no_personal_identity_fields():
    schema = OccupancyObservation.model_json_schema()["properties"]
    assert "face" not in schema
    assert "person_id" not in schema
    assert set(schema) == {"table_id", "occupied", "confidence", "observed_at", "source"}


def test_local_dashboard_cors():
    response = client.options("/api/floor", headers={"Origin": "http://127.0.0.1:5174", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5174"


def test_demo_surfaces_attention_state_on_first_step():
    repo = FloorRepository(":memory:")
    snapshot = DemoController().advance(repo)
    table = next(item for item in snapshot.tables if item.id == "T1")
    assert table.state == TableState.attention_due
    assert any(alert.alert_type == "service_check" for alert in snapshot.alerts)

