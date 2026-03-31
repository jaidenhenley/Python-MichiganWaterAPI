from dotenv import load_dotenv
load_dotenv()

from typing import Optional
from fastapi import HTTPException

import httpx
import os

from app.models import Traffic

api_key = os.getenv("TOMTOM_API_KEY")

if api_key is None: 
    raise ValueError("TOMTOM_API_KEY not found in env variables")


async def fetch_traffic_conditions(lat: float, lon: float):
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={api_key}&point={lat},{lon}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url,)

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502, detail="Traffic service is unavailable right now"
        )
    
    response.raise_for_status()

    data = response.json()
    return data

def parse_traffic(data: Optional[dict]) -> list:
    if not data:
        return []

    segment = data.get("flowSegmentData", {})

    if not segment:
        return []

    return [Traffic(
        currentSpeed=segment["currentSpeed"],
        freeFlowSpeed=segment["freeFlowSpeed"],
        currentTravelTime=segment["currentTravelTime"],
        freeFlowTravelTime=segment["freeFlowTravelTime"],
        confidence=segment["confidence"],
        roadClosures=segment.get("roadClosure", False),
    )]