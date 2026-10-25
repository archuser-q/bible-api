from langchain_core.messages import AIMessage

import agent


class FakeLLM:

    def __init__(self, replies):
        self.replies = list(replies)
        self.received = []

    def invoke(self, messages):
        self.received.append(messages)
        return self.replies.pop(0)


def call_tool(name, args, call_id="call_1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_agent_uses_search_tool(client, monkeypatch):
    fake = FakeLLM([call_tool("search_verses", {"query": "worry"}), AIMessage(content="Pray instead.")])
    monkeypatch.setattr(agent, "get_llm", lambda: fake)

    data = client.post("/agent/chat", json={"message": "What about worry?"}).json()

    assert data["reply"] == "Pray instead."
    tool_result = fake.received[1][-1].content
    assert "Philippians 4:6" in tool_result


def test_agent_saves_note(client, monkeypatch):
    args = {"book": "john", "chapter": 3, "verse": 16, "content": "Remember this"}
    fake = FakeLLM([call_tool("save_note", args), AIMessage(content="Saved.")])
    monkeypatch.setattr(agent, "get_llm", lambda: fake)

    client.post("/agent/chat", json={"message": "Save a note on John 3:16"})

    notes = client.get("/notes").json()
    assert len(notes) == 1
    assert notes[0]["content"] == "Remember this"


def test_agent_remembers_thread(client, monkeypatch):
    fake = FakeLLM([AIMessage(content="Hi!"), AIMessage(content="You said hello.")])
    monkeypatch.setattr(agent, "get_llm", lambda: fake)

    first = client.post("/agent/chat", json={"message": "hello"}).json()
    client.post("/agent/chat", json={"message": "what did I say?", "thread_id": first["thread_id"]})

    second_call = [m.content for m in fake.received[1]]
    assert "hello" in second_call
    assert "Hi!" in second_call


def test_agent_stops_infinite_tool_loop(client, monkeypatch):
    fake = FakeLLM([call_tool("search_verses", {"query": "x"}, call_id=f"c{i}") for i in range(20)])
    monkeypatch.setattr(agent, "get_llm", lambda: fake)

    response = client.post("/agent/chat", json={"message": "loop"})
    assert response.status_code == 500
    assert response.json()["detail"] == "Agent dùng quá nhiều bước"
