"""Small allowlist sanitizer for untrusted inbound email HTML.

This intentionally keeps only basic text/table formatting. Email HTML is
untrusted and must never be treated as trusted application markup.
"""

from __future__ import annotations

import html
from html.parser import HTMLParser
from urllib.parse import urlsplit

MAX_EMAIL_HTML_CHARS = 250_000
_ALLOWED_TAGS = frozenset(
    {
        "a",
        "b",
        "blockquote",
        "br",
        "caption",
        "code",
        "dd",
        "div",
        "dl",
        "dt",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "s",
        "span",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
)
_VOID_TAGS = frozenset({"br", "hr"})
_DROP_CONTENT_TAGS = frozenset(
    {
        "audio",
        "embed",
        "form",
        "iframe",
        "math",
        "object",
        "script",
        "style",
        "svg",
        "template",
        "video",
    }
)
_ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto", "tel"})


def _safe_href(value: str) -> str | None:
    href = str(value or "").strip()
    if not href or any(ord(char) < 0x20 or ord(char) == 0x7F for char in href):
        return None
    try:
        parsed = urlsplit(href)
    except ValueError:
        return None
    if parsed.scheme and parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        return None
    # Protocol-relative links make an email unexpectedly navigate externally.
    if not parsed.scheme and href.startswith("//"):
        return None
    return href


class _EmailHTMLAllowlistParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.suppressed_tags: list[str] = []

    def _safe_attributes(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        safe: list[str] = []
        for raw_name, raw_value in attrs:
            name = str(raw_name or "").lower()
            value = str(raw_value or "")
            if name == "href" and tag == "a":
                normalized = _safe_href(value)
                if normalized is not None:
                    safe.append(f' href="{html.escape(normalized, quote=True)}"')
            elif name in {"colspan", "rowspan"} and tag in {"td", "th"}:
                if value.isdigit() and 1 <= int(value) <= 100:
                    safe.append(f' {name}="{int(value)}"')
            elif name == "scope" and tag == "th" and value.lower() in {
                "row",
                "col",
                "rowgroup",
                "colgroup",
            }:
                safe.append(f' scope="{value.lower()}"')
            elif name == "title" and tag in {"a", "td", "th"}:
                safe.append(f' title="{html.escape(value[:500], quote=True)}"')
        return "".join(safe)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.suppressed_tags:
            if tag in _DROP_CONTENT_TAGS and tag not in _VOID_TAGS:
                self.suppressed_tags.append(tag)
            return
        if tag in _DROP_CONTENT_TAGS:
            self.suppressed_tags.append(tag)
            return
        if tag not in _ALLOWED_TAGS:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(tag, attrs)}>")
        if tag not in _VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self.suppressed_tags or tag in _DROP_CONTENT_TAGS or tag not in _ALLOWED_TAGS:
            return
        self.parts.append(f"<{tag}{self._safe_attributes(tag, attrs)}>")
        if tag not in _VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.suppressed_tags:
            for index in range(len(self.suppressed_tags) - 1, -1, -1):
                if self.suppressed_tags[index] == tag:
                    del self.suppressed_tags[index:]
                    break
            return
        if tag not in _ALLOWED_TAGS or tag in _VOID_TAGS or tag not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.parts.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self.suppressed_tags and data:
            self.parts.append(html.escape(data, quote=False))

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_email_html(value: str) -> str:
    """Return safe, formatting-only HTML; strip active content and unsafe URLs."""
    source = str(value or "")[:MAX_EMAIL_HTML_CHARS]
    parser = _EmailHTMLAllowlistParser()
    try:
        parser.feed(source)
        parser.close()
        return parser.get_html()[: MAX_EMAIL_HTML_CHARS * 2]
    except Exception:
        # Fail closed: an unexpected parser failure must never return raw HTML.
        return html.escape(source, quote=False)
