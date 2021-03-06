import pytest
import house_server
import os
import tempfile
import time

from utils import *


@pytest.fixture
def application():
    application = house_server.create_application(
        {
            "TESTING": True,
            "test": False,
            "database": "sqlite://",
            "pi_key": "test_pi_key",
        }
    )
    with application.app_context():
        house_server.db.create_all()
        return application


@pytest.fixture
def client(application):
    with application.test_client() as client:
        yield client


def test_logged_out(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"This app requires you to authenticate with Google" in rv.data
    assert b"Manage light groups" not in rv.data

    rv = client.get("/edit/light/0")
    assert rv.status_code == 200
    assert b"This app requires you to authenticate with Google" in rv.data
    assert b"Manage light groups" not in rv.data


def test_logged_in(client):
    spoof_login(client)

    rv = client.get("/")
    assert rv.status_code == 200
    assert b"This app requires you to authenticate with Google" not in rv.data
    assert b"Manage light groups" in rv.data

    rv = client.get("/edit/light/0")
    assert b"This app requires you to authenticate with Google" not in rv.data


def test_bad_upload(client):
    rv = client.post(
        "/state",
        json={"lighs": [{"id": "new1", "state": "0"}, {"id": "new2", "state": "1"}]},
    )
    assert rv.status_code == 400
    rv = client.post(
        "/state",
        json={"lights": [{"d": "new1", "state": "0"}, {"id": "new2", "state": "1"}]},
    )
    assert rv.status_code == 400
    rv = client.post("/state", json={"lights": {"s": {"id": "new1", "state": "0"}}})
    assert rv.status_code == 400


def test_add_lights(client):
    add_light(client, "new1")
    add_light(client, "new2")
    spoof_login(client)

    rv = client.get("/lights")
    assert rv.data.count('<td class="clickable-link"') == 2


def test_redundant_info(client):
    add_light(client, "new1")
    time.sleep(1)
    add_light(client, "new1")

    spoof_login(client)
    rv = client.get("/edit/light/new1")
    assert rv.data.count("<li ") == 1


def test_get_commands_when_empty(client):
    # No requests made yet: no data to get, return empty list
    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": []}


def test_get_commands_when_added_light(client):
    add_light(client, "0000")
    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": []}


def test_get_commands(client):
    add_light(client, "0000")
    update_light_status(client, "0000", "on")

    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [{"id": "0000", "state": "on"}], "messages": []}


def test_get_commands_only_once(client):
    add_light(client, "0000")
    update_light_status(client, "0000", "on")

    rv = client.get("/updates?key=test_pi_key")
    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": []}


def test_get_multiple_updates(client):
    add_light(client, "0000")
    add_light(client, "0001")

    update_light_status(client, "0000", "on")
    update_light_status(client, "0001", "off")

    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert (
        rv.get_json()
        == {
            "lights": [{"id": "0000", "state": "on"}, {"id": "0001", "state": "off"}],
            "messages": [],
        }
    )


def test_get_multiple_updates_only_once(client):
    add_light(client, "0000")
    add_light(client, "0001")

    update_light_status(client, "0000", "on")
    update_light_status(client, "0001", "off")

    rv = client.get("/updates")
    rv = client.get("/updates")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": []}


def test_all_on(client):
    add_light(client, "0000")
    add_light(client, "0001")
    add_light(client, "0002")

    rv = client.post("/all", data={"state": "on"})
    assert rv.status_code == 200

    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert (
        rv.get_json()
        == {
            "lights": [
                {"id": "0000", "state": "on"},
                {"id": "0001", "state": "on"},
                {"id": "0002", "state": "on"},
            ],
            "messages": [],
        }
    )


def test_all_off(client):
    add_light(client, "0000")
    add_light(client, "0001")
    add_light(client, "0002")

    rv = client.post("/all", data={"state": "off"})
    assert rv.status_code == 200

    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert (
        rv.get_json()
        == {
            "lights": [
                {"id": "0000", "state": "off"},
                {"id": "0001", "state": "off"},
                {"id": "0002", "state": "off"},
            ],
            "messages": [],
        }
    )


def test_custom_message(client):
    rv = client.post("/messages", data={"message": "test_message"})
    assert rv.status_code == 200

    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": ["test_message"]}


def test_custom_message_only_once(client):
    rv = client.post("/messages", data={"message": "test_message"})
    assert rv.status_code == 200

    rv = client.get("/updates?key=test_pi_key")
    rv = client.get("/updates?key=test_pi_key")
    assert rv.status_code == 200
    assert rv.get_json() == {"lights": [], "messages": []}
