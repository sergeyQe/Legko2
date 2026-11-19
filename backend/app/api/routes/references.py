"""Маршруты справочников: домены, группы, источники, поиск офферов."""
from fastapi import APIRouter, Depends, Query

from app.api import mappers
from app.api.docs import KEITARO_CODES, responses
from app.api.deps import get_reference_service
from app.api.schemas import OfferSearchOut, ReferencesOut
from app.services.reference_service import ReferenceService

router = APIRouter(tags=["Справочники"])


@router.get(
    "/references",
    response_model=ReferencesOut,
    summary="Получить справочники для формы создания кампании",
    description=(
        "Возвращает домены, группы кампаний и источники трафика из Keitaro, а также значения по умолчанию "
        "(ID по названиям из настроек сервиса). Если значение по умолчанию не найдено в Keitaro, его ID равен null, "
        "а название попадает в `defaults.missing`. Ничего не меняет."
    ),
    responses=responses(*KEITARO_CODES),
)
def get_references(service: ReferenceService = Depends(get_reference_service)) -> ReferencesOut:
    """Справочники и значения по умолчанию."""
    return ReferencesOut(
        domains=[mappers.reference_out(r) for r in service.domains()],
        groups=[mappers.reference_out(r) for r in service.groups()],
        sources=[mappers.reference_out(r) for r in service.sources()],
        defaults=mappers.defaults_out(service.defaults()),
    )


@router.get(
    "/offers/search",
    response_model=list[OfferSearchOut],
    summary="Найти оффер в базе Keitaro",
    description=(
        "Ищет офферы по ID или по части названия (регистр не важен), возвращает не более 20 штук. "
        "Пустой запрос даёт пустой список. Используется для добавления оффера в поток и в форме создания кампании. "
        "Ничего не меняет."
    ),
    responses=responses(*KEITARO_CODES),
)
def search_offers(
    q: str = Query(default="", description="ID оффера или часть названия", examples=["11112"]),
    service: ReferenceService = Depends(get_reference_service),
) -> list[OfferSearchOut]:
    """Поиск офферов."""
    return [mappers.catalog_offer_out(o) for o in service.search_offers(q)]
