#!/usr/bin/env python3
"""Model-agnostic self-consistency canaries against a llama-server endpoint.

Objective checks only (no cross-model oracle): 8x same-prompt hash
stability at temperature 0, exact arithmetic, exact copy, and JSON-schema
emission. Writes a result JSON; exit 0 only if every canary passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request


def chat(base, model, prompt, max_tokens=512):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "seed": 42,
        "max_tokens": max_tokens,
        "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(
        f"{base}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    msg = d["choices"][0]["message"]
    # Reasoning-style models may put everything in reasoning_content and
    # leave content empty; the objective checks scan the combined text.
    return (msg.get("reasoning_content") or "") + (msg.get("content") or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    results = {}

    outs = [chat(a.base_url, a.model,
                 "List exactly four colors, comma-separated, nothing else.")
            for _ in range(8)]
    hashes = sorted({hashlib.sha256(o.encode()).hexdigest() for o in outs})
    results["repeat_8x"] = {
        "unique_outputs": len(hashes),
        "pass": len(hashes) == 1 and bool(outs[0].strip()),
        "sample": outs[0][:80],
    }

    arith = chat(a.base_url, a.model,
                 "Compute 47*89. Reply with only the integer.")
    results["arithmetic"] = {
        "raw": arith.strip()[:40],
        "pass": "4183" in arith,
    }

    phrase = "B70 packet canary 7391 holds steady."
    copy = chat(a.base_url, a.model,
                f"Repeat exactly, with no extra words: {phrase}")
    results["copy"] = {"raw": copy.strip()[:80], "pass": phrase in copy}

    js = chat(a.base_url, a.model,
              'Output only a JSON object with keys "name" (string) and "count"'
              ' (integer), for three apples named Fuji.', 512)
    ok = False
    try:
        start, end = js.index("{"), js.rindex("}") + 1
        parsed = json.loads(js[start:end])
        ok = isinstance(parsed.get("name"), str) and isinstance(
            parsed.get("count"), int)
    except (ValueError, KeyError):
        ok = False
    results["json_schema"] = {"raw": js.strip()[:100], "pass": ok}

    results["pass_all"] = all(v["pass"] for v in results.values()
                              if isinstance(v, dict))
    json.dump(results, open(a.out, "w"), indent=1)
    print(json.dumps({k: (v["pass"] if isinstance(v, dict) else v)
                      for k, v in results.items()}))
    return 0 if results["pass_all"] else 1


if __name__ == "__main__":
    sys.exit(main())
