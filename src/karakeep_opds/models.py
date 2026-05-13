from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from re import DOTALL, IGNORECASE, sub
from typing import Any

MAX_SUMMARY_LENGTH = 500
MAX_CONTENT_LENGTH = 4000


@dataclass(frozen=True)
class FeedItem:
    id: str
    kind: str
    title: str
    updated: datetime
    summary: str | None
    url: str | None
    content: str | None
    author: str | None
    html_content: str | None = None
    content_asset_id: str | None = None
    image_asset_id: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class BookmarkPage:
    items: list[FeedItem]
    next_cursor: str | None


def normalize_page(payload: dict[str, Any]) -> BookmarkPage:
    raw_bookmarks = payload.get("bookmarks")
    if raw_bookmarks is None:
        raw_bookmarks = payload.get("data", [])
    if not isinstance(raw_bookmarks, list):
        raw_bookmarks = []

    return BookmarkPage(
        items=[item for bookmark in raw_bookmarks if (item := normalize_bookmark(bookmark))],
        next_cursor=payload.get("nextCursor"),
    )


def normalize_bookmark(bookmark: dict[str, Any]) -> FeedItem | None:
    content = bookmark.get("content") or {}
    kind = content.get("type")
    if kind not in {"link", "text"}:
        return None

    bookmark_id = str(bookmark.get("id") or "")
    if not bookmark_id:
        return None
    assets = bookmark.get("assets") if isinstance(bookmark.get("assets"), list) else []

    updated = parse_datetime(
        bookmark.get("modifiedAt")
        or bookmark.get("updatedAt")
        or content.get("dateModified")
        or bookmark.get("createdAt")
    )
    summary = excerpt(
        first_text(
            bookmark.get("summary"),
            bookmark.get("note"),
            content.get("description"),
            content.get("text"),
            html_to_text(content.get("htmlContent")),
        ),
        MAX_SUMMARY_LENGTH,
    )

    if kind == "link":
        url = content.get("url")
        title = first_text(bookmark.get("title"), content.get("title"), url, bookmark_id)
        html_content = content.get("htmlContent")
        body = excerpt(clean_text(html_to_text(html_content)), MAX_CONTENT_LENGTH)
        author = first_text(content.get("author"), content.get("publisher"))
    else:
        url = content.get("sourceUrl")
        html_content = content.get("htmlContent")
        body = excerpt(clean_text(content.get("text")), MAX_CONTENT_LENGTH)
        title = first_text(bookmark.get("title"), excerpt(body, 80), bookmark_id)
        author = None

    return FeedItem(
        id=bookmark_id,
        kind=kind,
        title=title or bookmark_id,
        updated=updated,
        summary=summary,
        url=url,
        content=body,
        html_content=html_content,
        author=author,
        content_asset_id=content.get("contentAssetId") or asset_id(assets, "linkHtmlContent"),
        image_asset_id=content.get("imageAssetId")
        or asset_id(assets, "bannerImage")
        or content.get("screenshotAssetId")
        or asset_id(assets, "screenshot"),
        image_url=content.get("imageUrl"),
    )


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def asset_id(assets: list[Any], asset_type: str) -> str | None:
    for asset in assets:
        if isinstance(asset, dict) and asset.get("assetType") == asset_type and asset.get("id"):
            return str(asset["id"])
    return None


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
    return datetime.now(UTC)


def html_to_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = sub(r"<img\b[^>]*>", " ", value, flags=DOTALL | IGNORECASE)
    no_tags = sub(r"<[^>]+>", " ", value)
    return clean_text(unescape(no_tags))


def clean_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = sub(r"!\[[^\]]*]\(data:[^)]+\)", " ", value, flags=DOTALL)
    text = sub(r"<img\b[^>]*>", " ", text, flags=DOTALL | IGNORECASE)
    text = sub(r"data:[^\s)>\"]+", " ", text)
    return sub(r"\s+", " ", text).strip() or None


def excerpt(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    compact = sub(r"\s+", " ", value).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."
