# db.py — SQLAlchemy engine + session factory (no models here)
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Lambda can only write to /tmp. Allow override via env.
_SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:////tmp/finops.db")

# SQLite pragmas for Lambda cold starts are fine at default isolation
engine = create_engine(
    _SQLITE_URL,
    connect_args={"check_same_thread": False} if _SQLITE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
