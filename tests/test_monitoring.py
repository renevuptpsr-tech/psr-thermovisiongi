from thermovisi.monitoring import build_upload_monitoring_rows


def test_monitoring_marks_uploaded_and_missing_bays():
    rows = build_upload_monitoring_rows(
        [
            {"ultg_name": "ULTG", "gi_name": "GI", "bay_flc": "BAY-1", "bay_name": "Bay 1", "bay_function_code": "2"},
            {"ultg_name": "ULTG", "gi_name": "GI", "bay_flc": "BAY-2", "bay_name": "Bay 2", "bay_function_code": "2"},
        ],
        [
            {"inspection_id": "I-1", "target_functloc_id": "BAY-1", "measurement_date": "2026-08-16", "measurement_time": "18:00:00"},
        ],
    )
    assert rows[0]["Status upload"] == "SUDAH UPLOAD"
    assert rows[1]["Status upload"] == "BELUM UPLOAD"


def test_monitoring_uses_latest_inspection_for_same_bay():
    rows = build_upload_monitoring_rows(
        [{"ultg_name": "ULTG", "gi_name": "GI", "bay_flc": "BAY-1", "bay_name": "Bay 1"}],
        [
            {"inspection_id": "OLD", "target_functloc_id": "BAY-1", "measurement_date": "2026-08-01", "measurement_time": "18:00:00"},
            {"inspection_id": "NEW", "target_functloc_id": "BAY-1", "measurement_date": "2026-08-15", "measurement_time": "18:00:00"},
        ],
    )
    assert rows[0]["Inspection ID"] == "NEW"
