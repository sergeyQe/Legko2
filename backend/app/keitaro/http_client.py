"""Клиент настоящего Keitaro Admin API (по схеме openapi.json).

ВАЖНО: на живом Keitaro клиент не проверялся (доступа к ключу нет). Допущения помечены в коде как «не подтверждено»
и описаны в README. Поля Keitaro переводятся в нашу модель только здесь.
"""
import logging
from typing import Any, Optional

import httpx

from app.domain.states import KtOfferState
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroEditionError,
    KeitaroError,
    KeitaroNotFoundError,
    KeitaroRejectedError,
    KeitaroUnreachableError,
)
from app.keitaro.models import CatalogOffer, KtCampaign, KtReference, KtStream, NewCampaign, PushOffer

logger = logging.getLogger(__name__)

API_PREFIX = "/admin_api/v1"
CAMPAIGNS_PAGE_SIZE = 100
CAMPAIGNS_MAX_PAGES = 50  # защита от бесконечного перебора страниц
MAX_LOGGED_BODY = 2000  # сколько символов тела пишем в DEBUG-лог

# Не подтверждено на живом Keitaro: ключ действия «редирект» (список доступных действий отдаёт GET /streams_actions)
REDIRECT_ACTION_TYPE = "http"
# Не подтверждено на живом Keitaro: имя фильтра по стране (список фильтров отдаёт GET /stream_filters)
COUNTRY_FILTER_NAME = "country"
# Состояние оффера в потоке, которое считаем активным
ACTIVE_OFFER_STATE = "active"


class HttpKeitaroClient(KeitaroClient):
    """Работает через HTTP с заголовком Api-Key."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        # ключ передаётся только в заголовке и нигде не логируется
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + API_PREFIX,
            headers={"Api-Key": api_key},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        """Закрывает HTTP-соединения."""
        self._client.close()

    # ---------- низкоуровневый запрос ----------

    def _request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> Any:
        """Отправляет запрос, переводит ответы-ошибки в наши исключения и возвращает разобранный JSON."""
        logger.info("Keitaro: %s %s", method, path)
        logger.debug("Keitaro запрос: %s %s params=%s body=%s", method, path, params, json)
        try:
            response = self._client.request(method, path, params=params, json=json)
        except httpx.TimeoutException as exc:
            raise KeitaroUnreachableError("Keitaro не ответил вовремя") from exc
        except httpx.HTTPError as exc:
            raise KeitaroUnreachableError(f"Нет соединения с Keitaro: {exc.__class__.__name__}") from exc

        logger.debug("Keitaro ответ: %s %s", response.status_code, response.text[:MAX_LOGGED_BODY])
        if response.is_success:
            return self._parse_json(response)
        raise self._error_from_response(response, path)

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        """Разбирает успешный ответ; нечитаемое тело считаем сбоем Keitaro."""
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise KeitaroUnreachableError("Keitaro вернул некорректный ответ") from exc

    @staticmethod
    def _error_text(response: httpx.Response) -> str:
        """Достаёт текст ошибки Keitaro: поле error, ошибки полей {"поле": ["текст"]} или сырой текст."""
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("error"):
                return str(body["error"])
            if isinstance(body, dict) and body:
                parts = []
                for field, messages in body.items():
                    texts = messages if isinstance(messages, list) else [messages]
                    parts.append(f"{field}: {'; '.join(str(m) for m in texts)}")
                return "; ".join(parts)[:500]
        except ValueError:
            pass
        return response.text[:500] or f"HTTP {response.status_code}"

    def _error_from_response(self, response: httpx.Response, path: str) -> KeitaroError:
        """Переводит HTTP-статус ошибки в исключение."""
        status = response.status_code
        text = self._error_text(response)
        if status == 401:
            return KeitaroAuthError(text, status_code=status)
        if status == 402:
            return KeitaroEditionError(text, status_code=status)
        if status == 404:
            return KeitaroNotFoundError(text, status_code=status)
        if status >= 500:
            return KeitaroUnreachableError(text, status_code=status)
        return KeitaroRejectedError(text, status_code=status)

    # ---------- перевод полей Keitaro в нашу модель ----------

    def _offer_info(self, offer_id: int, cache: dict[int, CatalogOffer]) -> CatalogOffer:
        """Название и гео оффера (в потоке Keitaro их нет, берём из GET /offers/{id})."""
        if offer_id not in cache:
            offer = self.get_offer(offer_id)
            cache[offer_id] = offer or CatalogOffer(offer_id, f"Оффер {offer_id}", "")
        return cache[offer_id]

    def _to_stream(self, data: dict, cache: dict[int, CatalogOffer]) -> KtStream:
        """Преобразует поток Admin API (offers[].share) в KtStream (offers[].weight)."""
        offers: list[KtOfferState] = []
        for item in data.get("offers") or []:
            if item.get("state", ACTIVE_OFFER_STATE) != ACTIVE_OFFER_STATE:
                continue  # отключённые офферы не получают трафик, не показываем
            info = self._offer_info(int(item["offer_id"]), cache)
            offers.append(KtOfferState(info.offer_id, info.name, info.geo, int(item.get("share", 0))))
        return KtStream(
            stream_id=int(data["id"]),
            campaign_id=int(data.get("campaign_id", 0)),
            name=str(data.get("name", "")),
            position=int(data.get("position", 0)),
            offers=offers,
        )

    @staticmethod
    def _to_catalog_offer(data: dict) -> CatalogOffer:
        """Преобразует оффер Admin API (country — список кодов) в CatalogOffer."""
        countries = data.get("country") or []
        return CatalogOffer(int(data["id"]), str(data.get("name", "")), ", ".join(str(c) for c in countries))

    @staticmethod
    def _to_references(items: list[dict]) -> list[KtReference]:
        """Преобразует список справочника (домены, группы, источники) в KtReference."""
        return [KtReference(int(i["id"]), str(i.get("name", ""))) for i in items]

    # ---------- контракт клиента ----------

    def list_campaigns(self) -> list[KtCampaign]:
        # перебираем страницы, пока Keitaro отдаёт полные
        result: list[KtCampaign] = []
        for page in range(CAMPAIGNS_MAX_PAGES):
            items = self._request(
                "GET", "/campaigns", params={"offset": page * CAMPAIGNS_PAGE_SIZE, "limit": CAMPAIGNS_PAGE_SIZE}
            )
            result.extend(KtCampaign(int(c["id"]), str(c.get("name", "")), str(c.get("alias", ""))) for c in items)
            if len(items) < CAMPAIGNS_PAGE_SIZE:
                break
        return result

    def get_campaign(self, campaign_id: int) -> KtCampaign:
        data = self._request("GET", f"/campaigns/{campaign_id}")
        return KtCampaign(int(data["id"]), str(data.get("name", "")), str(data.get("alias", "")))

    def get_campaign_streams(self, campaign_id: int) -> list[KtStream]:
        items = self._request("GET", f"/campaigns/{campaign_id}/streams")
        cache: dict[int, CatalogOffer] = {}
        return [self._to_stream(item, cache) for item in items]

    def get_stream(self, stream_id: int) -> KtStream:
        return self._to_stream(self._request("GET", f"/streams/{stream_id}"), {})

    def replace_stream_offers(self, stream_id: int, offers: list[PushOffer]) -> KtStream:
        # Не подтверждено: PUT с массивом offers заменяет его целиком (а не дополняет)
        body = {"offers": [{"offer_id": o.offer_id, "share": o.share, "state": ACTIVE_OFFER_STATE} for o in offers]}
        return self._to_stream(self._request("PUT", f"/streams/{stream_id}", json=body), {})

    def search_offers(self, query: str) -> list[CatalogOffer]:
        # GET /offers отдаёт все офферы без фильтров, поэтому ищем по ID или названию у себя
        needle = query.strip().casefold()
        if not needle:
            return []
        offers = [self._to_catalog_offer(o) for o in self._request("GET", "/offers")]
        found = [o for o in offers if str(o.offer_id) == needle or needle in o.name.casefold()]
        return found[:20]

    def get_offer(self, offer_id: int) -> Optional[CatalogOffer]:
        try:
            return self._to_catalog_offer(self._request("GET", f"/offers/{offer_id}"))
        except KeitaroNotFoundError:
            return None

    def list_domains(self) -> list[KtReference]:
        return self._to_references(self._request("GET", "/domains"))

    def list_groups(self) -> list[KtReference]:
        return self._to_references(self._request("GET", "/groups", params={"type": "campaigns"}))

    def list_traffic_sources(self) -> list[KtReference]:
        return self._to_references(self._request("GET", "/traffic_sources"))

    def create_campaign(self, campaign: NewCampaign) -> KtCampaign:
        # необязательные поля без значения не отправляем
        body: dict[str, Any] = {"name": campaign.name, "alias": campaign.alias, "type": "weight"}
        if campaign.domain_id is not None:
            body["domain_id"] = campaign.domain_id
        if campaign.group_id is not None:
            body["group_id"] = campaign.group_id
        if campaign.source_id is not None:
            body["traffic_source_id"] = campaign.source_id
        data = self._request("POST", "/campaigns", json=body)
        return KtCampaign(int(data["id"]), str(data.get("name", campaign.name)), str(data.get("alias", campaign.alias)))

    def create_country_redirect_stream(self, campaign_id: int, name: str, country_code: str, url: str) -> KtStream:
        body = {
            "campaign_id": campaign_id,
            "name": name,
            "schema": "redirect",
            "type": "regular",
            "position": 1,
            "state": "active",
            "action_type": REDIRECT_ACTION_TYPE,
            "action_payload": url,
            "filters": [{"name": COUNTRY_FILTER_NAME, "mode": "accept", "payload": [country_code]}],
        }
        return self._to_stream(self._request("POST", "/streams", json=body), {})

    def create_offer_stream(self, campaign_id: int, name: str, offer_id: int, share: int = 100) -> KtStream:
        body = {
            "campaign_id": campaign_id,
            "name": name,
            "schema": "landings",
            "type": "default",
            "position": 2,
            "state": "active",
            "action_type": REDIRECT_ACTION_TYPE,  # Не подтверждено: поле обязательно по схеме, значение для schema=landings
            "offers": [{"offer_id": offer_id, "share": share, "state": ACTIVE_OFFER_STATE}],
        }
        return self._to_stream(self._request("POST", "/streams", json=body), {})
