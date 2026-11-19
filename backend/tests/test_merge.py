"""Трёхсторонний merge черновика с текущим состоянием Keitaro."""
import pytest

from app.domain import draft
from app.domain.errors import InvalidResolutionError
from app.domain.merge import merge_with_keitaro
from app.domain.states import KtOfferState, OfferState, offer_state
from tests.domain_helpers import published, screenshot_stream, weights


def kt(offer_id: int, weight: int) -> KtOfferState:
    """Оффер в Keitaro с указанным весом."""
    return KtOfferState(offer_id=offer_id, name=f"Оффер {offer_id}", geo="XX", weight=weight)


def keitaro_same_as_snapshot() -> list[KtOfferState]:
    """Поток в Keitaro, совпадающий со скриншотным снимком."""
    return [kt(11109, 33), kt(11110, 33), kt(11111, 34)]


def by_id(result, offer_id):
    return next(o for o in result.offers if o.offer_id == offer_id)


def test_no_changes_in_keitaro_gives_no_items_and_keeps_draft():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, keitaro_same_as_snapshot())
    assert not result.needs_merge
    assert weights(result.offers) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}


def test_merge_does_not_mutate_input():
    offers = screenshot_stream()
    merge_with_keitaro(offers, keitaro_same_as_snapshot() + [kt(11120, 20)])
    assert [o.offer_id for o in offers] == [11109, 11110, 11111]


def test_offer_added_in_keitaro_is_kept_and_weights_recalculated():
    offers = screenshot_stream()
    result = merge_with_keitaro(offers, keitaro_same_as_snapshot() + [kt(11120, 20)])
    assert [i.key for i in result.items] == ["11120:added_in_kt"]
    assert result.items[0].kind == "auto"
    added = by_id(result, 11120)
    assert offer_state(added) == OfferState.PUBLISHED
    assert weights(result.offers) == {11109: 25, 11110: 25, 11111: 25, 11120: 25}


def test_offer_added_only_in_draft_is_kept():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, keitaro_same_as_snapshot() + [kt(11120, 20)])
    assert set(weights(result.offers)) == {11109, 11110, 11111, 11112, 11120}
    assert offer_state(by_id(result, 11112)) == OfferState.ADDED


def test_same_offer_added_in_draft_and_keitaro_becomes_published():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, keitaro_same_as_snapshot() + [kt(11112, 25)])
    assert offer_state(by_id(result, 11112)) == OfferState.PUBLISHED
    assert result.items[0].key == "11112:appeared_in_kt"


def test_offer_removed_only_in_keitaro_goes_to_archive():
    offers = screenshot_stream()
    result = merge_with_keitaro(offers, [kt(11109, 33), kt(11110, 33)])
    removed = by_id(result, 11111)
    assert offer_state(removed) == OfferState.REMOVED and removed.archived
    assert result.items[0].kind == "auto"
    assert weights(result.offers) == {11109: 50, 11110: 50, 11111: 0}


def test_offer_removed_in_both_is_archived_without_conflict():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11111)
    result = merge_with_keitaro(offers, [kt(11109, 33), kt(11110, 33)])
    assert offer_state(by_id(result, 11111)) == OfferState.REMOVED
    assert not result.unresolved


def test_weight_changed_only_in_keitaro_is_taken_and_others_recalculated():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, [kt(11109, 33), kt(11110, 40), kt(11111, 34)])
    assert weights(result.offers) == {11109: 20, 11110: 40, 11111: 20, 11112: 20}
    assert any(i.key == "11110:weight_changed" for i in result.items)
    assert by_id(result, 11110).temp_pinned


def test_pinned_draft_weight_wins_over_keitaro_change():
    offers = screenshot_stream()
    draft.set_pin(offers, 11110, True)
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, [kt(11109, 33), kt(11110, 40), kt(11111, 34)])
    assert by_id(result, 11110).weight == 33
    assert not by_id(result, 11110).temp_pinned
    assert any(i.key == "11110:weight_changed_pinned" for i in result.items)


def test_keitaro_weight_that_does_not_fit_falls_back_to_draft_calculation():
    offers = [published(1, 50), published(2, 50)]
    draft.set_pin(offers, 1, True)
    draft.add_offer(offers, 3, "Новый")
    result = merge_with_keitaro(offers, [kt(1, 50), kt(2, 60)])
    # закреплено 50 + вес из Keitaro 60 > 100, поэтому остаётся расчёт черновика
    assert weights(result.offers) == {1: 50, 2: 25, 3: 25}
    assert any(i.key == "weights_overflow" for i in result.items)


def test_removed_in_draft_but_weight_changed_in_keitaro_is_conflict():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11110)
    keitaro = [kt(11109, 33), kt(11110, 40), kt(11111, 34)]

    result = merge_with_keitaro(offers, keitaro)
    assert [i.key for i in result.unresolved] == ["11110:weight_changed_removed"]
    # без решения применяется вариант «черновик»: оффер остаётся убранным
    assert offer_state(by_id(result, 11110)) == OfferState.REMOVING


def test_conflict_resolved_as_draft_keeps_offer_removed():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11110)
    keitaro = [kt(11109, 33), kt(11110, 40), kt(11111, 34)]
    result = merge_with_keitaro(offers, keitaro, {"11110:weight_changed_removed": "draft"})
    assert not result.unresolved
    assert offer_state(by_id(result, 11110)) == OfferState.REMOVING
    assert weights(result.offers) == {11109: 50, 11110: 0, 11111: 50}


def test_conflict_resolved_as_keitaro_returns_offer_with_keitaro_weight():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11110)
    keitaro = [kt(11109, 33), kt(11110, 40), kt(11111, 34)]
    result = merge_with_keitaro(offers, keitaro, {"11110:weight_changed_removed": "keitaro"})
    assert not result.unresolved
    assert weights(result.offers) == {11109: 30, 11110: 40, 11111: 30}
    assert offer_state(by_id(result, 11110)) == OfferState.PUBLISHED


def test_pinned_offer_removed_in_keitaro_is_conflict():
    offers = screenshot_stream()
    draft.set_pin(offers, 11111, True)
    keitaro = [kt(11109, 33), kt(11110, 33)]
    result = merge_with_keitaro(offers, keitaro)
    assert [i.key for i in result.unresolved] == ["11111:pinned_removed_in_kt"]


def test_pinned_removed_in_keitaro_resolved_as_draft_keeps_offer_as_new():
    offers = screenshot_stream()
    draft.set_pin(offers, 11111, True)
    keitaro = [kt(11109, 33), kt(11110, 33)]
    result = merge_with_keitaro(offers, keitaro, {"11111:pinned_removed_in_kt": "draft"})
    kept = by_id(result, 11111)
    assert offer_state(kept) == OfferState.ADDED and kept.weight == 34


def test_pinned_removed_in_keitaro_resolved_as_keitaro_archives_offer():
    offers = screenshot_stream()
    draft.set_pin(offers, 11111, True)
    keitaro = [kt(11109, 33), kt(11110, 33)]
    result = merge_with_keitaro(offers, keitaro, {"11111:pinned_removed_in_kt": "keitaro"})
    assert offer_state(by_id(result, 11111)) == OfferState.REMOVED
    assert weights(result.offers) == {11109: 50, 11110: 50, 11111: 0}


def test_snapshot_weight_is_updated_to_current_keitaro_weight():
    offers = screenshot_stream()
    result = merge_with_keitaro(offers, [kt(11109, 20), kt(11110, 33), kt(11111, 34)])
    assert by_id(result, 11109).kt_weight == 20


def test_invalid_resolution_is_rejected():
    offers = screenshot_stream()
    with pytest.raises(InvalidResolutionError):
        merge_with_keitaro(offers, keitaro_same_as_snapshot(), {"x": "maybe"})


def test_push_after_merge_clears_temporary_pins():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    result = merge_with_keitaro(offers, [kt(11109, 33), kt(11110, 40), kt(11111, 34)])
    draft.apply_push(result.offers)
    assert all(not o.pinned and not o.temp_pinned for o in result.offers)
    assert weights(result.offers)[11110] == 40
