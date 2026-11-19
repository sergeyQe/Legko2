"""Маршруты создателя кампаний."""
from fastapi import APIRouter, Body, Depends, Path

from app.api import mappers
from app.api.deps import get_creator_service
from app.api.docs import KEITARO_CODES, responses
from app.api.schemas import MAX_ID, CreateCampaignBody, CreateReportOut, RetryStream2Body
from app.services.creator_service import CreatorService

router = APIRouter(prefix="/campaign-creator", tags=["Создание кампании"])


@router.post(
    "/campaigns",
    response_model=CreateReportOut,
    status_code=201,
    summary="Создать кампанию с двумя потоками",
    description=(
        "Создаёт в Keitaro кампанию с ротацией по весу и два потока: поток 1 принимает посетителей из страны `geo` "
        "и редиректит на https://google.com, поток 2 ведёт на оффер `offer_id` (доля 100%). Алиас строится из названия. "
        "Домен, группа и источник необязательны: null означает «создать без этого параметра». "
        "Публикует в Keitaro сразу, без черновика. Если кампания создалась, а поток нет, вернётся `CREATE_PARTIAL` "
        "с результатом каждого шага; кампанию мы не удаляем."
    ),
    responses=responses("VALIDATION", "KEITARO_REJECTED", "CREATE_PARTIAL", *KEITARO_CODES),
)
def create_campaign(
    body: CreateCampaignBody = Body(), service: CreatorService = Depends(get_creator_service)
) -> CreateReportOut:
    """Создание кампании."""
    report = service.create_campaign(
        name=body.name, geo=body.geo, offer_id=body.offer_id,
        domain_id=body.domain_id, group_id=body.group_id, source_id=body.source_id,
    )
    return mappers.report_out(report)


@router.post(
    "/campaigns/{campaign_id}/retry-stream2",
    response_model=CreateReportOut,
    summary="Повторить создание потока 2",
    description=(
        "Повторно создаёт поток 2 (на оффер `offer_id`) для кампании, у которой он не создался. "
        "Если поток с этим оффером уже есть, ничего не создаёт и возвращает успех. "
        "Требует, чтобы в кампании был поток 1 (без офферов)."
    ),
    responses=responses("VALIDATION", "CREATE_PARTIAL", "KEITARO_NOT_FOUND", *KEITARO_CODES),
)
def retry_stream2(
    campaign_id: int = Path(ge=1, le=MAX_ID, description="ID кампании в Keitaro (`campaign_id` из отчёта о создании)"),
    body: RetryStream2Body = Body(),
    service: CreatorService = Depends(get_creator_service),
) -> CreateReportOut:
    """Повтор создания потока 2."""
    return mappers.report_out(service.retry_stream2(campaign_id, body.offer_id, body.name, body.alias, body.geo))
