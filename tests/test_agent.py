import json

import httpx

from asistan.agent import Agent
from asistan.llm import OpenAICompatibleModel
from tests.conftest import FakeModel, call, text_message, tool_message


def last_tool_result(model):
    tool_messages = [m for m in model.seen[-1] if m["role"] == "tool"]
    return json.loads(tool_messages[-1]["content"])


def test_read_question_uses_tool_and_answers(stok):
    model = FakeModel(tool_message(call("search_products", {"query": "çekiç"})), text_message("Stokta 10 çekiç var."))
    reply = Agent(model, stok.client()).ask("Kaç çekiç kaldı?")

    assert reply.text == "Stokta 10 çekiç var."
    assert reply.tool_log == ["search_products"]
    assert stok.requests[0][:3] == ("GET", "/products", {"search": "çekiç"})
    assert last_tool_result(model)[0]["name"] == "Çekiç"


def test_write_tool_waits_for_approval(stok):
    sale = {"items": [{"product_id": 1, "quantity": 2}], "payment_type": "cash"}
    model = FakeModel(tool_message(call("create_sale", sale)), text_message("2 çekiç satıldı, toplam 240 TL."))
    agent = Agent(model, stok.client())

    reply = agent.ask("2 çekiç sat")
    assert reply.text is None
    assert reply.pending.tool_name == "create_sale"
    assert stok.writes() == []

    reply = agent.resolve(approve=True)
    assert [w[1] for w in stok.writes()] == ["/sales"]
    assert reply.text == "2 çekiç satıldı, toplam 240 TL."
    assert reply.tool_log == ["create_sale (onaylandı)"]


def test_rejected_write_is_never_sent(stok):
    sale = {"items": [{"product_id": 1, "quantity": 2}]}
    model = FakeModel(tool_message(call("create_sale", sale)), text_message("Tamam, satış yapılmadı."))
    agent = Agent(model, stok.client())
    agent.ask("2 çekiç sat")

    reply = agent.resolve(approve=False)
    assert stok.writes() == []
    assert "reddetti" in last_tool_result(model)["error"]
    assert reply.text == "Tamam, satış yapılmadı."


def test_new_question_is_blocked_while_action_pending(stok):
    model = FakeModel(tool_message(call("record_purchase", {"product_id": 1, "quantity": 5})))
    agent = Agent(model, stok.client())
    agent.ask("5 çekiç geldi")

    reply = agent.ask("kâr ne?")
    assert reply.pending is not None
    assert "onaylayın" in reply.text
    assert len(model.seen) == 1


def test_api_error_is_passed_to_model(stok):
    sale = {"items": [{"product_id": 1, "quantity": 50}]}
    model = FakeModel(tool_message(call("create_sale", sale)), text_message("Stok yetersiz."))
    agent = Agent(model, stok.client())
    agent.ask("50 çekiç sat")
    agent.resolve(approve=True)

    assert "409" in last_tool_result(model)["error"]


def test_read_calls_run_before_write_in_same_message(stok):
    model = FakeModel(
        tool_message(
            call("search_products", {"query": "çekiç"}, "c1"),
            call("create_sale", {"items": [{"product_id": 1, "quantity": 1}]}, "c2"),
            call("low_stock", {}, "c3"),
        ),
        text_message("Satış tamam."),
    )
    agent = Agent(model, stok.client())
    reply = agent.ask("Çekiç bul ve 1 tane sat")

    assert reply.pending.tool_name == "create_sale"
    assert reply.tool_log == ["search_products"]
    # Every tool call gets an answer, so the conversation stays valid for the model.
    answered = {m["tool_call_id"] for m in agent.messages if m["role"] == "tool"}
    assert answered == {"c1", "c3"}
    agent.resolve(approve=True)
    assert {m["tool_call_id"] for m in agent.messages if m["role"] == "tool"} == {"c1", "c2", "c3"}


def test_unknown_tool_and_bad_arguments_do_not_crash(stok):
    bad_json = {"id": "x", "type": "function", "function": {"name": "search_products", "arguments": "{nope"}}
    model = FakeModel(tool_message(call("delete_everything")), tool_message(bad_json), text_message("Bitti."))
    reply = Agent(model, stok.client()).ask("test")

    assert reply.text == "Bitti."
    tool_results = [json.loads(m["content"]) for m in model.seen[-1] if m["role"] == "tool"]
    assert tool_results[0] == {"error": "Bilinmeyen araç: delete_everything"}
    assert stok.requests[-1][:3] == ("GET", "/products", {})


def test_step_limit_stops_endless_tool_loops(stok):
    model = FakeModel(*[tool_message(call("low_stock", {}, f"c{i}")) for i in range(3)])
    reply = Agent(model, stok.client(), max_steps=3).ask("döngü")
    assert "çok fazla adım" in reply.text


def test_unreachable_stok_api_is_reported(stok):
    def down(request):
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(base_url="http://stok", transport=httpx.MockTransport(down))
    model = FakeModel(tool_message(call("low_stock")), text_message("API kapalı."))
    Agent(model, client).ask("kritik stok?")
    assert "ulaşılamadı" in last_tool_result(model)["error"]


def test_openai_compatible_model_parses_tool_calls():
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        sent["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [call("low_stock")]}}]})

    model = OpenAICompatibleModel("http://llm/v1", "key123", "test-model")
    model.client = httpx.Client(base_url="http://llm/v1", headers={"Authorization": "Bearer key123"}, transport=httpx.MockTransport(handler))
    message = model.complete([{"role": "user", "content": "hi"}], [{"type": "function"}])

    assert message["tool_calls"][0]["function"]["name"] == "low_stock"
    assert sent["model"] == "test-model" and sent["temperature"] == 0
    assert sent["auth"] == "Bearer key123"
