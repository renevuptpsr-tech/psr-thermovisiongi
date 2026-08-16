from thermovisi.anomaly import build_telegram_anomaly_message, prepare_anomaly_rows


def test_only_abnormal_evaluations_become_anomalies():
    rows = prepare_anomaly_rows(
        inspection_id="inspection-1",
        evaluation_rows=[
            {"evaluation_id": "normal", "severity": 0, "condition_label": "Normal", "recommendation": "Rutin"},
            {"evaluation_id": "hot", "severity": 2, "condition_label": "Kondisi II", "recommendation": "Jadwalkan perbaikan", "ahi_score": 3},
        ],
    )
    assert len(rows) == 1
    assert rows[0]["evaluation_id"] == "hot"
    assert rows[0]["notification_status"] == "PENDING"


def test_telegram_summary_contains_location_and_recommendation():
    message = build_telegram_anomaly_message(
        ultg_name="ULTG TOBA",
        gi_name="GI PORSEA",
        bay_name="PHT PSTAR",
        bay_functloc_id="BAY-1",
        measurement_date="2026-08-16",
        work_type="ROUTINE",
        stage_code="TAHAP_1",
        anomalies=[
            {
                "severity": 2,
                "equipment_group_code": "PMT",
                "point_code": "PMT_INSULATOR",
                "condition_label": "Kondisi II",
                "analyzed_delta_c": 12.5,
                "ahi_score": 3,
                "ahi_category": "Fair",
                "recommendation": "Jadwalkan perbaikan",
            }
        ],
    )
    assert "GI PORSEA" in message
    assert "12.5 °C" in message
    assert "Jadwalkan perbaikan" in message
