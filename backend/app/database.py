from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .engine import elapsed_minutes, occupancy_transition, timer_transition
from .models import Alert, CleaningAction, Event, FloorSnapshot, OccupancyObservation, TableState, TableStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FloorRepository:
    def __init__(self, db_path: str | None = None, config_path: str | None = None):
        configured = db_path or os.getenv("MIDAPULSE_DB_PATH", "./midapulse.db")
        self.db_path = configured
        if configured != ":memory:":
            Path(configured).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if configured == ":memory:" else None
        if self._memory:
            self._memory.row_factory = sqlite3.Row
        self.config_path = Path(config_path) if config_path else Path(__file__).resolve().parents[2] / "config" / "floor.json"
        self.init_schema()
        self.seed_tables()

    @contextmanager
    def connect(self):
        if self._memory:
            yield self._memory
            self._memory.commit()
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS dining_tables (
                    id TEXT PRIMARY KEY, label TEXT NOT NULL, seats INTEGER NOT NULL,
                    zone_x INTEGER NOT NULL, zone_y INTEGER NOT NULL, state TEXT NOT NULL,
                    occupied_since TEXT, state_changed_at TEXT NOT NULL,
                    last_confidence REAL NOT NULL DEFAULT 0,
                    attention_after_minutes INTEGER NOT NULL,
                    assigned_server TEXT
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, table_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL, priority TEXT NOT NULL, message TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, acknowledged_by TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, table_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, detail TEXT NOT NULL, source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, created_at);
                CREATE INDEX IF NOT EXISTS idx_events_table ON events(table_id, created_at);
                """
            )

    def seed_tables(self):
        floor = json.loads(self.config_path.read_text(encoding="utf-8"))
        now = utc_now()
        with self.connect() as conn:
            for table in floor["tables"]:
                conn.execute(
                    """INSERT OR IGNORE INTO dining_tables
                    (id, label, seats, zone_x, zone_y, state, occupied_since, state_changed_at,
                     last_confidence, attention_after_minutes, assigned_server)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, ?, 0, ?, ?)""",
                    (table["id"], table["label"], table["seats"], table["x"], table["y"],
                     TableState.available_clean.value, now, table["attention_after_minutes"], table.get("server")),
                )

    def observe(self, observation: OccupancyObservation) -> TableStatus | None:
        observed_at = observation.observed_at or utc_now()
        table = self.get_table(observation.table_id, observed_at)
        if not table:
            return None
        next_state = occupancy_transition(table.state, observation.occupied)
        occupied_since = table.occupied_since
        if next_state == TableState.occupied and table.state not in {TableState.occupied, TableState.attention_due}:
            occupied_since = observed_at
        if next_state == TableState.vacated_needs_cleaning:
            occupied_since = None

        with self.connect() as conn:
            conn.execute(
                "UPDATE dining_tables SET state=?, occupied_since=?, state_changed_at=?, last_confidence=? WHERE id=?",
                (next_state.value, occupied_since, observed_at, observation.confidence, observation.table_id),
            )
            if next_state != table.state:
                self._event(conn, table.id, "STATE_CHANGED", f"{table.state.value} -> {next_state.value}", observation.source, observed_at)
                if next_state == TableState.vacated_needs_cleaning:
                    self._open_alert(conn, table.id, "cleaning", "normal", f"{table.label} is free and needs cleaning.", observed_at)
                if next_state == TableState.occupied and table.state in {TableState.vacated_needs_cleaning, TableState.cleaning}:
                    self._open_alert(conn, table.id, "hygiene_override", "high", f"{table.label} was occupied before cleaning was completed.", observed_at)
        return self.get_table(observation.table_id, observed_at)

    def evaluate(self, now: str | None = None):
        current_time = now or utc_now()
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM dining_tables").fetchall()
            for row in rows:
                minutes = elapsed_minutes(row["occupied_since"], current_time)
                state = TableState(row["state"])
                next_state = timer_transition(state, minutes, row["attention_after_minutes"])
                if next_state != state:
                    conn.execute("UPDATE dining_tables SET state=?, state_changed_at=? WHERE id=?", (next_state.value, current_time, row["id"]))
                    self._event(conn, row["id"], "ATTENTION_THRESHOLD", f"Occupied for {minutes} minutes.", "timer", current_time)
                    self._open_alert(conn, row["id"], "service_check", "high", f"{row['label']} has been occupied for {minutes} minutes. Check whether guests need assistance.", current_time)

    def cleaning(self, table_id: str, action: CleaningAction) -> TableStatus | None:
        table = self.get_table(table_id)
        if not table:
            return None
        now = utc_now()
        next_state = TableState.cleaning if action.action == "start" else TableState.available_clean
        with self.connect() as conn:
            conn.execute("UPDATE dining_tables SET state=?, state_changed_at=? WHERE id=?", (next_state.value, now, table_id))
            self._event(conn, table_id, f"CLEANING_{action.action.upper()}", f"Cleaning {action.action} by {action.staff}.", action.staff, now)
            if action.action == "complete":
                conn.execute("UPDATE alerts SET status='resolved', acknowledged_by=? WHERE table_id=? AND alert_type='cleaning' AND status!='resolved'", (action.staff, table_id))
        return self.get_table(table_id)

    def acknowledge(self, alert_id: int, server: str) -> Alert | None:
        with self.connect() as conn:
            conn.execute("UPDATE alerts SET status='acknowledged', acknowledged_by=? WHERE id=?", (server, alert_id))
            row = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        return Alert(**dict(row)) if row else None

    def snapshot(self, now: str | None = None) -> FloorSnapshot:
        current_time = now or utc_now()
        self.evaluate(current_time)
        tables = self.list_tables(current_time)
        alerts = self.list_alerts()
        metrics = {
            "occupied": sum(table.state in {TableState.occupied, TableState.attention_due} for table in tables),
            "attention_due": sum(table.state == TableState.attention_due for table in tables),
            "needs_cleaning": sum(table.state == TableState.vacated_needs_cleaning for table in tables),
            "available": sum(table.state == TableState.available_clean for table in tables),
        }
        return FloorSnapshot(generated_at=current_time, tables=tables, alerts=alerts, metrics=metrics)

    def get_table(self, table_id: str, now: str | None = None) -> TableStatus | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM dining_tables WHERE id=?", (table_id,)).fetchone()
        return self._to_table(row, now or utc_now()) if row else None

    def list_tables(self, now: str) -> list[TableStatus]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM dining_tables ORDER BY id").fetchall()
        return [self._to_table(row, now) for row in rows]

    def list_alerts(self) -> list[Alert]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM alerts WHERE status!='resolved' ORDER BY CASE priority WHEN 'high' THEN 0 ELSE 1 END, created_at DESC").fetchall()
        return [Alert(**dict(row)) for row in rows]

    def events(self, limit: int = 50) -> list[Event]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Event(**dict(row)) for row in rows]

    def reset_demo(self):
        now = utc_now()
        with self.connect() as conn:
            conn.execute("DELETE FROM alerts")
            conn.execute("DELETE FROM events")
            conn.execute("UPDATE dining_tables SET state=?, occupied_since=NULL, state_changed_at=?, last_confidence=0", (TableState.available_clean.value, now))

    @staticmethod
    def _event(conn, table_id: str, event_type: str, detail: str, source: str, created_at: str):
        conn.execute("INSERT INTO events (table_id,event_type,detail,source,created_at) VALUES (?,?,?,?,?)", (table_id, event_type, detail, source, created_at))

    @staticmethod
    def _open_alert(conn, table_id: str, alert_type: str, priority: str, message: str, created_at: str):
        existing = conn.execute("SELECT id FROM alerts WHERE table_id=? AND alert_type=? AND status!='resolved'", (table_id, alert_type)).fetchone()
        if not existing:
            conn.execute("INSERT INTO alerts (table_id,alert_type,priority,message,status,created_at,acknowledged_by) VALUES (?,?,?,?, 'open', ?, NULL)", (table_id, alert_type, priority, message, created_at))

    @staticmethod
    def _to_table(row: sqlite3.Row, now: str) -> TableStatus:
        data = dict(row)
        data["elapsed_minutes"] = elapsed_minutes(data["occupied_since"], now)
        return TableStatus(**data)

