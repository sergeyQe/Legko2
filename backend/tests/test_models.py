"""Сущности БД и перевод между записями и доменной моделью."""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Campaign, Stream, StreamOffer
from app.models.mapping import stream_to_drafts, sync_stream_offers, to_draft
from tests.domain_helpers import published


def make_stream(session) -> Stream:
    campaign = Campaign(keitaro_id=93212, name="campaign 2", alias="campaign-2")
    stream = Stream(keitaro_id=2, name="Поток 2", position=2, campaign=campaign)
    session.add(campaign)
    session.commit()
    return stream


def test_campaign_stream_offer_are_saved_and_linked(session):
    stream = make_stream(session)
    stream.offers.append(StreamOffer(offer_id=11109, name="Оффер", position=0, in_kt=True, kt_weight=100, weight=100))
    session.commit()

    loaded = session.scalar(select(Campaign))
    assert loaded.streams[0].name == "Поток 2"
    assert loaded.streams[0].offers[0].offer_id == 11109
    assert loaded.fetched_at is None


def test_offer_is_unique_within_stream(session):
    stream = make_stream(session)
    stream.offers.append(StreamOffer(offer_id=1, name="A", position=0))
    stream.offers.append(StreamOffer(offer_id=1, name="B", position=1))
    with pytest.raises(IntegrityError):
        session.commit()


def test_weight_must_be_between_0_and_100(session):
    stream = make_stream(session)
    stream.offers.append(StreamOffer(offer_id=1, name="A", position=0, weight=101))
    with pytest.raises(IntegrityError):
        session.commit()


def test_keitaro_id_is_unique(session):
    session.add(Campaign(keitaro_id=1, name="a", alias="a"))
    session.commit()
    session.add(Campaign(keitaro_id=1, name="b", alias="b"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_campaign_deletes_streams_and_offers(session):
    stream = make_stream(session)
    stream.offers.append(StreamOffer(offer_id=1, name="A", position=0))
    session.commit()
    session.delete(stream.campaign)
    session.commit()
    assert session.scalars(select(Stream)).all() == []
    assert session.scalars(select(StreamOffer)).all() == []


def test_offers_are_returned_in_position_order(session):
    stream = make_stream(session)
    for offer_id, position in ((3, 2), (1, 0), (2, 1)):
        stream.offers.append(StreamOffer(offer_id=offer_id, name=str(offer_id), position=position))
    session.commit()
    session.expire_all()
    assert [o.offer_id for o in session.scalars(select(Stream)).one().offers] == [1, 2, 3]


def test_draft_round_trip_preserves_all_fields(session):
    stream = make_stream(session)
    original = published(11109, 33)
    original.pinned = True
    original.geo = "Румыния"
    sync_stream_offers(stream, [original])
    session.commit()

    restored = to_draft(session.scalar(select(StreamOffer)))
    assert restored == original


def test_sync_updates_adds_removes_and_orders(session):
    stream = make_stream(session)
    sync_stream_offers(stream, [published(1, 50), published(2, 50)])
    session.commit()
    first_row_id = next(o.id for o in stream.offers if o.offer_id == 1)

    # оффер 2 исчез, оффер 3 добавлен, вес оффера 1 изменён, порядок: 3, 1
    drafts = [published(3, 40), published(1, 60)]
    sync_stream_offers(stream, drafts)
    session.commit()
    session.expire_all()

    rows = session.scalars(select(Stream)).one().offers
    assert [(o.offer_id, o.weight) for o in rows] == [(3, 40), (1, 60)]
    # запись оффера 1 обновлена, а не пересоздана
    assert next(o.id for o in rows if o.offer_id == 1) == first_row_id


def test_stream_to_drafts_keeps_order(session):
    stream = make_stream(session)
    sync_stream_offers(stream, [published(2, 50), published(1, 50)])
    session.commit()
    assert [d.offer_id for d in stream_to_drafts(stream)] == [2, 1]
