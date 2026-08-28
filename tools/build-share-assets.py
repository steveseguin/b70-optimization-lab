#!/usr/bin/env python3
"""Generate the site's icons and social share cards from the brand.

Outputs (repo root unless noted):
  favicon.svg, favicon.ico (16/32/48), apple-touch-icon.png (180x180),
  site.webmanifest, og-image.png (1200x630 site card),
  models/cards/<page-id>.png (1200x630 per model page: name + headline number).

Run after changing packages/catalog.json or families/*.json:
    python tools/build-share-assets.py
Pure PIL; deterministic; no network.
"""
from __future__ import annotations

import json
import os
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PAPER = (246, 241, 229)
INK = (20, 18, 14)
SPOT = (15, 98, 232)
WHITE = (255, 255, 255)
MUTED = (200, 210, 235)

W, H = 1200, 630


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def mono(size: int) -> ImageFont.FreeTypeFont:
    for path in ["C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/cour.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def brand_mark(draw: ImageDraw.ImageDraw, x: int, y: int, unit: int, color=WHITE) -> None:
    """Three rising bars, the site's mark."""
    for i, (top, height) in enumerate(((34, 20), (22, 32), (10, 44))):
        bx = x + i * unit * 16 // 64
        draw.rectangle([bx, y + top * unit // 64, bx + unit * 12 // 64, y + (top + height) * unit // 64], fill=color)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= max_width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def site_card(path: Path) -> None:
    img = Image.new("RGB", (W, H), SPOT)
    d = ImageDraw.Draw(img)
    brand_mark(d, 72, 56, 64)
    d.text((150, 62), "NEURAL.DOWNLOAD", font=mono(30), fill=WHITE)
    d.text((72, 150), "RUN AI AT HOME.", font=font(82), fill=WHITE)
    d.text((72, 242), "WE MAKE IT FASTER.", font=font(82), fill=WHITE)
    body = "Tuned recipes for open AI models on an Intel Arc Pro B70 — every number links to its measured proof."
    y = 380
    for line in wrap(d, body, font(32, bold=False), 1000):
        d.text((72, y), line, font=font(32, bold=False), fill=WHITE)
        y += 44
    d.rectangle([72, 552, 1128, 556], fill=WHITE)
    d.text((72, 572), "UNOFFICIAL LAB · NOT AFFILIATED WITH INTEL · neural.download", font=mono(22), fill=MUTED)
    img.save(path, optimize=True)


def model_card(path: Path, name: str, headline: str | None, unit: str, subline: str) -> None:
    img = Image.new("RGB", (W, H), SPOT)
    d = ImageDraw.Draw(img)
    brand_mark(d, 72, 56, 56)
    d.text((140, 62), "NEURAL.DOWNLOAD · MEASURED ON INTEL ARC PRO B70", font=mono(24), fill=WHITE)
    name_font = font(66)
    lines = wrap(d, name.upper(), name_font, 1056)[:2]
    y = 140
    for line in lines:
        d.text((72, y), line, font=name_font, fill=WHITE)
        y += 76
    if headline:
        d.text((72, y + 24), headline, font=font(150), fill=WHITE)
        num_w = d.textlength(headline, font=font(150))
        d.text((72 + num_w + 22, y + 118), unit.upper(), font=mono(28), fill=WHITE)
        y += 200
    else:
        d.text((72, y + 24), "NOT MEASURED YET", font=font(56), fill=MUTED)
        y += 110
    sub_font = font(28, bold=False)
    for line in wrap(d, subline, sub_font, 1056)[:2]:
        d.text((72, y + 10), line, font=sub_font, fill=WHITE)
        y += 38
    d.rectangle([72, 552, 1128, 556], fill=WHITE)
    d.text((72, 572), "EVERY NUMBER LINKS TO ITS PROOF · neural.download", font=mono(22), fill=MUTED)
    img.save(path, optimize=True)


def favicon_svg(path: Path) -> None:
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#0f62e8"/>'
        '<rect x="10" y="34" width="12" height="20" fill="#f6f1e5"/><rect x="26" y="22" width="12" height="32" fill="#f6f1e5"/>'
        '<rect x="42" y="10" width="12" height="44" fill="#f6f1e5"/></svg>\n',
        encoding="utf-8",
    )


def icon_png(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), SPOT)
    d = ImageDraw.Draw(img)
    brand_mark(d, 0, 0, size, color=PAPER)
    return img


def favicon_ico(path: Path) -> None:
    icon_png(48).save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])


def apple_touch(path: Path) -> None:
    img = Image.new("RGB", (180, 180), SPOT)
    d = ImageDraw.Draw(img)
    brand_mark(d, 26, 26, 128, color=PAPER)
    img.save(path, optimize=True)


def manifest(path: Path) -> None:
    path.write_text(json.dumps({
        "name": "neural.download",
        "short_name": "neural.download",
        "description": "Tuned recipes and measured LLM speeds on Intel Arc Pro B70, every number linked to its proof.",
        "start_url": "/",
        "display": "browser",
        "background_color": "#f6f1e5",
        "theme_color": "#0f62e8",
        "icons": [
            {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/png"},
            {"src": "/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
        ],
    }, indent=2) + "\n", encoding="utf-8")


def fmt(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    return f"{v:,.0f}" if v >= 100 else f"{v:.1f}"


def first_sentence(text: str) -> str:
    """First sentence of a summary, keeping its terminal punctuation."""
    text = " ".join(str(text or "").split())
    if not text:
        return ""
    first = text.split(". ")[0].rstrip()
    return first if first.endswith((".", "!", "?")) else first + "."


def main() -> None:
    favicon_svg(ROOT / "favicon.svg")
    favicon_ico(ROOT / "favicon.ico")
    apple_touch(ROOT / "apple-touch-icon.png")
    manifest(ROOT / "site.webmanifest")
    site_card(ROOT / "og-image.png")
    cards = ROOT / "models" / "cards"
    cards.mkdir(parents=True, exist_ok=True)
    written = 5

    # Package pages: headline from the catalog.
    catalog = json.loads((ROOT / "packages" / "catalog.json").read_text(encoding="utf-8"))
    for pkg in catalog["packages"]:
        lib = pkg.get("library") or {}
        fm = lib.get("featured_metric") or {}
        hw = pkg.get("hardware") or {}
        cards_n = hw.get("cards", 1)
        sub = f"{cards_n}× Intel Arc Pro B70 · {lib.get('quantization', '')} · {lib.get('runtime_label', '')}".strip(" ·")
        model_card(cards / f"{pkg['id']}.png", pkg.get("name") or pkg["id"], fmt(fm.get("value")) or None, fm.get("unit", "tok/s") + " measured", sub)
        written += 1

    # Family pages: hero from featured_results, else the promoted packet metric
    # via the family generator's own resolver so the card never disagrees with
    # the page.
    import importlib.util
    spec = importlib.util.spec_from_file_location("bfp", ROOT / "tools" / "build-family-pages.py")
    bfp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bfp)
    family_catalog = json.loads((ROOT / "families" / "catalog.json").read_text(encoding="utf-8"))
    for entry in family_catalog.get("families", []):
        family = json.loads((ROOT / entry["manifest"]).read_text(encoding="utf-8"))
        entries = bfp.featured_result_entries(family)
        hero = next((e for e in entries if e.get("role") == "hero"), None)
        summary = str(family.get("summary") or "")
        model_card(
            cards / f"{family['id']}.png",
            family.get("display_name") or family.get("name") or family["id"],
            fmt(hero["value"]) if hero else None,
            (hero["unit"] if hero else "tok/s") + " measured",
            first_sentence(summary),
        )
        written += 1
    print(f"wrote {written} share assets (icons, site card, {written - 5} model cards)")


if __name__ == "__main__":
    main()
