import httpx
import pytest
from fastapi.testclient import TestClient

from karakeep_opds import app as app_module
from karakeep_opds.app import app, safe_remote_image_url
from karakeep_opds.config import get_settings


@pytest.fixture
def test_client(settings):
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


AUTH = ("reader", "password123")


def test_missing_basic_auth_returns_401(test_client: TestClient) -> None:
    response = test_client.get("/opds")

    assert response.status_code == 401


def test_bad_basic_auth_returns_401(test_client: TestClient) -> None:
    response = test_client.get("/opds", auth=("reader", "wrong-password"))

    assert response.status_code == 401


def test_recent_feed_returns_entries(test_client: TestClient, respx_mock) -> None:
    respx_mock.get("https://karakeep.test/bookmarks").mock(
        return_value=httpx.Response(
            200,
            json={
                "bookmarks": [
                    {
                        "id": "abc",
                        "createdAt": "2026-01-01T00:00:00Z",
                        "title": "Example",
                        "content": {"type": "link", "url": "https://example.com"},
                    }
                ],
                "nextCursor": None,
            },
        )
    )

    response = test_client.get("/opds/recent", auth=AUTH)

    assert response.status_code == 200
    assert "Example" in response.text
    assert "/opds/bookmarks/abc.epub" in response.text
    assert response.headers["content-type"].startswith("application/atom+xml")


def test_search_passes_query_and_cursor(test_client: TestClient, respx_mock) -> None:
    route = respx_mock.get("https://karakeep.test/bookmarks/search").mock(
        return_value=httpx.Response(200, json={"bookmarks": [], "nextCursor": "next"})
    )

    response = test_client.get(
        "/opds/search",
        params={"q": "python", "cursor": "cursor1"},
        auth=AUTH,
    )

    assert response.status_code == 200
    request = route.calls.last.request
    assert request.url.params["q"] == "python"
    assert request.url.params["cursor"] == "cursor1"
    assert request.url.params["limit"] == "2"
    assert request.headers["authorization"] == "Bearer karakeep-token"


def test_opds2_recent_pagination_link(test_client: TestClient, respx_mock) -> None:
    respx_mock.get("https://karakeep.test/bookmarks").mock(
        return_value=httpx.Response(200, json={"bookmarks": [], "nextCursor": "next"})
    )

    response = test_client.get("/opds2/recent", auth=AUTH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["links"][1]["rel"] == "next"
    assert "cursor=next" in payload["links"][1]["href"]


@pytest.mark.parametrize(
    ("route", "upstream_path"),
    [
        ("/opds/recent", "/bookmarks"),
        ("/opds/search?q=python", "/bookmarks/search"),
        ("/opds2/recent", "/bookmarks"),
        ("/opds2/search?q=python", "/bookmarks/search"),
    ],
)
def test_feed_routes_return_502_on_karakeep_error(
    test_client: TestClient,
    respx_mock,
    route: str,
    upstream_path: str,
) -> None:
    respx_mock.get(f"https://karakeep.test{upstream_path}").mock(
        return_value=httpx.Response(503, json={"error": "unavailable"})
    )

    response = test_client.get(route, auth=AUTH)

    assert response.status_code == 502
    assert response.json()["detail"] == "Karakeep API request failed"


def test_epub_endpoint_returns_epub(test_client: TestClient, respx_mock) -> None:
    respx_mock.get("https://karakeep.test/bookmarks/abc").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "abc",
                "createdAt": "2026-01-01T00:00:00Z",
                "title": "Example",
                "content": {"type": "text", "text": "Body"},
            },
        )
    )

    response = test_client.get("/opds/bookmarks/abc.epub", auth=AUTH)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/epub+zip"
    assert response.content.startswith(b"PK")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "ips", "expected"),
    [
        ("http://127.0.0.1/image.jpg", {"127.0.0.1"}, False),
        ("http://localhost/image.jpg", {"127.0.0.1"}, False),
        ("http://192.168.1.20/image.jpg", {"192.168.1.20"}, False),
        ("http://169.254.1.1/image.jpg", {"169.254.1.1"}, False),
        ("https://example.com/image.jpg", {"93.184.216.34"}, True),
    ],
)
async def test_safe_remote_image_url_blocks_private_addresses(
    monkeypatch: pytest.MonkeyPatch,
    url: str,
    ips: set[str],
    expected: bool,
) -> None:
    async def fake_resolve_hostname(hostname: str) -> set[str]:
        return ips

    monkeypatch.setattr(app_module, "resolve_hostname", fake_resolve_hostname)

    assert await safe_remote_image_url(url) is expected
