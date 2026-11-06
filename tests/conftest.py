import json

import httpx
import pytest


def call(name, arguments=None, call_id=None):
    return {
        "id": call_id or f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments or {}, ensure_ascii=False)},
    }


def tool_message(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def text_message(text):
    return {"role": "assistant", "content": text, "tool_calls": []}


class FakeModel:
    """Replays scripted assistant messages and records what it was sent."""

    def __init__(self, *script):
        self.script = list(script)
        self.seen = []

    def complete(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        if not self.script:
            raise AssertionError("FakeModel ran out of scripted replies")
        return self.script.pop(0)


class FakeStokAPI:
    """In-memory stand-in for the Stok API, served through httpx.MockTransport."""

    def __init__(self):
        self.requests = []
        self.products = [{"id": 1, "name": "Çekiç", "stock": "10", "sale_price": "120.00"}]

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append((request.method, request.url.path, dict(request.url.params), request.content))
        if request.method == "GET" and request.url.path == "/products":
            query = request.url.params.get("search", "").lower()
            return httpx.Response(200, json=[p for p in self.products if query in p["name"].lower()])
        if request.method == "GET" and request.url.path == "/products/low-stock":
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/sales":
            body = json.loads(request.content)
            quantity = sum(i["quantity"] for i in body["items"])
            if quantity > 10:
                return httpx.Response(409, json={"detail": {"message": "Insufficient stock"}})
            return httpx.Response(201, json={"id": 7, "total": str(quantity * 120)})
        return httpx.Response(404, json={"detail": "Not found"})

    def client(self):
        return httpx.Client(base_url="http://stok", transport=httpx.MockTransport(self.handler))

    def writes(self):
        return [r for r in self.requests if r[0] != "GET"]


@pytest.fixture()
def stok():
    return FakeStokAPI()
