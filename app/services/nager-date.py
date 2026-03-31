from typing import Optional
from fastapi import HTTPException

import httpx

from app.models import Holiday

async def fetch_holidays(year: int, countryCode: str):
    url = f"https://date.nager.at/api/v3/publicholidays/{year}/{countryCode}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url,)


    if response.status_code >= 500:
        raise HTTPException(
            status_code=502, detail="Traffic service is unavailable right now"
        )
    
    response.raise_for_status()

    data = response.json()
    return data

def parse_holiday(data: Optional[dict]) -> list:
    if not data: 
        return []
    
    segment = data.get("publicholidays", {})

    if not segment:
        return []
    
    return [Holiday(
        date=segment["date"],
        localName=segment["localName"],
        name=segment["name"],
    )]