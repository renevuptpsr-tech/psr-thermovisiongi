import pytest

from thermovisi.rule_router import (
    route_for_item,
    supported_analysis_rule_codes,
    validate_template_rule_configuration,
)


def test_configured_rule_is_routed_explicitly():
    route = route_for_item({"analysis_rule_code": "CT_CLAMP"})
    assert route.rule_set_code == "THERMOVISI_CT_V1"
    assert route.grouping_mode == "COMPARISON_PAIR"


def test_missing_rule_is_not_guessed_from_label():
    assert route_for_item({"point_code": "CT_TERMINAL_CLAMP"}) is None


def test_unknown_rule_is_rejected():
    with pytest.raises(ValueError, match="tidak didukung"):
        route_for_item({"analysis_rule_code": "MAGIC_RULE"})


def test_all_current_rule_families_are_registered():
    codes = set(supported_analysis_rule_codes())
    assert {
        "TRAFO_BUSHING", "TRAFO_CLAMP", "TRAFO_GRADIENT",
        "PMT_CLAMP", "PMT_INTERRUPTER", "PMT_GRADING_CAPACITOR",
        "PMT_INSULATOR", "PMS_BLADE", "PMS_MAIN_TERMINAL", "PMS_INSULATOR", "CVT_PT_COMPONENT",
        "CT_CLAMP", "CT_INSULATOR_HOUSING", "LA_NORMALIZED",
    } <= codes


def test_validation_reports_item_id_for_unknown_rule():
    errors = validate_template_rule_configuration([
        {"template_item_id": 10, "analysis_rule_code": "CT_CLAMP"},
        {"template_item_id": 11, "analysis_rule_code": "UNKNOWN"},
    ])
    assert len(errors) == 1
    assert "11" in errors[0]
