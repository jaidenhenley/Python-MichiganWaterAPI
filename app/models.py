from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional
from typing import List


class Status(str, Enum):
    SAFE = "Safe"
    ADVISORY = "Advisory"
    CLOSED = "Closed"


class HazardLevel(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    EXTREME = "Extreme"


class Beach(BaseModel):
    id: int
    name: str
    county: str
    status: Status
    latitude: float
    longitude: float
    lake: str
    buoy_station: str
    nws_station_id: Optional[str] = None

class WaterConditions(BaseModel):
    source: str = "NDBC"
    station_id: Optional[str] = None
    water_temp_c: Optional[float] = None
    wave_height_m: Optional[float] = None
    wave_period_sec: Optional[float] = None
    wind_speed_mph: Optional[float] = None
    wind_direction: Optional[str] = None
    timestamp: Optional[datetime] = None


class WeatherAlert(BaseModel):
    headline: str
    severity: Optional[str] = None
    description: Optional[str] = None
    expires: Optional[datetime] = None

class WeatherConditions(BaseModel):
    station_id: str
    text_description: str
    temperature_c: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed_km: Optional[float] = None
    wind_chill_c: Optional[float] = None

class Forecast(BaseModel):
    number: int
    name: str
    startTime: datetime
    endTime: datetime
    isDaytime: bool
    temp: int
    tempUnit: str
    probOfPrecip: float
    windSpeed: str
    windDirection: str
    icon: str
    shortForecast: str
    detailForecast: str

class Traffic(BaseModel):
    currentSpeed: int
    freeFlowSpeed: int
    currentTravelTime: int
    freeFlowTravelTime: int
    confidence: float
    roadClosures: bool
    

class BeachModelResponse(BaseModel):
    weather: Optional[WeatherConditions] = None
    forecast: List[Forecast] = []
    buoy_data: Optional[WaterConditions] = None
    alerts: List[WeatherAlert] = []
    traffic: List[Traffic] = []
