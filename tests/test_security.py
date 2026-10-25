import rag


def fake_chat(messages, **kwargs):
    return "answer", "fake-model", None


def test_public_endpoints_need_no_key(anonymous_client):
    assert anonymous_client.get("/books").status_code == 200
    assert anonymous_client.get("/search", params={"q": "love"}).status_code == 200


def test_protected_endpoints_need_key(anonymous_client):
    assert anonymous_client.post("/ask", json={"question": "Why worry?"}).status_code == 401
    assert anonymous_client.post("/agent/chat", json={"message": "hi"}).status_code == 401
    assert anonymous_client.get("/notes").status_code == 401


def test_wrong_key_rejected(anonymous_client):
    response = anonymous_client.get("/notes", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(rag, "chat", fake_chat)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")

    assert client.post("/ask", json={"question": "Why worry?"}).status_code == 200
    assert client.post("/ask", json={"question": "Why worry?"}).status_code == 200

    blocked = client.post("/ask", json={"question": "Why worry?"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_missing_server_key_denies_all(client, monkeypatch):
    monkeypatch.delenv("APP_API_KEY")
    assert client.get("/notes").status_code == 503
