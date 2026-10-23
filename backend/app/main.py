import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import FloorRepository
from .demo import DemoController
from .models import Alert, AlertAcknowledgement, CleaningAction, Event, FloorSnapshot, OccupancyObservation, TableStatus


repository = FloorRepository()
demo = DemoController()
app = FastAPI(title="MidaPulse", version="0.1.0", description="Privacy-first restaurant floor intelligence API.")

origins = [
    item.strip()
    for item in os.getenv(
        "MIDAPULSE_CORS_ORIGINS",
        "http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "midapulse-api", "privacy_mode": "anonymous-events-only"}


@app.get("/api/floor", response_model=FloorSnapshot)
def floor():
    return repository.snapshot()


@app.post("/api/observations", response_model=TableStatus)
def observe(payload: OccupancyObservation):
    table = repository.observe(payload)
    if not table:
        raise HTTPException(404, "Unknown table")
    return table


@app.post("/api/tables/{table_id}/cleaning", response_model=TableStatus)
def cleaning(table_id: str, payload: CleaningAction):
    table = repository.cleaning(table_id, payload)
    if not table:
        raise HTTPException(404, "Unknown table")
    return table


@app.post("/api/alerts/{alert_id}/acknowledge", response_model=Alert)
def acknowledge(alert_id: int, payload: AlertAcknowledgement):
    alert = repository.acknowledge(alert_id, payload.server)
    if not alert:
        raise HTTPException(404, "Unknown alert")
    return alert


@app.get("/api/events", response_model=list[Event])
def events(limit: int = 50):
    return repository.events(min(limit, 200))


@app.post("/api/demo/step", response_model=FloorSnapshot)
def demo_step():
    return demo.advance(repository)


@app.post("/api/demo/reset", response_model=FloorSnapshot)
def demo_reset():
    return demo.reset(repository)

