from thermovisi.evaluation_engine import build_evaluation_patches
from thermovisi.excel_parser import ParsedMeasurement


def measurement(item_id, phase, value):
    return ParsedMeasurement(
        "Sheet", "MAIN", item_id, item_id, "EQ", "POINT", "Point", phase, value, None,
        None, str(value), "VALID", None,
    )


def test_pms_blade_is_evaluated_by_explicit_rule_code():
    items = [{
        "template_item_id": 1, "analysis_rule_code": "PMS_BLADE",
        "point_code": "PMS_BLADE", "comparison_group_code": None,
    }]
    patches, statuses = build_evaluation_patches(
        items,
        [measurement(1, "R", 40), measurement(1, "S", 45), measurement(1, "T", 41)],
        measurement_current_a=100, monthly_peak_current_a=200, ambient_temperature_c=30,
    )
    assert not statuses
    assert patches[0].values["Rule set"] == "THERMOVISI_PMS_V1"
    assert patches[0].values["Status analisa"] == "TEREVALUASI"
    assert patches[0].values["ΔT analisa (°C)"] == 5


def test_missing_rule_is_visible_and_not_guessed():
    items = [{"template_item_id": 1, "point_code": "PMS_BLADE"}]
    patches, statuses = build_evaluation_patches(
        items, [measurement(1, "R", 40), measurement(1, "S", 41)],
        measurement_current_a=0, monthly_peak_current_a=0, ambient_temperature_c=30,
    )
    assert patches == []
    assert statuses[1] == "RULE_NOT_CONFIGURED"


def test_ct_pair_uses_load_correction_and_covers_reference():
    items = [
        {"template_item_id": 1, "analysis_rule_code": "CT_CLAMP", "comparison_group_code": "CT_IN", "comparison_role": "CLAMP"},
        {"template_item_id": 2, "analysis_rule_code": "CT_CLAMP", "comparison_group_code": "CT_IN", "comparison_role": "CONDUCTOR"},
    ]
    patches, statuses = build_evaluation_patches(
        items, [measurement(1, "R", 42), measurement(2, "R", 40)],
        measurement_current_a=100, monthly_peak_current_a=200, ambient_temperature_c=30,
    )
    assert not statuses
    assert patches[0].covered_item_ids == (2,)
    assert patches[0].values["ΔT analisa (°C)"] == 8
    assert patches[0].values["Rule set"] == "THERMOVISI_CT_V1"


def test_invalid_pair_configuration_is_not_evaluated():
    items = [{
        "template_item_id": 1, "analysis_rule_code": "PMT_CLAMP",
        "comparison_group_code": "PMT_IN", "comparison_role": "CLAMP",
    }]
    patches, statuses = build_evaluation_patches(
        items, [measurement(1, "R", 40)],
        measurement_current_a=100, monthly_peak_current_a=200, ambient_temperature_c=30,
    )
    assert patches == []
    assert statuses[1] == "INCOMPLETE_PAIR"
