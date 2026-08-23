#!/usr/bin/env python3
"""Reusable on-brand SVG chart generator for the learn/ concept guides.
Writes standalone SVG files (baked colors, system fonts) referenced by the
guide HTML via <img>. Supports multi-series line charts and grouped bars.

Usage: gen-learn-chart.py OUT.svg '<json-spec>'
Line spec:
  {"type":"line","title":"...","x_label":"context tokens","y_label":"tok/s",
   "x_ticks":[0,8192,...],"x_tick_labels":["0","8K",...],"y_max":26,
   "series":[{"name":"KV f16","color":"#0f62e8","points":[[0,24.8],...]},
             {"name":"KV q8_0","color":"#8b3b14","dashed":true,"points":[...]}]}
Bars spec:
  {"type":"bars","title":"...","y_label":"tok/s","y_max":110,
   "categories":["off","1","2","3","4"],
   "series":[{"name":"...","color":"#0f62e8","values":[33.2,...]}]}
"""
import json, sys

PAPER = "#f6f1e5"; INK = "#14120e"; MUTED = "#4a463f"; LINE = "#c7c0b2"
SANS = "Inter, Arial, sans-serif"
MONO = "'American Typewriter', 'Courier New', monospace"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def frame(spec, W, H, L, R, T, B):
    """axes + gridlines + y labels; returns (parts, x(),y(),iw,ih)."""
    iw, ih = W - L - R, H - T - B
    ymax = spec["y_max"]
    p = [f'<rect x="0" y="0" width="{W}" height="{H}" fill="{PAPER}"/>']
    # horizontal gridlines + y ticks (5 divisions)
    for i in range(6):
        yv = ymax * i / 5
        yy = T + ih - ih * (yv / ymax)
        p.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{W-R}" y2="{yy:.1f}" stroke="{LINE}" stroke-width="1" stroke-dasharray="3 4"/>')
        lab = f"{yv:.0f}" if ymax >= 10 else f"{yv:.1f}"
        p.append(f'<text x="{L-7}" y="{yy+3.5:.1f}" text-anchor="end" fill="{MUTED}" font="10px {MONO}" font-family="{MONO}" font-size="10">{lab}</text>')
    # axes
    p.append(f'<line x1="{L}" y1="{T+ih:.1f}" x2="{W-R}" y2="{T+ih:.1f}" stroke="{INK}" stroke-width="1.6"/>')
    p.append(f'<line x1="{L}" y1="{T}" x2="{L}" y2="{T+ih:.1f}" stroke="{INK}" stroke-width="1.6"/>')
    # y axis label
    if spec.get("y_label"):
        cx, cy = L - 38, T + ih / 2
        p.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" transform="rotate(-90 {cx} {cy})" fill="{MUTED}" font-family="{MONO}" font-size="10.5">{esc(spec["y_label"])}</text>')
    return p, iw, ih, ymax


def legend(series, W, H):
    p = []
    x = 54
    y = H - 8
    for s in series:
        dash = ' stroke-dasharray="6 4"' if s.get("dashed") else ""
        p.append(f'<line x1="{x}" y1="{y-4}" x2="{x+22}" y2="{y-4}" stroke="{s["color"]}" stroke-width="3"{dash}/>')
        p.append(f'<text x="{x+27}" y="{y}" fill="{MUTED}" font-family="{MONO}" font-size="10.5">{esc(s["name"])}</text>')
        x += 27 + len(s["name"]) * 6.6 + 26
    return p


def line_chart(spec):
    W, H, L, R, T, B = 720, 320, 54, 14, 30, 58
    p, iw, ih, ymax = frame(spec, W, H, L, R, T, B)
    xmax = max(spec["x_ticks"])
    xmin = min(spec["x_ticks"])
    def X(v): return L + (v - xmin) / (xmax - xmin) * iw
    def Y(v): return T + ih - v / ymax * ih
    # title
    if spec.get("title"):
        p.insert(1, f'<text x="{W/2}" y="18" text-anchor="middle" fill="{INK}" font-family="{MONO}" font-size="12" font-weight="700">{esc(spec["title"])}</text>')
    # x ticks
    for v, lab in zip(spec["x_ticks"], spec.get("x_tick_labels") or spec["x_ticks"]):
        xx = X(v)
        p.append(f'<text x="{xx:.1f}" y="{T+ih+16:.1f}" text-anchor="middle" fill="{MUTED}" font-family="{MONO}" font-size="10">{esc(lab)}</text>')
    if spec.get("x_label"):
        p.append(f'<text x="{L+iw/2:.1f}" y="{T+ih+34:.1f}" text-anchor="middle" fill="{MUTED}" font-family="{MONO}" font-size="10.5">{esc(spec["x_label"])}</text>')
    # series
    for s in spec["series"]:
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in s["points"])
        dash = ' stroke-dasharray="6 4"' if s.get("dashed") else ""
        p.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"{dash} points="{pts}"/>')
        for x, y in s["points"]:
            p.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3.2" fill="{PAPER}" stroke="{s["color"]}" stroke-width="2"/>')
        # endpoint label
        lx, ly = s["points"][-1]
        p.append(f'<text x="{X(lx)-5:.1f}" y="{Y(ly)+(s.get("label_dy",-7)):.1f}" text-anchor="end" fill="{s["color"]}" font-family="{MONO}" font-size="10.5" font-weight="700">{ly:g}</text>')
    p += legend(spec["series"], W, H)
    return svg_wrap(p, W, H, spec.get("title", "chart"))


def bar_chart(spec):
    cats = spec["categories"]
    series = spec["series"]
    W, H, L, R, T, B = 720, 320, 54, 14, 30, 58
    p, iw, ih, ymax = frame(spec, W, H, L, R, T, B)
    if spec.get("title"):
        p.insert(1, f'<text x="{W/2}" y="18" text-anchor="middle" fill="{INK}" font-family="{MONO}" font-size="12" font-weight="700">{esc(spec["title"])}</text>')
    def Y(v): return T + ih - v / ymax * ih
    n = len(cats); ns = len(series)
    group_w = iw / n
    bar_w = group_w * 0.72 / ns
    for ci, cat in enumerate(cats):
        gx = L + ci * group_w + group_w * 0.14
        for si, s in enumerate(series):
            v = s["values"][ci]
            if v is None:
                continue
            bx = gx + si * bar_w
            by = Y(v)
            p.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w-2:.1f}" height="{T+ih-by:.1f}" fill="{s["color"]}"/>')
            p.append(f'<text x="{bx+(bar_w-2)/2:.1f}" y="{by-4:.1f}" text-anchor="middle" fill="{INK}" font-family="{MONO}" font-size="9.5" font-weight="700">{v:g}</text>')
        p.append(f'<text x="{L+ci*group_w+group_w/2:.1f}" y="{T+ih+16:.1f}" text-anchor="middle" fill="{MUTED}" font-family="{MONO}" font-size="10.5">{esc(cat)}</text>')
    if spec.get("x_label"):
        p.append(f'<text x="{L+iw/2:.1f}" y="{T+ih+34:.1f}" text-anchor="middle" fill="{MUTED}" font-family="{MONO}" font-size="10.5">{esc(spec["x_label"])}</text>')
    if ns > 1:
        p += legend(series, W, H)
    return svg_wrap(p, W, H, spec.get("title", "chart"))


def svg_wrap(parts, W, H, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'width="100%" role="img" aria-label="{esc(title)}">\n'
            + "\n".join(parts) + "\n</svg>\n")


def main():
    out = sys.argv[1]
    spec = json.loads(sys.argv[2])
    svg = line_chart(spec) if spec["type"] == "line" else bar_chart(spec)
    open(out, "w").write(svg)
    print("wrote", out)


if __name__ == "__main__":
    main()
