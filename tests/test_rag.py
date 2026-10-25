import rag
from llm import LLMError


def test_ask_sends_passages_to_llm(client, monkeypatch):
    sent = {}

    def fake_chat(messages, **kwargs):
        sent["messages"] = messages
        return "A deep answer", "fake-model", None

    monkeypatch.setattr(rag, "chat", fake_chat)

    response = client.post("/ask", json={"question": "Why do I worry?", "top_k": 1})

    assert response.status_code == 200
    assert response.json()["answer"] == "A deep answer"
    assert response.json()["model"] == "fake-model"

    prompt = sent["messages"][1]["content"]
    assert "Philippians 4:5-7" in prompt
    assert "peace of God" in prompt


def test_ask_returns_503_when_llm_fails(client, monkeypatch):
    def broken_chat(messages, **kwargs):
        raise LLMError("Dịch vụ AI tạm thời không khả dụng")

    monkeypatch.setattr(rag, "chat", broken_chat)

    response = client.post("/ask", json={"question": "Why do I worry?"})
    assert response.status_code == 503


def test_ask_validation(client):
    assert client.post("/ask", json={"question": "hi"}).status_code == 422
