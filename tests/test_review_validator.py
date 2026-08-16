from thermovisi.review_validator import validate_bay_review, validation_summary_row


def row(data="VALID", analysis="TEREVALUASI", ahi=1, severity=0):
    return {
        "Status data": data,
        "Status analisa": analysis,
        "AHI Thermovisi": ahi,
        "Tingkat perhatian": severity,
        "Kondisi": "Normal" if severity == 0 else "Kondisi II",
        "Titik peralatan yang diperiksa": "Titik",
    }


def test_valid_and_not_measured_rows_are_ready():
    result = validate_bay_review([row(), row(data="NOT_MEASURED", analysis="DATA TIDAK LENGKAP", ahi=None)])
    assert result.ready
    assert result.not_measured_rows == 1


def test_invalid_data_blocks_save():
    result = validate_bay_review([row(data="INVALID", analysis="BELUM DIEVALUASI", ahi=None)])
    assert not result.ready
    assert result.status_label == "DIBLOKIR"


def test_incomplete_requires_explicit_acceptance():
    rows = [row(analysis="DATA TIDAK LENGKAP", ahi=None)]
    assert not validate_bay_review(rows).ready
    assert validate_bay_review(rows, accept_incomplete=True).ready


def test_unknown_analysis_status_blocks_save():
    result = validate_bay_review([row(analysis="RULE_NOT_CONFIGURED", ahi=None)])
    assert not result.ready
    assert result.blocking_rows == 1
    assert result.blocking_messages


def test_summary_exposes_worst_ahi():
    result = validate_bay_review([row(), row(ahi=4, severity=3)])
    summary = validation_summary_row("Bay A", result)
    assert summary["AHI terburuk"] == "4 — Poor"
    assert summary["Kesiapan"] == "SIAP DISIMPAN"
