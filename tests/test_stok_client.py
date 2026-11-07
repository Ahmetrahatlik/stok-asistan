import httpx

from asistan import stok_client
from asistan.config import Settings


def test_logs_in_when_credentials_are_set(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path == "/auth/token":
            assert b"username=demo" in request.content
            return httpx.Response(200, json={"access_token": "abc", "token_type": "bearer"})
        return httpx.Response(200, json=[])

    real_client = httpx.Client
    monkeypatch.setattr(stok_client.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    client = stok_client.make_stok_client(Settings(stok_api_url="http://stok", stok_api_username="demo", stok_api_password="demo1234"))
    client.get("/products")

    assert seen[-1].headers["Authorization"] == "Bearer abc"


def test_no_login_without_credentials(monkeypatch):
    def handler(request):
        raise AssertionError("no request expected")

    real_client = httpx.Client
    monkeypatch.setattr(stok_client.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    client = stok_client.make_stok_client(Settings(stok_api_url="http://stok", stok_api_username=""))
    assert "Authorization" not in client.headers
