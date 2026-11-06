import pytest
from fastapi.testclient import TestClient

from asistan import api
from asistan.agent import Agent
from tests.conftest import FakeModel, call, text_message, tool_message


@pytest.fixture()
def client(stok, monkeypatch):
    api._sessions.clear()
    script = [
        tool_message(call("record_purchase", {"product_id": 1, "quantity": 5})),
        text_message("5 çekiç stoğa eklendi."),
    ]
    monkeypatch.setattr(api, "make_agent", lambda: Agent(FakeModel(*script), stok.client()))
    return TestClient(api.app)


def test_chat_then_approve(client, stok):
    first = client.post("/chat", json={"message": "5 çekiç geldi"}).json()
    assert first["reply"] is None
    assert first["pending_action"].startswith("record_purchase")

    second = client.post(f"/chat/{first['session_id']}/decision", json={"approve": True}).json()
    assert second["reply"] == "5 çekiç stoğa eklendi."
    assert second["tools_used"] == ["record_purchase (onaylandı)"]
    assert [w[1] for w in stok.writes()] == ["/stock/purchases"]


def test_unknown_session_returns_404(client):
    assert client.post("/chat/nope/decision", json={"approve": True}).status_code == 404


def test_empty_message_is_rejected(client):
    assert client.post("/chat", json={"message": ""}).status_code == 422
