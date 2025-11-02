# Utility modules
# Handles profitability analysis
# backend/utils/analyze.py
from typing import List, Dict

def analyze_csv_rows(rows: List[Dict[str, str]]):
    """
    Parse CSV rows representing billing data and return per-client insights
    with margin calculation, license waste percentage, and a health tag.

    Expected CSV columns:
        client, revenue, cost, licenses_used, licenses_purchased
    """
    insights = []

    for r in rows:
        client = (r.get("client") or r.get("name") or "Unknown").strip()

        try:
            revenue = float(r.get("revenue", 0) or 0)
        except Exception:
            revenue = 0.0

        try:
            cost = float(r.get("cost", 0) or 0)
        except Exception:
            cost = 0.0

        try:
            licenses_used = float(r.get("licenses_used", 0) or 0)
            licenses_purchased = float(r.get("licenses_purchased", 0) or 0)
        except Exception:
            licenses_used = 0.0
            licenses_purchased = 0.0

        margin = round(revenue - cost, 2)

        # Calculate license waste percentage
        license_waste_pct = 0.0
        if licenses_purchased > 0:
            license_waste_pct = max(
                0.0, (licenses_purchased - licenses_used) / licenses_purchased * 100.0
            )

        # Determine client health
        health = "Healthy"
        if margin < 0:
            health = "At Risk"
        elif license_waste_pct > 30:
            health = "Inefficient"

        insights.append({
            "client": client,
            "revenue": round(revenue, 2),
            "cost": round(cost, 2),
            "margin": margin,
            "license_waste_pct": round(license_waste_pct, 1),
            "health": health
        })

    # Sort by margin ascending so low-margin/at-risk clients appear first
    insights_sorted = sorted(insights, key=lambda x: x["margin"])
    return insights_sorted
