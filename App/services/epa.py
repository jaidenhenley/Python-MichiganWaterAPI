"""
EPA Water Quality Exchange (WQX) service for E. coli beach data.

Fetches E. coli sample results from the Water Quality Portal (WQP) REST API.
API docs: https://www.waterqualitydata.us/webservices_documentation/
Michigan FIPS code: US:26
"""

import asyncio
import csv
import io
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import Optional
from datetime import date, timedelta
import logging


# Michigan's E. coli standards (per 100mL) — from EGLE Rule 62
TOTAL_BODY_CONTACT_DAILY_MAX = 300   # May 1 – Oct 31
TOTAL_BODY_CONTACT_30DAY_MEAN = 130  # May 1 – Oct 31
PARTIAL_BODY_CONTACT_MAX = 1000      # Year-round

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EcoliSample:
    site_id: str
    site_name: str
    org_name: str
    sample_date: str                         # "YYYY-MM-DD"
    value: Optional[float] = None            # colony count per 100mL
    unit: str = "cfu/100mL"
    detection_condition: Optional[str] = None  # e.g. "Not Detected"
    exceeds_daily_max: Optional[bool] = None
    exceeds_30day_mean: Optional[bool] = None


@dataclass
class EcoliReport:
    state: str
    query_date_range: str
    total_results: int
    samples: list[EcoliSample] = field(default_factory=list)
    
    def get_recent_samples(self, days: int = 30) -> list[EcoliSample]:
        """Get samples from the last N days"""
        cutoff_date = (date.today() - timedelta(days=days)).isoformat()
        return [s for s in self.samples if s.sample_date >= cutoff_date]
    
    def get_exceedance_samples(self) -> list[EcoliSample]:
        """Get samples that exceed Michigan standards"""
        return [s for s in self.samples if s.exceeds_daily_max or s.exceeds_30day_mean]


def _build_url(
    state_fips: str = "US:26",
    characteristic: str = "Escherichia coli",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    providers: str = "STORET",
    site_type: Optional[str] = None,
) -> str:
    """
    Build the WQP REST query URL.

    Dates use MM-DD-YYYY format per WQP docs.
    Default provider is STORET (EPA/state data) — most beach monitoring
    comes through here rather than NWIS.
    """
    params = {
        "statecode": state_fips,
        "characteristicName": characteristic,
        "mimeType": "csv",
        "zip": "no",
        "providers": providers,
        "sorted": "no",  # faster when we don't need server-side sort
    }
    
    # Add lake filtering if specified
    if site_type:
        params["siteType"] = site_type
    
    if start_date:
        params["startDateLo"] = start_date
    if end_date:
        params["startDateHi"] = end_date

    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def _parse_value(raw: str) -> Optional[float]:
    """Parse a result value. Returns None for empty or non-numeric entries."""
    if not raw or raw.strip() == "":
        return None
    
    # Clean the value - remove common non-numeric characters
    cleaned = raw.strip().replace(",", "").replace("*", "").replace("<", "").replace(">", "")
    
    try:
        return float(cleaned)
    except ValueError:
        logger.debug(f"Could not parse value: '{raw}'")
        return None


def _check_advisory(value: Optional[float], sample_date_str: str) -> tuple[Optional[bool], Optional[bool]]:
    """
    Compare an E. coli count against Michigan's recreation standards.
    Returns (exceeds_daily_max, exceeds_30day_mean).
    """
    if value is None:
        return None, None

    # Determine if we're in total body contact season (May–Oct)
    try:
        d = date.fromisoformat(sample_date_str)
        in_swim_season = 5 <= d.month <= 10
    except (ValueError, TypeError):
        in_swim_season = False

    if in_swim_season:
        return (value > TOTAL_BODY_CONTACT_DAILY_MAX, value > TOTAL_BODY_CONTACT_30DAY_MEAN)
    else:
        # Partial body contact standard applies year-round
        return (value > PARTIAL_BODY_CONTACT_MAX, None)


def _parse_csv(text: str) -> list[EcoliSample]:
    """
    Parse WQP CSV response into EcoliSample objects.

    Key columns from the WQP Result profile:
      - OrganizationFormalName
      - MonitoringLocationIdentifier
      - ActivityStartDate          (YYYY-MM-DD)
      - CharacteristicName         (should be "Escherichia coli")
      - ResultMeasureValue         (the count)
      - ResultMeasure/MeasureUnitCode  (cfu/100mL, MPN/100mL, etc.)
      - ResultDetectionConditionText   ("Not Detected", etc.)
      - MonitoringLocationName     (human-readable site name — may be empty)
    """
    if not text or not text.strip():
        logger.warning("Empty response from WQP API")
        return []
    
    try:
        reader = csv.DictReader(io.StringIO(text))
        samples = []

        for row in reader:
            char_name = row.get("CharacteristicName", "")
            if "coli" not in char_name.lower():
                continue  # skip non-ecoli rows that snuck in

            site_id = row.get("MonitoringLocationIdentifier", "unknown")
            site_name = row.get("MonitoringLocationName", "") or site_id
            org_name = row.get("OrganizationFormalName", "")
            sample_date = row.get("ActivityStartDate", "")
            raw_value = row.get("ResultMeasureValue", "")
            unit = row.get("ResultMeasure/MeasureUnitCode", "cfu/100mL") or "cfu/100mL"
            detection = row.get("ResultDetectionConditionText", "") or None

            # Skip rows with missing critical data
            if not sample_date or not site_id:
                continue

            value = _parse_value(raw_value)
            exceeds_daily, exceeds_mean = _check_advisory(value, sample_date)

            samples.append(EcoliSample(
                site_id=site_id,
                site_name=site_name,
                org_name=org_name,
                sample_date=sample_date,
                value=value,
                unit=unit,
                detection_condition=detection,
                exceeds_daily_max=exceeds_daily,
                exceeds_30day_mean=exceeds_mean,
            ))

        logger.info(f"Parsed {len(samples)} E. coli samples from CSV response")
        return samples
    
    except Exception as e:
        logger.error(f"Error parsing CSV response: {e}")
        return []


async def fetch_ecoli(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    state_fips: str = "US:26",
    site_type: Optional[str] = None,
    timeout: int = 60,
) -> EcoliReport:
    """
    Fetch E. coli sample results for Michigan (or another state).

    Dates should be MM-DD-YYYY format per WQP convention.
    If no dates given, defaults to last 90 days.

    Args:
        start_date: Start date in MM-DD-YYYY format
        end_date: End date in MM-DD-YYYY format  
        state_fips: State FIPS code (default: US:26 for Michigan)
        site_type: Filter by site type (e.g., "Lake", "Stream")
        timeout: Request timeout in seconds

    Example:
        report = await fetch_ecoli(start_date="06-01-2025", end_date="09-01-2025")
        for s in report.samples:
            print(f"{s.site_name}: {s.value} {s.unit} on {s.sample_date}")
    """
    # Default to last 90 days if no range given
    if not start_date:
        start_date_obj = date.today() - timedelta(days=90)
        start_date = start_date_obj.strftime("%m-%d-%Y")
    if not end_date:
        end_date = date.today().strftime("%m-%d-%Y")

    url = _build_url(
        state_fips=state_fips,
        start_date=start_date,
        end_date=end_date,
        site_type=site_type,
    )

    logger.info(f"Fetching E. coli data from WQP: {url}")

    def _fetch():
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "epa-wqx-client/1.0",
                "Accept": "text/csv",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.getcode() != 200:
                    raise urllib.error.HTTPError(url, resp.getcode(), 
                                               f"HTTP {resp.getcode()}", None, None)
                return resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            logger.error(f"Network error fetching WQP data: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching WQP data: {e}")
            raise

    try:
        text = await asyncio.get_event_loop().run_in_executor(None, _fetch)
        samples = _parse_csv(text)

        # Sort by date descending so most recent samples come first
        samples.sort(key=lambda s: s.sample_date, reverse=True)

        date_range = f"{start_date} to {end_date}"
        state_name = "Michigan" if state_fips == "US:26" else state_fips

        logger.info(f"Successfully fetched {len(samples)} E. coli samples for {state_name}")

        return EcoliReport(
            state=state_name,
            query_date_range=date_range,
            total_results=len(samples),
            samples=samples,
        )
    
    except Exception as e:
        logger.error(f"Failed to fetch E. coli data: {e}")
        # Return empty report instead of crashing
        return EcoliReport(
            state="Michigan" if state_fips == "US:26" else state_fips,
            query_date_range=f"{start_date} to {end_date}",
            total_results=0,
            samples=[],
        )


async def get_latest_readings(days_back: int = 7, site_type: Optional[str] = "Lake") -> EcoliReport:
    """
    Get the most recent E. coli readings from the last N days.
    
    Args:
        days_back: Number of days to look back
        site_type: Filter by site type (e.g., "Lake" for lakes only)
    """
    end_date = date.today().strftime("%m-%d-%Y")
    start_date = (date.today() - timedelta(days=days_back)).strftime("%m-%d-%Y")
    
    return await fetch_ecoli(
        start_date=start_date, 
        end_date=end_date,
        site_type=site_type
    )


# Test/example usage
async def main():
    """Example usage of the E. coli data fetcher"""
    logger.info("Testing EPA WQX E. coli data fetcher...")
    
    try:
        # Get latest lake data from Michigan
        report = await get_latest_readings(days_back=30, site_type="Lake")
        
        print(f"\n=== {report.state} E. coli Report ===")
        print(f"Date range: {report.query_date_range}")
        print(f"Total samples: {report.total_results}")
        
        if report.samples:
            print(f"\nMost recent 5 samples:")
            for sample in report.samples[:5]:
                status = ""
                if sample.exceeds_daily_max:
                    status = " ⚠️  EXCEEDS STANDARD"
                elif sample.value and sample.value > 100:
                    status = " ⚡ Elevated"
                
                print(f"  {sample.site_name}: {sample.value or 'N/A'} {sample.unit} "
                      f"({sample.sample_date}){status}")
            
            # Show exceedances
            exceedances = report.get_exceedance_samples()
            if exceedances:
                print(f"\n⚠️  {len(exceedances)} sites exceed Michigan standards")
        else:
            print("No recent samples found")
            
    except Exception as e:
        logger.error(f"Error in main: {e}")


if __name__ == "__main__":
    asyncio.run(main())