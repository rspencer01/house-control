import pytest
import house_server
import os
import tempfile


@pytest.fixture
def application():
    application = house_server.create_application(
        {"TESTING": True, "test": False, "database": "sqlite://"}
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
    assert b"Tap on a row to edit the light." not in rv.data

    rv = client.get("/edit/light/0")
    assert rv.status_code == 200
    assert b"This app requires you to authenticate with Google" in rv.data
    assert b"Tap on a row to edit the light." not in rv.data


def test_logged_in(client):
    with client.session_transaction() as sess:
        sess["access_token"] = "a value"

    rv = client.get("/")
    assert rv.status_code == 200
    assert b"This app requires you to authenticate with Google" not in rv.data
    assert b"Tap on a row to edit the light." in rv.data


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
    rv = client.post(
        "/state",
        json={"lights": [{"id": "new1", "state": "0"}, {"id": "new2", "state": "1"}]},
    )
    assert rv.status_code == 200

    with client.session_transaction() as sess:
        sess["access_token"] = "a value"
    rv = client.get("/")
    assert rv.data.count('<tr class="clickable-row"') == 2
