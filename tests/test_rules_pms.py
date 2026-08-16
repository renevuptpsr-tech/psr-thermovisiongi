import pytest

from thermovisi.rules_pms import (
    RULE_SET_CODE,
    evaluate_pms_blade,
    evaluate_pms_main_terminal,
)


def test_rule_set_is_versioned():
    assert RULE_SET_CODE == "THERMOVISI_PMS_V1"


def test_main_terminal_uses_actual_clamp_conductor_delta():
    result = evaluate_pms_main_terminal(45, 40, 30)
    assert result.delta_t1_c == 5
    assert result.delta_t2_c == 15
    assert result.delta_t1_condition == "Kondisi II"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"


def test_pms_blade_compares_phases_and_ambient():
    result = evaluate_pms_blade({"R": 40, "S": 42, "T": 41}, 30)
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 12
    assert result.delta_t1_condition == "Kondisi I"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"
    assert result.governing_basis == "DELTA_T2_OVER_AMBIENT"


@pytest.mark.parametrize(
    ("maximum", "expected"),
    [(30.9, "Normal"), (31, "Kondisi I"), (40.9, "Kondisi I"),
     (41, "Kondisi II"), (50.9, "Kondisi II"), (51, "Kondisi III"),
     (70, "Kondisi III"), (70.1, "Kondisi IV")],
)
def test_pms_ambient_boundaries(maximum, expected):
    result = evaluate_pms_blade({"R": maximum, "S": maximum}, 30)
    assert result.delta_t2_condition == expected


def test_pms_blade_requires_two_phases():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_pms_blade({"R": 40}, 30)
