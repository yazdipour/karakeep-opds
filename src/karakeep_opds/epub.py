from html import escape
from io import BytesIO
from re import findall, search, sub
from typing import NamedTuple
from uuid import NAMESPACE_URL, uuid5

import markdown
import markdownify
from bs4 import BeautifulSoup, Tag
from ebooklib import epub

from karakeep_opds.models import FeedItem

EPUB_IMAGE_MEDIA_TYPES = {"image/gif", "image/jpeg", "image/png"}


def render_epub(
    item: FeedItem,
    article_html: str | None = None,
    images: list[tuple[bytes, str, str | None]] | None = None,
) -> bytes:
    epub_images = _epub_images(images or [])
    image_by_source = {source: image for image in epub_images for source in image.sources}

    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid5(NAMESPACE_URL, f'karakeep:bookmark:{item.id}')}")
    book.set_title(item.title)
    book.set_language("en")
    book.add_author(item.author or "Karakeep")

    for image in epub_images:
        book.add_item(
            epub.EpubItem(
                uid=image.uid,
                file_name=image.path,
                media_type=image.media_type,
                content=image.data,
            )
        )

    stylesheet = epub.EpubItem(
        uid="style",
        file_name="style/book.css",
        media_type="text/css",
        content=(
            "body { font-family: serif; line-height: 1.45; padding: 0 1em; }\n"
            "h1, h2, h3, h4, h5, h6 { font-family: sans-serif; line-height: 1.2; margin-top: 1.2em; margin-bottom: 0.6em; font-weight: bold; }\n"
            "h1 { font-size: 1.75em; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; }\n"
            "h2 { font-size: 1.5em; }\n"
            "h3 { font-size: 1.25em; }\n"
            "strong, b { font-weight: bold; }\n"
            "em, i { font-style: italic; }\n"
            "img { max-width: 100%; height: auto; display: block; margin: 1em auto; }\n"
            "figure { margin: 1em 0; text-align: center; }\n"
            "blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding-left: 1em; font-style: italic; }\n"
            "pre { background: #f4f4f4; padding: 1em; overflow-x: auto; font-family: monospace; }\n"
            "code { font-family: monospace; background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; }\n"
            "a { color: #0056b3; text-decoration: none; }\n"
            "a:hover { text-decoration: underline; }\n"
            "hr { border: 0; border-top: 1px solid #ddd; margin: 2em 0; }\n"
        ),
    )
    book.add_item(stylesheet)

    chapter = epub.EpubHtml(title=item.title, file_name="content.xhtml", lang="en")
    chapter.content = _chapter_body(item, article_html, epub_images, image_by_source)
    chapter.add_item(stylesheet)
    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    book.toc = (epub.Link("content.xhtml", item.title, "content"),)

    buffer = BytesIO()
    epub.write_epub(buffer, book, options={"raise_exceptions": True})
    return buffer.getvalue()


def extract_image_urls(article_html: str | None, limit: int = 5) -> list[str]:
    if not article_html:
        return []
    urls: list[str] = []
    soup = BeautifulSoup(article_html, "html.parser")
    for tag in soup.find_all("img"):
        url = _best_image_source_from_tag(tag)
        if url and url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _chapter_body(
    item: FeedItem,
    article_html: str | None,
    images: list["EpubImage"],
    image_by_source: dict[str, "EpubImage"],
) -> str:
    sanitized = (
        _sanitize_article_html(article_html, image_by_source, item.title)
        if article_html
        else SanitizedArticle(None, set())
    )
    article = sanitized.html
    if not article:
        article = _fallback_article(item)

    source = f'<p><a href="{escape(item.url)}">Source link</a></p>' if item.url else ""
    hero = ""
    if images and images[0].path not in sanitized.image_paths:
        hero = f'<figure><img src="{escape(images[0].path)}" alt=""/></figure>'

    return f"{source}\n{hero}\n{article}"


class SanitizedArticle(NamedTuple):
    html: str | None
    image_paths: set[str]


def _sanitize_article_html(
    article_html: str | None,
    image_by_source: dict[str, "EpubImage"],
    title: str,
) -> SanitizedArticle:
    if not article_html:
        return SanitizedArticle(None, set())

    soup = BeautifulSoup(article_html, "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "embed", "svg"]):
        tag.decompose()
    
    # Convert HTML to Markdown to remove cruft but preserve semantic structure
    md_content = markdownify.markdownify(str(soup), heading_style="ATX")
    # Convert back to clean HTML
    clean_html = markdown.markdown(md_content, extensions=["extra", "sane_lists"])

    soup = BeautifulSoup(clean_html, "html.parser")
    image_paths = set()

    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if tag.name == "img":
            source = _best_image_source_from_tag(tag)
            image = image_by_source.get(source or "")
            if image is None:
                tag.decompose()
                continue
            tag.attrs = {"src": image.path, "alt": tag.get("alt", "")}
            image_paths.add(image.path)
            continue
        if tag.name == "a":
            href = tag.get("href")
            tag.attrs = {"href": href} if href else {}
            continue
        tag.attrs = {}

    body = soup.body or soup
    _remove_leading_duplicate_title(body, title)
    html = "".join(str(child) for child in body.children).strip()
    return SanitizedArticle(html or None, image_paths)


def _fallback_article(item: FeedItem) -> str:
    text = item.content or item.summary or ""
    if _same_text(text, item.title):
        return "<p>No extracted article text is available for this bookmark.</p>"
    return _paragraphs(text)


def _paragraphs(text: str) -> str:
    paragraphs = "\n".join(f"<p>{escape(part)}</p>" for part in text.splitlines() if part.strip())
    return paragraphs or "<p>No extracted text is available for this bookmark.</p>"


def _remove_leading_duplicate_title(body: Tag | BeautifulSoup, title: str) -> None:
    for child in list(body.children):
        if isinstance(child, str):
            if child.strip():
                return
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in {"h1", "h2", "p"} and _same_text(child.get_text(" ", strip=True), title):
            child.decompose()
            continue
        return


def _same_text(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return sub(r"\s+", " ", left).strip().casefold() == sub(r"\s+", " ", right).strip().casefold()


class EpubImage:
    def __init__(
        self,
        uid: str,
        path: str,
        data: bytes,
        media_type: str,
        sources: list[str],
    ) -> None:
        self.uid = uid
        self.path = path
        self.data = data
        self.media_type = media_type
        self.sources = sources


def _epub_images(images: list[tuple[bytes, str, str | None]]) -> list[EpubImage]:
    result = []
    seen = set()
    for data, media_type, source in images:
        if media_type not in EPUB_IMAGE_MEDIA_TYPES:
            continue
        digest_key = (media_type, data[:64], len(data))
        if digest_key in seen:
            continue
        seen.add(digest_key)
        index = len(result) + 1
        path = f"images/image-{index}{_extension_for_media_type(media_type)}"
        sources = [source] if source else []
        result.append(EpubImage(f"image-{index}", path, data, media_type, sources))
    return result


def _extension_for_media_type(media_type: str) -> str:
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
    }.get(media_type, ".bin")


def _best_image_source_from_tag(tag: Tag) -> str | None:
    src = tag.get("src")
    if isinstance(src, str) and src:
        return src
    srcset = tag.get("srcset")
    if not isinstance(srcset, str) or not srcset:
        return None
    return _best_srcset_url(srcset)


def _best_srcset_url(srcset: str) -> str | None:
    candidates = []
    for chunk in srcset.split(","):
        match = search(r"(\S+)(?:\s+(\d+)w)?", chunk.strip())
        if match:
            candidates.append((int(match.group(2) or 0), match.group(1)))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def _parse_attrs(tag: str) -> list[tuple[str, str | None]]:
    return [
        (key.lower(), value)
        for key, value in findall(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)=["\']([^"\']*)["\']', tag)
    ]


def _best_image_source(attrs: list[tuple[str, str | None]]) -> str | None:
    src = next((value for key, value in attrs if key == "src" and value), None)
    if src:
        return src
    srcset = next((value for key, value in attrs if key == "srcset" and value), None)
    if not srcset:
        return None
    return _best_srcset_url(srcset)
