import httpx
from fastapi import HTTPException
from typing import Optional

from app.models import NPSVisitation

NPS_STATS_URL = "https://irmaservices.nps.gov/statistics/api/v2/visitation"

# Michigan NPS parks with beach/lakeshore access
MICHIGAN_BEACH_PARKS = ["SLBE", "PIRO", "ISRO"]


async def fetch_nps_visitation(park_code: str, year: int):
    params = {"unitCode": park_code, "year": year}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(NPS_STATS_URL, params=params)

    if response.status_code >= 500:
        raise HTTPException(status_code=502, detail="NPS statistics service is unavailable")

    response.raise_for_status()
    return response.json()


def parse_nps_visitation(data: list, park_code: str) -> list[NPSVisitation]:
    if not data:
        return []

    monthly = [
        entry for entry in data
        if entry.get("RecreationVisitors") is not None
    ]

    if not monthly:
        return []

    max_visitors = max(entry["RecreationVisitors"] for entry in monthly)

    results = []
    for entry in monthly:
        visitors = entry["RecreationVisitors"]
        results.append(NPSVisitation(
            park_code=park_code,
            park_name=entry.get("UnitName", ""),
            year=entry["Year"],
            month=entry["Month"],
            recreation_visitors=visitors,
            crowd_weight=round(visitors / max_visitors, 4) if max_visitors else 0.0,
        ))

    return sorted(results, key=lambda x: x.month)
