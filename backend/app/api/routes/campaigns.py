"""Маршруты кампаний: список, просмотр и загрузка потоков из Keitaro."""
from fastapi import APIRouter, Depends, Path

from app.api import mappers
from app.api.deps import get_editor_service
from app.api.docs import KEITARO_CODES, responses
from app.api.schemas import CampaignOut, CampaignSummaryOut
from app.services.editor_service import EditorService

router = APIRouter(prefix="/campaigns", tags=["Кампании"])


@router.get(
    "",
    response_model=list[CampaignSummaryOut],
    summary="Получить список кампаний",
    description=(
        "Запрашивает кампании у Keitaro, обновляет их названия в нашей БД и добавляет к каждой сводку: "
        "загружены ли потоки, сколько потоков и есть ли неопубликованные изменения. "
        "Потоки и офферы не меняет, в Keitaro ничего не отправляет."
    ),
    responses=responses(*KEITARO_CODES),
)
def list_campaigns(service: EditorService = Depends(get_editor_service)) -> list[CampaignSummaryOut]:
    """Список кампаний из Keitaro со сводкой по нашим черновикам."""
    return [mappers.summary_out(s) for s in service.list_campaigns()]


@router.get(
    "/{campaign_id}",
    response_model=CampaignOut,
    summary="Открыть кампанию с потоками",
    description=(
        "Возвращает кампанию с потоками и офферами из нашей БД, включая черновик. "
        "К Keitaro не обращается. Если потоки ещё не загружали, `streams` пуст, а `fetched_at` равен null: "
        "вызовите загрузку `POST /campaigns/{campaign_id}/fetch`."
    ),
    responses=responses("NOT_FOUND"),
)
def get_campaign(
    campaign_id: int = Path(description="Внутренний ID кампании (поле `id` из списка кампаний)"),
    service: EditorService = Depends(get_editor_service),
) -> CampaignOut:
    """Кампания с потоками из нашей БД."""
    return mappers.campaign_out(service.get_campaign(campaign_id))


@router.post(
    "/{campaign_id}/fetch",
    response_model=CampaignOut,
    summary="Загрузить потоки кампании из Keitaro",
    description=(
        "Запрашивает потоки кампании у Keitaro и обновляет нашу копию. Неопубликованные изменения (черновик) "
        "не сбрасываются: если они есть, черновик объединяется с Keitaro, а спорные пункты решаются в пользу "
        "черновика (сообщения в `notes` потока). Офферы, пропавшие в Keitaro, остаются в потоке как удалённые "
        "(`state=removed`) с возможностью вернуть. Потоки без офферов добавляются без содержимого. "
        "В Keitaro ничего не отправляет. При ошибке Keitaro наша копия не меняется."
    ),
    responses=responses("NOT_FOUND", "KEITARO_NOT_FOUND", *KEITARO_CODES),
)
def fetch_campaign(
    campaign_id: int = Path(description="Внутренний ID кампании"),
    service: EditorService = Depends(get_editor_service),
) -> CampaignOut:
    """Загрузка потоков кампании из Keitaro."""
    campaign = service.get_campaign(campaign_id)
    return mappers.campaign_out(service.fetch_campaign(campaign.keitaro_id))
