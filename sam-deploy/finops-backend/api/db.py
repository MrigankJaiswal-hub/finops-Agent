# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Writeable in Lambda:
DB_URL = os.getenv("SQLALCHEMY_URL", "sqlite:////tmp/sqlite/finops.db")
if DB_URL.startswith("sqlite:////tmp"):
    os.makedirs("/tmp/sqlite", exist_ok=True)

engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from models import Base
    Base.metadata.create_all(bind=engine)