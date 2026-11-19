"""Операции над черновиком потока (сценарий из видео)."""
import pytest

from app.domain import draft
from app.domain.errors import (
    EmptyStreamError,
    OfferAlreadyInStreamError,
    OfferNotFoundError,
    OfferRemovedError,
    OfferStateError,
    WeightError,
)
from app.domain.states import OfferState, offer_state
from tests.domain_helpers import published, screenshot_stream, weights


def test_fresh_stream_is_not_dirty():
    offers = screenshot_stream()
    assert not draft.is_dirty(offers)
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34}


def test_add_offer_gives_25_each_and_makes_stream_dirty():
    offers = screenshot_stream()
    added = draft.add_offer(offers, 11112, "Новый", "BE")
    assert weights(offers) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}
    assert offer_state(added) == OfferState.ADDED
    assert draft.is_dirty(offers)


def test_cancel_removes_added_offers_and_restores_weights():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    draft.cancel(offers)
    assert [o.offer_id for o in offers] == [11109, 11110, 11111]
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34}
    assert not draft.is_dirty(offers)


def test_remove_published_offer_zeroes_it_and_recalculates_others():
    offers = screenshot_stream()
    deleted = draft.remove_offer(offers, 11109)
    assert deleted is False
    assert weights(offers) == {11109: 0, 11110: 50, 11111: 50}
    assert offer_state(offers[0]) == OfferState.REMOVING
    assert draft.is_dirty(offers)


def test_remove_one_of_four_gives_33_33_34():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    draft.apply_push(offers)
    draft.remove_offer(offers, 11112)
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34, 11112: 0}


def test_remove_unpublished_offer_deletes_it_completely():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    deleted = draft.remove_offer(offers, 11112)
    assert deleted is True
    assert [o.offer_id for o in offers] == [11109, 11110, 11111]
    assert not draft.is_dirty(offers)


def test_push_moves_removed_offer_to_archive():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    draft.apply_push(offers)
    removed = next(o for o in offers if o.offer_id == 11109)
    assert offer_state(removed) == OfferState.REMOVED
    assert removed.archived and removed.was_archived
    assert not draft.is_dirty(offers)
    assert weights(offers) == {11109: 0, 11110: 50, 11111: 50}


def test_bring_back_removing_offer_restores_published_state():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    draft.bring_back(offers, 11109)
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34}
    assert not draft.is_dirty(offers)


def test_bring_back_archived_offer_becomes_added_and_push_returns_it_to_keitaro():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    draft.apply_push(offers)
    returned = draft.bring_back(offers, 11109)
    assert offer_state(returned) == OfferState.ADDED
    assert draft.is_dirty(offers)
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34}
    draft.apply_push(offers)
    assert offer_state(next(o for o in offers if o.offer_id == 11109)) == OfferState.PUBLISHED


def test_cancel_after_bring_back_from_archive_returns_offer_to_archive():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    draft.apply_push(offers)
    draft.bring_back(offers, 11109)
    draft.cancel(offers)
    restored = next(o for o in offers if o.offer_id == 11109)
    assert offer_state(restored) == OfferState.REMOVED
    assert restored.weight == 0


def test_cancel_after_remove_restores_published_offer():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    draft.cancel(offers)
    assert weights(offers) == {11109: 33, 11110: 33, 11111: 34}
    assert not draft.is_dirty(offers)


def test_pinned_weight_survives_add_and_remove():
    offers = [published(1, 25), published(2, 25), published(3, 25), published(4, 25)]
    draft.set_pin(offers, 1, True)
    draft.remove_offer(offers, 4)
    assert weights(offers) == {1: 25, 2: 37, 3: 38, 4: 0}
    draft.bring_back(offers, 4)
    assert weights(offers) == {1: 25, 2: 25, 3: 25, 4: 25}
    assert offers[0].pinned


def snapshot(offers):
    """Состояние списка офферов для сравнения до и после неудачной операции."""
    return [(o.offer_id, o.weight, o.pinned, o.active) for o in offers]


def test_remove_rolls_back_when_remaining_pins_do_not_sum_to_100():
    # оба оффера закреплены (60+40); если убрать второй, единственный закреплённый даст 60%, а не 100%
    offers = [published(1, 60), published(2, 40)]
    draft.set_pin(offers, 1, True)
    draft.set_pin(offers, 2, True)
    before = snapshot(offers)
    with pytest.raises(WeightError):
        draft.remove_offer(offers, 2)
    assert snapshot(offers) == before


def test_pinning_to_exact_100_is_allowed_and_free_offer_gets_zero():
    offers = [published(1, 60), published(2, 40)]
    draft.set_pin(offers, 1, True)
    draft.set_pin(offers, 2, True)
    added = draft.add_offer(offers, 3, "Третий")
    assert weights(offers) == {1: 60, 2: 40, 3: 0}
    assert added.weight == 0


def test_pinning_one_offer_shares_rest_between_free_offers():
    offers = [published(1, 34), published(2, 33), published(3, 33)]
    draft.set_pin(offers, 1, True)
    draft.remove_offer(offers, 3)
    assert weights(offers) == {1: 34, 2: 66, 3: 0}


def test_set_pin_on_removed_offer_is_rejected():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    with pytest.raises(OfferStateError):
        draft.set_pin(offers, 11109, True)


def test_unpin_returns_offer_to_shared_weights():
    offers = [published(1, 25), published(2, 25), published(3, 25), published(4, 25)]
    draft.set_pin(offers, 1, True)
    draft.remove_offer(offers, 4)
    draft.set_pin(offers, 1, False)
    assert weights(offers) == {1: 33, 2: 33, 3: 34, 4: 0}


def test_add_duplicate_offer_is_rejected():
    offers = screenshot_stream()
    with pytest.raises(OfferAlreadyInStreamError):
        draft.add_offer(offers, 11109, "Дубль")


def test_add_removed_offer_asks_to_bring_it_back():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    with pytest.raises(OfferRemovedError):
        draft.add_offer(offers, 11109, "Повтор")


def test_unknown_offer_raises_not_found():
    offers = screenshot_stream()
    with pytest.raises(OfferNotFoundError):
        draft.remove_offer(offers, 999)
    with pytest.raises(OfferNotFoundError):
        draft.set_pin(offers, 999, True)


def test_remove_twice_is_rejected():
    offers = screenshot_stream()
    draft.remove_offer(offers, 11109)
    with pytest.raises(OfferStateError):
        draft.remove_offer(offers, 11109)


def test_bring_back_active_offer_is_rejected():
    offers = screenshot_stream()
    with pytest.raises(OfferStateError):
        draft.bring_back(offers, 11109)


def test_push_without_active_offers_is_rejected():
    offers = [published(1, 100)]
    draft.remove_offer(offers, 1)
    with pytest.raises(EmptyStreamError):
        draft.apply_push(offers)
    with pytest.raises(EmptyStreamError):
        draft.ensure_pushable(offers)


def test_changes_describe_add_remove_and_weight_change():
    offers = screenshot_stream()
    draft.add_offer(offers, 11112, "Новый")
    draft.remove_offer(offers, 11110)
    changes = {c.offer.offer_id: c for c in draft.compute_changes(offers)}
    assert changes[11112].kind == "add" and changes[11112].from_weight is None
    assert changes[11110].kind == "remove" and changes[11110].to_weight == 0
    # активны 11109, 11111, 11112 -> 33/33/34: у 11109 вес прежний, у 11111 стало 33 вместо 34
    assert 11109 not in changes
    assert changes[11111].kind == "change"
    assert changes[11111].from_weight == 34 and changes[11111].to_weight == 33


def test_changes_include_changed_weight_of_published_offer():
    offers = [published(1, 50), published(2, 50)]
    draft.add_offer(offers, 3, "Новый")
    changes = {c.offer.offer_id: c for c in draft.compute_changes(offers)}
    assert changes[1].kind == "change" and changes[1].from_weight == 50 and changes[1].to_weight == 33
    assert changes[2].to_weight == 33 and changes[3].to_weight == 34


def test_changes_mark_pinned_weight():
    offers = [published(1, 33), published(2, 33), published(3, 34)]
    draft.set_pin(offers, 1, True)  # закрепили текущие 33
    draft.remove_offer(offers, 3)
    change = next(c for c in draft.compute_changes(offers) if c.offer.offer_id == 2)
    assert change.kind == "change" and change.to_weight == 67
