import httpx

from asistan.config import Settings


def make_stok_client(settings: Settings) -> httpx.Client:
    """HTTP client for the Stok API, logged in when credentials are configured."""
    client = httpx.Client(base_url=settings.stok_api_url, timeout=15)
    if settings.stok_api_username:
        response = client.post(
            "/auth/token",
            data={"username": settings.stok_api_username, "password": settings.stok_api_password},
        )
        response.raise_for_status()
        client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return client
