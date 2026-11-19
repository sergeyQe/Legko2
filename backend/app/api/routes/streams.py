"""Маршруты потоков: действия над черновиком, предпросмотр и отправка в Keitaro."""
from fastapi import APIRouter, Body, Depends, Path

from app.api import mappers
from app.api.deps import get_editor_service
from app.api.docs import KEITARO_CODES, responses
from app.api.schemas import MAX_ID, AddOfferBody, PinBody, PreviewOut, ResolutionsBody, StreamOut
from app.services.editor_service import EditorService

offers_router = APIRouter(prefix="/streams", tags=["Офферы потока"])
push_router = APIRouter(prefix="/streams", tags=["Предпросмотр и Push"])

STREAM_ID = Path(ge=1, le=MAX_ID, description="Внутренний ID потока (поле `id` потока из кампании)")
OFFER_ID = Path(ge=1, le=MAX_ID, description="ID оффера в Keitaro")


@offers_router.post(
    "/{stream_id}/offers",
    response_model=StreamOut,
    summary="Добавить оффер в черновик потока",
    description=(
        "Находит оффер в базе Keitaro по ID и добавляет его в черновик потока, веса пересчитываются по правилу пинов "
        "(закреплённые не меняются, остаток делится поровну). Меняет только нашу БД: в Keitaro ничего не уходит, "
        "поток становится неопубликованным (`dirty=true`)."
    ),
    responses=responses("NOT_FOUND", "OFFER_STATE_ERROR", "WEIGHTS_INVALID", *KEITARO_CODES),
)
def add_offer(
    stream_id: int = STREAM_ID, body: AddOfferBody = Body(), service: EditorService = Depends(get_editor_service)
) -> StreamOut:
    """Добавление оффера в черновик."""
    return mappers.stream_out(service.add_offer(stream_id, body.offer_id))


@offers_router.delete(
    "/{stream_id}/offers/{offer_id}",
    response_model=StreamOut,
    summary="Убрать оффер из потока",
    description=(
        "Убирает оффер в черновике. Опубликованный оффер получает вес 0%, остальные пересчитываются, "
        "оффер уйдёт в архив после отправки в Keitaro. Неопубликованный (добавленный в черновике) оффер "
        "удаляется полностью. Меняет только нашу БД."
    ),
    responses=responses("NOT_FOUND", "OFFER_STATE_ERROR", "WEIGHTS_INVALID"),
)
def remove_offer(
    stream_id: int = STREAM_ID, offer_id: int = OFFER_ID, service: EditorService = Depends(get_editor_service)
) -> StreamOut:
    """Удаление оффера из черновика."""
    return mappers.stream_out(service.remove_offer(stream_id, offer_id))


@offers_router.post(
    "/{stream_id}/offers/{offer_id}/restore",
    response_model=StreamOut,
    summary="Вернуть убранный оффер в поток",
    description=(
        "Возвращает убранный или удалённый (архивный) оффер в черновик потока и пересчитывает веса. "
        "Если оффер был в архиве, он станет добавленным (`state=added`) и вернётся в Keitaro при отправке. "
        "Меняет только нашу БД."
    ),
    responses=responses("NOT_FOUND", "OFFER_STATE_ERROR", "WEIGHTS_INVALID"),
)
def restore_offer(
    stream_id: int = STREAM_ID, offer_id: int = OFFER_ID, service: EditorService = Depends(get_editor_service)
) -> StreamOut:
    """Возврат оффера в черновик."""
    return mappers.stream_out(service.bring_back(stream_id, offer_id))


@offers_router.put(
    "/{stream_id}/offers/{offer_id}/pin",
    response_model=StreamOut,
    summary="Закрепить или открепить вес оффера",
    description=(
        "Закреплённый вес не меняется при пересчёте, остальные офферы делят оставшиеся проценты. "
        "Закрепить вес убранного оффера нельзя. Если сумма закреплённых весов больше 100% или все офферы закреплены и "
        "не дают 100%, вернётся `WEIGHTS_INVALID`, состояние не изменится. Пин живёт только у нас и в Keitaro не уходит. "
        "Меняет только нашу БД."
    ),
    responses=responses("NOT_FOUND", "OFFER_STATE_ERROR", "WEIGHTS_INVALID"),
)
def pin_offer(
    stream_id: int = STREAM_ID,
    offer_id: int = OFFER_ID,
    body: PinBody = Body(),
    service: EditorService = Depends(get_editor_service),
) -> StreamOut:
    """Закрепление веса оффера."""
    return mappers.stream_out(service.set_pin(stream_id, offer_id, body.pinned))


@offers_router.post(
    "/{stream_id}/cancel",
    response_model=StreamOut,
    summary="Отменить неопубликованные изменения потока",
    description=(
        "Выбрасывает черновик: добавленные офферы удаляются, убранные возвращаются, веса и пины сбрасываются "
        "к состоянию из Keitaro. Офферы из архива остаются в архиве. Меняет только нашу БД."
    ),
    responses=responses("NOT_FOUND"),
)
def cancel_stream(stream_id: int = STREAM_ID, service: EditorService = Depends(get_editor_service)) -> StreamOut:
    """Отмена изменений потока."""
    return mappers.stream_out(service.cancel(stream_id))


@push_router.post(
    "/{stream_id}/preview",
    response_model=PreviewOut,
    summary="Показать, что уйдёт в Keitaro",
    description=(
        "Запрашивает текущий поток у Keitaro, объединяет с ним черновик и показывает результат: изменения "
        "(`changes`), пункты объединения (`merge_items`) и спорные пункты без решения (`unresolved`). "
        "Решения по спорным пунктам передаются в `resolutions`. Ничего не сохраняет и не отправляет."
    ),
    responses=responses("NOT_FOUND", "VALIDATION", "KEITARO_NOT_FOUND", *KEITARO_CODES),
)
def preview_stream(
    stream_id: int = STREAM_ID,
    body: ResolutionsBody = Body(default_factory=ResolutionsBody),
    service: EditorService = Depends(get_editor_service),
) -> PreviewOut:
    """Предпросмотр отправки."""
    return mappers.preview_out(service.preview(stream_id, dict(body.resolutions)))


@push_router.post(
    "/{stream_id}/push",
    response_model=StreamOut,
    summary="Отправить поток в Keitaro",
    description=(
        "Отправляет поток в Keitaro: полностью заменяет его офферы итогом объединения (убранные офферы не "
        "отправляются и остаются у нас в архиве). Перед отправкой черновик объединяется с текущим состоянием Keitaro; "
        "если есть спорные пункты без решения, вернётся `MERGE_CONFLICT`. Поток без активных офферов отправить нельзя. "
        "При любой ошибке Keitaro черновик в нашей БД не меняется, повторить отправку можно."
    ),
    responses=responses("NOT_FOUND", "VALIDATION", "EMPTY_STREAM", "MERGE_CONFLICT", "KEITARO_NOT_FOUND",
                        "KEITARO_REJECTED", *KEITARO_CODES),
)
def push_stream(
    stream_id: int = STREAM_ID,
    body: ResolutionsBody = Body(default_factory=ResolutionsBody),
    service: EditorService = Depends(get_editor_service),
) -> StreamOut:
    """Отправка потока в Keitaro."""
    return mappers.stream_out(service.push(stream_id, dict(body.resolutions)))
