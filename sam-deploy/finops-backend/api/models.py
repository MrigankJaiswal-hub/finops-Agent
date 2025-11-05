# models.py — declarative Base + table classes
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Text
from datetime import datetime

Base = declarative_base()

class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    targets: Mapped[str] = mapped_column(Text, nullable=True)
    est_impact: Mapped[float] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=True, default="finops-agent")


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(String(1024), nullable=True)
