"""Схемы запросов и ответов API (поля описаны для Swagger)."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- ошибки ----------

class ErrorOut(BaseModel):
    """Единый формат ошибки."""

    code: str = Field(description="Код ошибки для программной обработки", examples=["KEITARO_UNREACHABLE"])
    message: str = Field(description="Готовый русский текст для пользователя", examples=["Keitaro не отвечает."])
    details: dict = Field(default_factory=dict, description="Подробности (состав зависит от code)")


# ---------- кампании, потоки, офферы ----------

class OfferOut(BaseModel):
    """Оффер в потоке."""

    offer_id: int = Field(description="ID оффера в Keitaro", examples=[11109])
    name: str = Field(description="Название оффера", examples=["Oxys [BEAUTY-CL-RO_0140]"])
    geo: str = Field(description="Гео оффера для подписи", examples=["Румыния"])
    state: Literal["published", "added", "removing", "removed"] = Field(
        description="published — опубликован; added — добавлен, не опубликован; "
                    "removing — убран, в Keitaro ещё есть; removed — удалён (архив обёртки)"
    )
    weight: int = Field(description="Вес в черновике, % (у убранных 0)", examples=[25])
    kt_weight: int = Field(description="Вес в Keitaro по последней загрузке, %", examples=[33])
    pinned: bool = Field(description="Вес закреплён пользователем")


class StreamOut(BaseModel):
    """Поток кампании."""

    id: int = Field(description="Внутренний ID потока (используется в маршрутах /streams/{stream_id})")
    keitaro_id: int = Field(description="ID потока в Keitaro")
    name: str = Field(description="Название потока", examples=["Поток 2"])
    position: int = Field(description="Позиция потока в кампании")
    has_offers: bool = Field(description="Есть ли у потока офферы. Потоки без офферов показываем без содержимого")
    dirty: bool = Field(description="Есть неопубликованные изменения (поток «жёлтый»)")
    weight_sum: int = Field(description="Сумма весов активных офферов, должна быть 100")
    offers: list[OfferOut] = Field(description="Офферы потока, включая убранные и удалённые")
    notes: list[str] = Field(default_factory=list, description="Сообщения по итогам загрузки из Keitaro")


class CampaignOut(BaseModel):
    """Кампания с потоками."""

    id: int = Field(description="Внутренний ID кампании")
    keitaro_id: int = Field(description="ID кампании в Keitaro", examples=[93212])
    name: str = Field(description="Название кампании", examples=["campaign 2"])
    alias: str = Field(description="Алиас кампании")
    fetched_at: Optional[datetime] = Field(description="Когда загружали потоки из Keitaro (null — ещё не загружали)")
    streams: list[StreamOut] = Field(description="Потоки кампании (пусто, пока потоки не загружены)")


class CampaignSummaryOut(BaseModel):
    """Строка списка кампаний."""

    id: int = Field(description="Внутренний ID кампании")
    keitaro_id: int = Field(description="ID кампании в Keitaro")
    name: str = Field(description="Название кампании")
    alias: str = Field(description="Алиас кампании")
    fetched: bool = Field(description="Загружали ли потоки из Keitaro")
    streams_total: Optional[int] = Field(description="Число потоков (null, если не загружали)")
    streams_with_offers: Optional[int] = Field(description="Число потоков с офферами (null, если не загружали)")
    dirty: bool = Field(description="Есть ли неопубликованные изменения хотя бы в одном потоке")


# ---------- действия над потоком ----------

class AddOfferBody(BaseModel):
    """Тело запроса добавления оффера."""

    offer_id: int = Field(description="ID оффера из базы Keitaro (выбирается через /offers/search)", examples=[11112])


class PinBody(BaseModel):
    """Тело запроса закрепления веса."""

    pinned: bool = Field(description="true — закрепить текущий вес, false — открепить", examples=[True])


class ResolutionsBody(BaseModel):
    """Решения по спорным пунктам объединения с Keitaro."""

    resolutions: dict[str, Literal["draft", "keitaro"]] = Field(
        default_factory=dict,
        description="Ключ пункта (из merge_items[].key) и выбор: draft — оставить как в черновике, keitaro — взять из Keitaro",
        examples=[{"11110:weight_changed_removed": "draft"}],
    )


class ChangeOut(BaseModel):
    """Одно отличие черновика от Keitaro."""

    kind: Literal["add", "remove", "change"] = Field(description="add — добавится, remove — уйдёт в архив, change — изменится вес")
    offer_id: int = Field(description="ID оффера")
    name: str = Field(description="Название оффера")
    from_weight: Optional[int] = Field(description="Вес в Keitaro сейчас (null — там оффера нет)")
    to_weight: int = Field(description="Вес после отправки")
    note: str = Field(description="Пояснение для пользователя")


class MergeItemOut(BaseModel):
    """Пункт объединения с Keitaro."""

    key: str = Field(description="Ключ пункта (по нему присылается решение)", examples=["11110:weight_changed_removed"])
    kind: Literal["auto", "conflict"] = Field(description="auto — объединено само, conflict — нужно решение")
    offer_id: int = Field(description="ID оффера (0 для общих сообщений)")
    message: str = Field(description="Описание для пользователя")
    resolution: Optional[Literal["draft", "keitaro"]] = Field(description="Выбранное решение для конфликта")


class KtOfferOut(BaseModel):
    """Оффер потока в Keitaro."""

    offer_id: int = Field(description="ID оффера")
    name: str = Field(description="Название оффера")
    geo: str = Field(description="Гео оффера")
    weight: int = Field(description="Вес в Keitaro, %")


class PreviewOut(BaseModel):
    """Предпросмотр отправки потока в Keitaro."""

    stream: StreamOut = Field(description="Поток после объединения с Keitaro (то, что будет отправлено)")
    keitaro_offers: list[KtOfferOut] = Field(description="Офферы потока в Keitaro сейчас")
    changes: list[ChangeOut] = Field(description="Что изменится в Keitaro")
    merge_items: list[MergeItemOut] = Field(description="Пункты объединения с Keitaro (пусто, если расхождений нет)")
    unresolved: list[MergeItemOut] = Field(description="Спорные пункты, по которым нужно решение")
    can_push: bool = Field(description="Можно ли отправлять: нет нерешённых конфликтов и есть активные офферы")


# ---------- создание кампании ----------

class CreateCampaignBody(BaseModel):
    """Данные для создания кампании."""

    name: str = Field(description="Название кампании", examples=["Тест кампания"])
    geo: str = Field(description="Код страны: две латинские буквы (приводится к верхнему регистру)", examples=["AU"])
    offer_id: int = Field(description="ID оффера для потока 2", examples=[11112])
    domain_id: Optional[int] = Field(default=None, description="ID домена; null — создать без домена")
    group_id: Optional[int] = Field(default=None, description="ID группы; null — создать без группы")
    source_id: Optional[int] = Field(default=None, description="ID источника трафика; null — создать без источника")


class RetryStream2Body(BaseModel):
    """Данные для повторного создания потока 2."""

    offer_id: int = Field(description="ID оффера для потока 2", examples=[11112])
    name: str = Field(default="", description="Название кампании (для отчёта)")
    alias: str = Field(default="", description="Алиас кампании (для отчёта)")


class StepOut(BaseModel):
    """Результат шага создания кампании."""

    name: Literal["campaign", "stream1", "stream2"] = Field(description="Шаг")
    description: str = Field(description="Что делает шаг")
    status: Literal["ok", "failed", "skipped"] = Field(description="ok — выполнен, failed — ошибка, skipped — не выполнялся")
    error: Optional[str] = Field(default=None, description="Текст ошибки Keitaro для шага со статусом failed")


class CreateReportOut(BaseModel):
    """Отчёт о создании кампании."""

    ok: bool = Field(description="Все ли шаги выполнены")
    campaign_id: Optional[int] = Field(description="ID созданной кампании в Keitaro")
    name: str = Field(description="Название кампании")
    alias: str = Field(description="Алиас кампании")
    steps: list[StepOut] = Field(description="Шаги создания")


# ---------- справочники ----------

class ReferenceOut(BaseModel):
    """Запись справочника Keitaro (домен, группа, источник)."""

    id: int = Field(description="ID записи в Keitaro")
    name: str = Field(description="Название")


class DefaultsOut(BaseModel):
    """Значения по умолчанию для формы создания кампании."""

    domain_id: Optional[int] = Field(description="ID домена по умолчанию (null — не найден в Keitaro)")
    group_id: Optional[int] = Field(description="ID группы по умолчанию")
    source_id: Optional[int] = Field(description="ID источника по умолчанию")
    missing: list[str] = Field(description="Названия значений по умолчанию, которых нет в Keitaro")


class ReferencesOut(BaseModel):
    """Справочники для формы создания кампании."""

    domains: list[ReferenceOut] = Field(description="Домены")
    groups: list[ReferenceOut] = Field(description="Группы кампаний")
    sources: list[ReferenceOut] = Field(description="Источники трафика")
    defaults: DefaultsOut = Field(description="Значения по умолчанию")


class OfferSearchOut(BaseModel):
    """Оффер из базы Keitaro."""

    offer_id: int = Field(description="ID оффера")
    name: str = Field(description="Название")
    geo: str = Field(description="Гео")


# ---------- служебные и демо ----------

class MetaOut(BaseModel):
    """Сведения о сервисе."""

    mode: Literal["mock", "real"] = Field(description="Режим Keitaro: mock — заглушка, real — настоящий Admin API")
    version: str = Field(description="Версия сервиса")


class ExternalChangeBody(BaseModel):
    """Имитация правки в Keitaro (только режим mock)."""

    scenario: Literal["offer_added", "weight_changed", "offer_removed"] = Field(
        description="offer_added — добавлен оффер, weight_changed — изменён вес, offer_removed — удалён оффер"
    )
    stream_id: int = Field(description="ID потока в Keitaro (keitaro_id)", examples=[2])
    offer_id: int = Field(description="ID оффера", examples=[11120])
    weight: int = Field(default=20, ge=0, le=100, description="Вес оффера, % (для offer_added и weight_changed)")


class FailureBody(BaseModel):
    """Планирование сбоя Keitaro (только режим mock)."""

    kind: Literal["network", "auth", "edition", "not_found", "rejected"] = Field(description="Вид сбоя")
    target: Literal["fetch", "push", "create_campaign", "create_stream1", "create_stream2"] = Field(
        description="На какой операции сработает сбой"
    )
    times: int = Field(default=1, ge=1, le=20, description="Сколько вызовов подряд завершатся ошибкой")
