#!/usr/bin/env python3
"""Fold tools/gemma4-26b-sweep.py results into packages/gemma4-26b-a4b-q8-b70/package.json as performance_profiles,
so the model page shows the same curves the Qwen packages have: writing speed by draft length, writing and reading
speed by prompt length (draft on / off), wait for the first token, and many-user totals for the 8x4K and 4x16K shapes.

usage: tools/gemma4-26b-sweep-to-package.py data/profiles/2026-10-10/gemma-sweep [--write]
Profiles written by this tool carry ids starting with "sweep-" and replace any earlier "sweep-" profiles. The three
2026-07-02 four-lane curves stay (they reach 32K+ tokens, which the home picker and tests rely on). Evidence files
are added to the package dependencies list.
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packages", "gemma4-26b-a4b-q8-b70", "package.json")
BUILD_NOTE = ("One Intel Arc Pro B70, llama.cpp SYCL compat build c926 with the deterministic oneDNN switch, 16-bit KV, "
              "launched through the production launcher (its kernel switches on), temperature 0, 256-token answers, "
              "prompt cache off for every measured request. Speeds are the server's own timing counters.")


def load(d):
    rows = {}
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and ".noenv" not in f and ".canary" not in f:
            j = json.load(open(os.path.join(d, f)))
            if j.get("ok"):
                rows[j["label"]] = j
    return rows


def rel(d, label):
    return os.path.relpath(os.path.join(d, label + ".json"), ROOT)


def ctx_points(r, field, scale=1.0):
    """x = the requested prompt length (the measured prompt_n is within 20 tokens; kept in the evidence file)."""
    pts = []
    for k, v in sorted(r["single"].items(), key=lambda kv: int(kv[0])):
        if v.get(field) is not None:
            pts.append({"context_tokens": int(k), "value": round(v[field] * scale, 3), "samples": len(v["runs"]), "measured_prompt_tokens": int(v["prompt_n"])})
    return pts


def main():
    d = sys.argv[1]; write = "--write" in sys.argv
    rows = load(d)
    profiles = []
    draft_desc = {0: "no draft", 1: "MTP draft 1", 2: "MTP draft 2", 3: "MTP draft 3", 4: "MTP draft 4", 5: "MTP draft 5"}

    # 1. writing speed by draft length (single user, after a 2K prompt and after a 300-token prompt)
    for ctx_key, ctx_name in (("2048", "2,000-token prompt"), ("300", "300-token prompt")):
        pts = []
        for dn in range(6):
            r = rows.get(f"single-16k-draft{dn}")
            if r and ctx_key in r["single"]:
                v = r["single"][ctx_key]
                pts.append({"speculative_tokens": dn, "value": round(v["decode_tps"], 3), "samples": len(v["runs"]),
                            "accept_rate": v.get("draft_accept_rate")})
        if len(pts) >= 2:
            profiles.append({"id": f"sweep-decode-vs-draft-length-{ctx_key}", "label": f"Writing speed by MTP draft length · after a {ctx_name}",
                             "public_label": f"Writing speed · different draft lengths · one user · after a {ctx_name}",
                             "public_scope": "The built-in draft head guesses several next tokens and the main model checks them. Zero is plain decoding. Three is the single-user recipe; longer drafts get rejected more often and gain nothing.",
                             "metric": "decode", "unit": "tok/s", "x_metric": "speculative_tokens", "x_label": "MTP draft tokens per step",
                             "scope": f"{BUILD_NOTE} One user, one 16K slot, {ctx_name}; draft 0 is plain decoding, the others use the Q4_0 MTP draft head "
                                      f"(draft-n-min 1 for draft 1, else 2; p-min 0.0475). Every draft length repeated the same long question identically three times.",
                             "evidence": rel(d, "single-16k-draft3" if "single-16k-draft3" in rows else next(iter(rows))), "points": pts})

    # 2. writing / reading / wait by prompt length, draft 3 and no draft
    for dn, tag in ((3, "draft3"), (0, "no-draft")):
        r = rows.get(f"single-16k-draft{dn}")
        if not r:
            continue
        name = draft_desc[dn]
        base_scope = f"{BUILD_NOTE} One user, one 16K slot, {name}; prompts of about 300, 2K, 8K and 16K tokens of filler text, median of the runs at each length."
        pub = "3-token draft (single-user recipe)" if dn == 3 else "no draft (shared-server recipe)"
        profiles.append({"id": f"sweep-decode-vs-context-{tag}", "label": f"Writing speed after the prompt · {name}", "metric": "decode", "unit": "tok/s",
                         "public_label": f"Writing speed · one user · {pub}", "public_scope": "Writing speed after the answer starts, for prompts from 300 to 16,000 tokens. Longer prompts slow writing because every new token looks back over the whole prompt.",
                         "x_metric": "context_tokens", "x_label": "Input tokens", "scope": base_scope, "evidence": rel(d, r["label"]), "points": ctx_points(r, "decode_tps")})
        profiles.append({"id": f"sweep-prefill-vs-context-{tag}", "label": f"Prompt reading speed · {name}", "metric": "prefill", "unit": "tok/s",
                         "public_label": f"Reading speed (prefill) · one user · {pub}", "public_scope": "How fast the server reads the prompt before the answer starts, measured by the server's own counters with no saved prompt cache. The draft does not change reading speed.",
                         "x_metric": "context_tokens", "x_label": "Input tokens",
                         **({"measurement_kind": "server_prefill", "operating_profile": {"speculative_tokens": dn, "max_model_len": 16384, "tensor_parallel_size": 1}} if dn == 3 else {}),
                         "scope": base_scope + " Reading speed is prompt tokens divided by the server's prompt time, with no saved prompt cache.",
                         "evidence": rel(d, r["label"]), "points": ctx_points(r, "prefill_tps")})
        if dn == 0:
            profiles.append({"id": "sweep-ttft-vs-context-no-draft", "label": "Wait for the first token · no draft", "metric": "ttft", "unit": "ms",
                             "public_label": "Wait for the first token · one user · cold prompt", "public_scope": "How long the user waits for the answer to start when nothing about the prompt is cached. With a shared system prompt cached, only the new part counts.",
                             "x_metric": "context_tokens", "x_label": "Input tokens", "scope": base_scope + " Wait is the server's prompt time for a cold prompt.",
                             "evidence": rel(d, r["label"]), "points": ctx_points(r, "ttft_s", 1000.0)})

    # 3. many people at once
    shapes = [("p8x4k-draft0", "8 slots of 4K · no draft (the shared-server recipe)"), ("p8x4k-draft1", "8 slots of 4K · MTP draft 1"),
              ("p8x4k-draft3", "8 slots of 4K · MTP draft 3"), ("p4x16k-draft0", "4 slots of 16K · no draft"),
              ("p4x16k-draft1", "4 slots of 16K · MTP draft 1 (the balanced recipe)"), ("p4x16k-draft3", "4 slots of 16K · MTP draft 3")]
    for label, name in shapes:
        r = rows.get(label)
        if not r or not r.get("users"):
            continue
        pts = [{"concurrent_sequences": u["users"], "value": round(u["aggregate_decode_tps"], 3), "per_user_value": round(u["per_stream_decode_tps"], 3), "samples": 1}
               for u in r["users"]]
        extra = ""
        if r.get("users_8k"):
            u = r["users_8k"][0]
            extra = f" With {u['users']} people each sending an 8K-token prompt: {u['aggregate_decode_tps']:.0f} tok/s total, {u['per_stream_decode_tps']:.0f} each."
        pub_scope = "Everyone sends a different 2,000-token prompt at the same moment. The speed is the combined total; divide by the user count for each person's share." + (extra and (" " + extra.strip()) or "")
        profiles.append({"id": f"sweep-aggregate-decode-vs-users-{label}", "label": f"Total writing speed by people served at once · {name}",
                         "public_label": f"Total writing speed · {name}", "public_scope": pub_scope,
                         "metric": "aggregate_decode", "unit": "tok/s", "x_metric": "concurrent_sequences", "x_label": "People writing at once",
                         "scope": f"{BUILD_NOTE} Each person sends a different 2K-token prompt at the same moment and gets 256 tokens; total is the sum of the per-person "
                                  f"server decode rates while all are writing.{extra}", "evidence": rel(d, r["label"]), "points": pts})

    if not write:
        print(json.dumps(profiles, indent=1)); return
    pkg = json.load(open(PKG))
    keep = [p for p in pkg.get("performance_profiles", []) if not p["id"].startswith("sweep-")]
    old_labels = {"decode-vs-context": "Writing speed · one user · 3-token draft · July 2026 service sweep, up to 32K tokens",
                  "prefill-vs-context": "Reading speed (prefill) · estimated from first-token wait · July 2026 service sweep",
                  "ttft-vs-context": "Wait for the first token · July 2026 service sweep, up to 32K tokens"}
    for p_ in keep:
        if p_["id"] in old_labels and not p_.get("public_label"):
            p_["public_label"] = old_labels[p_["id"]]
    pkg["performance_profiles"] = keep + profiles
    deps = pkg.setdefault("dependencies", [])
    for ev in sorted({p["evidence"] for p in profiles}):
        if ev not in deps:
            deps.append(ev)
    json.dump(pkg, open(PKG, "w"), indent=2, ensure_ascii=False)
    open(PKG, "a").write("\n")
    print(f"wrote {len(profiles)} sweep profiles (+{len(keep)} kept) into {os.path.relpath(PKG, ROOT)}")


if __name__ == "__main__":
    main()
