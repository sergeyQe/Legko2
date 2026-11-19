"""Сервис создателя кампаний и справочников на заглушке Keitaro."""
import pytest

from app.config import Settings
from app.domain.errors import ValidationError
from app.keitaro.errors import KeitaroRejectedError, KeitaroUnreachableError
from app.keitaro.mock_client import MockKeitaroClient
from app.keitaro.models import NewCampaign
from app.services.creator_service import CreatorService
from app.services.errors import CreatePartialError
from app.services.reference_service import ReferenceService


@pytest.fixture
def kt() -> MockKeitaroClient:
    return MockKeitaroClient()


@pytest.fixture
def creator(kt) -> CreatorService:
    return CreatorService(kt)


def test_create_campaign_makes_two_streams(creator, kt):
    report = creator.create_campaign("Тест кампания", "au", 11112, domain_id=1, group_id=1, source_id=1)
    assert report.ok and report.alias == "test-kampaniya"
    assert [s.status for s in report.steps] == ["ok", "ok", "ok"]
    streams = kt.get_campaign_streams(report.campaign_id)
    assert [s.name for s in streams] == ["Поток 1", "Поток 2"]
    assert streams[0].offers == [] and [(o.offer_id, o.weight) for o in streams[1].offers] == [(11112, 100)]


def test_create_campaign_works_without_domain_group_and_source(creator):
    report = creator.create_campaign("Без справочников", "AU", 11112)
    assert report.ok


def test_invalid_input_is_rejected_before_touching_keitaro(creator, kt):
    before = len(kt.list_campaigns())
    for kwargs, field in (
        ({"name": "", "geo": "AU", "offer_id": 11112}, "name"),
        ({"name": "Тест", "geo": "AUS", "offer_id": 11112}, "geo"),
        ({"name": "Тест", "geo": "AU", "offer_id": 99999}, "offer"),
    ):
        with pytest.raises(ValidationError) as info:
            creator.create_campaign(**kwargs)
        assert info.value.field == field
    assert len(kt.list_campaigns()) == before


def test_failure_on_campaign_step_is_raised_as_is_and_nothing_is_created(creator, kt):
    kt.fail_next("network", "create_campaign")
    before = len(kt.list_campaigns())
    with pytest.raises(KeitaroUnreachableError):
        creator.create_campaign("Тест", "AU", 11112)
    assert len(kt.list_campaigns()) == before


def test_duplicate_alias_is_rejected_by_keitaro(creator):
    creator.create_campaign("Тест", "AU", 11112)
    with pytest.raises(KeitaroRejectedError):
        creator.create_campaign("Тест", "RO", 11113)


def test_failure_on_stream2_returns_partial_report_and_keeps_campaign(creator, kt):
    kt.fail_next("rejected", "create_stream2")
    with pytest.raises(CreatePartialError) as info:
        creator.create_campaign("Тест", "AU", 11112)
    report = info.value.report
    assert [s.status for s in report.steps] == ["ok", "ok", "failed"]
    assert report.steps[2].error and report.campaign_id is not None
    # кампания и поток 1 остались
    streams = kt.get_campaign_streams(report.campaign_id)
    assert [s.name for s in streams] == ["Поток 1"]


def test_failure_on_stream1_stops_before_stream2(creator, kt):
    kt.fail_next("network", "create_stream1")
    with pytest.raises(CreatePartialError) as info:
        creator.create_campaign("Тест", "AU", 11112)
    report = info.value.report
    assert [s.status for s in report.steps] == ["ok", "failed", "skipped"]
    assert kt.get_campaign_streams(report.campaign_id) == []


def test_retry_requires_stream1_to_exist(creator, kt):
    campaign = kt.create_campaign(NewCampaign("Пустая", "empty"))
    with pytest.raises(ValidationError) as info:
        creator.retry_stream2(campaign.campaign_id, 11112)
    assert info.value.field == "campaign"


def test_retry_stream2_creates_missing_stream(creator, kt):
    kt.fail_next("rejected", "create_stream2")
    with pytest.raises(CreatePartialError) as info:
        creator.create_campaign("Тест", "AU", 11112)
    campaign_id = info.value.report.campaign_id

    report = creator.retry_stream2(campaign_id, 11112, "Тест", "test")
    assert report.ok and report.steps[2].status == "ok"
    assert [s.name for s in kt.get_campaign_streams(campaign_id)] == ["Поток 1", "Поток 2"]


def test_retry_stream2_does_not_duplicate_existing_stream(creator, kt):
    first = creator.create_campaign("Тест", "AU", 11112)
    report = creator.retry_stream2(first.campaign_id, 11112)
    assert report.ok
    assert len(kt.get_campaign_streams(first.campaign_id)) == 2


def test_retry_that_fails_again_reports_partial(creator, kt):
    kt.fail_next("rejected", "create_stream2", times=2)
    with pytest.raises(CreatePartialError) as first:
        creator.create_campaign("Тест", "AU", 11112)
    with pytest.raises(CreatePartialError) as second:
        creator.retry_stream2(first.value.report.campaign_id, 11112)
    assert second.value.report.steps[2].status == "failed"


def test_defaults_are_found_by_name_ignoring_case(kt):
    refs = ReferenceService(kt, Settings(default_domain="IN.POSDK.XYZ", default_group="fortests", default_source="FORTESTS"))
    defaults = refs.defaults()
    assert (defaults.domain_id, defaults.group_id, defaults.source_id) == (1, 1, 1)
    assert defaults.missing == []


def test_missing_defaults_stay_empty_and_are_reported(kt):
    refs = ReferenceService(kt, Settings(default_domain="nope.example", default_group="FORTESTS", default_source=""))
    defaults = refs.defaults()
    assert defaults.domain_id is None and defaults.group_id == 1 and defaults.source_id is None
    assert defaults.missing == ["nope.example"]


def test_reference_lists_and_offer_search(kt):
    refs = ReferenceService(kt, Settings())
    assert refs.domains() and refs.groups() and refs.sources()
    assert [o.offer_id for o in refs.search_offers("11112")] == [11112]
