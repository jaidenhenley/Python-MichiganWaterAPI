from typing import List
import httpx

from app.models import WeatherAlert

BEACH_KEYWORDS = [
    "swim",
    "swimming",
    "marine",
    "rip current",
    "rip currents",
    "thunderstorm",
    "beach",
    "surf",
    "small craft",
    "hazardous seas",
]


def _is_beach_relevant(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in BEACH_KEYWORDS)


async def fetch_nws_alerts(lat: float, lon: float):
    url = f"https://api.weather.gov/alerts/active?point={lat},{lon}"
    headers = {
        "User-Agent": "MichiganWaterAPI/1.0",
        "Accept": "application/geo+json",
    }

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        response = await client.get(url)

    if response.status_code == 400:
        raise HTTPException(
            status_code=400,
            detail="Invalid latitude or longitude passed to NWS"
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail="NWS service is unavailable right now"
        )

    response.raise_for_status()

    data = response.json()
    return data