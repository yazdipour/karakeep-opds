from karakeep_opds.models import MAX_CONTENT_LENGTH, normalize_bookmark, normalize_page


def test_normalizes_link_bookmark() -> None:
    item = normalize_bookmark(
        {
            "id": "abc",
            "createdAt": "2026-01-01T00:00:00Z",
            "title": "Saved title",
            "summary": "Short summary",
            "content": {
                "type": "link",
                "url": "https://example.com/article",
                "title": "Article title",
                "description": "Description",
                "author": "Author",
            },
            "assets": [
                {"id": "html-asset", "assetType": "linkHtmlContent"},
                {"id": "image-asset", "assetType": "bannerImage"},
            ],
        }
    )

    assert item is not None
    assert item.kind == "link"
    assert item.title == "Saved title"
    assert item.url == "https://example.com/article"
    assert item.author == "Author"
    assert item.content_asset_id == "html-asset"
    assert item.image_asset_id == "image-asset"


def test_normalizes_text_bookmark_with_title_fallback() -> None:
    item = normalize_bookmark(
        {
            "id": "note1",
            "createdAt": "2026-01-01T00:00:00Z",
            "content": {"type": "text", "text": "This is a saved note body.", "sourceUrl": None},
        }
    )

    assert item is not None
    assert item.kind == "text"
    assert item.title == "This is a saved note body."
    assert item.content == "This is a saved note body."


def test_skips_asset_bookmarks() -> None:
    item = normalize_bookmark(
        {
            "id": "asset1",
            "createdAt": "2026-01-01T00:00:00Z",
            "content": {"type": "asset", "assetType": "pdf", "assetId": "file1"},
        }
    )

    assert item is None


def test_normalizes_paginated_response() -> None:
    page = normalize_page(
        {
            "bookmarks": [
                {
                    "id": "a",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "content": {"type": "text", "text": "A"},
                },
                {
                    "id": "b",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "content": {"type": "asset", "assetId": "x"},
                },
            ],
            "nextCursor": "next",
        }
    )

    assert len(page.items) == 1
    assert page.next_cursor == "next"


def test_strips_embedded_data_images_and_caps_text_content() -> None:
    item = normalize_bookmark(
        {
            "id": "note1",
            "createdAt": "2026-01-01T00:00:00Z",
            "content": {
                "type": "text",
                "text": "Intro ![](data:image/png;base64," + ("a" * 10000) + ") Outro",
            },
        }
    )

    assert item is not None
    assert "data:image" not in item.content
    assert len(item.content) <= MAX_CONTENT_LENGTH
