from typing import List
import httpx
from fastapi import HTTPException

from app.models import WeatherAlert
from app.models import WeatherConditions
from app.models import WeatherAlert
from app.models import Forecast



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


async def fetch_weather_conditions(station_id: str):
    url = f"https://api.weather.gov/stations/{station_id}/observations"
    headers = {
        "User-Agent": "MichiganWater/API/1.0",
        "Accept": "application/geo+json",
    }

    params = {"limit": 1}

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        response = await client.get(url, params=params)

    if response.status_code == 400:
        raise HTTPException(status_code=400, detail="Invalid Station ID passed to NWS")

    if response.status_code == 404:
        raise HTTPException(
            status_code=404, detail=f"Station '{station_id}' not found in NWS"
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502, detail="NWS service is unavailable right now"
        )

    response.raise_for_status()

    data = response.json()
    return data

def parse_weather_conditions(data: dict) -> WeatherConditions:
    props = data["features"][0]["properties"]
    return WeatherConditions(
        station_id=props.get("station", "").split("/")[-1],
        text_description=props.get("textDescription", ""),
        temperature_c=props["temperature"]["value"],
        humidity=props["relativeHumidity"]["value"],
        wind_speed_km=props["windSpeed"]["value"],
        wind_chill_c=props["windChill"]["value"],
    )


async def fetch_nws_forecast(lat: float, lon: float):
    headers = {
        "User-Agent": "MichiganWaterAPI/1.0",
        "Accept": "application/geo+json",
    }

    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        points_response = await client.get(f"https://api.weather.gov/points/{round(lat, 4)},{round(lon, 4)}")

        if points_response.status_code == 400:
            raise HTTPException(
                status_code=400,
                detail="Invalid latitude or longitude passed to NWS",
            )

        if points_response.status_code >= 500:
            raise HTTPException(
                status_code=502,
                detail="NWS service is unavailable right now",
            )

        points_response.raise_for_status()

        points_data = points_response.json()
        forecast_url = points_data.get("properties", {}).get("forecast")
        if not forecast_url:
            raise HTTPException(
                status_code=502,
                detail="NWS forecast URL was missing from the points response",
            )

        response = await client.get(forecast_url)

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail="NWS service is unavailable right now",
        )

    response.raise_for_status()

    return response.json()


def parse_forecast(data: dict) -> List[Forecast]:
    periods = data["properties"]["periods"]
    return [
        Forecast(
            number=p["number"],
            name=p["name"],
            startTime=p["startTime"],
            endTime=p["endTime"],
            isDaytime=p["isDaytime"],
            temp=p["temperature"],
            tempUnit=p["temperatureUnit"],
            probOfPrecip=p["probabilityOfPrecipitation"]["value"] or 0.0,
            windSpeed=p["windSpeed"],
            windDirection=p["windDirection"],
            icon=p["icon"],
            shortForecast=p["shortForecast"],
            detailForecast=p["detailedForecast"],
        )
        for p in periods
    ]

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
            status_code=400, detail="Invalid latitude or longitude passed to NWS"
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502, detail="NWS service is unavailable right now"
        )

    response.raise_for_status()

    data = response.json()
    return data

def parse_alerts(data: dict) -> List[WeatherAlert]:
    return [
        WeatherAlert(
            headline=f["properties"]["headline"],
            severity=f["properties"].get("severity"),
            description=f["properties"].get("description"),
            expires=f["properties"].get("expires"),
        )
        for f in data.get("features", [])
    ]
