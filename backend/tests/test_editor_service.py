"""Сервис редактора: сценарий из видео на заглушке Keitaro и БД SQLite."""
import pytest

from app.domain.errors import EmptyStreamError, OfferAlreadyInStreamError
from app.domain.states import OfferState
from app.keitaro.errors import KeitaroUnreachableError
from tests.fake_keitaro import FOREIGN_CAMPAIGN_ID, PREFIX, FakeKeitaroClient
from app.services.editor_service import EditorService
from app.services.errors import EntityNotFoundError, MergeConflictError

CAMPAIGN = 93212  # кампания со скриншотов: поток 1 без офферов, поток 2 с тремя офферами


@pytest.fixture
def kt() -> FakeKeitaroClient:
    return FakeKeitaroClient()


@pytest.fixture
def svc(session, kt) -> EditorService:
    return EditorService(session, kt, PREFIX)


@pytest.fixture
def stream_id(svc) -> int:
    """Внутренний ID потока 2 после загрузки кампании."""
    view = svc.fetch_campaign(CAMPAIGN)
    return next(s.id for s in view.streams if s.name == "Поток 2")


def weights(view) -> dict[int, int]:
    return {o.offer.offer_id: o.offer.weight for o in view.offers}


def states(view) -> dict[int, OfferState]:
    return {o.offer.offer_id: o.state for o in view.offers}


def kt_weights(kt, stream_keitaro_id=2) -> dict[int, int]:
    return {o.offer_id: o.weight for o in kt.get_stream(stream_keitaro_id).offers}


def stream_view(svc, stream_id):
    campaign = next(c for c in svc.list_campaigns() if c.keitaro_id == CAMPAIGN)
    return next(s for s in svc.get_campaign(campaign.id).streams if s.id == stream_id)


def test_fetch_loads_streams_and_stream_without_offers_stays_empty(svc):
    view = svc.fetch_campaign(CAMPAIGN)
    assert [s.name for s in view.streams] == ["Поток 1", "Поток 2"]
    assert view.streams[0].offers == [] and not view.streams[0].dirty
    assert weights(view.streams[1]) == {11109: 33, 11110: 33, 11111: 34}
    assert not view.streams[1].dirty and view.streams[1].weight_sum == 100
    assert view.fetched_at is not None


def test_campaign_list_reports_fetch_state_and_counts(svc):
    before = {c.keitaro_id: c for c in svc.list_campaigns()}
    assert not before[CAMPAIGN].fetched and before[CAMPAIGN].streams_total is None
    svc.fetch_campaign(CAMPAIGN)
    after = {c.keitaro_id: c for c in svc.list_campaigns()}
    assert after[CAMPAIGN].fetched and after[CAMPAIGN].streams_total == 2
    assert after[CAMPAIGN].streams_with_offers == 1 and not after[CAMPAIGN].dirty


def test_add_offer_changes_only_draft(svc, kt, stream_id):
    view = svc.add_offer(stream_id, 11112)
    assert weights(view) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}
    assert view.dirty and states(view)[11112] == OfferState.ADDED
    assert kt_weights(kt) == {11109: 33, 11110: 33, 11111: 34}


def test_draft_survives_page_reload_and_repeated_fetch(svc, stream_id):
    svc.add_offer(stream_id, 11112)
    svc.fetch_campaign(CAMPAIGN)
    view = stream_view(svc, stream_id)
    assert view.dirty and weights(view) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}


def test_cancel_discards_added_offers(svc, stream_id):
    svc.add_offer(stream_id, 11112)
    view = svc.cancel(stream_id)
    assert weights(view) == {11109: 33, 11110: 33, 11111: 34} and not view.dirty


def test_push_replaces_offers_in_keitaro(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    view = svc.push(stream_id)
    assert kt_weights(kt) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}
    assert not view.dirty and states(view)[11112] == OfferState.PUBLISHED


def test_remove_then_push_leaves_offer_in_archive(svc, kt, stream_id):
    view = svc.remove_offer(stream_id, 11109)
    assert weights(view) == {11109: 0, 11110: 50, 11111: 50} and view.dirty
    assert kt_weights(kt) == {11109: 33, 11110: 33, 11111: 34}

    view = svc.push(stream_id)
    assert kt_weights(kt) == {11110: 50, 11111: 50}
    assert states(view)[11109] == OfferState.REMOVED and not view.dirty
    # архив сохраняется после повторной загрузки
    svc.fetch_campaign(CAMPAIGN)
    assert states(stream_view(svc, stream_id))[11109] == OfferState.REMOVED


def test_bring_back_and_push_returns_offer_to_keitaro(svc, kt, stream_id):
    svc.remove_offer(stream_id, 11109)
    svc.push(stream_id)
    view = svc.bring_back(stream_id, 11109)
    assert view.dirty and states(view)[11109] == OfferState.ADDED
    svc.push(stream_id)
    assert set(kt_weights(kt)) == {11109, 11110, 11111}


def test_offer_removed_in_keitaro_appears_as_removed_after_fetch(svc, kt, stream_id):
    kt.external_offer_removed(2, 11111)
    view = svc.fetch_campaign(CAMPAIGN).streams[1]
    assert states(view)[11111] == OfferState.REMOVED
    assert any("11111" in note for note in view.notes)
    # в Keitaro осталось 33+33=66%: доли пересчитаны до 100%, поток требует отправки
    assert weights(view) == {11109: 50, 11110: 50, 11111: 0}
    assert view.dirty and view.weight_sum == 100
    assert any("сумма долей 66%" in note for note in view.notes)


def test_fetch_with_bad_sum_and_unfixable_pins_only_warns(svc, kt, stream_id):
    svc.set_pin(stream_id, 11109, True)
    svc.set_pin(stream_id, 11110, True)
    svc.set_pin(stream_id, 11111, True)
    svc.push(stream_id)
    kt.external_offer_removed(2, 11111)
    view = svc.fetch_campaign(CAMPAIGN).streams[1]
    # закреплены все оставшиеся офферы (33+33=66): пересчитать нельзя, веса остаются как в Keitaro
    assert weights(view) == {11109: 33, 11110: 33, 11111: 0}
    assert not view.dirty and view.weight_sum == 66
    assert any("Открепите вес" in note for note in view.notes)


def test_fetch_with_valid_sum_keeps_stream_clean(svc, kt, stream_id):
    kt.external_weight_changed(2, 11109, 34)
    kt.external_weight_changed(2, 11111, 33)
    view = svc.fetch_campaign(CAMPAIGN).streams[1]
    assert weights(view) == {11109: 34, 11110: 33, 11111: 33} and not view.dirty


def test_pinned_weight_is_kept_through_changes_and_pushed(svc, kt, stream_id):
    svc.set_pin(stream_id, 11109, True)
    svc.add_offer(stream_id, 11112)
    view = svc.remove_offer(stream_id, 11111)
    assert weights(view)[11109] == 33 and view.offers[0].offer.pinned
    svc.push(stream_id)
    assert kt_weights(kt)[11109] == 33


def test_unpin_returns_weight_to_shared_calculation(svc, stream_id):
    svc.set_pin(stream_id, 11109, True)
    svc.remove_offer(stream_id, 11111)
    view = svc.set_pin(stream_id, 11109, False)
    assert weights(view) == {11109: 50, 11110: 50, 11111: 0}


def test_failed_push_keeps_draft_and_keitaro_unchanged(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    kt.fail_next("network", "push")
    with pytest.raises(KeitaroUnreachableError):
        svc.push(stream_id)
    view = stream_view(svc, stream_id)
    assert view.dirty and len(view.offers) == 4
    assert kt_weights(kt) == {11109: 33, 11110: 33, 11111: 34}
    # повтор проходит
    assert not svc.push(stream_id).dirty


def test_push_without_active_offers_is_rejected(svc, stream_id):
    for offer_id in (11109, 11110, 11111):
        view = svc.remove_offer(stream_id, offer_id)
    assert view.dirty and view.weight_sum == 0
    with pytest.raises(EmptyStreamError):
        svc.push(stream_id)


def test_add_unknown_offer_and_duplicate_are_rejected(svc, stream_id):
    with pytest.raises(EntityNotFoundError) as info:
        svc.add_offer(stream_id, 99999)
    assert info.value.entity == "offer"
    with pytest.raises(OfferAlreadyInStreamError):
        svc.add_offer(stream_id, 11109)


def test_unknown_stream_is_rejected(svc):
    with pytest.raises(EntityNotFoundError):
        svc.add_offer(999, 11112)
    with pytest.raises(EntityNotFoundError):
        svc.get_campaign(999)


def test_failed_fetch_changes_nothing(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    kt.fail_next("network", "fetch")
    with pytest.raises(KeitaroUnreachableError):
        svc.fetch_campaign(CAMPAIGN)
    assert stream_view(svc, stream_id).dirty


def test_fetch_with_draft_merges_external_changes_without_losing_draft(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    kt.external_offer_added(2, 11120, 20)
    view = svc.fetch_campaign(CAMPAIGN).streams[1]
    assert set(weights(view)) == {11109, 11110, 11111, 11112, 11120}
    assert states(view)[11112] == OfferState.ADDED and states(view)[11120] == OfferState.PUBLISHED
    assert any("11120" in n for n in view.notes)
    assert sum(w for w in weights(view).values()) == 100


def test_preview_shows_merge_without_saving(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    kt.external_offer_added(2, 11120, 20)
    preview = svc.preview(stream_id)
    assert [i.key for i in preview.merge_items] == ["11120:added_in_kt"]
    assert preview.can_push and preview.unresolved == []
    assert {c.offer.offer_id for c in preview.changes} >= {11112}
    assert [o.offer_id for o in preview.keitaro_offers] == [11109, 11110, 11111, 11120]
    # в БД ничего не изменилось
    assert 11120 not in weights(stream_view(svc, stream_id))


def test_push_merges_new_keitaro_offer(svc, kt, stream_id):
    svc.add_offer(stream_id, 11112)
    kt.external_offer_added(2, 11120, 20)
    svc.push(stream_id)
    assert kt_weights(kt) == {11109: 20, 11110: 20, 11111: 20, 11112: 20, 11120: 20}


def test_conflict_blocks_push_until_resolved(svc, kt, stream_id):
    svc.remove_offer(stream_id, 11110)
    kt.external_weight_changed(2, 11110, 40)

    preview = svc.preview(stream_id)
    assert not preview.can_push and [i.key for i in preview.unresolved] == ["11110:weight_changed_removed"]
    with pytest.raises(MergeConflictError) as info:
        svc.push(stream_id)
    assert [c.key for c in info.value.conflicts] == ["11110:weight_changed_removed"]
    # после неудачи Keitaro не изменён
    assert kt_weights(kt) == {11109: 33, 11110: 40, 11111: 34}


def test_conflict_resolved_as_draft_removes_offer(svc, kt, stream_id):
    svc.remove_offer(stream_id, 11110)
    kt.external_weight_changed(2, 11110, 40)
    svc.push(stream_id, {"11110:weight_changed_removed": "draft"})
    assert kt_weights(kt) == {11109: 50, 11111: 50}


def test_conflict_resolved_as_keitaro_keeps_offer_with_its_weight(svc, kt, stream_id):
    svc.remove_offer(stream_id, 11110)
    kt.external_weight_changed(2, 11110, 40)
    view = svc.push(stream_id, {"11110:weight_changed_removed": "keitaro"})
    assert kt_weights(kt) == {11109: 30, 11110: 40, 11111: 30}
    assert not view.dirty and not any(o.offer.pinned for o in view.offers)


# ---------- защита по префиксу ----------

def test_service_requires_prefix(session, kt):
    with pytest.raises(ValueError):
        EditorService(session, kt, "")


def test_foreign_campaign_is_not_listed_and_cannot_be_fetched(svc, kt):
    names = [c.name for c in svc.list_campaigns()]
    assert "test_other_campaign1" not in names and names == ["test_titov_campaign2", "test_titov_campaign5"]
    with pytest.raises(EntityNotFoundError):
        svc.fetch_campaign(FOREIGN_CAMPAIGN_ID)
    # чужой поток в Keitaro не прочитан и не изменён
    assert len(kt.get_campaign_streams(FOREIGN_CAMPAIGN_ID)) == 1


def test_prefix_check_ignores_case(session, kt):
    service = EditorService(session, kt, "TEST_TITOV_")
    assert [c.name for c in service.list_campaigns()] == ["test_titov_campaign2", "test_titov_campaign5"]
