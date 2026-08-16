import pytest

from thermovisi.ahi import aggregate_ahi, ahi_from_severity


@pytest.mark.parametrize(
    ("severity", "score", "label"),
    [(0, 1, "Very Good"), (1, 2, "Good"), (2, 3, "Fair"),
     (3, 4, "Poor"), (4, 5, "Critical")],
)
def test_severity_is_normalized_to_pln_ahi(severity, score, label):
    rating = ahi_from_severity(severity)
    assert rating.score == score
    assert rating.label == label


def test_invalid_data_has_no_ahi():
    assert ahi_from_severity(4, evaluable=False) is None


def test_aggregate_uses_worst_score_and_ignores_missing():
    rating = aggregate_ahi([1, None, 4, 2])
    assert rating.score == 4
    assert rating.label == "Poor"


def test_aggregate_without_evaluable_data_is_empty():
    assert aggregate_ahi([None, None]) is None


def test_out_of_range_values_are_rejected():
    with pytest.raises(ValueError):
        ahi_from_severity(5)
    with pytest.raises(ValueError):
        aggregate_ahi([6])
