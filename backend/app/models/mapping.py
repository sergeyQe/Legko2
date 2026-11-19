"""Перевод между записями БД (StreamOffer) и доменной моделью (DraftOffer)."""
from app.domain.states import DraftOffer
from app.models.entities import Stream, StreamOffer


def to_draft(row: StreamOffer) -> DraftOffer:
    """Запись БД -> доменный оффер."""
    return DraftOffer(
        offer_id=row.offer_id,
        name=row.name,
        geo=row.geo,
        in_kt=row.in_kt,
        kt_weight=row.kt_weight,
        active=row.active,
        weight=row.weight,
        pinned=row.pinned,
        archived=row.archived,
        was_archived=row.was_archived,
    )


def stream_to_drafts(stream: Stream) -> list[DraftOffer]:
    """Все офферы потока в порядке position."""
    return [to_draft(row) for row in stream.offers]


def sync_stream_offers(stream: Stream, drafts: list[DraftOffer]) -> None:
    """Приводит записи потока в соответствие с доменным списком: обновляет, добавляет, удаляет, задаёт порядок."""
    existing = {row.offer_id: row for row in stream.offers}
    wanted_ids = {d.offer_id for d in drafts}

    # удаляем записи, которых больше нет в доменном списке
    for offer_id, row in existing.items():
        if offer_id not in wanted_ids:
            stream.offers.remove(row)

    # обновляем найденные записи и добавляем новые, порядок задаём по списку
    for position, draft in enumerate(drafts):
        row = existing.get(draft.offer_id)
        if row is None:
            row = StreamOffer(offer_id=draft.offer_id)
            stream.offers.append(row)
        row.position = position
        row.name = draft.name
        row.geo = draft.geo
        row.in_kt = draft.in_kt
        row.kt_weight = draft.kt_weight
        row.active = draft.active
        row.weight = draft.weight
        row.pinned = draft.pinned
        row.archived = draft.archived
        row.was_archived = draft.was_archived
