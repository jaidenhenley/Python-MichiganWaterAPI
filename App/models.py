from pydantic import BaseModel
from datetime import time
from enum import Enum

class Status(str, Enum):
    SAFE = 'Safe'
    ADVISORY = 'Advisory'
    CLOSED = 'Closed'

class HazardLevel(str, Enum):
    LOW = 'Low'
    MODERATE = 'Moderate'
    HIGH = 'High'
    EXTREME = 'Extreme'

class Beach(BaseModel):
    id: int
    name: str
    county: str
    status: str
    ecoli_value: int
    latitude: float
    longitude: float
    lake: str
    ecoli_value: float
    hazard_score: int
    status: Status


class WaterConditions(BaseModel):
    beach_id: int
    water_temp_f: int
    wave_height_ft: float
    wave_period_sec: int
    wind_speed_mph: int
    wind_direction: str
    source: str
    timestamp: time

class WeatherAlert(BaseModel):
    headline: str
    severity: str
    description: str
    expires: time

class HazardReport(BaseModel):
    beach_id: int
    beach_name: str
    hazard_score: int
    hazard_level: HazardLevel
    water_conditions: str
    weather_alerts: str
    ecoli_value: int
    summary: str
