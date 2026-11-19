"""Заглушка Keitaro: данные, замена офферов, создание кампании, сбои и внешние правки."""
import pytest

from app.config import Settings
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroEditionError,
    KeitaroNotFoundError,
    KeitaroRejectedError,
    KeitaroUnreachableError,
)
from app.keitaro.factory import build_keitaro_client
from app.keitaro.http_client import HttpKeitaroClient
from tests.fake_keitaro import FakeKeitaroClient
from app.keitaro.models import NewCampaign, PushOffer


@pytest.fixture
def kt() -> FakeKeitaroClient:
    return FakeKeitaroClient()


def test_seed_matches_screenshots(kt):
    streams = kt.get_campaign_streams(93212)
    assert [s.name for s in streams] == ["Поток 1", "Поток 2"]
    assert streams[0].offers == []
    assert [(o.offer_id, o.weight) for o in streams[1].offers] == [(11109, 33), (11110, 33), (11111, 34)]


def test_returned_streams_are_copies(kt):
    stream = kt.get_stream(2)
    stream.offers.clear()
    assert len(kt.get_stream(2).offers) == 3


def test_unknown_campaign_and_stream_raise_not_found(kt):
    with pytest.raises(KeitaroNotFoundError):
        kt.get_campaign_streams(1)
    with pytest.raises(KeitaroNotFoundError):
        kt.get_stream(999)


def test_replace_offers_replaces_the_whole_list(kt):
    updated = kt.replace_stream_offers(2, [PushOffer(11112, 50), PushOffer(11113, 50)])
    assert [(o.offer_id, o.weight) for o in updated.offers] == [(11112, 50), (11113, 50)]
    assert [o.offer_id for o in kt.get_stream(2).offers] == [11112, 11113]


def test_replace_offers_validates_input(kt):
    with pytest.raises(KeitaroRejectedError):
        kt.replace_stream_offers(2, [])
    with pytest.raises(KeitaroRejectedError):
        kt.replace_stream_offers(2, [PushOffer(11109, 60), PushOffer(11110, 30)])
    with pytest.raises(KeitaroNotFoundError):
        kt.replace_stream_offers(2, [PushOffer(99999, 100)])
    # после ошибок поток не изменился
    assert len(kt.get_stream(2).offers) == 3


def test_search_finds_by_id_and_by_name(kt):
    assert [o.offer_id for o in kt.search_offers("11112")] == [11112]
    assert 11113 in [o.offer_id for o in kt.search_offers("dermia")]
    assert kt.search_offers("   ") == []
    assert kt.get_offer(11112).name.startswith("Oxys")
    assert kt.get_offer(1) is None


def test_references_are_available(kt):
    assert "kylovoa.com" in [d.name for d in kt.list_domains()]
    assert "FORTESTS" in [g.name for g in kt.list_groups()]
    assert "FORTESTS" in [s.name for s in kt.list_traffic_sources()]


def test_create_campaign_with_two_streams(kt):
    campaign = kt.create_campaign(NewCampaign("Тест", "test", domain_id=1, group_id=1, source_id=1))
    s1 = kt.create_country_redirect_stream(campaign.campaign_id, "Поток 1", "AU", "https://google.com")
    s2 = kt.create_offer_stream(campaign.campaign_id, "Поток 2", 11112)
    streams = kt.get_campaign_streams(campaign.campaign_id)
    assert [s.stream_id for s in streams] == [s1.stream_id, s2.stream_id]
    assert streams[0].offers == [] and [o.offer_id for o in streams[1].offers] == [11112]


def test_create_campaign_without_domain_group_and_source(kt):
    campaign = kt.create_campaign(NewCampaign("Без справочников", "bare"))
    assert campaign.alias == "bare"


def test_create_campaign_rejects_duplicate_alias_and_unknown_domain(kt):
    kt.create_campaign(NewCampaign("Тест", "test"))
    with pytest.raises(KeitaroRejectedError):
        kt.create_campaign(NewCampaign("Ещё", "test"))
    with pytest.raises(KeitaroRejectedError):
        kt.create_campaign(NewCampaign("Ещё", "other", domain_id=999))


def test_create_offer_stream_rejects_unknown_offer(kt):
    campaign = kt.create_campaign(NewCampaign("Тест", "test"))
    with pytest.raises(KeitaroRejectedError):
        kt.create_offer_stream(campaign.campaign_id, "Поток 2", 99999)


@pytest.mark.parametrize("kind,error", [
    ("network", KeitaroUnreachableError),
    ("auth", KeitaroAuthError),
    ("edition", KeitaroEditionError),
    ("not_found", KeitaroNotFoundError),
    ("rejected", KeitaroRejectedError),
])
def test_planned_failure_kinds(kt, kind, error):
    kt.fail_next(kind, "push")
    with pytest.raises(error):
        kt.replace_stream_offers(2, [PushOffer(11109, 100)])


def test_failure_fires_given_number_of_times_then_stops(kt):
    kt.fail_next("network", "push", times=2)
    for _ in range(2):
        with pytest.raises(KeitaroUnreachableError):
            kt.replace_stream_offers(2, [PushOffer(11109, 100)])
    kt.replace_stream_offers(2, [PushOffer(11109, 100)])
    assert kt.describe()["failures"] == []


def test_failure_does_not_change_data(kt):
    kt.fail_next("network", "push")
    with pytest.raises(KeitaroUnreachableError):
        kt.replace_stream_offers(2, [PushOffer(11109, 100)])
    assert len(kt.get_stream(2).offers) == 3


def test_failure_targets_are_independent(kt):
    kt.fail_next("rejected", "create_stream2")
    campaign = kt.create_campaign(NewCampaign("Тест", "test"))
    kt.create_country_redirect_stream(campaign.campaign_id, "Поток 1", "AU", "https://google.com")
    with pytest.raises(KeitaroRejectedError):
        kt.create_offer_stream(campaign.campaign_id, "Поток 2", 11112)


def test_invalid_failure_parameters_are_rejected(kt):
    with pytest.raises(ValueError):
        kt.fail_next("boom", "push")
    with pytest.raises(ValueError):
        kt.fail_next("network", "nowhere")
    with pytest.raises(ValueError):
        kt.fail_next("network", "push", times=0)


def test_external_changes_are_visible_in_stream(kt):
    kt.external_offer_added(2, 11120, 20)
    kt.external_weight_changed(2, 11110, 40)
    weights = {o.offer_id: o.weight for o in kt.get_stream(2).offers}
    assert weights == {11109: 33, 11110: 40, 11111: 34, 11120: 20}
    kt.external_offer_removed(2, 11111)
    assert 11111 not in {o.offer_id for o in kt.get_stream(2).offers}


def test_external_changes_validate_input(kt):
    with pytest.raises(KeitaroRejectedError):
        kt.external_offer_added(2, 11109, 10)
    with pytest.raises(KeitaroNotFoundError):
        kt.external_weight_changed(2, 11120, 10)
    with pytest.raises(KeitaroNotFoundError):
        kt.external_offer_removed(2, 11120)


def test_reset_restores_seed_and_clears_failures(kt):
    kt.external_weight_changed(2, 11110, 40)
    kt.fail_next("network", "push")
    kt.reset()
    assert kt.get_stream(2).offers[1].weight == 33
    assert kt.describe()["failures"] == []


def test_factory_builds_http_client_for_real_keitaro():
    client = build_keitaro_client(Settings(_env_file=None, keitaro_url="https://kt.example.com", keitaro_api_key="k",
                                          campaign_prefix="test_titov_"))
    assert isinstance(client, HttpKeitaroClient)


def test_factory_requires_campaign_prefix():
    with pytest.raises(ValueError):
        build_keitaro_client(Settings(_env_file=None, keitaro_url="https://kt.example.com", keitaro_api_key="k"))


def test_factory_requires_url_and_key():
    with pytest.raises(ValueError):
        build_keitaro_client(Settings(_env_file=None, keitaro_url="", keitaro_api_key=""))
    with pytest.raises(ValueError):
        build_keitaro_client(Settings(_env_file=None, keitaro_url="https://kt.example.com", keitaro_api_key=""))


def test_fake_get_campaign(kt):
    assert kt.get_campaign(93212).name == "test_titov_campaign2"
    with pytest.raises(KeitaroNotFoundError):
        kt.get_campaign(1)
