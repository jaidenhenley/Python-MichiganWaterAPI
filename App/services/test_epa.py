"""Offline tests for EPA WQX E. coli service — no network needed."""

import asyncio
from unittest.mock import patch, MagicMock
from app.services.epa import (
    fetch_ecoli, _parse_csv, _parse_value, _check_advisory, EcoliSample
)

# Simplified WQP CSV — only the columns the parser actually reads
SAMPLE_CSV = """\
OrganizationFormalName,MonitoringLocationIdentifier,MonitoringLocationName,ActivityStartDate,CharacteristicName,ResultMeasureValue,ResultMeasure/MeasureUnitCode,ResultDetectionConditionText
Michigan Department of Environment Great Lakes and Energy,21MICH-BELLE_ISLE_BEACH,Belle Isle Beach,2025-07-15,Escherichia coli,245,cfu/100mL,
Michigan Department of Environment Great Lakes and Energy,21MICH-METRO_BEACH,Metro Beach,2025-07-15,Escherichia coli,450,cfu/100mL,
Michigan Department of Environment Great Lakes and Energy,21MICH-SOUTH_BEACH,South Beach Traverse City,2025-07-16,Escherichia coli,,cfu/100mL,Not Detected
Michigan Department of Environment Great Lakes and Energy,21MICH-PIER_PARK,Pier Park Beach,2025-12-01,Escherichia coli,1200,cfu/100mL,
"""


def _mock_urlopen(text):
    mock_resp = MagicMock()
    mock_resp.read.return_value = text.encode("utf-8")
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def test_parse_value():
    assert _parse_value("245") == 245.0
    assert _parse_value("0") == 0.0
    assert _parse_value("") is None
    assert _parse_value("   ") is None
    assert _parse_value("not a number") is None
    print("  _parse_value: passed")


def test_check_advisory():
    # Summer (swim season) — daily max = 300, 30-day mean = 130
    exceed_d, exceed_m = _check_advisory(450, "2025-07-15")
    assert exceed_d is True
    assert exceed_m is True

    safe_d, safe_m = _check_advisory(50, "2025-07-15")
    assert safe_d is False
    assert safe_m is False

    # Between thresholds: 200 > 130 mean but < 300 daily
    mid_d, mid_m = _check_advisory(200, "2025-08-01")
    assert mid_d is False
    assert mid_m is True

    # Winter — partial body contact max = 1000
    winter_d, winter_m = _check_advisory(1200, "2025-12-01")
    assert winter_d is True
    assert winter_m is None  # 30-day mean doesn't apply outside swim season

    # None value
    none_d, none_m = _check_advisory(None, "2025-07-15")
    assert none_d is None
    assert none_m is None

    print("  _check_advisory: passed")


def test_parse_csv():
    samples = _parse_csv(SAMPLE_CSV)
    assert len(samples) == 4

    # First sample: Belle Isle, 245 cfu — swim season, under daily max
    belle = samples[0]
    assert belle.site_name == "Belle Isle Beach"
    assert belle.value == 245
    assert belle.sample_date == "2025-07-15"
    assert belle.exceeds_daily_max is False
    assert belle.exceeds_30day_mean is True  # 245 > 130

    # Second: Metro Beach, 450 — exceeds both
    metro = samples[1]
    assert metro.value == 450
    assert metro.exceeds_daily_max is True

    # Third: Not Detected — value should be None
    south = samples[2]
    assert south.value is None
    assert south.detection_condition == "Not Detected"
    assert south.exceeds_daily_max is None

    # Fourth: Winter sample, 1200 — exceeds partial body contact
    pier = samples[3]
    assert pier.value == 1200
    assert pier.exceeds_daily_max is True
    assert pier.exceeds_30day_mean is None

    print("  _parse_csv: passed")


async def test_fetch_ecoli():
    with patch("app.services.epa_wqx.urllib.request.urlopen", return_value=_mock_urlopen(SAMPLE_CSV)):
        report = await fetch_ecoli(start_date="07-01-2025", end_date="12-31-2025")

    assert report.state == "Michigan"
    assert report.total_results == 4
    # Should be sorted date descending
    assert report.samples[0].sample_date == "2025-12-01"
    assert report.samples[-1].sample_date == "2025-07-15"
    print("  fetch_ecoli: passed")


async def test_empty_response():
    empty_csv = "OrganizationIdentifier,OrganizationFormalName,CharacteristicName,ResultMeasureValue\n"
    with patch("app.services.epa_wqx.urllib.request.urlopen", return_value=_mock_urlopen(empty_csv)):
        report = await fetch_ecoli(start_date="01-01-2025", end_date="01-02-2025")

    assert report.total_results == 0
    assert report.samples == []
    print("  empty response: passed")


async def main():
    print("Running EPA WQX parser tests...\n")
    test_parse_value()
    test_check_advisory()
    test_parse_csv()
    await test_fetch_ecoli()
    await test_empty_response()
    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(main())