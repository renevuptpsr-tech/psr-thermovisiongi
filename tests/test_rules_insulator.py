import pytest

from thermovisi.rules_insulator import evaluate_insulator_neta


@pytest.mark.parametrize("equipment", ["PMT", "PMS"])
def test_insulator_uses_worst_of_interphase_and_ambient(equipment):
    result = evaluate_insulator_neta(equipment, {"R": 40, "S": 42, "T": 41}, 20)
    assert result.delta_t1_c == 2
    assert result.delta_t2_c == 22
    assert result.governing_basis == "DELTA_T2_OVER_AMBIENT"
    assert result.severity == 3


def test_insulator_major_interphase_condition():
    result = evaluate_insulator_neta("PMT", {"R": 40, "S": 56, "T": 41}, 30)
    assert result.delta_t1_c == 16
    assert result.governing_basis == "DELTA_T1_INTERPHASE"
    assert result.severity == 4


def test_insulator_requires_two_phases():
    with pytest.raises(ValueError, match="minimal dua"):
        evaluate_insulator_neta("PMS", {"R": 40}, 30)
