import pytest

from thermovisi.rules_cvt_pt import RULE_SET_CODE, evaluate_cvt_pt_component


def test_rule_set_is_versioned():
    assert RULE_SET_CODE == "THERMOVISI_CVT_PT_V1"


@pytest.mark.parametrize(
    "component",
    ["CLAMP_CONDUCTOR", "CLAMP_MAIN_TERMINAL", "INSULATOR", "HOUSING", "SECONDARY_BOX"],
)
def test_all_documented_components_are_supported(component):
    result = evaluate_cvt_pt_component(component, {"R": 40, "S": 42, "T": 41}, 30)
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 12
    assert result.delta_t1_condition == "Kondisi I"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"
    assert result.governing_basis == "DELTA_T2_OVER_AMBIENT"


def test_major_interphase_delta_is_condition_four_for_cvt_pt():
    result = evaluate_cvt_pt_component("INSULATOR", {"R": 40, "S": 56, "T": 41}, 30)
    assert result.delta_t1_c == 16
    assert result.delta_t1_condition == "Kondisi IV"
    assert result.condition == "Kondisi IV"
    assert result.governing_basis == "DELTA_T1_INTERPHASE"


def test_ambient_condition_three_requires_continuous_monitoring():
    result = evaluate_cvt_pt_component("HOUSING", {"R": 60, "S": 60, "T": 60}, 30)
    assert result.delta_t2_condition == "Kondisi III"
    assert result.condition == "Kondisi III"
    assert "monitoring kontinu" in result.recommendation


def test_cvt_pt_requires_two_phases():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_cvt_pt_component("SECONDARY_BOX", {"R": 40}, 30)


def test_unknown_component_is_rejected():
    with pytest.raises(ValueError, match="component_code"):
        evaluate_cvt_pt_component("UNKNOWN", {"R": 40, "S": 41}, 30)
