"""Расчёт долей с пинами."""
import pytest

from app.domain.errors import WeightError
from app.domain.weights import calculate_weights


def test_empty_stream_has_no_weights():
    assert calculate_weights([]) == []


def test_four_free_offers_get_25_each():
    assert calculate_weights([None, None, None, None]) == [25, 25, 25, 25]


def test_three_free_offers_last_gets_extra_percent():
    assert calculate_weights([None, None, None]) == [33, 33, 34]


def test_single_offer_gets_everything():
    assert calculate_weights([None]) == [100]


def test_pinned_weight_stays_and_rest_is_shared():
    assert calculate_weights([25, None, None, None]) == [25, 25, 25, 25]
    assert calculate_weights([25, None, None]) == [25, 37, 38]


def test_extra_percent_goes_to_last_free_offer_not_last_offer():
    assert calculate_weights([None, None, 50]) == [25, 25, 50]
    assert calculate_weights([None, None, None, 1]) == [33, 33, 33, 1]


def test_all_pinned_must_sum_to_100():
    assert calculate_weights([60, 40]) == [60, 40]
    with pytest.raises(WeightError):
        calculate_weights([60, 30])


def test_pinned_sum_above_100_is_rejected():
    with pytest.raises(WeightError):
        calculate_weights([60, 50, None])


def test_pinned_out_of_range_is_rejected():
    with pytest.raises(WeightError):
        calculate_weights([-1, None])
    with pytest.raises(WeightError):
        calculate_weights([101])


def test_pinned_100_leaves_zero_to_free_offers():
    assert calculate_weights([100, None]) == [100, 0]
