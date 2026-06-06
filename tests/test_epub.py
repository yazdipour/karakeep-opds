from datetime import UTC, datetime
from zipfile import ZIP_STORED, ZipFile

from ebooklib import epub

import karakeep_opds.epub
from karakeep_opds.epub import render_epub
from karakeep_opds.models import FeedItem


def test_render_epub_embeds_article_html_and_image(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="link",
        title="Example",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary="Summary",
        url="https://example.com",
        content=None,
        author="Author",
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(
        render_epub(
            item,
            article_html=(
                '<p>Hello <strong>world</strong></p>'
                '<img src="https://example.com/image.jpg" alt="Example"/>'
                "<script>bad()</script>"
            ),
            images=[(b"fake-jpeg", "image/jpeg", "https://example.com/image.jpg")],
        )
    )

    with ZipFile(epub_path) as epub:
        names = set(epub.namelist())
        content = epub.read("EPUB/content.xhtml").decode()
        package = epub.read("EPUB/content.opf").decode()

    assert "EPUB/images/image-1.jpg" in names
    assert "Hello <strong>world</strong>" in content
    assert 'src="images/image-1.jpg"' in content
    assert "<h1>Example</h1>" not in content
    assert "style/book.css" in content
    assert "bad()" not in content
    assert "images/image-1.jpg" in package


def test_render_epub_uses_max_zip_compression(monkeypatch) -> None:
    write_options = None
    original_write_epub = epub.write_epub

    def capture_write_options(name, book, options=None):
        nonlocal write_options
        write_options = options
        return original_write_epub(name, book, options=options)

    monkeypatch.setattr(karakeep_opds.epub.epub, "write_epub", capture_write_options)

    item = FeedItem(
        id="abc",
        kind="text",
        title="Compressed",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url=None,
        content="\n".join(["Repeated content for compression."] * 100),
        author=None,
    )

    render_epub(item)

    assert write_options == {"raise_exceptions": True, "compresslevel": 9}


def test_render_epub_stores_mimetype_uncompressed(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="text",
        title="Compressed",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url=None,
        content="Body",
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(render_epub(item))

    with ZipFile(epub_path) as epub:
        mimetype = epub.getinfo("mimetype")

    assert mimetype.compress_type == ZIP_STORED


def test_render_epub_drops_repeated_title_from_body(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="text",
        title="Repeated Title",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary="Repeated Title",
        url=None,
        content="Repeated Title",
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(render_epub(item))

    with ZipFile(epub_path) as epub:
        content = epub.read("EPUB/content.xhtml").decode()

    assert "<h1>Repeated Title</h1>" not in content
    assert "<p>Repeated Title</p>" not in content
    assert "No extracted article text is available" in content


def test_render_epub_drops_leading_title_from_article_html(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="link",
        title="Article Title",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url="https://example.com",
        content=None,
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(
        render_epub(
            item,
            article_html="<h1>Article Title</h1><p>Actual body.</p>",
        )
    )

    with ZipFile(epub_path) as epub:
        content = epub.read("EPUB/content.xhtml").decode()

    assert "<h1>Article Title</h1>" not in content
    assert "<p>Actual body.</p>" in content


def test_render_epub_skips_webp_images(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="link",
        title="Example",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url="https://example.com",
        content=None,
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(
        render_epub(
            item,
            article_html='<p>Body</p><img src="https://example.com/image.webp"/>',
            images=[(b"fake-webp", "image/webp", "https://example.com/image.webp")],
        )
    )

    with ZipFile(epub_path) as epub:
        names = set(epub.namelist())
        content = epub.read("EPUB/content.xhtml").decode()

    assert "EPUB/images/image-1.webp" not in names
    assert "<img" not in content


def test_render_epub_does_not_duplicate_existing_article_image(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="link",
        title="Example",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url="https://example.com",
        content=None,
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(
        render_epub(
            item,
            article_html='<p>Body</p><img src="https://example.com/image.jpg"/>',
            images=[(b"fake-jpeg", "image/jpeg", "https://example.com/image.jpg")],
        )
    )

    with ZipFile(epub_path) as epub:
        content = epub.read("EPUB/content.xhtml").decode()

    assert content.count('src="images/image-1.jpg"') == 1


def test_render_epub_adds_hero_when_article_does_not_use_image(tmp_path) -> None:
    item = FeedItem(
        id="abc",
        kind="link",
        title="Example",
        updated=datetime(2026, 1, 1, tzinfo=UTC),
        summary=None,
        url="https://example.com",
        content=None,
        author=None,
    )

    epub_path = tmp_path / "book.epub"
    epub_path.write_bytes(
        render_epub(
            item,
            article_html="<p>Body</p>",
            images=[(b"fake-jpeg", "image/jpeg", "https://example.com/image.jpg")],
        )
    )

    with ZipFile(epub_path) as epub:
        content = epub.read("EPUB/content.xhtml").decode()

    assert '<figure><img src="images/image-1.jpg" alt=""/></figure>' in content
