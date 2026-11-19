"""Представления результатов сервисов (то, что отдаём наружу: API и фронтенд)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.draft import Change
from app.domain.merge import MergeItem
from app.domain.states import DraftOffer, KtOfferState, OfferState


@dataclass
class OfferView:
    """Оффер потока с его состоянием."""

    offer: DraftOffer  # данные оффера (черновик и снимок Keitaro)
    state: OfferState  # состояние: опубликован, добавлен, убирается, удалён


@dataclass
class StreamView:
    """Поток с офферами и признаком «не опубликован»."""

    id: int  # внутренний ID потока
    keitaro_id: int  # ID потока в Keitaro
    name: str  # название потока
    position: int  # позиция в кампании
    offers: list[OfferView]  # офферы потока (пусто — поток без офферов, содержимое не показываем)
    dirty: bool  # есть неопубликованные изменения (поток «жёлтый»)
    weight_sum: int  # сумма весов активных офферов
    notes: list[str] = field(default_factory=list)  # сообщения о загрузке (появились, удалены в Keitaro)


@dataclass
class CampaignView:
    """Кампания с потоками."""

    id: int  # внутренний ID кампании
    keitaro_id: int  # ID кампании в Keitaro
    name: str  # название
    alias: str  # алиас
    fetched_at: Optional[datetime]  # когда загружали потоки из Keitaro (None — ещё не загружали)
    streams: list[StreamView]  # потоки


@dataclass
class CampaignSummary:
    """Строка списка кампаний."""

    id: int  # внутренний ID кампании
    keitaro_id: int  # ID кампании в Keitaro
    name: str  # название
    alias: str  # алиас
    fetched: bool  # загружали ли потоки из Keitaro
    streams_total: Optional[int]  # число потоков (None, если не загружали)
    streams_with_offers: Optional[int]  # число потоков с офферами (None, если не загружали)
    dirty: bool  # есть ли неопубликованные изменения хотя бы в одном потоке


@dataclass
class StepResult:
    """Результат одного шага создания кампании."""

    name: str  # шаг: campaign, stream1, stream2
    description: str  # что делает шаг (для показа пользователю)
    status: str  # ok — выполнен, failed — ошибка, skipped — не выполнялся
    error: Optional[str] = None  # текст ошибки Keitaro, если шаг не выполнен


@dataclass
class CreateReport:
    """Отчёт о создании кампании по шагам."""

    ok: bool  # все ли шаги выполнены
    campaign_id: Optional[int]  # ID созданной кампании в Keitaro (None, если кампания не создана)
    name: str  # название кампании
    alias: str  # алиас кампании
    steps: list[StepResult]  # результаты шагов


@dataclass
class ReferenceDefaults:
    """ID значений по умолчанию (домен, группа, источник); None — такого значения нет в Keitaro."""

    domain_id: Optional[int]  # ID домена по умолчанию
    group_id: Optional[int]  # ID группы по умолчанию
    source_id: Optional[int]  # ID источника по умолчанию
    missing: list[str]  # названия значений по умолчанию, которых нет в Keitaro


@dataclass
class PreviewView:
    """Предпросмотр отправки: что изменится в Keitaro и какие есть расхождения."""

    stream: StreamView  # поток после объединения с Keitaro (то, что будет отправлено)
    keitaro_offers: list[KtOfferState]  # офферы потока в Keitaro сейчас
    changes: list[Change]  # отличия от Keitaro
    merge_items: list[MergeItem]  # пункты объединения (автоматические и спорные)
    unresolved: list[MergeItem]  # спорные пункты без решения
    can_push: bool  # можно ли отправлять (нет нерешённых конфликтов и есть активные офферы)
