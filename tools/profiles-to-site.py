#!/usr/bin/env python3
"""Render the uniform profiling pass (data/profiles/<day>/*.json) as the home-page section
"Same test, every model" and splice it into index.html between the markers
<!-- BEGIN GENERATED UNIFORM PROFILES --> and <!-- END GENERATED UNIFORM PROFILES -->.

usage: tools/profiles-to-site.py data/profiles/2026-10-10 [--write]
Rows come from tools/profiles-site-map.json (label -> display fields); labels not in the map are skipped so
experimental or duplicate runs never reach the page.
"""
import json, sys, glob, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fmt(v, nd=0):
    if v is None: return None
    return f"{v:,.{nd}f}"

def bar(v, vmax, cls=""):
    if not v or not vmax: return '<span class="ubar empty" aria-hidden="true"></span>'
    w = max(2, round(100 * v / vmax))
    return f'<span class="ubar{(" " + cls) if cls else ""}" style="width:{w}%" aria-hidden="true"></span>'

def main():
    day_dir = sys.argv[1]; write = "--write" in sys.argv
    day = os.path.basename(day_dir.rstrip("/"))
    smap = json.load(open(os.path.join(ROOT, "tools", "profiles-site-map.json")))
    rows = []
    for label, meta in smap.items():
        f = os.path.join(day_dir, label + ".json")
        if not os.path.exists(f): continue
        j = json.load(open(f))
        pre = j.get("prefill", {}); mu = j.get("multi_user", {}); nu = j.get("decode_nusers", {}); can = j.get("canary") or {}
        rows.append({"meta": meta, "dec1": (j.get("decode_1user") or {}).get("median_tps"),
                     "pf2k": (pre.get("2048") or {}).get("prompt_tps"), "pf8k": (pre.get("8192") or {}).get("prompt_tps"),
                     "users": j.get("users"), "agg": nu.get("aggregate_tps"), "load_total": mu.get("total_tok_s"),
                     "rep": (j.get("repeat_identical") or {}).get("distinct"), "batch": (j.get("batch_identical") or {}).get("distinct_incl_alone"),
                     "canary": can, "mem": j.get("card_memory_used_mib_after_load"), "label": label})
    rows.sort(key=lambda r: -(r["dec1"] or 0))
    dmax = max((r["dec1"] or 0) for r in rows) or 1; amax = max((r["agg"] or 0) for r in rows) or 1; pmax = max((r["pf2k"] or 0) for r in rows) or 1
    out = []
    out.append(f'<!-- BEGIN GENERATED UNIFORM PROFILES -->\n<section id="uniform">\n  <div class="wrap">\n'
               f'    <h2 id="t-uniform">Same test, every model <span class="key"><span class="dot">&#9679;</span> one card, one harness, {html.escape(day)}</span></h2>\n'
               f'    <p class="sub">Every model we could put on one B70 that day, run through the same script back to back. One person: 256 tokens written after a 300-token prompt. Reads: a 2,000-token prompt. Together: {"/".join(sorted({str(r["users"]) for r in rows if r["users"]}))} people at once. Temperature 0 everywhere.</p>\n'
               f'    <p class="sub"><b>Repeats</b>: the same long question three times gave the same answer. <b>Together</b>: still the same while others were being served. Packages keep their own tuned numbers elsewhere on this page; this table is the fair side-by-side.</p>\n'
               f'    <div class="scroller"><table class="uniform-table" aria-labelledby="t-uniform">\n      <thead><tr><th scope="col">Model and setup</th><th scope="col" class="r">One person</th><th scope="col" class="r">Reads 2K prompt</th><th scope="col" class="r">Together</th><th scope="col">Repeats</th><th scope="col">Answers</th></tr></thead>\n      <tbody>\n')
    for r in rows:
        m = r["meta"]; name = html.escape(m["name"]); sub = html.escape(m["sub"])
        rep = "identical" if r["rep"] == 1 else (f"{r['rep']} of 3 differ" if r["rep"] else "not measured")
        bat = "identical" if r["batch"] == 1 else (f"differs" if r["batch"] else "not measured")
        can = r["canary"]; cantxt = f"{can.get('ok')} of {can.get('rows')} checks" if can and can.get("rows") else "not run"
        if m.get("answers"): cantxt = m["answers"]; can = None
        agg_txt = f"{fmt(r['agg'])} tok/s<small>{r['users']} people total</small>" if r["agg"] else "not measured"
        link = f'<a href="{html.escape(m["href"])}">{name}</a>' if m.get("href") else name
        if r["mem"]: sub = sub + f' &middot; {fmt(r["mem"] / 1024, 1)} GB on the card'
        chip = f'<span class="card-chip{" two" if m.get("cards", 1) > 1 else ""}">{m.get("cards", 1)} card{"s" if m.get("cards", 1) > 1 else ""}</span>'
        answers_td = (f'          <td data-label="Answers"><span class="utag warn" title="This endpoint replies with its thinking text, so the quick canary does not apply; the package has its own strict checks.">{html.escape(cantxt)}</span></td>\n' if m.get("answers")
                      else f'          <td data-label="Answers"><span class="utag {"ok" if can and can.get("ok") == can.get("rows") else "warn"}">{cantxt}</span></td>\n')
        out.append(f'        <tr>\n          <th scope="row" class="model">{link}<small>{chip}{sub}</small></th>\n'
                   f'          <td class="num r" data-label="One person">{fmt(r["dec1"], 1) or "&mdash;"} tok/s{bar(r["dec1"], dmax, "max" if r["dec1"] == dmax else "")}</td>\n'
                   f'          <td class="num r" data-label="Reads 2K prompt">{(fmt(r["pf2k"]) + " tok/s") if r["pf2k"] else "&mdash;"}{bar(r["pf2k"], pmax)}</td>\n'
                   f'          <td class="num r" data-label="Together">{agg_txt}{bar(r["agg"], amax, "spot")}</td>\n'
                   f'          <td data-label="Repeats"><span class="utag {"ok" if r["rep"] == 1 else "warn"}">{rep}</span><small>together: {bat}</small></td>\n'
                   + answers_td + '        </tr>\n')
    out.append('      </tbody>\n    </table></div>\n'
               '    <p class="research-links">Raw results for every row: <a href="https://github.com/steveseguin/b70-optimization-lab/tree/main/data/profiles/' + html.escape(day) + '">data/profiles/' + html.escape(day) + '</a> (one JSON per run, plus the server log). Harness: <a href="https://github.com/steveseguin/b70-optimization-lab/blob/main/tools/profile-openai-endpoint.py">tools/profile-openai-endpoint.py</a>.</p>\n'
               '  </div>\n</section>\n<!-- END GENERATED UNIFORM PROFILES -->')
    section = "".join(out)
    if not write:
        print(section); return
    p = os.path.join(ROOT, "index.html"); s = open(p).read()
    b, e = "<!-- BEGIN GENERATED UNIFORM PROFILES -->", "<!-- END GENERATED UNIFORM PROFILES -->"
    if b in s and e in s:
        s = s[:s.index(b)] + section + s[s.index(e) + len(e):]
    else:
        anchor = '<section id="pick">'
        s = s.replace(anchor, section + "\n\n" + anchor, 1)
    open(p, "w").write(s); print(f"wrote {len(rows)} rows into index.html")

if __name__ == "__main__":
    main()
