"""HTTP API: сценарий из видео, формат ошибок, демо-маршруты и описание Swagger."""
import pytest
from fastapi.testclient import TestClient

from app.api.docs import ERROR_CATALOG
from app.config import Settings
from app.db import get_session
from app.keitaro.factory import get_keitaro_client
from app.main import create_app

CAMPAIGN_KT_ID = 93212


def fetch(api) -> dict:
    """Загружает кампанию со скриншотов и возвращает её."""
    campaigns = api.get("/campaigns").json()
    campaign = next(c for c in campaigns if c["keitaro_id"] == CAMPAIGN_KT_ID)
    response = api.post(f"/campaigns/{campaign['id']}/fetch")
    assert response.status_code == 200
    return response.json()


def stream2(api) -> dict:
    """Поток 2 кампании."""
    campaign = fetch(api)
    return next(s for s in campaign["streams"] if s["name"] == "Поток 2")


def weights(stream: dict) -> dict[int, int]:
    return {o["offer_id"]: o["weight"] for o in stream["offers"]}


def assert_error(response, status: int, code: str) -> dict:
    """Проверяет единый формат ошибки."""
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code and body["message"]
    return body


# ---------- служебные ----------

def test_health_and_meta(api):
    assert api.get("/health").json() == {"status": "ok"}
    meta = api.get("/meta").json()
    assert meta["mode"] == "mock" and meta["version"] and meta["keitaro_url"] == ""


# ---------- сценарий из видео ----------

def test_campaign_list_and_fetch(api):
    campaigns = api.get("/campaigns").json()
    target = next(c for c in campaigns if c["keitaro_id"] == CAMPAIGN_KT_ID)
    assert target["fetched"] is False and target["streams_total"] is None

    campaign = fetch(api)
    assert [s["name"] for s in campaign["streams"]] == ["Поток 1", "Поток 2"]
    assert campaign["streams"][0]["has_offers"] is False and campaign["streams"][0]["offers"] == []
    assert weights(campaign["streams"][1]) == {11109: 33, 11110: 33, 11111: 34}
    assert campaign["fetched_at"] is not None
    assert api.get(f"/campaigns/{campaign['id']}").json()["streams"][1]["dirty"] is False


def test_add_offer_is_a_draft_and_push_sends_it(api, mock_kt):
    stream = stream2(api)
    sid = stream["id"]

    added = api.post(f"/streams/{sid}/offers", json={"offer_id": 11112}).json()
    assert weights(added) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}
    assert added["dirty"] is True and added["weight_sum"] == 100
    assert next(o for o in added["offers"] if o["offer_id"] == 11112)["state"] == "added"
    assert len(mock_kt.get_stream(2).offers) == 3  # Keitaro не изменён

    assert api.post(f"/streams/{sid}/cancel").json()["dirty"] is False

    api.post(f"/streams/{sid}/offers", json={"offer_id": 11112})
    pushed = api.post(f"/streams/{sid}/push", json={}).json()
    assert pushed["dirty"] is False
    assert {o.offer_id: o.weight for o in mock_kt.get_stream(2).offers} == {11109: 25, 11110: 25, 11111: 25, 11112: 25}


def test_remove_restore_and_archive_flow(api, mock_kt):
    sid = stream2(api)["id"]
    removed = api.delete(f"/streams/{sid}/offers/11109").json()
    assert weights(removed)[11109] == 0 and removed["dirty"]
    api.post(f"/streams/{sid}/push", json={})
    assert {o.offer_id for o in mock_kt.get_stream(2).offers} == {11110, 11111}

    campaign = fetch(api)
    archived = next(o for s in campaign["streams"] for o in s["offers"] if o["offer_id"] == 11109)
    assert archived["state"] == "removed"

    restored = api.post(f"/streams/{sid}/offers/11109/restore").json()
    assert next(o for o in restored["offers"] if o["offer_id"] == 11109)["state"] == "added"


def test_pin_is_kept_and_unpin_works(api):
    sid = stream2(api)["id"]
    pinned = api.put(f"/streams/{sid}/offers/11109/pin", json={"pinned": True}).json()
    assert next(o for o in pinned["offers"] if o["offer_id"] == 11109)["pinned"] is True
    after = api.delete(f"/streams/{sid}/offers/11111").json()
    assert weights(after) == {11109: 33, 11110: 67, 11111: 0}
    unpinned = api.put(f"/streams/{sid}/offers/11109/pin", json={"pinned": False}).json()
    assert weights(unpinned) == {11109: 50, 11110: 50, 11111: 0}


def test_preview_does_not_change_anything(api, mock_kt):
    sid = stream2(api)["id"]
    api.post(f"/streams/{sid}/offers", json={"offer_id": 11112})
    preview = api.post(f"/streams/{sid}/preview", json={}).json()
    assert preview["can_push"] is True and preview["merge_items"] == []
    assert {c["kind"] for c in preview["changes"]} == {"add", "change"}
    assert [o["offer_id"] for o in preview["keitaro_offers"]] == [11109, 11110, 11111]
    assert len(mock_kt.get_stream(2).offers) == 3


# ---------- merge и ошибки ----------

def test_merge_conflict_flow_over_http(api, mock_kt):
    sid = stream2(api)["id"]
    api.delete(f"/streams/{sid}/offers/11110")
    assert api.post("/mock/external-change", json={"scenario": "weight_changed", "stream_id": 2, "offer_id": 11110, "weight": 40}).status_code == 200

    preview = api.post(f"/streams/{sid}/preview", json={}).json()
    assert preview["can_push"] is False
    assert [i["key"] for i in preview["unresolved"]] == ["11110:weight_changed_removed"]

    body = assert_error(api.post(f"/streams/{sid}/push", json={}), 409, "MERGE_CONFLICT")
    assert body["details"]["conflicts"][0]["key"] == "11110:weight_changed_removed"

    pushed = api.post(f"/streams/{sid}/push", json={"resolutions": {"11110:weight_changed_removed": "keitaro"}})
    assert pushed.status_code == 200
    assert {o.offer_id: o.weight for o in mock_kt.get_stream(2).offers} == {11109: 30, 11110: 40, 11111: 30}


def test_keitaro_failure_returns_502_and_keeps_draft(api, mock_kt):
    sid = stream2(api)["id"]
    api.post(f"/streams/{sid}/offers", json={"offer_id": 11112})
    api.post("/mock/failure", json={"kind": "network", "target": "push"})
    body = assert_error(api.post(f"/streams/{sid}/push", json={}), 502, "KEITARO_UNREACHABLE")
    assert body["details"] == {"retryable": True}
    assert api.get(f"/campaigns/{fetch_id(api)}").json()["streams"][1]["dirty"] is True
    assert api.post(f"/streams/{sid}/push", json={}).status_code == 200


def fetch_id(api) -> int:
    return next(c["id"] for c in api.get("/campaigns").json() if c["keitaro_id"] == CAMPAIGN_KT_ID)


@pytest.mark.parametrize("kind,status,code", [
    ("auth", 502, "KEITARO_AUTH"),
    ("edition", 502, "KEITARO_EDITION"),
    ("not_found", 409, "KEITARO_NOT_FOUND"),
    ("rejected", 422, "KEITARO_REJECTED"),
])
def test_keitaro_error_kinds_are_mapped(api, kind, status, code):
    sid = stream2(api)["id"]
    api.post("/mock/failure", json={"kind": kind, "target": "push"})
    assert_error(api.post(f"/streams/{sid}/push", json={}), status, code)


def test_rejected_error_keeps_keitaro_text(api):
    sid = stream2(api)["id"]
    api.post("/mock/failure", json={"kind": "rejected", "target": "push"})
    body = assert_error(api.post(f"/streams/{sid}/push", json={}), 422, "KEITARO_REJECTED")
    assert body["details"]["keitaro_error"] and body["details"]["keitaro_error"] in body["message"]


def test_domain_errors_are_mapped(api):
    sid = stream2(api)["id"]
    assert_error(api.post("/streams/999/offers", json={"offer_id": 11112}), 404, "NOT_FOUND")
    assert_error(api.get("/campaigns/999"), 404, "NOT_FOUND")
    assert_error(api.post(f"/streams/{sid}/offers", json={"offer_id": 99999}), 404, "NOT_FOUND")
    assert_error(api.post(f"/streams/{sid}/offers", json={"offer_id": 11109}), 409, "OFFER_STATE_ERROR")
    assert_error(api.delete(f"/streams/{sid}/offers/12345"), 404, "NOT_FOUND")

    api.put(f"/streams/{sid}/offers/11109/pin", json={"pinned": True})
    api.put(f"/streams/{sid}/offers/11110/pin", json={"pinned": True})
    api.put(f"/streams/{sid}/offers/11111/pin", json={"pinned": True})
    assert_error(api.delete(f"/streams/{sid}/offers/11111"), 422, "WEIGHTS_INVALID")


def test_push_without_active_offers_returns_empty_stream_error(api):
    sid = stream2(api)["id"]
    for offer_id in (11109, 11110, 11111):
        api.delete(f"/streams/{sid}/offers/{offer_id}")
    assert_error(api.post(f"/streams/{sid}/push", json={}), 422, "EMPTY_STREAM")


def test_request_validation_uses_common_error_format(api):
    sid = stream2(api)["id"]
    body = assert_error(api.post(f"/streams/{sid}/offers", json={"offer_id": "abc"}), 422, "VALIDATION")
    assert body["details"]["errors"][0]["field"] == "offer_id"
    assert_error(api.post(f"/streams/{sid}/push", json={"resolutions": {"x": "maybe"}}), 422, "VALIDATION")


def test_too_large_ids_are_validation_errors_not_server_errors(api):
    huge = 99999999999999999999
    for response in (
        api.get(f"/campaigns/{huge}"),
        api.post(f"/campaigns/{huge}/fetch"),
        api.post(f"/streams/{huge}/cancel"),
        api.delete(f"/streams/1/offers/{huge}"),
        api.post("/streams/1/offers", json={"offer_id": huge}),
        api.post("/campaign-creator/campaigns", json={"name": "Т", "geo": "AU", "offer_id": 11112, "domain_id": huge}),
    ):
        body = assert_error(response, 422, "VALIDATION")
        assert body["details"]["errors"]
    assert_error(api.get("/campaigns/0"), 422, "VALIDATION")


def test_framework_errors_use_the_common_format(api):
    body = assert_error(api.get("/no/such/path"), 404, "NOT_FOUND")
    assert body["message"] == "Такого адреса нет."
    assert_error(api.put("/health"), 405, "METHOD_NOT_ALLOWED")


def test_error_texts_are_in_russian(api):
    assert api.get("/campaigns/999").json()["message"] == "Кампания 999 не найдена."
    sid = stream2(api)["id"]
    assert api.post(f"/streams/{sid}/offers", json={"offer_id": 99999}).json()["message"] == "Оффер 99999 не найден."
    body = api.post(f"/streams/{sid}/offers", json={"offer_id": "abc"}).json()
    assert body["details"]["errors"][0]["message"] == "Нужно целое число."
    missing = api.post(f"/streams/{sid}/offers", json={}).json()
    assert missing["details"]["errors"][0]["message"] == "Поле обязательно."


def test_retry_stream2_report_uses_detailed_labels_when_context_is_given(api, mock_kt):
    api.post("/mock/failure", json={"kind": "rejected", "target": "create_stream2"})
    created = api.post("/campaign-creator/campaigns", json={"name": "Лето", "geo": "AU", "offer_id": 11112})
    campaign_id = created.json()["details"]["campaign_id"]
    retry = api.post(
        f"/campaign-creator/campaigns/{campaign_id}/retry-stream2",
        json={"offer_id": 11112, "name": "Лето", "alias": "leto", "geo": "au"},
    ).json()
    texts = [s["description"] for s in retry["steps"]]
    assert texts[0] == "Кампания «Лето» (алиас leto)"
    assert texts[1].startswith("Поток 1: страна AU принимается")


def test_unexpected_error_is_hidden_behind_generic_response(session):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session

    def broken():
        raise RuntimeError("секретные подробности")

    app.dependency_overrides[get_keitaro_client] = broken
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/campaigns")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR" and "секретные" not in response.text


def test_unexpected_error_still_carries_cors_header_for_allowed_origin(session):
    # без заголовка браузер показал бы «заблокировано CORS» вместо нашего сообщения об ошибке
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_keitaro_client] = lambda: (_ for _ in ()).throw(RuntimeError("сбой"))
    with TestClient(app, raise_server_exceptions=False) as client:
        allowed = client.get("/campaigns", headers={"Origin": "http://localhost:5173"})
        foreign = client.get("/campaigns", headers={"Origin": "http://evil.example"})
    assert allowed.status_code == 500 and allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in foreign.headers


# ---------- создание кампании и справочники ----------

def test_references_and_offer_search(api):
    refs = api.get("/references").json()
    assert "in.posdk.xyz" in [d["name"] for d in refs["domains"]]
    assert refs["defaults"] == {"domain_id": 1, "group_id": 1, "source_id": 1, "missing": []}
    assert [o["offer_id"] for o in api.get("/offers/search", params={"q": "11112"}).json()] == [11112]
    assert api.get("/offers/search").json() == []


def test_create_campaign_and_open_it_in_editor(api):
    response = api.post("/campaign-creator/campaigns", json={
        "name": "Тест кампания", "geo": "au", "offer_id": 11112, "domain_id": 1, "group_id": 1, "source_id": 1,
    })
    assert response.status_code == 201
    report = response.json()
    assert report["ok"] and report["alias"] == "test-kampaniya"
    assert [s["status"] for s in report["steps"]] == ["ok", "ok", "ok"]

    created = next(c for c in api.get("/campaigns").json() if c["keitaro_id"] == report["campaign_id"])
    campaign = api.post(f"/campaigns/{created['id']}/fetch").json()
    assert [s["name"] for s in campaign["streams"]] == ["Поток 1", "Поток 2"]
    assert weights(campaign["streams"][1]) == {11112: 100}


def test_create_campaign_without_domain_group_source(api):
    response = api.post("/campaign-creator/campaigns", json={"name": "Без всего", "geo": "RO", "offer_id": 11113})
    assert response.status_code == 201


def test_create_campaign_validation_errors(api):
    for body, field in (
        ({"name": "", "geo": "AU", "offer_id": 11112}, "name"),
        ({"name": "Тест", "geo": "AUS", "offer_id": 11112}, "geo"),
        ({"name": "Тест", "geo": "AU", "offer_id": 99999}, "offer"),
    ):
        error = assert_error(api.post("/campaign-creator/campaigns", json=body), 422, "VALIDATION")
        assert error["details"]["field"] == field


def test_partial_creation_returns_steps_and_can_be_retried(api, mock_kt):
    api.post("/mock/failure", json={"kind": "rejected", "target": "create_stream2"})
    response = api.post("/campaign-creator/campaigns", json={"name": "Частично", "geo": "AU", "offer_id": 11112})
    body = assert_error(response, 502, "CREATE_PARTIAL")
    assert [s["status"] for s in body["details"]["steps"]] == ["ok", "ok", "failed"]
    # у каждого шага есть описание для показа пользователю
    assert all(s["description"] for s in body["details"]["steps"])
    campaign_id = body["details"]["campaign_id"]

    retry = api.post(f"/campaign-creator/campaigns/{campaign_id}/retry-stream2", json={"offer_id": 11112})
    assert retry.status_code == 200 and retry.json()["ok"] is True
    assert [s.name for s in mock_kt.get_campaign_streams(campaign_id)] == ["Поток 1", "Поток 2"]


# ---------- демо-маршруты ----------

def test_mock_state_and_reset(api, mock_kt):
    api.post("/mock/external-change", json={"scenario": "offer_added", "stream_id": 2, "offer_id": 11120, "weight": 20})
    assert 11120 in [o["offer_id"] for s in api.get("/mock/state").json()["streams"] for o in s["offers"]]
    api.post("/mock/failure", json={"kind": "network", "target": "fetch", "times": 3})
    assert api.get("/mock/state").json()["failures"][0]["times"] == 3
    api.post("/mock/reset")
    state = api.get("/mock/state").json()
    assert state["failures"] == [] and 11120 not in [o["offer_id"] for s in state["streams"] for o in s["offers"]]


def test_mock_reset_also_clears_our_copy_of_the_data(api):
    sid = stream2(api)["id"]
    api.post(f"/streams/{sid}/offers", json={"offer_id": 11112})
    api.post(f"/streams/{sid}/push", json={})

    assert api.post("/mock/reset").status_code == 200
    summary = next(c for c in api.get("/campaigns").json() if c["keitaro_id"] == CAMPAIGN_KT_ID)
    assert summary["fetched"] is False and summary["dirty"] is False
    # после повторной загрузки поток снова как на скриншотах: 33/33/34, без лишних удалённых офферов
    stream = stream2(api)
    assert weights(stream) == {11109: 33, 11110: 33, 11111: 34} and not stream["dirty"]


def test_mock_routes_are_absent_in_real_mode(monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(keitaro_mode="real", keitaro_url="https://x", keitaro_api_key="k"))
    app = create_app()
    assert not any(path.startswith("/mock") for path in app.openapi()["paths"])


# ---------- Swagger ----------

def test_every_endpoint_is_documented(api):
    spec = api.get("/openapi.json").json()
    assert spec["paths"]
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            assert operation.get("summary"), f"{method.upper()} {path}: нет summary"
            assert len(operation.get("description", "")) > 30, f"{method.upper()} {path}: нет описания"
            assert operation.get("tags"), f"{method.upper()} {path}: нет тега"


def test_error_codes_listed_in_swagger_exist_in_catalog(api):
    spec = api.get("/openapi.json").json()
    documented = " ".join(
        r.get("description", "")
        for methods in spec["paths"].values() for op in methods.values() for r in op["responses"].values()
    )
    for code in ERROR_CATALOG:
        assert code in documented, f"код {code} не описан ни в одном эндпоинте"
