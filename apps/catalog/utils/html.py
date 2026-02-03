from __future__ import annotations

from typing import Iterable

import bleach
from bleach.css_sanitizer import CSSSanitizer


ALLOWED_TAGS: list[str] = [
    "p",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "span",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
]

ALLOWED_ATTRIBUTES: dict[str, Iterable[str]] = {
    "*": ["style"],
    "a": ["href", "title", "rel", "target"],
}

ALLOWED_PROTOCOLS: list[str] = ["http", "https", "mailto", "tel"]

CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "background-color",
        "font-weight",
        "font-style",
        "text-decoration",
        "text-align",
        "font-size",
        "line-height",
        "letter-spacing",
        "margin",
        "margin-left",
        "margin-right",
        "margin-top",
        "margin-bottom",
        "padding",
        "padding-left",
        "padding-right",
        "padding-top",
        "padding-bottom",
        "border",
        "border-width",
        "border-style",
        "border-color",
        "border-radius",
        "display",
        "list-style",
        "list-style-type",
    ]
)

_CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=ALLOWED_ATTRIBUTES,
    protocols=ALLOWED_PROTOCOLS,
    strip=True,
    css_sanitizer=CSS_SANITIZER,
)


def sanitize_html(value: str | None) -> str | None:
    if value is None:
        return None
    return _CLEANER.clean(value)
