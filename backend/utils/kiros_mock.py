# Optional SuperOps mock data
# backend/utils/kiros_mock.py
def get_mock_kiros_clients():
    """
    Simple mock of SuperOps / Kiros client data structure.
    Replace with real API integration when SuperOps API access is available.
    """
    return {
        "clients": [
            {"name": "AlphaTech", "tickets_open": 5, "contracts": 3, "region": "US"},
            {"name": "BetaCorp", "tickets_open": 1, "contracts": 1, "region": "EU"},
            {"name": "DeltaSoft", "tickets_open": 12, "contracts": 2, "region": "APAC"},
        ]
    }
