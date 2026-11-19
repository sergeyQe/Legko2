"""Приёмочный сценарий из видео ТЗ по HTTP API: от загрузки потоков до закреплённого веса.

Запускается на SQLite всегда и на PostgreSQL, если задана переменная TEST_DATABASE_URL
(отдельная пустая база, например postgresql+psycopg://legko2:legko2@localhost:5432/legko2_test).
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.config import Settings, get_settings
from app.db import Base, get_session
from app.keitaro.factory import get_keitaro_client
from app.main import create_app


@pytest.fixture(params=["sqlite", "postgres"])
def scenario(request, fake_kt):
    """HTTP-клиент на выбранной БД и заглушка Keitaro."""
    if request.param == "sqlite":
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    else:
        url = os.environ.get("TEST_DATABASE_URL")
        if not url:
            pytest.skip("TEST_DATABASE_URL не задан: проверка на PostgreSQL пропущена")
        engine = create_engine(url)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        app = create_app()
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_keitaro_client] = lambda: fake_kt
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, campaign_prefix="test_titov_")
        with TestClient(app) as client:
            yield client
    Base.metadata.drop_all(engine)
    engine.dispose()


def weights(stream: dict) -> dict[int, int]:
    return {o["offer_id"]: o["weight"] for o in stream["offers"]}


def states(stream: dict) -> dict[int, str]:
    return {o["offer_id"]: o["state"] for o in stream["offers"]}


def kt_weights(fake_kt) -> dict[int, int]:
    return {o.offer_id: o.weight for o in fake_kt.get_stream(2).offers}


def test_full_scenario_from_the_video(scenario, fake_kt):
    api = scenario

    # 1. Загрузка: два потока, поток без офферов виден пустым, у второго 33/33/34
    campaign_id = next(c["id"] for c in api.get("/campaigns").json() if c["keitaro_id"] == 93212)
    campaign = api.post(f"/campaigns/{campaign_id}/fetch").json()
    flow1, flow2 = campaign["streams"]
    sid = flow2["id"]
    assert flow1["has_offers"] is False and flow1["offers"] == []
    assert weights(flow2) == {11109: 33, 11110: 33, 11111: 34} and flow2["dirty"] is False

    # 2. Добавление: веса 25% x 4, поток жёлтый, Keitaro без изменений
    added = api.post(f"/streams/{sid}/offers", json={"offer_id": 11112}).json()
    assert weights(added) == {11109: 25, 11110: 25, 11111: 25, 11112: 25} and added["dirty"] is True
    assert kt_weights(fake_kt) == {11109: 33, 11110: 33, 11111: 34}

    # 3. Обновление страницы: черновик остался, Keitaro по-прежнему с тремя офферами
    reloaded = api.get(f"/campaigns/{campaign_id}").json()["streams"][1]
    assert reloaded["dirty"] is True and len(reloaded["offers"]) == 4
    assert len(fake_kt.get_stream(2).offers) == 3

    # 4. Cancel: добавленный оффер исчез, поток снова белый
    cancelled = api.post(f"/streams/{sid}/cancel").json()
    assert weights(cancelled) == {11109: 33, 11110: 33, 11111: 34} and cancelled["dirty"] is False

    # 5. Добавление и Push: в Keitaro четыре оффера по 25%
    api.post(f"/streams/{sid}/offers", json={"offer_id": 11112})
    pushed = api.post(f"/streams/{sid}/push", json={}).json()
    assert pushed["dirty"] is False
    assert kt_weights(fake_kt) == {11109: 25, 11110: 25, 11111: 25, 11112: 25}

    # 6. Remove: оффер серый с 0%, у остальных 33/33/34
    removed = api.delete(f"/streams/{sid}/offers/11112").json()
    assert states(removed)[11112] == "removing" and removed["dirty"] is True
    assert weights(removed) == {11109: 33, 11110: 33, 11111: 34, 11112: 0}

    # 7. Push: оффер исчез из Keitaro, у нас остался в архиве (Removed)
    pushed = api.post(f"/streams/{sid}/push", json={}).json()
    assert 11112 not in kt_weights(fake_kt) and states(pushed)[11112] == "removed" and not pushed["dirty"]

    # 8. Bring Back и Push: оффер вернулся в Keitaro
    back = api.post(f"/streams/{sid}/offers/11112/restore").json()
    assert back["dirty"] is True and states(back)[11112] == "added"
    api.post(f"/streams/{sid}/push", json={})
    assert set(kt_weights(fake_kt)) == {11109, 11110, 11111, 11112}

    # 9. Оффер удалили прямо в Keitaro: после Fetch он Removed с возможностью вернуть
    fake_kt.external_offer_removed(2, 11112)
    fetched = api.post(f"/campaigns/{campaign_id}/fetch").json()["streams"][1]
    assert states(fetched)[11112] == "removed"
    # в Keitaro осталось 75%: доли пересчитаны до 100%, поток требует отправки, об этом есть сообщение
    assert fetched["weight_sum"] == 100 and fetched["dirty"] is True
    assert any("сумма долей 75%" in note for note in fetched["notes"])
    api.post(f"/streams/{sid}/push", json={})
    assert kt_weights(fake_kt) == {11109: 33, 11110: 33, 11111: 34}

    # 10. Пин: закреплённый вес держится при добавлении и удалении, остальные делят остаток
    api.post(f"/streams/{sid}/offers/11112/restore")
    pinned = api.put(f"/streams/{sid}/offers/11109/pin", json={"pinned": True}).json()
    assert next(o for o in pinned["offers"] if o["offer_id"] == 11109)["pinned"] is True
    pinned_weight = weights(pinned)[11109]
    after_remove = api.delete(f"/streams/{sid}/offers/11112").json()
    assert weights(after_remove)[11109] == pinned_weight
    others = [w for oid, w in weights(after_remove).items() if oid not in (11109, 11112)]
    assert sum(others) + pinned_weight == 100
    final = api.post(f"/streams/{sid}/push", json={}).json()
    assert kt_weights(fake_kt)[11109] == pinned_weight and sum(kt_weights(fake_kt).values()) == 100
    assert final["weight_sum"] == 100 and final["dirty"] is False


def test_parallel_fetch_of_the_same_campaign_does_not_fail(fake_kt):
    """Двойной клик или две вкладки: одновременные загрузки одной кампании обе проходят (только PostgreSQL).

    На каждый запрос открывается своя сессия, как в работающем приложении.
    """
    import threading

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL не задан: проверка параллельной загрузки пропущена")
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    def session_per_request():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = session_per_request
    app.dependency_overrides[get_keitaro_client] = lambda: fake_kt
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, campaign_prefix="test_titov_")
    try:
        with TestClient(app) as client:
            campaign_id = next(c["id"] for c in client.get("/campaigns").json() if c["keitaro_id"] == 93212)
            for _ in range(5):  # несколько раундов: гонка срабатывает не всегда
                Base.metadata.drop_all(engine)
                Base.metadata.create_all(engine)
                campaign_id = next(c["id"] for c in client.get("/campaigns").json() if c["keitaro_id"] == 93212)
                results: list[int] = []
                barrier = threading.Barrier(2)

                def load():
                    barrier.wait()
                    results.append(client.post(f"/campaigns/{campaign_id}/fetch").status_code)

                threads = [threading.Thread(target=load) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                assert results == [200, 200]
                assert len(client.get(f"/campaigns/{campaign_id}").json()["streams"]) == 2
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_scenario_merge_and_error_over_http(scenario, fake_kt):
    api = scenario
    campaign_id = next(c["id"] for c in api.get("/campaigns").json() if c["keitaro_id"] == 93212)
    sid = api.post(f"/campaigns/{campaign_id}/fetch").json()["streams"][1]["id"]

    # правка в Keitaro и конфликт: оффер убран у нас, а там изменён вес
    api.delete(f"/streams/{sid}/offers/11110")
    fake_kt.external_weight_changed(2, 11110, 40)
    fake_kt.external_offer_added(2, 11120, 20)
    preview = api.post(f"/streams/{sid}/preview", json={}).json()
    assert preview["can_push"] is False
    assert {i["key"] for i in preview["merge_items"]} == {"11110:weight_changed_removed", "11120:added_in_kt"}

    # ошибка сети при отправке: черновик цел, повтор проходит
    resolutions = {"resolutions": {"11110:weight_changed_removed": "keitaro"}}
    fake_kt.fail_next("network", "push")
    assert api.post(f"/streams/{sid}/push", json=resolutions).status_code == 502
    assert api.get(f"/campaigns/{campaign_id}").json()["streams"][1]["dirty"] is True
    assert api.post(f"/streams/{sid}/push", json=resolutions).status_code == 200
    assert kt_weights(fake_kt)[11110] == 40 and 11120 in kt_weights(fake_kt)
