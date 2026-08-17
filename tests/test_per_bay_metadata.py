from datetime import date, time

import pytest

from thermovisi.inspection import build_inspection_row


def metadata(current=159.0, peak=200.0, ambient=31.5):
    return {
        "measurement_date": date(2026, 8, 14),
        "measurement_time": time(16, 33),
        "measurement_current_a": current,
        "monthly_peak_current_a": peak,
        "ambient_temperature_c": ambient,
    }


def test_inspection_payload_uses_selected_bay_metadata():
    row = build_inspection_row(
        inspection_id="inspection-1",
        upload_id="upload-1",
        target_functloc_id="TRS-3213-056.056-B0001",
        source_sheet_name="PORSA-PSTAR1",
        template_code="PHT_150_STANDARD_V1",
        metadata=metadata(),
        executor="Tim Thermovisi",
        notes=None,
        user_id="user-1",
    )
    assert row["measurement_date"] == "2026-08-14"
    assert row["measurement_time"] == "16:33:00"
    assert row["measurement_current_a"] == 159.0
    assert row["monthly_peak_current_a"] == 200.0
    assert row["ambient_temperature_c"] == 31.5


def test_peak_current_cannot_be_lower_than_measurement_current():
    with pytest.raises(ValueError, match="tidak boleh lebih kecil"):
        build_inspection_row(
            inspection_id="inspection-1",
            upload_id="upload-1",
            target_functloc_id="BAY-1",
            source_sheet_name="SHEET-1",
            template_code="PHT_150_STANDARD_V1",
            metadata=metadata(current=200.0, peak=150.0),
            executor=None,
            notes=None,
            user_id="user-1",
        )


def test_zero_measurement_current_is_allowed_for_non_operating_transformer():
    row = build_inspection_row(
        inspection_id="inspection-1",
        upload_id="upload-1",
        target_functloc_id="BAY-1",
        source_sheet_name="SHEET-1",
        template_code="TRAFO_150_20_STANDARD_V1",
        metadata=metadata(current=0.0, peak=200.0),
        executor=None,
        notes=None,
        user_id="user-1",
    )
    assert row["measurement_current_a"] == 0.0
