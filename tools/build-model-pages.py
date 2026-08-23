#!/usr/bin/env python3
"""Generate the per-package detail pages (models/<id>.html) and models/index.html
from packages/catalog.json.

Each page shows the package's measured numbers (featured metric, measured
context-depth profiles drawn as static SVG from the catalog's exact points —
nothing interpolated), links to the proof and the full guide, and a clearly
labeled projection block that learn/assets/mlbottleneck-bridge.js fills from
the ML Bottleneck engine at page load. Run after changing packages/catalog.json:

    python3 tools/build-model-pages.py

The ML mapping (which ML Bottleneck preset / quant / runtime / speed-up a
package corresponds to) lives in PACKAGE_ML below; add an entry when a new
package lands, or the page simply omits the projection block.
"""
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "packages", "catalog.json")
OUT_DIR = os.path.join(ROOT, "models")
GITHUB = "https://github.com/steveseguin/b70-optimization-lab/blob/main/"
ISSUE = "https://github.com/steveseguin/b70-optimization-lab/issues/new?template=result.yml&title="
SITE = "https://neural.download/"

# package id -> ML Bottleneck request (preset key, exact quant label, runtime, speed-up, strategy)
PACKAGE_ML = {
    "gemma4-26b-a4b-q8-b70-125tps-20260701": {"model": "gemma4_26b_a4b", "quant": "UD-Q8_K_XL", "runtime": "llama_cpp", "spec": "mtp:3"},
    "laguna-s-2.1-int4-b70-125tps-20260731": {"model": "laguna_s_2.1", "quant": "AutoRound INT4", "runtime": "vllm", "spec": "dflash:11"},
    "lfm25-26b-q8-b70": {"model": "lfm2.5_2.6b", "quant": "Q8_0", "runtime": "llama_cpp", "spec": "none"},
    "minimax-m27-b70-89tps-20260520": {"model": "minimax_m2.7", "quant": "AutoRound INT4", "runtime": "vllm", "spec": "none"},
    "muse-glimmer-30b-q8-woq-b70-100tps-20260813": {"model": "muse_glimmer_30b", "quant": "UD-Q8_K_XL", "runtime": "llama_cpp", "spec": "draft_model:15", "strategy": "tensor"},
    "nemotron-35-lightning-30b-a3b-b70": {"model": "nemotron3.5_lightning_30b_a3b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none"},
    "ornith-15-35b-a3b-q4km-b70": {"model": "ornith_1.5_35b_a3b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none"},
    "ornith-15-9b-q8-b70": {"model": "ornith_1.5_9b", "quant": "Q8_0", "runtime": "llama_cpp", "spec": "none"},
    "qwen38-27b-256k-vision-mtp-b70": {"model": "qwen3.8_27b", "quant": "Q5_K_S", "runtime": "llama_cpp", "spec": "mtp:3"},
    "qwen38-27b-fp8-vllm-tp2-asrock-b70": {"model": "qwen3.8_27b", "quant": "FP8", "runtime": "vllm", "spec": "none"},
    "qwen38-27b-q4km-tp1-b70": {"model": "qwen3.8_27b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none"},
    "qwen38-27b-q8-tp2-asrock-b70": {"model": "qwen3.8_27b", "quant": "Q8_0", "runtime": "llama_cpp", "spec": "none", "strategy": "tensor"},
}

STATUS_LABEL = {"candidate": "Candidate package", "lab": "Lab result", "research": "Research", "starter": "Starter guide", "record": "Record replay"}


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def fmt(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:.1f}" if value < 100 else f"{value:.0f}"


def gb(value):
    try:
        return f"{float(value) / 1e9:.1f} GB"
    except (TypeError, ValueError):
        return "—"


def svg_profile(profile):
    """Static SVG of one measured profile: exact points, straight connectors."""
    points = [p for p in profile.get("points", []) if isinstance(p.get("value"), (int, float))]
    if len(points) < 2:
        return ""
    xs = [max(1, float(p.get("context_tokens", 0))) for p in points]
    ys = [float(p["value"]) for p in points]
    width, height, left, top, right, bottom = 640, 260, 64, 20, 20, 44
    import math
    lx = [math.log2(x) for x in xs]
    x0, x1 = min(lx), max(lx)
    y1 = max(ys) * 1.1
    def sx(v):
        return left + ((math.log2(max(1, v)) - x0) / max(1e-9, x1 - x0)) * (width - left - right)
    def sy(v):
        return top + (1 - v / y1) * (height - top - bottom)
    path = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots = "".join(
        f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="var(--spot)"></circle>'
        f'<text x="{sx(x):.1f}" y="{sy(y) - 9:.1f}" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--ink)">{fmt(y)}</text>'
        for x, y in zip(xs, ys)
    )
    def ktok(v):
        v = int(v)
        if v < 2:
            return "0"
        return f"{v // 1024}K" if v >= 1024 and v % 1024 == 0 else (f"{v / 1024:.1f}K" if v >= 1024 else str(v))
    ticks = "".join(
        f'<text x="{sx(x):.1f}" y="{height - 24}" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--muted)">{ktok(x)}</text>'
        for x in xs
    )
    unit = profile.get("unit", "tok/s")
    label = profile.get("label") or profile.get("id", "")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{esc(label)}" xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="{left}" y1="{sy(0):.1f}" x2="{width - right}" y2="{sy(0):.1f}" stroke="var(--ink)" stroke-width="2"></line>'
        f'<path d="{path}" fill="none" stroke="var(--spot)" stroke-width="3"></path>{dots}{ticks}'
        f'<text x="{left}" y="{height - 6}" font-size="11" font-family="var(--mono)" fill="var(--muted)">{esc(profile.get("x_label", "context tokens"))} ({unit})</text>'
        f"</svg>"
    )


def page(pkg, all_pkgs):
    lib = pkg["library"]
    fm = lib.get("featured_metric") or {}
    hw = pkg.get("hardware") or {}
    model = pkg.get("model") or {}
    runtime = pkg.get("runtime") or {}
    pid = pkg["id"]
    name = pkg["name"]
    title = f"{name} — {fmt(fm.get('value'))} {fm.get('unit', 'tok/s')} measured — neural.download"
    desc = f"{lib.get('summary', '')} Measured {fmt(fm.get('value'))} {fm.get('unit', 'tok/s')} {fm.get('label', 'decode')} on {hw.get('cards', 1)}× {hw.get('accelerator', 'Intel Arc Pro B70')} with {lib.get('runtime_label', '')} ({lib.get('quantization', '')}). Exact pins, patches, proof, and a projected optimization headroom."
    desc = re.sub(r"\s+", " ", desc).strip()[:300]
    url = f"{SITE}models/{pid}.html"
    status = STATUS_LABEL.get(pkg.get("status"), pkg.get("status", "").title())
    ml = PACKAGE_ML.get(pid)
    ml_attrs = ""
    if ml:
        ml_attrs = (f' data-ml-model="{esc(ml["model"])}" data-ml-quant="{esc(ml["quant"])}" data-ml-runtime="{esc(ml["runtime"])}"'
                    f' data-ml-cards="{esc(hw.get("cards", 1))}" data-ml-hardware="Intel Arc Pro B70" data-ml-hardware-label="B70" data-ml-spec="{esc(ml.get("spec", "none"))}"'
                    f' data-ml-measured="{esc(fm.get("value", ""))}" data-ml-quant-label="{esc(lib.get("quantization", ""))}" data-ml-runtime-label="{esc(lib.get("runtime_label", ""))}"'
                    + (f' data-ml-strategy="{esc(ml["strategy"])}"' if ml.get("strategy") else ""))
    facts = [
        ("Model", f"{lib.get('model_family', '')} {lib.get('variant', '')}".strip()),
        ("Publisher", lib.get("publisher", "")),
        ("Checkpoint", model.get("repository", "")),
        ("Compression", lib.get("quantization", "")),
        ("Software", lib.get("runtime_label", "")),
        ("Cards", f"{hw.get('cards', 1)}× {hw.get('accelerator', 'Intel Arc Pro B70')}"),
        ("Model weight bytes", gb(hw.get("model_weight_bytes") or hw.get("target_model_bytes"))),
        ("Operating systems", ", ".join(lib.get("operating_systems", []))),
        ("Delivery", ", ".join("Docker / container" if v == "container" else v for v in lib.get("delivery", []))),
        ("Good for", ", ".join(lib.get("use_cases", []))),
        ("Published", lib.get("published_at", "")),
        ("Clean-host replay", "yes" if pkg.get("clean_host_tested") else "not yet"),
    ]
    facts_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v) if v else '—'}</dd></div>" for k, v in facts)
    profiles = [p for p in (pkg.get("performance_profiles") or []) if p.get("points")]
    profiles_html = "".join(
        f'<figure class="chart"><h4>{esc(p.get("label") or p.get("id"))} <span class="badge lab">Lab-measured</span></h4>{svg_profile(p)}'
        f'<figcaption>{esc(p.get("scope", ""))}' + (f' <a class="inline" href="{GITHUB}{esc(p["evidence"])}">evidence</a>' if p.get("evidence") else "") + "</figcaption></figure>"
        for p in profiles
    )
    evidence_link = f'<a class="inline" href="{GITHUB}{esc(fm["evidence"])}">proof file</a>' if fm.get("evidence") else ""
    missing = pkg.get("missing") or []
    missing_html = ""
    if missing:
        items = "".join(f"<li>{esc(m if isinstance(m, str) else m.get('item') or m.get('description') or json.dumps(m))}</li>" for m in missing[:8])
        missing_html = f'<div class="missing"><p class="missing-tag">Still missing before this becomes an install guide</p><ul>{items}</ul></div>'
    related = [p for p in all_pkgs if p["id"] != pid and p["library"].get("model_family") == lib.get("model_family")][:4]
    related_html = "".join(
        f'<a href="{esc(p["id"])}.html"><b>{esc(p["name"])}</b><span>{esc(fmt((p["library"].get("featured_metric") or {}).get("value")))} tok/s · {esc(p["library"].get("runtime_label", ""))}</span></a>'
        for p in related
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": name,
        "description": desc,
        "url": url,
        "dateModified": lib.get("published_at", "2026-08-23"),
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "author": {"@type": "Organization", "name": "Unofficial Intel XPU Optimization Lab", "url": SITE},
        "publisher": {"@type": "Organization", "name": "neural.download", "url": SITE},
        "isPartOf": {"@type": "WebSite", "name": "neural.download", "url": SITE},
        "about": [lib.get("model_family", ""), "Intel Arc Pro B70", "local LLM inference"],
    }
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "neural.download", "item": SITE},
            {"@type": "ListItem", "position": 2, "name": "Models", "item": f"{SITE}models/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": url},
        ],
    }
    projection_html = ""
    if ml:
        projection_html = f"""
  <h2 id="projection">How much faster could this get? <span class="badge spec">Projected — not measured</span></h2>
  <p>The <a class="inline" href="https://mlbottleneck.com/">ML Bottleneck</a> physics engine projects what stock software, a tuned run, and the physical ceiling look like for this exact model, compression, card count, and software. The grade is optimization headroom against the tuned-run target, not model quality.</p>
  <div id="package-projection" class="projection" hidden>
    <p class="projection-status" data-projection-status>Loading projections from mlbottleneck.com…</p>
    <div data-package-card></div>
    <div data-package-charts></div>
  </div>
  <noscript><p class="projection-status">Projections need JavaScript; the measured numbers above are static.</p></noscript>"""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2064%2064'%3E%3Crect%20width='64'%20height='64'%20fill='%230f62e8'/%3E%3Crect%20x='10'%20y='34'%20width='12'%20height='20'%20fill='%23f6f1e5'/%3E%3Crect%20x='26'%20y='22'%20width='12'%20height='32'%20fill='%23f6f1e5'/%3E%3Crect%20x='42'%20y='10'%20width='12'%20height='44'%20fill='%23f6f1e5'/%3E%3C/svg%3E">
<link rel="canonical" href="{esc(url)}">
<meta name="theme-color" content="#f6f1e5">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(url)}">
<meta property="og:title" content="{esc(name)} — {esc(fmt(fm.get('value')))} tok/s on Intel Arc Pro B70">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="https://neural.download/og-image.png">
<meta property="og:site_name" content="neural.download">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False)}
</script>
<script type="application/ld+json">
{json.dumps(crumbs, ensure_ascii=False)}
</script>
<link rel="stylesheet" href="../learn/learn.css">
<link rel="preconnect" href="https://mlbottleneck.com">
<style>
  .facts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px 16px; margin: 14px 0 22px; padding: 14px 16px; border: 2px solid var(--ink); background: var(--paper); }}
  .facts div {{ min-width: 0; }}
  .facts dt {{ font: 700 10px var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
  .facts dd {{ margin: 2px 0 0; font-size: 13.5px; overflow-wrap: anywhere; }}
  .missing {{ margin: 0 0 22px; padding: 12px 16px; border: 2px solid var(--ink); background: var(--surface); }}
  .missing-tag {{ margin: 0 0 6px; font: 700 10px var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--warn); }}
  .missing ul {{ margin: 0; padding-left: 18px; font-size: 13px; }}
  .measured {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 18px; margin: 8px 0 6px; }}
  .measured .big {{ font: 900 44px/1 var(--display); color: var(--spot-dark); }}
  .measured .unit {{ font: 700 13px var(--mono); text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }}
  .scope {{ margin: 0 0 12px; color: var(--muted); font-size: 13px; }}
  .actions {{ display: flex; flex-wrap: wrap; gap: 9px 12px; margin: 14px 0 22px; align-items: center; }}
  .actions .button {{ display: inline-flex; align-items: center; min-height: 36px; padding: 7px 12px; border: 2px solid var(--ink); background: var(--ink); color: var(--paper); font: 700 11px var(--mono); text-transform: uppercase; letter-spacing: .05em; }}
  .actions .button:hover {{ background: var(--spot); border-color: var(--spot); color: #fff; }}
  .actions .button.secondary {{ background: transparent; color: var(--ink); }}
  .actions .button.secondary:hover {{ background: var(--ink); color: var(--paper); }}
  .copy-md {{ appearance: none; border: 2px solid var(--ink); border-radius: 0; background: transparent; color: var(--ink); min-height: 36px; padding: 6px 10px; font: 700 11px var(--mono); letter-spacing: .05em; text-transform: uppercase; cursor: pointer; }}
  .copy-md:hover {{ background: var(--ink); color: var(--paper); }}
  .copy-md.copied {{ background: var(--spot); border-color: var(--spot); color: #fff; }}
  .copy-md.failed {{ border-color: #a12820; color: #a12820; }}
  .hr-card {{ border: 2px solid var(--ink); background: var(--paper); padding: 13px 14px 11px; margin: 0 0 12px; }}
  .hr-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px; }}
  .hr-card h3 {{ margin: 0; font: 900 15px var(--display); text-transform: uppercase; }}
  .hr-deploy {{ margin: 3px 0 0; color: var(--muted); font: 10.5px var(--mono); }}
  .hr-grade {{ flex: 0 0 auto; text-align: right; }}
  .hr-grade-letter {{ display: block; font: 900 26px/1 var(--display); color: var(--spot-dark); }}
  .hr-grade-note {{ display: block; margin-top: 3px; color: var(--muted); font: 700 9.5px var(--mono); text-transform: uppercase; letter-spacing: .05em; }}
  .hr-bar-row {{ display: grid; grid-template-columns: 108px 1fr 78px; align-items: center; gap: 8px; margin: 5px 0; font: 10.5px var(--mono); }}
  .hr-bar-label {{ color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .hr-bar-track {{ display: block; height: 9px; background: var(--surface); border: 1px solid var(--ink); }}
  .hr-bar {{ display: block; height: 100%; background: var(--ink); }}
  .hr-bar.is-measured {{ background: var(--spot); }}
  .hr-bar.is-stock {{ background: var(--ink); opacity: .45; }}
  .hr-bar.is-physical {{ background: var(--muted); opacity: .55; }}
  .hr-bar-value {{ text-align: right; font-weight: 700; white-space: nowrap; }}
  .hr-bar-value small {{ font-weight: 400; color: var(--muted); }}
  .hr-why {{ margin: 9px 0 0; color: var(--muted); font-size: 12px; }}
  .hr-links {{ margin: 7px 0 0; font: 10.5px var(--mono); text-transform: uppercase; letter-spacing: .05em; }}
  .hr-links a {{ border-bottom: 1px solid currentColor; }}
  @media (max-width: 520px) {{ .hr-bar-row {{ grid-template-columns: 92px 1fr 70px; }} .measured .big {{ font-size: 36px; }} }}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="site-nav"><div class="wrap">
  <a class="brand" href="../index.html"><span class="brand-mark" aria-hidden="true">▮▮▮</span>neural.download</a>
  <nav aria-label="Primary">
    <a href="../index.html">Home</a>
    <a href="index.html" aria-current="page">Models</a>
    <a href="../learn.html">Learn</a>
    <a href="../guides.html">Guide library</a>
    <a href="../index.html#lab-speeds">Benchmarks</a>
    <a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a>
  </nav>
</div></div>

<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / <a href="index.html">Models</a> / {esc(lib.get('model_family', ''))}</p>
  <p class="eyebrow">{esc(status)} · {esc(lib.get('runtime_label', ''))} · {esc(hw.get('cards', 1))}× Intel Arc Pro B70</p>
  <h1>{esc(name)}</h1>
  <p>{esc(lib.get('summary', ''))}</p>
</div></header>

<main id="main"><div class="wrap"><div class="col prose" id="package-page"{ml_attrs}>

  <h2 id="measured">What we measured <span class="badge lab">Lab-measured</span></h2>
  <div class="measured"><span class="big">{esc(fmt(fm.get('value')))}</span><span class="unit">{esc(fm.get('unit', 'tok/s'))} {esc(fm.get('label', 'decode'))}</span></div>
  <p class="scope">{esc(fm.get('scope', ''))} {evidence_link}</p>
  <div class="actions">
    <a class="button" href="{GITHUB}{esc(pkg.get('guide', ''))}">Open the full guide</a>
    <button type="button" class="copy-md" data-copy-markdown="../{esc(pkg.get('guide', ''))}" aria-label="Copy the guide Markdown" aria-live="polite">Copy Markdown</button>
    <a class="button secondary" href="{ISSUE}{esc(name.replace(' ', '%20'))}">Submit an improvement</a>
  </div>

  <dl class="facts">{facts_html}</dl>
  {missing_html}
  {('<h2 id="profiles">Measured across context depth <span class="badge lab">Lab-measured</span></h2>' + profiles_html) if profiles_html else ''}
  {projection_html}

  <div class="related">
    <h2>Keep going</h2>
    <div class="related-grid">
      {related_html}
      <a href="../learn.html"><b>Learn</b><span>What sets these numbers</span></a>
      <a href="../guides.html"><b>Guide library</b><span>Every package, filterable</span></a>
      <a href="../index.html#contribute"><b>Contribute</b><span>Made it faster? Send it in</span></a>
    </div>
  </div>

</div></div></main>

<footer><div class="wrap">
  <span>Unofficial community lab — not affiliated with or endorsed by Intel. Measured numbers link to their proof; projections are labeled and come from a physics model.</span>
  <span><a href="../learn.html">Learn</a> · <a href="../guides.html">Guide library</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a> · <a href="https://mlbottleneck.com/" title="Physics-based LLM speed and memory planner for any GPU — same author">ML Bottleneck</a> · <a href="https://style-genome.com/" title="Design-system generator used to style this site — same author">Style Genome</a></span>
</div></footer>
<script defer src="../learn/assets/mlbottleneck-bridge.js"></script>
<script>
(() => {{
  document.querySelectorAll("[data-copy-markdown]").forEach((button) => {{
    button.addEventListener("click", async () => {{
      const original = button.textContent; button.disabled = true; button.textContent = "Copying…";
      try {{
        const response = await fetch(button.dataset.copyMarkdown, {{ cache: "no-store" }});
        if (!response.ok) throw new Error("fetch failed");
        await navigator.clipboard.writeText(await response.text());
        button.textContent = "Copied"; button.classList.add("copied");
      }} catch (error) {{ button.textContent = "Copy failed"; button.classList.add("failed"); }}
      window.setTimeout(() => {{ button.textContent = original; button.classList.remove("copied", "failed"); button.disabled = false; }}, 1800);
    }});
  }});
}})();
</script>
</body>
</html>
"""


def index_page(pkgs):
    rows = "".join(
        f'<a class="guide-card" href="{esc(p["id"])}.html"><div class="gc-top"><div class="gc-n">{esc(STATUS_LABEL.get(p.get("status"), p.get("status", "")))} · {esc(p["library"].get("runtime_label", ""))}</div><h3>{esc(p["name"])}</h3></div>'
        f'<div class="gc-body"><p>{esc(p["library"].get("summary", ""))}</p><p class="gc-meta"><strong>{esc(fmt((p["library"].get("featured_metric") or {}).get("value")))} tok/s</strong> measured · {esc((p.get("hardware") or {}).get("cards", 1))}× B70 · {esc(p["library"].get("quantization", ""))}</p></div></a>'
        for p in pkgs
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model deployments on Intel Arc Pro B70 — measured speeds, proofs, and projected headroom — neural.download</title>
<meta name="description" content="Every reproducible model package this lab has measured on Intel Arc Pro B70 cards: decode speed with proof links, exact pins and patches, measured context-depth curves, and a projected optimization headroom from the ML Bottleneck physics engine.">
<link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2064%2064'%3E%3Crect%20width='64'%20height='64'%20fill='%230f62e8'/%3E%3Crect%20x='10'%20y='34'%20width='12'%20height='20'%20fill='%23f6f1e5'/%3E%3Crect%20x='26'%20y='22'%20width='12'%20height='32'%20fill='%23f6f1e5'/%3E%3Crect%20x='42'%20y='10'%20width='12'%20height='44'%20fill='%23f6f1e5'/%3E%3C/svg%3E">
<link rel="canonical" href="{SITE}models/">
<meta name="theme-color" content="#f6f1e5">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE}models/">
<meta property="og:title" content="Model deployments on Intel Arc Pro B70 — neural.download">
<meta property="og:description" content="Measured speeds with proofs, exact pins, and projected headroom for every package.">
<meta property="og:image" content="https://neural.download/og-image.png">
<meta property="og:site_name" content="neural.download">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{json.dumps({"@context": "https://schema.org", "@type": "CollectionPage", "name": "Model deployments on Intel Arc Pro B70", "url": f"{SITE}models/", "isPartOf": {"@type": "WebSite", "name": "neural.download", "url": SITE}, "inLanguage": "en", "isAccessibleForFree": True})}
</script>
<link rel="stylesheet" href="../learn/learn.css">
<style>
  .guide-card .gc-body {{ padding: 12px 16px 14px; }}
  .guide-card .gc-body p {{ margin: 0 0 8px; color: var(--muted); font-size: 13px; }}
  .guide-card .gc-meta {{ font: 11px var(--mono); color: var(--ink); }}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="site-nav"><div class="wrap">
  <a class="brand" href="../index.html"><span class="brand-mark" aria-hidden="true">▮▮▮</span>neural.download</a>
  <nav aria-label="Primary">
    <a href="../index.html">Home</a>
    <a href="index.html" aria-current="page">Models</a>
    <a href="../learn.html">Learn</a>
    <a href="../guides.html">Guide library</a>
    <a href="../index.html#lab-speeds">Benchmarks</a>
    <a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a>
  </nav>
</div></div>
<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / Models</p>
  <p class="eyebrow">One page per measured deployment</p>
  <h1>Model deployments</h1>
  <p>Each page carries the lab's measured speed with its proof, the exact pins and patches, the measured context-depth curves where we swept them, and a clearly labeled projection of how much faster the setup could get.</p>
</div></header>
<main id="main"><div class="wrap">
  <div class="guide-cards">{rows}</div>
</div></main>
<footer><div class="wrap">
  <span>Unofficial community lab — not affiliated with or endorsed by Intel.</span>
  <span><a href="../learn.html">Learn</a> · <a href="../guides.html">Guide library</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a> · <a href="https://mlbottleneck.com/" title="Physics-based LLM speed and memory planner for any GPU — same author">ML Bottleneck</a> · <a href="https://style-genome.com/" title="Design-system generator used to style this site — same author">Style Genome</a></span>
</div></footer>
</body>
</html>
"""


def main():
    with open(CATALOG, encoding="utf-8") as handle:
        catalog = json.load(handle)
    pkgs = sorted(catalog["packages"], key=lambda p: -float(((p["library"].get("featured_metric") or {}).get("value") or 0)))
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for pkg in pkgs:
        path = os.path.join(OUT_DIR, f"{pkg['id']}.html")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(page(pkg, pkgs))
        written.append(path)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(index_page(pkgs))
    unmapped = [p["id"] for p in pkgs if p["id"] not in PACKAGE_ML]
    print(f"wrote {len(written)} package pages + models/index.html")
    if unmapped:
        print("packages without an ML Bottleneck mapping (no projection block):", ", ".join(unmapped), file=sys.stderr)


if __name__ == "__main__":
    main()
