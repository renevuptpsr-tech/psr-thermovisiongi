from datetime import date

import pytest

from thermovisi.supabase_service import _validate_incremental_import


def upload(**overrides):
    row = {
        "upload_id": "upload-1",
        "processing_status": "COMPLETED",
        "template_type": "PHT_150_STANDARD_V1",
    }
    row.update(overrides)
    return row


def inspection(**overrides):
    row = {
        "measurement_date": "2026-08-14",
        "work_type": "ROUTINE",
        "stage_code": "TAHAP_1",
    }
    row.update(overrides)
    return row


def validate(*, selected=None, inspections=None, sheets=None, **overrides):
    _validate_incremental_import(
        existing_upload=upload(**overrides),
        existing_inspections=(
            inspections if inspections is not None else [inspection()]
        ),
        existing_sheets=(
            sheets if sheets is not None else [{"source_sheet_name": "Sheet 1"}]
        ),
        template_code="PHT_150_STANDARD_V1",
        selected_sheet_names=(
            selected if selected is not None else {"Sheet 3", "Sheet 4"}
        ),
        destination_year=2026,
        destination_month=8,
        work_type="ROUTINE",
        stage_code="TAHAP_1",
    )


def test_same_workbook_can_continue_with_unused_sheets():
    validate()


def test_used_sheet_is_rejected_even_with_case_or_outer_spaces():
    with pytest.raises(ValueError, match="sudah pernah diimpor"):
        validate(selected={"  sheet 1  "})


def test_incremental_import_must_keep_template_period_and_stage():
    with pytest.raises(
        ValueError,
        match="template TRAFO, bukan PHT_150_STANDARD_V1",
    ):
        validate(template_type="TRAFO")
    with pytest.raises(ValueError, match="periode"):
        validate(inspections=[inspection(measurement_date=date(2026, 7, 31).isoformat())])
    with pytest.raises(ValueError, match="jenis pekerjaan/tahap"):
        validate(inspections=[inspection(stage_code="TAHAP_2")])


def test_processing_source_cannot_be_reused_concurrently():
    with pytest.raises(ValueError, match="sedang diproses"):
        validate(processing_status="PROCESSING")
