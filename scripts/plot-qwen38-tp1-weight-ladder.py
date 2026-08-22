#!/usr/bin/env python3
"""Single-panel decode-vs-context chart, three weight quants, from the
qwen38-tp1-weight-ladder JSON. Self-contained SVG, repo chart style."""
import json, sys

d = json.load(open(sys.argv[1]))
dst = sys.argv[2]
depths = d["depths"]
V = d["variants"]
order = ["Q4_K_M", "UD-Q5_K_S", "UD-Q4_K_XL"]
colors = {"Q4_K_M": "#2563eb", "UD-Q5_K_S": "#16a34a", "UD-Q4_K_XL": "#dc2626"}

W, H = 860, 440
PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 56, 72
pw = W - PAD_L - PAD_R
ph = H - PAD_T - PAD_B
xmax = max(depths)
ymax = 26.0

s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
     '<style>',
     ' .t { font: 600 14px sans-serif; fill: #111; }',
     ' .ax { font: 11px sans-serif; fill: #555; }',
     ' .val { font: 600 10px sans-serif; }',
     ' .grid { stroke: #e5e7eb; stroke-width: 1; }',
     ' .cap { font: 11px sans-serif; fill: #777; }',
     ' .lg { font: 12px sans-serif; fill: #333; }',
     '</style>',
     f'<rect width="{W}" height="{H}" fill="white"/>',
     f'<text x="{W/2}" y="22" text-anchor="middle" class="t">Qwen3.8-27B TP1 decode vs context by weight quant — 1× Arc Pro B70, KV f16 (llama-bench tg128)</text>']
for i in range(6):
    yv = ymax * i / 5
    yy = PAD_T + ph - ph * (yv / ymax)
    s.append(f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{PAD_L+pw}" y2="{yy:.1f}" class="grid"/>')
    s.append(f'<text x="{PAD_L-8}" y="{yy+4:.1f}" text-anchor="end" class="ax">{yv:.0f}</text>')
for xd in depths:
    xx = PAD_L + pw * (xd / xmax)
    lab = "0" if xd == 0 else f"{xd//1024}K"
    s.append(f'<text x="{xx:.1f}" y="{PAD_T+ph+18:.1f}" text-anchor="middle" class="ax">{lab}</text>')
s.append(f'<text x="{PAD_L+pw/2:.1f}" y="{PAD_T+ph+40:.1f}" text-anchor="middle" class="cap">context depth (tokens)</text>')
s.append(f'<text x="{PAD_L-46}" y="{PAD_T+ph/2:.1f}" text-anchor="middle" class="cap" transform="rotate(-90 {PAD_L-46} {PAD_T+ph/2:.1f})">decode tok/s</text>')
for name in order:
    vals = V[name]["decode_tg128"]
    col = colors[name]
    pts = []
    for xd, v in zip(depths, vals):
        xx = PAD_L + pw * (xd / xmax)
        yy = PAD_T + ph - ph * (v / ymax)
        pts.append(f"{xx:.1f},{yy:.1f}")
    s.append(f'<polyline fill="none" stroke="{col}" stroke-width="2.5" points="{" ".join(pts)}"/>')
    for xd, v in zip(depths, vals):
        xx = PAD_L + pw * (xd / xmax)
        yy = PAD_T + ph - ph * (v / ymax)
        s.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="2.6" fill="{col}"/>')
    xd, v = depths[-1], vals[-1]
    xx = PAD_L + pw * (xd / xmax)
    yy = PAD_T + ph - ph * (v / ymax)
    s.append(f'<text x="{xx-4:.1f}" y="{yy-6:.1f}" text-anchor="end" class="val" fill="{col}">{v:.1f}</text>')
lx = PAD_L + 20
for name in order:
    s.append(f'<line x1="{lx}" y1="{H-16}" x2="{lx+28}" y2="{H-16}" stroke="{colors[name]}" stroke-width="2.5"/>')
    label = f"{name} ({V[name]['size_gib']} GiB)"
    s.append(f'<text x="{lx+34}" y="{H-12}" class="lg">{label}</text>')
    lx += 34 + len(label) * 7 + 24
s.append('</svg>')
open(dst, "w").write("".join(s) + "\n")
print("wrote", dst)
