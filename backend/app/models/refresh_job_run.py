"""Refresh job run audit log for the real data pipeline."""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from app.db.base import Base


class RefreshJobRun(Base):
    __tablename__ = "refresh_job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(64), nullable=False, default="real_pipeline_sample")
    status = Column(String(32), nullable=False, default="running")
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    requested_limit = Column(Integer, nullable=True)
    sample_size = Column(Integer, nullable=True)
    financial_attempted = Column(Integer, default=0)
    financial_success = Column(Integer, default=0)
    financial_failed = Column(Integer, default=0)
    technical_attempted = Column(Integer, default=0)
    technical_success = Column(Integer, default=0)
    technical_failed = Column(Integer, default=0)
    scores_attempted = Column(Integer, default=0)
    scores_success = Column(Integer, default=0)
    scores_failed = Column(Integer, default=0)
    signals_attempted = Column(Integer, default=0)
    signals_success = Column(Integer, default=0)
    signals_failed = Column(Integer, default=0)
    failure_summary_json = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    trigger_source = Column(String(32), nullable=False, default="command")
