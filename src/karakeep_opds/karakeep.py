from typing import Any

import httpx

from karakeep_opds.config import Settings
from karakeep_opds.models import BookmarkPage, FeedItem, normalize_bookmark, normalize_page


class KarakeepClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def list_bookmarks(self, cursor: str | None = None) -> BookmarkPage:
        return normalize_page(await self._get("/bookmarks", cursor=cursor))

    async def search_bookmarks(self, query: str, cursor: str | None = None) -> BookmarkPage:
        return normalize_page(await self._get("/bookmarks/search", q=query, cursor=cursor))

    async def get_bookmark(self, bookmark_id: str) -> FeedItem | None:
        return normalize_bookmark(await self._get(f"/bookmarks/{bookmark_id}", include_limit=False))

    async def get_asset(self, asset_id: str) -> tuple[bytes, str] | None:
        response = await self._request("GET", f"/assets/{asset_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        media_type = response.headers.get("content-type", "application/octet-stream").split(";")[0]
        return response.content, media_type

    async def _get(
        self,
        path: str,
        include_limit: bool = True,
        **params: str | None,
    ) -> dict[str, Any]:
        clean_params = {
            key: value for key, value in params.items() if value is not None and value != ""
        }
        if include_limit:
            clean_params["limit"] = str(self._settings.opds_page_size)
        headers = {"Authorization": f"Bearer {self._settings.karakeep_api_token}"}

        response = await self._request("GET", path, params=clean_params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = kwargs.pop("headers", None) or {
            "Authorization": f"Bearer {self._settings.karakeep_api_token}"
        }
        if self._client is not None:
            return await self._client.request(method, path, headers=headers, **kwargs)

        async with httpx.AsyncClient(
            base_url=self._settings.karakeep_origin,
            timeout=20.0,
        ) as client:
            return await client.request(method, path, headers=headers, **kwargs)
