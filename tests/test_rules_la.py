import pytest

from thermovisi.rules_la import (
    REFERENCE_BASIS,
    RULE_SET_CODE,
    evaluate_la_normalized,
)


def test_rule_set_and_basis_are_explicit():
    result = evaluate_la_normalized(
        "BODY", {"R": 40, "S": 42, "T": 41}, 30, stack_no=1, position_code="TOP"
    )
    assert RULE_SET_CODE == "THERMOVISI_LA_NORMALIZED_V1"
    assert result.reference_basis == REFERENCE_BASIS == "NETA_GENERIC_NORMALIZATION"


def test_body_is_evaluated_within_same_stack_and_position():
    result = evaluate_la_normalized(
        "BODY", {"R": 40, "S": 42, "T": 41}, 30, stack_no=2, position_code="MIDDLE"
    )
    assert result.stack_no == 2
    assert result.position_code == "MIDDLE"
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 12
    assert result.delta_t1_condition == "Kondisi I"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"


@pytest.mark.parametrize("component", ["CLAMP", "CONNECTION"])
def test_connection_points_do_not_require_stack(component):
    result = evaluate_la_normalized(component, {"R": 40, "S": 41}, 30)
    assert result.stack_no is None
    assert result.delta_t1_condition == "Kondisi I"
    assert result.delta_t2_condition == "Kondisi II"
    assert result.condition == "Kondisi II"


def test_major_interphase_result_is_condition_four():
    result = evaluate_la_normalized(
        "BODY", {"R": 40, "S": 56, "T": 41}, 30, stack_no=1, position_code="BOTTOM"
    )
    assert result.delta_t1_condition == "Kondisi IV"
    assert result.condition == "Kondisi IV"
    assert result.severity == 4


def test_body_requires_stack_and_position():
    with pytest.raises(ValueError, match="stack_no"):
        evaluate_la_normalized("BODY", {"R": 40, "S": 41}, 30, position_code="TOP")
    with pytest.raises(ValueError, match="position_code"):
        evaluate_la_normalized("BODY", {"R": 40, "S": 41}, 30, stack_no=1)


def test_la_requires_two_phases():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_la_normalized(
            "BODY", {"R": 40}, 30, stack_no=1, position_code="TOP"
        )
