"""HTTP-клиент Keitaro на подставных ответах (по схеме openapi.json), без реальной сети."""
import json

import httpx
import pytest

from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroEditionError,
    KeitaroNotFoundError,
    KeitaroRejectedError,
    KeitaroUnreachableError,
)
from app.keitaro.http_client import HttpKeitaroClient
from app.keitaro.models import NewCampaign, PushOffer

BASE = "https://kt.example.com"
OFFERS = {
    11109: {"id": 11109, "name": "Oxys [RO]", "country": ["RO"]},
    11110: {"id": 11110, "name": "Oxys [CO]", "country": ["CO", "CL"]},
}


def make_client(handler):
    """Клиент с подменённым транспортом; handler получает httpx.Request и возвращает httpx.Response."""
    return HttpKeitaroClient(BASE, "secret-key", transport=httpx.MockTransport(handler))


def stream_json(stream_id=2):
    return {
        "id": stream_id, "campaign_id": 93212, "name": "Flow 2", "position": 2,
        "offers": [
            {"id": 1, "stream_id": stream_id, "offer_id": 11109, "state": "active", "share": 33},
            {"id": 2, "stream_id": stream_id, "offer_id": 11110, "state": "active", "share": 67},
            {"id": 3, "stream_id": stream_id, "offer_id": 11111, "state": "disabled", "share": 0},
        ],
    }


def test_get_campaign_reads_one_campaign():
    client = make_client(lambda request: httpx.Response(200, json={"id": 93212, "name": "test_titov_campaign1", "alias": "abc"}))
    campaign = client.get_campaign(93212)
    assert (campaign.campaign_id, campaign.name, campaign.alias) == (93212, "test_titov_campaign1", "abc")


def test_get_campaign_not_found_is_translated():
    client = make_client(lambda request: httpx.Response(404, json={"error": "Entity not found"}))
    with pytest.raises(KeitaroNotFoundError):
        client.get_campaign(1)


def test_streams_are_mapped_with_offer_names_and_only_active_offers():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/admin_api/v1/campaigns/93212/streams":
            return httpx.Response(200, json=[stream_json(), {"id": 1, "campaign_id": 93212, "name": "Flow 1", "position": 1}])
        offer_id = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json=OFFERS[offer_id])

    streams = make_client(handler).get_campaign_streams(93212)
    assert [s.name for s in streams] == ["Flow 2", "Flow 1"]
    assert [(o.offer_id, o.name, o.geo, o.weight) for o in streams[0].offers] == [
        (11109, "Oxys [RO]", "RO", 33), (11110, "Oxys [CO]", "CO, CL", 67)]
    assert streams[1].offers == []
    # ключ передаётся заголовком Api-Key
    assert all(r.headers["Api-Key"] == "secret-key" for r in seen)
    # название каждого оффера запрашивается один раз
    assert [r.url.path for r in seen].count("/admin_api/v1/offers/11109") == 1


def test_replace_offers_sends_put_with_full_list():
    captured = {}

    def handler(request):
        if request.method == "PUT":
            captured["body"] = json.loads(request.content)
            captured["path"] = request.url.path
            return httpx.Response(200, json=stream_json())
        return httpx.Response(200, json=OFFERS[int(request.url.path.rsplit("/", 1)[1])])

    make_client(handler).replace_stream_offers(2, [PushOffer(11109, 50), PushOffer(11110, 50)])
    assert captured["path"] == "/admin_api/v1/streams/2"
    assert captured["body"] == {"offers": [
        {"offer_id": 11109, "share": 50, "state": "active"},
        {"offer_id": 11110, "share": 50, "state": "active"},
    ]}


@pytest.mark.parametrize("status,error", [
    (401, KeitaroAuthError), (402, KeitaroEditionError), (404, KeitaroNotFoundError),
    (400, KeitaroRejectedError), (500, KeitaroUnreachableError), (503, KeitaroUnreachableError),
    (422, KeitaroRejectedError),
])
def test_error_statuses_are_translated(status, error):
    client = make_client(lambda request: httpx.Response(status, json={"error": "из Keitaro"}))
    with pytest.raises(error) as info:
        client.get_stream(2)
    assert info.value.message == "из Keitaro"
    assert info.value.status_code == status


def test_field_validation_errors_are_joined_into_text():
    client = make_client(lambda request: httpx.Response(
        422, json={"name": ["Name has already been used in the archive"]}))
    with pytest.raises(KeitaroRejectedError) as info:
        client.get_stream(2)
    assert info.value.message == "name: Name has already been used in the archive"


def test_error_without_json_body_uses_raw_text():
    client = make_client(lambda request: httpx.Response(400, text="Bad things"))
    with pytest.raises(KeitaroRejectedError) as info:
        client.get_stream(2)
    assert info.value.message == "Bad things"


def test_timeout_and_connection_errors_become_unreachable():
    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def refused(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(KeitaroUnreachableError):
        make_client(timeout).get_stream(2)
    with pytest.raises(KeitaroUnreachableError):
        make_client(refused).get_stream(2)


def test_search_filters_offers_by_id_and_name_on_our_side():
    client = make_client(lambda request: httpx.Response(200, json=list(OFFERS.values())))
    assert [o.offer_id for o in client.search_offers("11110")] == [11110]
    assert [o.offer_id for o in client.search_offers("oxys")] == [11109, 11110]
    assert client.search_offers("") == []


def test_get_offer_returns_none_when_not_found():
    client = make_client(lambda request: httpx.Response(404, json={"error": "Entity not found"}))
    assert client.get_offer(5) is None


def test_references_are_mapped_and_groups_request_campaign_type():
    seen = {}

    def handler(request):
        seen[request.url.path] = dict(request.url.params)
        return httpx.Response(200, json=[{"id": 1, "name": "FORTESTS"}])

    client = make_client(handler)
    assert client.list_domains()[0].name == "FORTESTS"
    assert client.list_groups()[0].ref_id == 1
    assert client.list_traffic_sources()[0].name == "FORTESTS"
    assert seen["/admin_api/v1/groups"] == {"type": "campaigns"}


def test_campaigns_are_loaded_page_by_page():
    pages = []

    def handler(request):
        offset = int(request.url.params["offset"])
        pages.append(offset)
        count = 100 if offset == 0 else 3
        return httpx.Response(200, json=[{"id": offset + i, "name": f"c{i}", "alias": f"a{i}"} for i in range(count)])

    campaigns = make_client(handler).list_campaigns()
    assert len(campaigns) == 103 and pages == [0, 100]


def test_create_campaign_omits_empty_optional_fields():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"id": 7, "name": "Тест", "alias": "test"})

    client = make_client(handler)
    created = client.create_campaign(NewCampaign("Тест", "test"))
    client.create_campaign(NewCampaign("Тест", "test2", domain_id=1, group_id=2, source_id=3))
    assert created.campaign_id == 7
    assert bodies[0] == {"name": "Тест", "alias": "test", "type": "weight"}
    assert bodies[1]["domain_id"] == 1 and bodies[1]["group_id"] == 2 and bodies[1]["traffic_source_id"] == 3


def test_create_streams_send_expected_bodies():
    bodies = []

    def handler(request):
        if request.method == "POST":
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"id": 50 + len(bodies), "campaign_id": 7, "name": "x", "position": 1, "offers": []})
        return httpx.Response(200, json=OFFERS[11109])

    client = make_client(handler)
    client.create_country_redirect_stream(7, "Поток 1", "AU", "https://google.com")
    client.create_offer_stream(7, "Поток 2", 11109)
    redirect, offer = bodies
    assert redirect["schema"] == "redirect" and redirect["type"] == "regular"
    assert redirect["filters"] == [{"name": "country", "mode": "accept", "payload": ["AU"]}]
    assert redirect["action_payload"] == "https://google.com"
    assert offer["schema"] == "landings" and offer["type"] == "default"
    assert offer["offers"] == [{"offer_id": 11109, "share": 100, "state": "active"}]


def test_non_json_success_body_is_reported_as_keitaro_failure():
    client = make_client(lambda request: httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(KeitaroUnreachableError):
        client.list_domains()


def test_close_can_be_called():
    make_client(lambda request: httpx.Response(200, json=[])).close()


def test_api_key_is_not_logged(caplog):
    caplog.set_level("DEBUG")
    client = make_client(lambda request: httpx.Response(200, json=[]))
    client.list_domains()
    assert "secret-key" not in caplog.text
