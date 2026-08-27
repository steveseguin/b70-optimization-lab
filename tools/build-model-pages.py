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
import hashlib
import html
import json
import sys
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from site_seo import seo_head  # noqa: E402
CATALOG = os.path.join(ROOT, "packages", "catalog.json")
FAMILY_CATALOG = os.path.join(ROOT, "families", "catalog.json")
OUT_DIR = os.path.join(ROOT, "models")
GITHUB = "https://github.com/steveseguin/b70-optimization-lab/blob/main/"
ISSUE = "https://github.com/steveseguin/b70-optimization-lab/issues/new?template=result.yml&title="
SITE = "https://neural.download/"
BRIDGE = os.path.join(ROOT, "learn", "assets", "mlbottleneck-bridge.js")


def bridge_version():
    with open(BRIDGE, "rb") as handle:
        return hashlib.sha1(handle.read()).hexdigest()[:10]


def stamp_bridge_includes(version):
    """Cache-bust the bridge script on the hand-written pages that load it."""
    for rel in ("index.html", os.path.join("learn", "hardware.html")):
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        updated = re.sub(r'(mlbottleneck-bridge\.js)(\?v=[0-9a-f]+)?"', lambda m: f'{m.group(1)}?v={version}"', source)
        if updated != source:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(updated)

# package id -> ML Bottleneck request (preset key, exact quant label, runtime, speed-up, strategy)
PACKAGE_ML = {
    "gemma4-26b-a4b-q8-b70-125tps-20260701": {"model": "gemma4_26b_a4b", "quant": "UD-Q8_K_XL", "runtime": "llama_cpp", "spec": "mtp:3", "prompt_tokens": 128, "output_tokens": 128},
    "laguna-s-2.1-int4-b70-125tps-20260731": {"model": "laguna_s_2.1", "quant": "AutoRound INT4", "runtime": "vllm", "spec": "dflash:11", "prompt_tokens": 128, "output_tokens": 128},
    "lfm25-26b-q8-b70": {"model": "lfm2.5_2.6b", "quant": "Q8_0", "runtime": "llama_cpp", "spec": "none", "prompt_tokens": 128, "output_tokens": 128},
    "minimax-m27-b70-89tps-20260520": {"model": "minimax_m2.7", "quant": "AutoRound INT4", "runtime": "vllm", "spec": "none", "prompt_tokens": 512, "output_tokens": 1536},
    "muse-glimmer-30b-q8-woq-b70-100tps-20260813": {"model": "muse_glimmer_30b", "quant": "UD-Q8_K_XL", "runtime": "llama_cpp", "spec": "draft_model:15", "strategy": "tensor", "prompt_tokens": 128, "output_tokens": 128},
    "nemotron-35-lightning-30b-a3b-b70": {"model": "nemotron3.5_lightning_30b_a3b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none", "prompt_tokens": 128, "output_tokens": 100},
    "ornith-15-35b-a3b-q4km-b70": {"model": "ornith_1.5_35b_a3b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none", "prompt_tokens": 128, "output_tokens": 100},
    "ornith-15-9b-q8-b70": {"model": "ornith_1.5_9b", "quant": "Q8_0", "runtime": "llama_cpp", "spec": "none", "prompt_tokens": 128, "output_tokens": 100},
    # Workload shapes are the packet's own convention: the conventional
    # first-hundred-words suites run ~128-token prompts with 100-128-token
    # answers; MiniMax and the FP8 TP2 packet record longer shapes explicitly.
    # The Q5 flagship and Q8 TP2 packets are intentionally omitted. The former
    # does not encode its draft depth; the latter's strict headline is a varied
    # 512-cap suite rather than one exact 128/128 ML Bottleneck workload. Their
    # measured 26.7 and 36.7 tok/s headlines remain shown unchanged.
    # The selected FP8 packet now uses a dynamic MTP2-at-one/MTP1-at-many
    # policy. ML Bottleneck has no configuration-exact dynamic-policy preset,
    # so omit its projection rather than binding the measured hero to MTP0 or
    # a fixed speculative depth.
    "qwen38-27b-q4km-tp1-b70": {"model": "qwen3.8_27b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none", "prompt_tokens": 128, "output_tokens": 128},
    "qwen38-27b-q4km-tp2-asrock-b70": {"model": "qwen3.8_27b", "quant": "Q4_K_M", "runtime": "llama_cpp", "spec": "none", "strategy": "tensor", "prompt_tokens": 128, "output_tokens": 128},
}

STATUS_LABEL = {"candidate": "Candidate package", "lab": "Lab result", "research": "Research", "starter": "Starter guide", "record": "Record replay"}


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def json_for_html_script(value):
    return (json.dumps(value, ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e"))


def fmt(value):
    if value is None:
        return "—"
    value = float(value)
    if value >= 1000:
        return f"{value:,.0f}"
    return f"{value:.1f}" if value < 100 else f"{value:.0f}"


def missing_headline_label(library):
    status = str(library.get("benchmark_status", ""))
    return "strict headline withheld" if "withheld" in status.lower() else "strict headline pending"


def axis_span(values):
    values = list(values or [])
    if not values:
        return "—"
    if len(values) == 1:
        return str(values[0])
    return f"{values[0]}–{values[-1]}"


def family_topology(family):
    dimensions = family.get("dimensions") or {}
    tp = dimensions.get("tp") or []
    if tp:
        return "TP " + " / ".join(str(value) for value in tp)
    cards = dimensions.get("cards") or []
    return "Cards " + (" / ".join(str(value) for value in cards) if cards else "—")


def family_speedup(family):
    dimensions = family.get("dimensions") or {}
    mtp = dimensions.get("mtp") or []
    methods = [str(value) for value in dimensions.get("speculative_method") or []]
    if mtp and max(mtp) > 0:
        return "MTP " + axis_span(mtp)
    if any("MTP" in method.upper() for method in methods):
        return f'{" / ".join(methods)} {axis_span(dimensions.get("draft_depth"))}'
    if any(method.lower() != "none" for method in methods):
        depth = dimensions.get("draft_depth") or dimensions.get("dflash_n_max") or []
        suffix = f" {axis_span(depth)}" if depth else ""
        return " / ".join(methods) + suffix
    return "target only"


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
    x_metric = profile.get("x_metric", "context_tokens")
    xs = [float(p.get(x_metric, 0)) for p in points]
    ys = [float(p["value"]) for p in points]
    width, height, left, top, right, bottom = 640, 260, 64, 20, 20, 44
    import math
    # Context depth is a cardinal scale and should read linearly. Concurrency
    # ladders are conventionally powers of two, so retain log2 spacing there
    # and name it in the axis label below.
    tx = (
        [math.log2(max(1, x)) for x in xs]
        if x_metric == "concurrent_sequences"
        else xs
    )
    x0, x1 = min(tx), max(tx)
    y1 = max(ys) * 1.1
    def sx(v):
        transformed = math.log2(max(1, v)) if x_metric == "concurrent_sequences" else v
        return left + ((transformed - x0) / max(1e-9, x1 - x0)) * (width - left - right)
    def sy(v):
        return top + (1 - v / y1) * (height - top - bottom)
    path = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
    dots = "".join(
        f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="var(--spot)"></circle>'
        f'<text x="{sx(x):.1f}" y="{sy(y) - 9:.1f}" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--ink)">{fmt(y)}</text>'
        for x, y in zip(xs, ys)
    )
    def x_tick(v):
        v = int(v)
        if x_metric == "concurrent_sequences":
            return str(v)
        if x_metric == "speculative_tokens":
            return f"MTP{v}"
        if v < 2:
            return "0"
        return f"{v // 1024}K" if v >= 1024 and v % 1024 == 0 else (f"{v / 1024:.1f}K" if v >= 1024 else str(v))
    ticks = "".join(
        f'<text x="{sx(x):.1f}" y="{height - 24}" text-anchor="middle" font-size="11" font-family="var(--mono)" fill="var(--muted)">{x_tick(x)}</text>'
        for x in xs
    )
    unit = profile.get("unit", "tok/s")
    label = profile.get("label") or profile.get("id", "")
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{esc(label)}" xmlns="http://www.w3.org/2000/svg">'
        f'<line x1="{left}" y1="{sy(0):.1f}" x2="{width - right}" y2="{sy(0):.1f}" stroke="var(--ink)" stroke-width="2"></line>'
        f'<path d="{path}" fill="none" stroke="var(--spot)" stroke-width="3"></path>{dots}{ticks}'
        f'<text x="{left}" y="{height - 6}" font-size="11" font-family="var(--mono)" fill="var(--muted)">{esc(profile.get("x_label", "Context tokens"))}{" · log2 spacing" if x_metric == "concurrent_sequences" else ""} · y: {esc(unit)}</text>'
        f"</svg>"
    )


def page(pkg, all_pkgs, family=None):
    lib = pkg["library"]
    fm = lib.get("featured_metric") or {}
    has_featured_metric = isinstance(lib.get("featured_metric"), dict)
    benchmark_status = lib.get("benchmark_status", "Strict benchmark pending")
    missing_label = missing_headline_label(lib)
    missing_benchmark_label = missing_label.replace("headline", "benchmark")
    hw = pkg.get("hardware") or {}
    model = pkg.get("model") or {}
    runtime = pkg.get("runtime") or {}
    pid = pkg["id"]
    name = pkg["name"]
    title = (
        f"{name} — {fmt(fm.get('value'))} {fm.get('unit', 'tok/s')} measured — neural.download"
        if has_featured_metric
        else f"{name} — {missing_benchmark_label} — neural.download"
    )
    url = f"{SITE}models/{pid}.html"
    status = STATUS_LABEL.get(pkg.get("status"), pkg.get("status", "").title())
    ml = PACKAGE_ML.get(pid)
    ml_attrs = ""
    exact_projection_workload = bool(
        has_featured_metric
        and ml
        and isinstance(ml.get("prompt_tokens"), int)
        and ml["prompt_tokens"] > 0
        and isinstance(ml.get("output_tokens"), int)
        and ml["output_tokens"] > 0
    )
    projection_tail = (
        " Exact pins, patches, proof, and a clearly labeled optimization projection."
        if exact_projection_workload
        else " Exact pins, patches, and proof; no unmatched projection is implied."
    )
    desc = (
        (
            f"{lib.get('summary', '')} Measured {fmt(fm.get('value'))} "
            f"{fm.get('unit', 'tok/s')} {fm.get('label', 'decode')} on "
            f"{hw.get('cards', 1)}× {hw.get('accelerator', 'Intel Arc Pro B70')} "
            f"with {lib.get('runtime_label', '')} ({lib.get('quantization', '')})."
            f"{projection_tail}"
        )
        if has_featured_metric
        else (
            f"{lib.get('summary', '')} {benchmark_status}. Exact recipe and "
            "diagnostic evidence are retained, but no unqualified headline is published."
        )
    )
    desc = re.sub(r"\s+", " ", desc).strip()[:300]
    if exact_projection_workload and has_featured_metric:
        ml_attrs = (f' data-ml-model="{esc(ml["model"])}" data-ml-quant="{esc(ml["quant"])}" data-ml-runtime="{esc(ml["runtime"])}"'
                    f' data-ml-cards="{esc(hw.get("cards", 1))}" data-ml-hardware="Intel Arc Pro B70" data-ml-hardware-label="B70" data-ml-spec="{esc(ml.get("spec", "none"))}"'
                    f' data-ml-measured="{esc(fm.get("value", ""))}" data-ml-quant-label="{esc(lib.get("quantization", ""))}" data-ml-runtime-label="{esc(lib.get("runtime_label", ""))}"'
                    f' data-ml-prompt="{esc(ml["prompt_tokens"])}" data-ml-output="{esc(ml["output_tokens"])}"'
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
        ("Good for", "\u0000USE_CHIPS\u0000"),
        ("Published", lib.get("published_at", "")),
        ("Clean-host replay", "yes" if pkg.get("clean_host_tested") else "not yet"),
    ]
    use_chips = "".join(f'<span class="use-chip">{esc(u)}</span> ' for u in lib.get("use_cases", [])) or "—"

    def fact_dd(value):
        if value == "\u0000USE_CHIPS\u0000":
            return use_chips.strip()
        return esc(value) if value else "—"

    facts_html = "".join(f"<div><dt>{esc(k)}</dt><dd>{fact_dd(v)}</dd></div>" for k, v in facts)
    profiles = [p for p in (pkg.get("performance_profiles") or []) if p.get("points")]
    context_profiles = [p for p in profiles if p.get("x_metric", "context_tokens") != "concurrent_sequences"]
    concurrent_profiles = [p for p in profiles if p.get("x_metric") == "concurrent_sequences"]

    def render_profiles(items):
        return "".join(
        f'<figure class="chart"><h4>{esc(p.get("label") or p.get("id"))} <span class="badge lab">Lab-measured</span></h4>{svg_profile(p)}'
        f'<figcaption>{esc(p.get("scope", ""))}' + (f' <a class="inline" href="{GITHUB}{esc(p["evidence"])}">evidence</a>' if p.get("evidence") else "") + "</figcaption></figure>"
        for p in items
        )

    profiles_html = render_profiles(context_profiles)
    concurrent_profiles_html = render_profiles(concurrent_profiles)
    evidence_link = f'<a class="inline" href="{GITHUB}{esc(fm["evidence"])}">proof file</a>' if fm.get("evidence") else ""
    # Plain words for the measurement vocabulary the scope line uses.
    GLOSS = [
        ("target-only", "target-only = no draft model assisting"),
        ("cache-zero", "cache-zero = a fresh start, nothing pre-computed"),
        ("99-interval", "99-interval median = the middle rate across 99 measured stretches of a long answer"),
        ("tg128", "tg128 = a raw 128-token generation benchmark, not the headline suite"),
        ("MTP", "MTP = multi-token prediction, a small draft the main model verifies"),
        ("oracle", "oracle = the fixed prompt set whose exact outputs are checked"),
    ]
    scope_text = f"{fm.get('scope', '')} {name}"
    gloss_bits = [words for term, words in GLOSS if term.lower() in scope_text.lower()]
    scope_gloss = f'<p class="scope-gloss">{esc(" · ".join(gloss_bits))}</p>' if gloss_bits else ""
    missing = pkg.get("missing") or []
    missing_html = ""
    if missing:
        items = "".join(f"<li>{esc(m if isinstance(m, str) else m.get('item') or m.get('description') or json.dumps(m))}</li>" for m in missing[:8])
        missing_html = f'<div class="missing"><p class="missing-tag">Still missing before this becomes an install guide</p><ul>{items}</ul></div>'
    limitations = pkg.get("known_limitations") or []
    limitations_html = ""
    if limitations:
        items = "".join(
            f"<li>{esc(item if isinstance(item, str) else json.dumps(item))}</li>"
            for item in limitations[:8]
        )
        limitations_html = (
            '<div class="limitations"><p class="limitations-tag">What to know</p>'
            f'<ul>{items}</ul></div>'
        )
    related = [p for p in all_pkgs if p["id"] != pid and p["library"].get("model_family") == lib.get("model_family")][:4]
    related_html = "".join(
        f'<a href="{esc(p["id"])}.html"><b>{esc(p["name"])}</b><span>{esc((fmt((p["library"].get("featured_metric") or {}).get("value")) + " tok/s") if p["library"].get("featured_metric") else missing_headline_label(p["library"]))} · {esc(p["library"].get("runtime_label", ""))}</span></a>'
        for p in related
    )
    family_href = f'{esc(family["id"])}.html' if family else ""
    family_label = (family.get("display_name") or family.get("name")) if family else lib.get("model_family", "")
    family_related = (
        f'<a href="{family_href}"><b>{esc(family_label)} coverage</b><span>Variants, evidence, gaps, and recipes</span></a>'
        if family
        else ""
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
    crumb_items = [
        {"@type": "ListItem", "position": 1, "name": "neural.download", "item": SITE},
        {"@type": "ListItem", "position": 2, "name": "Models", "item": f"{SITE}models/"},
    ]
    if family:
        crumb_items.append(
            {
                "@type": "ListItem",
                "position": 3,
                "name": family_label,
                "item": f'{SITE}models/{family["id"]}.html',
            }
        )
    crumb_items.append(
        {"@type": "ListItem", "position": len(crumb_items) + 1, "name": name, "item": url}
    )
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": crumb_items,
    }
    if profiles_html:
        profiles_section = '<h2 id="profiles">Measured performance profiles <span class="badge lab">Lab-measured</span></h2>' + profiles_html
    else:
        profiles_section = ('<h2 id="profiles">Measured performance profiles <span class="badge todo">Not published</span></h2>'
                            '<div class="placeholder"><p>No qualified structured context or depth profile is published for this package. '
                            'Diagnostic evidence may still be linked under “What to know” or in the full guide; nothing is estimated in its place'
                            + (' — the clearly labeled projection block below is the current best guess.' if ml else '.')
                            + '</p></div>')
    if concurrent_profiles_html:
        multiuser_section = ('<h2 id="multi-user">Many people at once <span class="badge lab">Lab-measured</span></h2>'
                             + concurrent_profiles_html)
    else:
        multiuser_section = ('<h2 id="multi-user">Many people at once <span class="badge todo">Not published</span></h2>'
                             '<div class="placeholder"><p>No qualified multi-user aggregate profile is published for this exact package. '
                             'Diagnostic or unsupported boundaries may still appear under “What to know” or in the full guide. '
                             'Nothing is interpolated or promoted from a different model, quantization, runtime, or card count'
                             + ('; the projection below remains clearly labeled as projected.' if exact_projection_workload else '.')
                             + '</p></div>')
    projection_html = ""
    if exact_projection_workload:
        projection_html = f"""
  <h2 id="projection">How much faster could this get? <span class="badge spec">Projected — not measured</span></h2>
  <p>The <a class="inline" href="https://mlbottleneck.com/">ML Bottleneck</a> physics engine projects what stock software, a tuned run, and the physical ceiling look like for this exact model, compression, card count, and software. The grade is optimization headroom against the tuned-run target, not model quality.</p>
  <div id="package-projection" class="projection" hidden>
    <p class="projection-status" data-projection-status>Loading projections from mlbottleneck.com…</p>
    <div data-package-card></div>
    <div data-package-charts></div>
  </div>
  <noscript><p class="projection-status">Projections need JavaScript; the measured numbers above are static.</p></noscript>"""
    elif ml and has_featured_metric:
        projection_html = """
  <h2 id="projection">Optimization grade <span class="badge spec">OPT —</span></h2>
  <p>The measured headline aggregates more than one prompt or completion shape, so a like-for-like tuned-run projection is withheld. The measured speed above is unchanged.</p>"""
    elif ml:
        projection_html = """
  <h2 id="projection">Optimization grade <span class="badge todo">Pending</span></h2>
  <p>No optimization grade is calculated because this package has no promoted measured headline. Diagnostic or scoped measurements never seed a headline projection.</p>"""
    else:
        projection_html = """
  <h2 id="projection">How much faster could this get? <span class="badge todo">No projection</span></h2>
  <div class="placeholder"><p>This package's measured workload does not map cleanly onto a single model + compression + card-count shape, so no like-for-like projection is shown. The measured numbers above stand on their own.</p></div>"""
    measured_html = (
        f'<h2 id="measured">What we measured <span class="badge lab">Lab-measured</span></h2>'
        f'<div class="measured"><span class="big">{esc(fmt(fm.get("value")))}</span><span class="unit">{esc(fm.get("unit", "tok/s"))} {esc(fm.get("label", "decode"))}</span></div>'
        f'<p class="scope">{esc(fm.get("scope", ""))} {evidence_link}</p>{scope_gloss}'
        if has_featured_metric
        else (
            f'<h2 id="measured">Public headline <span class="badge todo">{"Withheld" if "withheld" in missing_label else "Pending"}</span></h2>'
            f'<div class="placeholder"><p>{esc(benchmark_status)} Diagnostic measurements remain in the guide and evidence, but none is presented as the package headline.</p></div>'
        )
    )
    seo_title = (
        f"{name} — {fmt(fm.get('value'))} {fm.get('unit', 'tok/s')} measured"
        if has_featured_metric
        else f"{name} — {missing_benchmark_label}"
    )
    seo_alt = (
        f"{name}: {fmt(fm.get('value'))} {fm.get('unit', 'tok/s')} measured on Intel Arc Pro B70 — neural.download"
        if has_featured_metric
        else f"{name}: {missing_benchmark_label} on Intel Arc Pro B70 — neural.download"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
{seo_head(url, seo_title, desc, image=f"{SITE}models/cards/{pid}.png", image_alt=seo_alt, og_type="article", depth=1)}
<script type="application/ld+json">
{json_for_html_script(ld)}
</script>
<script type="application/ld+json">
{json_for_html_script(crumbs)}
</script>
<link rel="stylesheet" href="../learn/learn.css">
<link rel="preconnect" href="https://mlbottleneck.com">
<style>
  .facts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px 16px; margin: 14px 0 22px; padding: 14px 16px; border: 2px solid var(--ink); background: var(--paper); }}
  .facts div {{ min-width: 0; }}
  .facts dt {{ font: 700 10px var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
  .facts dd {{ margin: 2px 0 0; font-size: 13.5px; overflow-wrap: anywhere; }}
  .use-chip {{ display: inline-block; border: 1px solid var(--ink); padding: 1px 7px 0; font: 700 11px var(--mono); letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; margin: 0 4px 4px 0; }}
  .placeholder {{ margin: 10px 0 22px; padding: 12px 16px; border: 2px solid var(--line); background: var(--surface); color: var(--muted); }}
  .placeholder p {{ margin: 0; font-size: 13.5px; }}
  .badge.todo {{ background: var(--surface); color: var(--muted); border-color: var(--muted); }}
  .missing {{ margin: 0 0 22px; padding: 12px 16px; border: 2px solid var(--ink); background: var(--surface); }}
  .missing-tag {{ margin: 0 0 6px; font: 700 10px var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--warn); }}
  .missing ul {{ margin: 0; padding-left: 18px; font-size: 13px; }}
  .limitations {{ margin: 0 0 22px; padding: 12px 16px; border: 2px solid var(--line); background: var(--surface); }}
  .limitations-tag {{ margin: 0 0 6px; font: 700 10px var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--ink); }}
  .limitations ul {{ margin: 0; padding-left: 18px; font-size: 13px; }}
  .measured {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px 18px; margin: 8px 0 6px; }}
  .measured .big {{ font: 900 44px/1 var(--display); color: var(--spot-dark); }}
  .measured .unit {{ font: 700 13px var(--mono); text-transform: uppercase; letter-spacing: .05em; color: var(--muted); }}
  .scope {{ margin: 0 0 6px; color: var(--muted); font-size: 13px; }}
  .scope-gloss {{ margin: 0 0 12px; color: var(--muted); font-size: 11.5px; }}
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
    <a href="index.html" aria-current="page">Models</a>
    <a href="../learn.html">Learn</a>
    <a href="../guides.html">Recipes</a>
    <a href="../index.html#lab-speeds">Benchmarks</a>
    <a href="../index.html#contribute">Contribute</a>
    <a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a>
  </nav>
</div></div>

<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / <a href="index.html">Models</a> / {f'<a href="{family_href}">{esc(family_label)}</a> / ' if family else ''}{esc(lib.get('variant') or lib.get('model_family', ''))}</p>
  <p class="eyebrow">{esc(status)} · {esc(lib.get('runtime_label', ''))} · {esc(hw.get('cards', 1))}× Intel Arc Pro B70</p>
  <h1>{esc(name)}</h1>
  <p>{esc(lib.get('summary', ''))}</p>
</div></header>

<main id="main"><div class="wrap"><div class="col prose" id="package-page"{ml_attrs}>

  {measured_html}
  <div class="actions">
    <a class="button" href="{GITHUB}{esc(pkg.get('guide', ''))}">Open the full guide</a>
    <button type="button" class="copy-md" data-copy-markdown="../{esc(pkg.get('guide', ''))}" aria-label="Copy the guide Markdown" aria-live="polite">Copy Markdown</button>
    <a class="button secondary" href="{ISSUE}{esc(name.replace(' ', '%20'))}">Submit an improvement</a>
  </div>

  <dl class="facts">{facts_html}</dl>
{missing_html}
{limitations_html}
{profiles_section}
{multiuser_section}
{projection_html}

  <div class="related">
    <h2>Keep going</h2>
    <div class="related-grid">
      {family_related}
      {related_html}
      <a href="../learn.html"><b>Learn</b><span>What sets these numbers</span></a>
      <a href="../guides.html"><b>Recipes</b><span>Every package, filterable</span></a>
      <a href="../index.html#contribute"><b>Contribute</b><span>Made it faster? Send it in</span></a>
    </div>
  </div>

</div></div></main>

<footer><div class="wrap">
  <span>Unofficial lab, not affiliated with Intel. Measured numbers link to proof; projections are labeled.</span>
  <span><a href="../learn.html">Learn</a> · <a href="../guides.html">Recipes</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a> · <a href="https://mlbottleneck.com/" title="Physics-based LLM speed and memory planner for any GPU — same author">ML Bottleneck</a> · <a href="https://style-genome.com/" title="Design-system generator used to style this site — same author">Style Genome</a></span>
</div></footer>
<script defer src="../learn/assets/mlbottleneck-bridge.js?v={bridge_version()}"></script>
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


def index_page(pkgs, families):
    family_rows = "".join(
        f'<a class="guide-card family-card" href="{esc(f["id"])}.html"><div class="gc-top"><div class="gc-n">Model family · {esc(len(f.get("weight_revisions") or []))} revision{"s" if len(f.get("weight_revisions") or []) != 1 else ""} · {esc(len(f.get("packets") or []))} packet{"s" if len(f.get("packets") or []) != 1 else ""}</div><h3>{esc(f.get("display_name") or f.get("name"))}</h3></div>'
        f'<div class="gc-body"><p>{esc(f.get("summary", ""))}</p><p class="gc-meta"><strong>{esc(family_topology(f))}</strong> · {esc(family_speedup(f))} · context, KV, graph, quant, prefill, TTFT, quality</p></div><div class="gc-go">Open the model page →</div></a>'
        for f in sorted(families, key=lambda item: (item.get("display_name") or item.get("name", "")).casefold())
    )
    display_pkgs = sorted(
        pkgs,
        key=lambda p: (
            p["library"].get("model_family", "").casefold(),
            p["library"].get("variant", "").casefold(),
            int((p.get("hardware") or {}).get("cards", 1)),
            p["library"].get("quantization", "").casefold(),
        ),
    )
    rows = "".join(
        f'<a class="guide-card" href="{esc(p["id"])}.html"><div class="gc-top"><div class="gc-n">{esc(STATUS_LABEL.get(p.get("status"), p.get("status", "")))} · {esc(p["library"].get("runtime_label", ""))}</div><h3>{esc(p["name"])}</h3></div>'
        f'<div class="gc-body"><p>{esc(p["library"].get("summary", ""))}</p><p class="gc-meta"><strong>{esc((fmt((p["library"].get("featured_metric") or {}).get("value")) + " tok/s") if p["library"].get("featured_metric") else missing_headline_label(p["library"]))}</strong>{" measured" if p["library"].get("featured_metric") else ""} · {esc((p.get("hardware") or {}).get("cards", 1))}× B70 · {esc(p["library"].get("quantization", ""))}</p></div></a>'
        for p in display_pkgs
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Model families on Intel Arc Pro B70 — neural.download</title>
{seo_head(f"{SITE}models/", "Models measured on Intel Arc Pro B70 — neural.download", "Every model the lab has measured on Intel Arc Pro B70 cards: headline speed, deployment packets, and what has been tried, with every number linked to its proof.", depth=1)}
<script type="application/ld+json">
{json_for_html_script({"@context": "https://schema.org", "@type": "CollectionPage", "name": "Model families on Intel Arc Pro B70", "url": f"{SITE}models/", "isPartOf": {"@type": "WebSite", "name": "neural.download", "url": SITE}, "inLanguage": "en", "isAccessibleForFree": True})}
</script>
<link rel="stylesheet" href="../learn/learn.css">
<style>
  .guide-card .gc-body {{ padding: 12px 16px 14px; }}
  .guide-card .gc-body p {{ margin: 0 0 8px; color: var(--muted); font-size: 13px; }}
  .guide-card .gc-meta {{ font: 11px var(--mono); color: var(--ink); }}
  .family-card {{ grid-column: span 2; }}
  .family-card .gc-top {{ background: var(--spot); color: #fff; }}
  .family-card .gc-top .gc-n {{ color: rgba(255,255,255,.82); }}
  .section-title {{ margin: 30px 0 10px; font: 900 22px/1.1 var(--display); text-transform: uppercase; }}
  .section-note {{ max-width: 72ch; margin: -3px 0 14px; color: var(--muted); font-size: 13px; }}
  @media (max-width: 720px) {{ .family-card {{ grid-column: span 1; }} }}
</style>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<div class="site-nav"><div class="wrap">
  <a class="brand" href="../index.html"><span class="brand-mark" aria-hidden="true">▮▮▮</span>neural.download</a>
  <nav aria-label="Primary">
    <a href="index.html" aria-current="page">Models</a>
    <a href="../learn.html">Learn</a>
    <a href="../guides.html">Recipes</a>
    <a href="../index.html#lab-speeds">Benchmarks</a>
    <a href="../index.html#contribute">Contribute</a>
    <a class="github" href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a>
  </nav>
</div></div>
<header class="hero"><div class="wrap">
  <p class="breadcrumb"><a href="../index.html">Home</a> / Models</p>
  <p class="eyebrow">Families first · quantizations are deployment variants</p>
  <h1>Models</h1>
  <p>Start with the model family, then choose weights, quantization, cards, context, runtime, and speed-up. Mini graphs show decode, prefill, TTFT, quality, and gaps without turning every permutation into another model.</p>
</div></header>
<main id="main"><div class="wrap">
  <h2 class="section-title">Model families</h2>
  <p class="section-note">Shape-compatible weight updates share implementation work, while every measurement stays pinned to its exact checkpoint and runtime.</p>
  <div class="guide-cards">{family_rows}</div>
  <h2 class="section-title">Deployment packets</h2>
  <p class="section-note">Measured quantized variants, recipes, and research packets at their honest maturity. Speed is one field, not the sorting rule.</p>
  <div class="guide-cards">{rows}</div>
</div></main>
<footer><div class="wrap">
  <span>Unofficial lab, not affiliated with Intel.</span>
  <span><a href="../learn.html">Learn</a> · <a href="../guides.html">Recipes</a> · <a href="https://github.com/steveseguin/b70-optimization-lab">GitHub</a> · <a href="https://mlbottleneck.com/" title="Physics-based LLM speed and memory planner for any GPU — same author">ML Bottleneck</a> · <a href="https://style-genome.com/" title="Design-system generator used to style this site — same author">Style Genome</a></span>
</div></footer>
</body>
</html>
"""


def main():
    with open(CATALOG, encoding="utf-8") as handle:
        catalog = json.load(handle)
    pkgs = sorted(
        catalog["packages"],
        key=lambda p: (
            p["library"].get("model_family", "").casefold(),
            p["library"].get("variant", "").casefold(),
            p["id"],
        ),
    )
    with open(FAMILY_CATALOG, encoding="utf-8") as handle:
        family_catalog = json.load(handle)
    families = []
    for entry in family_catalog.get("families", []):
        with open(os.path.join(ROOT, entry["manifest"]), encoding="utf-8") as handle:
            families.append(json.load(handle))
    os.makedirs(OUT_DIR, exist_ok=True)
    stamp_bridge_includes(bridge_version())
    written = []
    for pkg in pkgs:
        path = os.path.join(OUT_DIR, f"{pkg['id']}.html")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            packet_family = next(
                (
                    family
                    for family in families
                    if any(packet.get("id") == pkg["id"] for packet in family.get("packets") or [])
                ),
                None,
            )
            handle.write(page(pkg, pkgs, packet_family))
        written.append(path)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(index_page(pkgs, families))
    unmapped = [p["id"] for p in pkgs if p["id"] not in PACKAGE_ML]
    print(f"wrote {len(written)} package pages + models/index.html")
    if unmapped:
        print("packages without an ML Bottleneck mapping (no projection block):", ", ".join(unmapped), file=sys.stderr)


if __name__ == "__main__":
    main()
