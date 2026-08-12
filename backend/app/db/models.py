"""Core ORM models: runs, events, escalation decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float, JSON, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="running")
    # Internal engine name stored in DB; translated to external label at API boundary.
    engine: Mapped[str] = mapped_column(String, default="langgraph")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class Event(Base):
    """Persistent structured event log — replaces the in-memory _EVENTS list.

    Every node_start, checkpoint_saved, sandbox_dispatch, sandbox_violation,
    escalation_decision, retry_attempt, and memory_grounding event is persisted
    here so a run's timeline is replayable after a process restart.
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("ix_events_run_id_timestamp", "run_id", "timestamp"),
    )


class EscalationDecision(Base):
    __tablename__ = "escalation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    step_index: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[float] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
