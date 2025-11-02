# models.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, func

Base = declarative_base()

class ActionLog(Base):
    __tablename__ = "action_logs"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    time       = Column(DateTime(timezone=True), server_default=func.now())
    user       = Column(String(255))
    title      = Column(String(1024))
    targets    = Column(String(1024))
    est_impact = Column(Float)
    source     = Column(String(128))

class HistoryEvent(Base):
    __tablename__ = "history_events"
    id      = Column(Integer, primary_key=True, autoincrement=True)
    time    = Column(DateTime(timezone=True), server_default=func.now())
    user    = Column(String(255))
    kind    = Column(String(64))
    message = Column(String(2048))
    key     = Column(String(1024), nullable=True)