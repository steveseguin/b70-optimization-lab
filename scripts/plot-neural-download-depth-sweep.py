#!/usr/bin/env python3
"""Render a neural.download depth-sweep JSON as a dependency-free SVG.

Two panels: decode tg128 tok/s vs context depth, and prefill pp2048 tok/s
vs context depth, with +/- stddev whiskers. Deterministic output bytes for
a given input.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

W, H = 860, 400
PAD_L, PAD_R, PAD_T, PAD_B = 70, 20, 42, 52
PANEL_GAP = 60
COLORS = {"tg": "#2563eb", "pp": "#dc2626"}


def nice_ticks(vmax: float, n: int = 5) -> list[float]:
    if vmax <= 0:
        return [0, 1]
    raw = vmax / n
    mag = 10 ** len(str(int(raw))) / 10 if raw >= 1 else 1
    step = max(1, round(raw / mag)) * mag
    ticks, v = [], 0.0
    while v <= vmax * 1.02:
        ticks.append(v)
        v += step
    return ticks


def panel(series, title, x0, panel_w, unit):
    depths = [p["depth"] for p in series]
    vmax = max(p["avg"] + p["std"] for p in series)
    xmax = max(depths) or 1
    ticks = nice_ticks(vmax)
    top = ticks[-1]
    ih = H - PAD_T - PAD_B
    iw = panel_w

    def sx(d):
        return x0 + d / xmax * iw

    def sy(v):
        return PAD_T + ih - v / top * ih

    parts = [
        f'<text x="{x0 + iw / 2:.1f}" y="{PAD_T - 18}" text-anchor="middle" '
        f'class="t">{title}</text>'
    ]
    for tv in ticks:
        y = sy(tv)
        parts.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + iw}" y2="{y:.1f}" class="grid"/>'
        )
        parts.append(
            f'<text x="{x0 - 8}" y="{y + 4:.1f}" text-anchor="end" class="ax">'
            f"{tv:g}</text>"
        )
    for d in depths:
        x = sx(d)
        label = f"{d // 1024}k" if d >= 1024 else str(d)
        parts.append(
            f'<text x="{x:.1f}" y="{H - PAD_B + 18}" text-anchor="middle" '
            f'class="ax">{label}</text>'
        )
    color = COLORS["tg" if "tg" in title else "pp"]
    pts = " ".join(f"{sx(p['depth']):.1f},{sy(p['avg']):.1f}" for p in series)
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"/>'
    )
    for p in series:
        x, ylo, yhi = sx(p["depth"]), sy(p["avg"] - p["std"]), sy(p["avg"] + p["std"])
        parts.append(
            f'<line x1="{x:.1f}" y1="{ylo:.1f}" x2="{x:.1f}" y2="{yhi:.1f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<circle cx="{x:.1f}" cy="{sy(p["avg"]):.1f}" r="3.2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{sy(p["avg"]) - 8:.1f}" text-anchor="middle" '
            f'class="val">{p["avg"]:.0f}</text>'
        )
    parts.append(
        f'<text x="{x0 + iw / 2:.1f}" y="{H - 12}" text-anchor="middle" class="ax">'
        f"context depth (tokens)</text>"
    )
    parts.append(
        f'<text x="{x0 - 52}" y="{PAD_T + ih / 2:.1f}" class="ax" '
        f'transform="rotate(-90 {x0 - 52} {PAD_T + ih / 2:.1f})" '
        f'text-anchor="middle">{unit}</text>'
    )
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = json.load(open(a.sweep))
    tg = sorted(
        (
            {"depth": r.get("n_depth", 0), "avg": r["avg_ts"], "std": r["stddev_ts"]}
            for r in rows
            if r["n_gen"] and not r["n_prompt"]
        ),
        key=lambda p: p["depth"],
    )
    pp = sorted(
        (
            {"depth": r.get("n_depth", 0), "avg": r["avg_ts"], "std": r["stddev_ts"]}
            for r in rows
            if r["n_prompt"] and not r["n_gen"]
        ),
        key=lambda p: p["depth"],
    )
    pw = (W - PAD_L - PAD_R - PANEL_GAP) / 2
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
 .t {{ font: 600 14px sans-serif; fill: #111; }}
 .ax {{ font: 11px sans-serif; fill: #555; }}
 .val {{ font: 10px sans-serif; fill: #333; }}
 .grid {{ stroke: #e5e7eb; stroke-width: 1; }}
 .cap {{ font: 11px sans-serif; fill: #777; }}
</style>
<rect width="{W}" height="{H}" fill="white"/>
<text x="{W / 2}" y="18" text-anchor="middle" class="t">{a.title}</text>
{panel(tg, "decode tg128 (tok/s)", PAD_L, pw, "tok/s")}
{panel(pp, "prefill pp2048 (tok/s)", PAD_L + pw + PANEL_GAP, pw, "tok/s")}
<text x="{W / 2}" y="{H - 0}" text-anchor="middle" class="cap"></text>
</svg>
"""
    Path(a.out).write_text(svg)
    print(f"wrote {a.out} (tg points: {len(tg)}, pp points: {len(pp)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
