from datetime import UTC, datetime
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from karakeep_opds.models import BookmarkPage, FeedItem, excerpt

ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/2010/catalog"
DC = "http://purl.org/dc/terms/"

ET.register_namespace("", ATOM)
ET.register_namespace("opds", OPDS)
ET.register_namespace("dcterms", DC)


def render_opds1_catalog(base_url: str) -> str:
    updated = datetime.now(UTC)
    feed = _feed("karakeep-opds", "Karakeep OPDS", updated)
    _link(feed, "self", f"{base_url}/opds", "application/atom+xml")
    _nav_entry(
        feed,
        "recent",
        "Recent bookmarks",
        f"{base_url}/opds/recent",
    )
    _nav_entry(
        feed,
        "search",
        "Search bookmarks",
        f"{base_url}/opds/search?{urlencode({'q': ''})}",
    )
    return _xml(feed)


def render_opds1_feed(
    title: str,
    page: BookmarkPage,
    base_url: str,
    self_path: str,
    query: str | None = None,
) -> str:
    updated = page.items[0].updated if page.items else datetime.now(UTC)
    feed = _feed(f"karakeep-opds:{self_path}:{query or ''}", title, updated)
    _link(feed, "self", _feed_url(base_url, self_path, query=query), "application/atom+xml")
    if page.next_cursor:
        _link(
            feed,
            "next",
            _feed_url(base_url, self_path, query=query, cursor=page.next_cursor),
            "application/atom+xml",
        )
    for item in page.items:
        _entry(feed, item, base_url)
    return _xml(feed)


def render_opds2_catalog(base_url: str) -> dict:
    return {
        "metadata": {"title": "Karakeep OPDS"},
        "links": [
            {
                "rel": "self",
                "href": f"{base_url}/opds2",
                "type": "application/opds+json",
            },
        ],
        "navigation": [
            {
                "metadata": {"title": "Recent bookmarks"},
                "links": [
                    {
                        "href": f"{base_url}/opds2/recent",
                        "type": "application/opds+json",
                    }
                ],
            },
            {
                "metadata": {"title": "Search bookmarks"},
                "links": [
                    {
                        "href": f"{base_url}/opds2/search?{urlencode({'q': ''})}",
                        "type": "application/opds+json",
                    }
                ],
            },
        ],
    }


def render_opds2_feed(
    title: str,
    page: BookmarkPage,
    base_url: str,
    self_path: str,
    query: str | None = None,
) -> dict:
    links = [
        {
            "rel": "self",
            "href": _feed_url(base_url, self_path, query=query),
            "type": "application/opds+json",
        }
    ]
    if page.next_cursor:
        links.append(
            {
                "rel": "next",
                "href": _feed_url(base_url, self_path, query=query, cursor=page.next_cursor),
                "type": "application/opds+json",
            }
        )

    return {
        "metadata": {"title": title},
        "links": links,
        "publications": [_opds2_publication(item, base_url) for item in page.items],
    }


def _feed(feed_id: str, title: str, updated: datetime) -> ET.Element:
    feed = ET.Element(f"{{{ATOM}}}feed")
    ET.SubElement(feed, f"{{{ATOM}}}id").text = feed_id
    ET.SubElement(feed, f"{{{ATOM}}}title").text = title
    ET.SubElement(feed, f"{{{ATOM}}}updated").text = _iso(updated)
    return feed


def _entry(feed: ET.Element, item: FeedItem, base_url: str) -> None:
    entry = ET.SubElement(feed, f"{{{ATOM}}}entry")
    ET.SubElement(entry, f"{{{ATOM}}}id").text = f"karakeep:bookmark:{item.id}"
    ET.SubElement(entry, f"{{{ATOM}}}title").text = item.title
    ET.SubElement(entry, f"{{{ATOM}}}updated").text = _iso(item.updated)
    if item.author:
        author = ET.SubElement(entry, f"{{{ATOM}}}author")
        ET.SubElement(author, f"{{{ATOM}}}name").text = item.author
    if item.summary:
        ET.SubElement(entry, f"{{{ATOM}}}summary").text = item.summary
    if item.url:
        _link(entry, "alternate", item.url, "text/html")
    _link(
        entry,
        "http://opds-spec.org/acquisition/open-access",
        f"{base_url}/opds/bookmarks/{item.id}.epub",
        "application/epub+zip",
    )
    if item.content:
        content = ET.SubElement(entry, f"{{{ATOM}}}content", {"type": "text"})
        content.text = item.content


def _nav_entry(feed: ET.Element, entry_id: str, title: str, href: str) -> None:
    entry = ET.SubElement(feed, f"{{{ATOM}}}entry")
    ET.SubElement(entry, f"{{{ATOM}}}id").text = f"karakeep-opds:{entry_id}"
    ET.SubElement(entry, f"{{{ATOM}}}title").text = title
    ET.SubElement(entry, f"{{{ATOM}}}updated").text = _iso(datetime.now(UTC))
    _link(entry, "subsection", href, "application/atom+xml;profile=opds-catalog")


def _link(parent: ET.Element, rel: str, href: str, media_type: str) -> None:
    ET.SubElement(parent, f"{{{ATOM}}}link", {"rel": rel, "href": href, "type": media_type})


def _opds2_publication(item: FeedItem, base_url: str) -> dict:
    publication = {
        "metadata": {
            "identifier": f"karakeep:bookmark:{item.id}",
            "title": item.title,
            "modified": _iso(item.updated),
        },
        "links": [],
    }
    if item.author:
        publication["metadata"]["author"] = [{"name": item.author}]
    if item.summary:
        publication["metadata"]["description"] = item.summary
    if item.url:
        publication["links"].append({"rel": "alternate", "href": item.url, "type": "text/html"})
    publication["links"].append(
        {
            "rel": "http://opds-spec.org/acquisition/open-access",
            "href": f"{base_url}/opds/bookmarks/{item.id}.epub",
            "type": "application/epub+zip",
        }
    )
    if item.content:
        publication["metadata"]["description"] = publication["metadata"].get(
            "description", excerpt(item.content, 500)
        )
    return publication


def _feed_url(
    base_url: str,
    path: str,
    query: str | None = None,
    cursor: str | None = None,
) -> str:
    params = {}
    if query is not None:
        params["q"] = query
    if cursor:
        params["cursor"] = cursor
    if not params:
        return f"{base_url}{path}"
    return f"{base_url}{path}?{urlencode(params)}"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _xml(feed: ET.Element) -> str:
    return ET.tostring(feed, encoding="utf-8", xml_declaration=True).decode("utf-8")
