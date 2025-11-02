# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.sql import func
from db import Base

class ActionLog(Base):
    __tablename__ = "action_logs"
    id = Column(Integer, primary_key=True, index=True)
    time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    targets = Column(String(255), nullable=False)
    est_impact = Column(Float, nullable=True)
    source = Column(String(64), nullable=False, default="finops-agent")

class HistoryEvent(Base):
    __tablename__ = "history_events"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = Column(String(255), nullable=False)
    kind = Column(String(64), nullable=False)     # e.g., 'insights_generated', 'snapshot_loaded'
    message = Column(Text, nullable=False)        # free text shown in UI
    key = Column(String(512), nullable=True)      # history key / s3 key / upload id
