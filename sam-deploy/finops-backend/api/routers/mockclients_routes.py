# api/routers/mockclients_routes.py
from fastapi import APIRouter, Query
from typing import List, Dict

router = APIRouter(tags=["mock"])

# Tiny mock source your front-end expects for the side widget
MOCK: List[Dict] = [
    {"client": "WaveOps",     "revenue": 4100, "cost": 4090, "margin": 10,  "license_waste_pct": 0.0, "health": "Healthy"},
    {"client": "ApexComms",   "revenue": 3000, "cost": 2950, "margin": 50,  "license_waste_pct": 0.0, "health": "Healthy"},
    {"client": "NimbusCloud", "revenue": 6000, "cost": 5900, "margin": 100, "license_waste_pct": 0.0, "health": "Healthy"},
    {"client": "GammaServe",  "revenue": 4800, "cost": 4700, "margin": 100, "license_waste_pct": 0.0, "health": "Healthy"},
    {"client": "OrionIT",     "revenue": 5500, "cost": 5200, "margin": 300, "license_waste_pct": 0.0, "health": "Healthy"},
]

@router.get("/mockclients")
def mockclients(_ts: int | None = Query(default=None)):
    # _ts only to match your UI’s call signature; ignored here
    return MOCK
