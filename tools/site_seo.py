"""Shared social/SEO head fragment for every neural.download page.

Both page generators and the hand-written pages use the same block, so a
share on X, Slack, iMessage, or Google always finds: a real favicon set,
canonical, Open Graph with image dimensions + alt, the twitter:* set
(X ignores the OG fallback more often than its docs say), and site name.

Usage:
    from site_seo import seo_head
    seo_head(url, title, description, image=..., image_alt=..., og_type="website")

`image` defaults to the site card; model pages pass their own card.
"""
from __future__ import annotations

import html

SITE = "https://neural.download/"
SITE_NAME = "neural.download"
TWITTER_SITE = "@xyster"
DEFAULT_IMAGE = SITE + "og-image.png"
DEFAULT_IMAGE_ALT = "neural.download — Run AI at home. We make it faster. Tuned recipes and measured LLM speeds on Intel Arc Pro B70, every number linked to its proof."
IMAGE_W = 1200
IMAGE_H = 630

FAVICON_LINKS = """<link rel="icon" href="{base}favicon.ico" sizes="32x32">
<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{base}apple-touch-icon.png">
<link rel="manifest" href="{base}site.webmanifest">"""


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def clip(text, limit: int = 320) -> str:
    """Collapse whitespace and cut to `limit` at a sentence end (preferred) or a
    word boundary with an ellipsis, never mid-word. Share previews truncate
    anyway, but the cut we control should read as a sentence."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "), cut.rfind(".") if cut.endswith(".") else -1)
    if end >= limit // 3:
        return cut[: end + 1]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "\u2026"


def favicon_links(depth: int = 0) -> str:
    """depth = how many folders below the site root the page lives."""
    base = "../" * depth
    return FAVICON_LINKS.format(base=base)


def seo_head(
    url: str,
    title: str,
    description: str,
    *,
    image: str = DEFAULT_IMAGE,
    image_alt: str = DEFAULT_IMAGE_ALT,
    og_type: str = "website",
    depth: int = 0,
) -> str:
    """Everything between <title> and the stylesheet, minus JSON-LD."""
    description = clip(description)
    return f"""<meta name="description" content="{esc(description)}">
{favicon_links(depth)}
<link rel="canonical" href="{esc(url)}">
<meta name="theme-color" content="#0f62e8">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:locale" content="en_US">
<meta property="og:url" content="{esc(url)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:image" content="{esc(image)}">
<meta property="og:image:secure_url" content="{esc(image)}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="{IMAGE_W}">
<meta property="og:image:height" content="{IMAGE_H}">
<meta property="og:image:alt" content="{esc(image_alt)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="{TWITTER_SITE}">
<meta name="twitter:creator" content="{TWITTER_SITE}">
<meta name="twitter:url" content="{esc(url)}">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{esc(image)}">
<meta name="twitter:image:alt" content="{esc(image_alt)}">"""
