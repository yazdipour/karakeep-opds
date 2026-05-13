import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from ipaddress import ip_address
from secrets import compare_digest
from socket import gaierror
from typing import Annotated
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from karakeep_opds.config import Settings, get_settings
from karakeep_opds.epub import extract_image_urls, render_epub
from karakeep_opds.karakeep import KarakeepClient
from karakeep_opds.render import (
    render_opds1_catalog,
    render_opds1_feed,
    render_opds2_catalog,
    render_opds2_feed,
)

SettingsDep = Annotated[Settings, Depends(get_settings)]
basic_auth = HTTPBasic()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.http_client = httpx.AsyncClient(base_url=settings.karakeep_origin, timeout=20.0)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="karakeep-opds", version="0.1.0", lifespan=lifespan)


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(basic_auth)],
    settings: SettingsDep,
) -> None:
    username_ok = compare_digest(credentials.username, settings.opds_username)
    password_ok = compare_digest(credentials.password, settings.opds_password)
    if not username_ok or not password_ok:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/opds")
async def opds_catalog(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
) -> Response:
    return xml_response(render_opds1_catalog(base_url(request, settings)))


@app.get("/opds/recent")
async def opds_recent(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
    cursor: str | None = None,
) -> Response:
    try:
        page = await client(request, settings).list_bookmarks(cursor=cursor)
    except httpx.HTTPError as exc:
        raise karakeep_bad_gateway() from exc
    return xml_response(
        render_opds1_feed(
            "Recent bookmarks",
            page,
            base_url(request, settings),
            "/opds/recent",
        )
    )


@app.get("/opds/search")
async def opds_search(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
    q: str = Query(default=""),
    cursor: str | None = None,
) -> Response:
    try:
        page = await client(request, settings).search_bookmarks(query=q, cursor=cursor)
    except httpx.HTTPError as exc:
        raise karakeep_bad_gateway() from exc
    return xml_response(
        render_opds1_feed(
            f"Search: {q}",
            page,
            base_url(request, settings),
            "/opds/search",
            query=q,
        )
    )


@app.get("/opds2")
async def opds2_catalog(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
) -> JSONResponse:
    return JSONResponse(
        render_opds2_catalog(base_url(request, settings)),
        media_type="application/opds+json",
    )


@app.get("/opds2/recent")
async def opds2_recent(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
    cursor: str | None = None,
) -> JSONResponse:
    try:
        page = await client(request, settings).list_bookmarks(cursor=cursor)
    except httpx.HTTPError as exc:
        raise karakeep_bad_gateway() from exc
    return JSONResponse(
        render_opds2_feed(
            "Recent bookmarks",
            page,
            base_url(request, settings),
            "/opds2/recent",
        ),
        media_type="application/opds+json",
    )


@app.get("/opds2/search")
async def opds2_search(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
    q: str = Query(default=""),
    cursor: str | None = None,
) -> JSONResponse:
    try:
        page = await client(request, settings).search_bookmarks(query=q, cursor=cursor)
    except httpx.HTTPError as exc:
        raise karakeep_bad_gateway() from exc
    return JSONResponse(
        render_opds2_feed(
            f"Search: {q}",
            page,
            base_url(request, settings),
            "/opds2/search",
            query=q,
        ),
        media_type="application/opds+json",
    )


@app.get("/opds/bookmarks/{bookmark_id}.epub")
async def opds_epub(
    request: Request,
    settings: SettingsDep,
    _: Annotated[None, Depends(require_basic_auth)],
    bookmark_id: str,
) -> Response:
    karakeep = client(request, settings)
    try:
        item = await karakeep.get_bookmark(bookmark_id)
    except httpx.HTTPError as exc:
        raise karakeep_bad_gateway() from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Bookmark not available as EPUB")
    article_html = item.html_content
    images = []
    if item.content_asset_id:
        asset = await safe_get_asset(karakeep, item.content_asset_id)
        if asset and asset[1] == "text/html":
            article_html = asset[0].decode("utf-8", errors="replace")
    if item.image_asset_id:
        image = await safe_get_asset(karakeep, item.image_asset_id)
        if image and supported_epub_image(image[1]):
            images.append((image[0], image[1], item.image_url))
    for image_url in extract_image_urls(article_html):
        image = await fetch_remote_image(image_url)
        if image:
            images.append((image[0], image[1], image_url))
    return Response(
        content=render_epub(item, article_html=article_html, images=images),
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="{bookmark_id}.epub"'},
    )


def client(request: Request, settings: Settings) -> KarakeepClient:
    return KarakeepClient(settings, request.app.state.http_client)


def base_url(request: Request, settings: Settings) -> str:
    if settings.service_origin:
        return settings.service_origin
    return str(request.base_url).rstrip("/")


def xml_response(body: str) -> Response:
    return Response(content=body, media_type="application/atom+xml; charset=utf-8")


async def fetch_remote_image(url: str) -> tuple[bytes, str] | None:
    if not await safe_remote_image_url(url):
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as http_client:
            response = await get_with_safe_redirects(http_client, url)
    except (httpx.HTTPError, ValueError):
        return None
    media_type = response.headers.get("content-type", "").split(";")[0]
    if not supported_epub_image(media_type):
        return None
    if len(response.content) > 2_000_000:
        return None
    return response.content, media_type


async def get_with_safe_redirects(http_client: httpx.AsyncClient, url: str) -> httpx.Response:
    current_url = url
    for _ in range(4):
        if not await safe_remote_image_url(current_url):
            raise ValueError("Unsafe image URL")
        response = await http_client.get(current_url)
        if response.status_code not in {301, 302, 303, 307, 308}:
            response.raise_for_status()
            return response
        location = response.headers.get("location")
        if not location:
            raise ValueError("Redirect missing location")
        current_url = urljoin(str(response.url), location)
    raise ValueError("Too many redirects")


async def safe_remote_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        ips = await resolve_hostname(parsed.hostname)
    except gaierror:
        return False
    return bool(ips) and all(safe_remote_ip(ip) for ip in ips)


async def resolve_hostname(hostname: str) -> set[str]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, None)
    return {info[4][0] for info in infos}


def safe_remote_ip(value: str) -> bool:
    address = ip_address(value)
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def supported_epub_image(media_type: str) -> bool:
    return media_type in {"image/gif", "image/jpeg", "image/png"}


def karakeep_bad_gateway() -> HTTPException:
    return HTTPException(status_code=502, detail="Karakeep API request failed")


async def safe_get_asset(
    karakeep: KarakeepClient,
    asset_id: str,
) -> tuple[bytes, str] | None:
    try:
        return await karakeep.get_asset(asset_id)
    except httpx.HTTPError:
        return None
