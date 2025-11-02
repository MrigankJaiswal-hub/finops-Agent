# Unit test folder
# backend/tests/test_app.py
from fastapi.testclient import TestClient
import os, sys
from app import app

client = TestClient(app)

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

def test_mockclients():
    resp = client.get("/mockclients")
    assert resp.status_code == 200
    data = resp.json()
    assert "clients" in data

def test_analyze_local():
    # Ensure local data file exists
    from pathlib import Path
    data_path = Path(__file__).parents[1] / "data" / "billing_data.csv"
    assert data_path.exists(), "billing_data.csv missing for tests"
    resp = client.get("/analyze")
    assert resp.status_code == 200
    body = resp.json()
    assert "client_insights" in body
    assert isinstance(body["client_insights"], list)
