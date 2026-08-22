#!/usr/bin/env python3
"""Two-panel decode+prefill vs context chart, KV f16 vs q8_0, from the
qwen38-tp1-context-kv-sweep JSON. Self-contained SVG, matches the repo
depth-sweep chart style (860-wide sans, #e5e7eb grid)."""
import json, sys

src = sys.argv[1]
dst = sys.argv[2]
d = json.load(open(src))
depths = d["depths"]
dec = d["decode_tg128_tok_s"]
pre = d["prefill_pp2048_tok_s"]

W, H = 900, 460
PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 60, 70
panel_w = (W - PAD_L - PAD_R - 40) / 2
panel_h = H - PAD_T - PAD_B
xmax = max(depths)

BLUE = "#2563eb"   # f16
RED = "#dc2626"    # q8_0


def panel(x0, title, f16, q8, ymax, unit):
    y0 = PAD_T
    s = [f'<text x="{x0 + panel_w/2:.1f}" y="{y0-14}" text-anchor="middle" class="t">{title}</text>']
    # y grid + labels
    steps = 5
    for i in range(steps + 1):
        yv = ymax * i / steps
        yy = y0 + panel_h - panel_h * (yv / ymax)
        s.append(f'<line x1="{x0}" y1="{yy:.1f}" x2="{x0+panel_w:.1f}" y2="{yy:.1f}" class="grid"/>')
        s.append(f'<text x="{x0-8}" y="{yy+4:.1f}" text-anchor="end" class="ax">{yv:.0f}</text>')
    # x labels
    for xd in depths:
        xx = x0 + panel_w * (xd / xmax)
        lab = "0" if xd == 0 else (f"{xd//1024}K")
        s.append(f'<text x="{xx:.1f}" y="{y0+panel_h+18:.1f}" text-anchor="middle" class="ax">{lab}</text>')
    s.append(f'<text x="{x0+panel_w/2:.1f}" y="{y0+panel_h+40:.1f}" text-anchor="middle" class="cap">context depth (tokens)</text>')
    s.append(f'<text x="{x0-46}" y="{y0+panel_h/2:.1f}" text-anchor="middle" class="cap" transform="rotate(-90 {x0-46} {y0+panel_h/2:.1f})">{unit}</text>')

    def poly(vals, color, dash):
        pts = []
        for xd, v in zip(depths, vals):
            xx = x0 + panel_w * (xd / xmax)
            yy = y0 + panel_h - panel_h * (v / ymax)
            pts.append(f"{xx:.1f},{yy:.1f}")
        da = f' stroke-dasharray="6 4"' if dash else ""
        out = [f'<polyline fill="none" stroke="{color}" stroke-width="2.5"{da} points="{" ".join(pts)}"/>']
        for xd, v in zip(depths, vals):
            xx = x0 + panel_w * (xd / xmax)
            yy = y0 + panel_h - panel_h * (v / ymax)
            out.append(f'<circle cx="{xx:.1f}" cy="{yy:.1f}" r="2.6" fill="{color}"/>')
        return "".join(out)

    s.append(poly(f16, BLUE, False))
    s.append(poly(q8, RED, True))
    # endpoint value labels
    for vals, color, dy in ((f16, BLUE, -8), (q8, RED, 14)):
        xd, v = depths[-1], vals[-1]
        xx = x0 + panel_w * (xd / xmax)
        yy = y0 + panel_h - panel_h * (v / ymax)
        s.append(f'<text x="{xx-4:.1f}" y="{yy+dy:.1f}" text-anchor="end" class="val" fill="{color}">{v:.1f}</text>')
    return "".join(s)


dec_ymax = 30
pre_ymax = 1000
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
    '<style>',
    ' .t { font: 600 14px sans-serif; fill: #111; }',
    ' .ax { font: 11px sans-serif; fill: #555; }',
    ' .val { font: 600 10px sans-serif; }',
    ' .grid { stroke: #e5e7eb; stroke-width: 1; }',
    ' .cap { font: 11px sans-serif; fill: #777; }',
    ' .lg { font: 12px sans-serif; fill: #333; }',
    '</style>',
    f'<rect width="{W}" height="{H}" fill="white"/>',
    f'<text x="{W/2}" y="24" text-anchor="middle" class="t">Qwen3.8-27B Q4_K_M — 1× Arc Pro B70 TP1 — KV f16 vs q8_0 (llama-bench, fa on, 5 reps)</text>',
    panel(PAD_L, "decode tg128 (tok/s)", dec["kv_f16"], dec["kv_q8_0"], dec_ymax, "tok/s"),
    panel(PAD_L + panel_w + 40, "prefill pp2048 (tok/s)", pre["kv_f16"], pre["kv_q8_0"], pre_ymax, "tok/s"),
    # legend
    f'<line x1="{W/2-120}" y1="{H-16}" x2="{W/2-90}" y2="{H-16}" stroke="{BLUE}" stroke-width="2.5"/>',
    f'<text x="{W/2-84}" y="{H-12}" class="lg">KV f16</text>',
    f'<line x1="{W/2+10}" y1="{H-16}" x2="{W/2+40}" y2="{H-16}" stroke="{RED}" stroke-width="2.5" stroke-dasharray="6 4"/>',
    f'<text x="{W/2+46}" y="{H-12}" class="lg">KV q8_0</text>',
    '</svg>',
]
open(dst, "w").write("".join(parts) + "\n")
print("wrote", dst)
