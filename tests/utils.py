def add_light(client, name="0000"):
    rv = client.post("/state", json={"lights": [{"id": name, "state": "0"}]})
    assert rv.status_code == 200


def spoof_login(client):
    with client.session_transaction() as sess:
        sess["access_token"] = "a value"
