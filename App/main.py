from fastapi import FastAPI, HTTPException, Query
from typing import Optional
from app.data import sample_beaches
from app.models import Beach

from app.services.ndbc import fetch_ndbc_conditions
from app.services.nws import fetch_nws_alerts
from app.services.epa import fetch_ecoli

app = FastAPI()

# @app.get("/conditions/{station_id}")
# async def get_conditions(station_id: str):
#     data = await fetch_conditions(station_id)
#     return data

@app.get("/ecoli")
async def get_ecoli(start: str, end: str):
    report = await fetch_ecoli(start_date=start, end_date=end)
    return report

@app.get("/alerts")
async def get_alerts(lat: float, lon: float):
    return await fetch_nws_alerts(lat, lon)

@app.get("/ndbc/{station_id}")
async def get_ndbc_conditions(station_id: str):
    return await fetch_ndbc_conditions(station_id)

@app.get("/")
def root():
    return {"message": "Michigan Water API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/beaches", response_model=list[Beach])
def get_beaches(
    county: Optional[str] = Query(None, description="Filter by county name"),
    lake: Optional[str] = Query(None, description="Filter by lake name"),
    status: Optional[str] = Query(None, description="Filter by status: safe, advisory, closed")
): 
    results = sample_beaches
    if county:
        results = [b for b in results if b["county"].lower() == county.lower()]
    if lake:
        results = [b for b in results if lake.lower() in b["lake"].lower()]
    if status:
        results = [b for b in results if b["status"].lower() == status.lower()]
    return results


@app.get("/beaches/{beach_id}", response_model=Beach)
def get_beach(beach_id: int):
    for beach in sample_beaches:
        if beach["id"] == beach_id:
            return beach
    raise HTTPException(status_code=404, detail="Beach not found")