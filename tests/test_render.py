from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from karakeep_opds.models import BookmarkPage, FeedItem
from karakeep_opds.render import render_opds1_feed, render_opds2_feed


def test_render_opds1_feed_is_parseable_xml() -> None:
    page = BookmarkPage(
        items=[
            FeedItem(
                id="abc",
                kind="link",
                title="Example",
                updated=datetime(2026, 1, 1, tzinfo=UTC),
                summary="Summary",
                url="https://example.com",
                content="Body",
                author="Author",
            )
        ],
        next_cursor="cursor2",
    )

    xml = render_opds1_feed("Recent", page, "https://opds.test", "/opds/recent")
    root = ET.fromstring(xml)

    assert root.tag.endswith("feed")
    assert root.find("{http://www.w3.org/2005/Atom}entry") is not None
    assert "cursor2" in xml
    assert "/opds/bookmarks/abc.epub" in xml


def test_render_opds2_feed_shape() -> None:
    page = BookmarkPage(
        items=[
            FeedItem(
                id="abc",
                kind="text",
                title="Note",
                updated=datetime(2026, 1, 1, tzinfo=UTC),
                summary=None,
                url=None,
                content="Note body",
                author=None,
            )
        ],
        next_cursor=None,
    )

    payload = render_opds2_feed("Recent", page, "https://opds.test", "/opds2/recent")

    assert payload["metadata"]["title"] == "Recent"
    assert payload["publications"][0]["metadata"]["title"] == "Note"
    assert payload["links"][0]["rel"] == "self"
    assert payload["publications"][0]["links"][0]["type"] == "application/epub+zip"
