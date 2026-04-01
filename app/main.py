import asyncio
from fastapi import FastAPI, HTTPException, Query
from typing import Optional

from app.data import sample_beaches
from app.models import Beach
from app.models import Holiday
from app.models import BeachModelResponse
from app.models import NPSVisitation


from dotenv import load_dotenv
load_dotenv()

from app.services.ndbc import fetch_ndbc_conditions
from app.services.nws import fetch_nws_alerts
from app.services.nws import fetch_weather_conditions
from app.services.nws import fetch_nws_forecast
from app.services.nws import parse_alerts, parse_forecast, parse_weather_conditions


from app.services.tomtom import fetch_traffic_conditions, parse_traffic

from app.services.nagerdate import fetch_holidays, parse_holiday
from app.services.nps import fetch_nps_visitation, parse_nps_visitation, MICHIGAN_BEACH_PARKS



app = FastAPI()

@app.get("/nps/visitation/{park_code}", response_model=list[NPSVisitation])
async def get_nps_visitation(park_code: str, year: int = 2024):
    data = await fetch_nps_visitation(park_code=park_code.upper(), year=year)
    return parse_nps_visitation(data, park_code=park_code.upper())

@app.get("/nps/visitation", response_model=list[NPSVisitation])
async def get_all_nps_visitation(year: int = 2024):
    results = await asyncio.gather(
        *[fetch_nps_visitation(park_code=code, year=year) for code in MICHIGAN_BEACH_PARKS],
        return_exceptions=True,
    )
    all_entries = []
    for code, data in zip(MICHIGAN_BEACH_PARKS, results):
        if not isinstance(data, Exception):
            all_entries.extend(parse_nps_visitation(data, park_code=code))
    return all_entries

@app.get("/holiday/{countryCode}/{year}", response_model=list[Holiday])
async def get_holidays(countryCode: str, year: int) -> list:
    data = await fetch_holidays(countryCode=countryCode, year=year)
    return parse_holiday(data)

@app.get("/beaches/{beach_id}/details", response_model=BeachModelResponse)
async def get_beach(beach_id: int) -> BeachModelResponse:
    beach = next((b for b in sample_beaches if b["id"] == beach_id), None)
    if not beach: 
        raise HTTPException(status_code=404, detail="Beach not found")

    weather_result, buoy_result, alerts_result, forecast_result, traffic_result, holiday_result = await asyncio.gather(
        fetch_weather_conditions(beach["nws_station_id"]),
        fetch_ndbc_conditions(beach["buoy_station"]),
        fetch_nws_alerts(beach["latitude"], beach["longitude"]),
        fetch_nws_forecast(lat=beach["latitude"], lon=beach["longitude"]),
        fetch_traffic_conditions(lat=beach["latitude"], lon=beach["longitude"]),
        fetch_holidays(countryCode=beach["countryCode"], year=beach["year"]),
        return_exceptions=True,
    )

    # Type-check each result — exceptions become None
    weather = weather_result if not isinstance(weather_result, Exception) else None
    buoy = buoy_result if not isinstance(buoy_result, Exception) else None
    alerts = alerts_result if not isinstance(alerts_result, Exception) else None
    forecast = forecast_result if not isinstance(forecast_result, Exception) else None
    traffic = traffic_result if not isinstance(traffic_result, Exception) else None
    holiday = holiday_result if not isinstance(holiday_result, Exception) else None

    return BeachModelResponse(
        weather=parse_weather_conditions(weather) if weather else None,
        forecast=parse_forecast(forecast) if forecast else [],
        buoy_data=buoy if not isinstance(buoy, Exception) else None,
        alerts=parse_alerts(alerts) if alerts else [],
        traffic=parse_traffic(traffic) if traffic else [],
        holiday=parse_holiday(holiday) if holiday else []
    )
