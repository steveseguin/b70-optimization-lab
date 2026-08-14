#!/usr/bin/env python3
"""Compare target-only and DFlash output in one Muse Q8 WOQ server process."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


PROMPTS = {
    "prose": "Write a detailed technical explanation of how a B-tree index accelerates database range queries, covering node structure, fanout, height, and cache behavior.",
    "code": "Implement an LRU cache class in Python with O(1) get and put using a doubly linked list plus dict. Include docstrings and a small usage example.",
    "json": "Produce only a JSON array of 12 objects, fields name, priority (1-3), eta_minutes, describing the ordered steps of a server migration runbook. No prose outside the JSON.",
}


def post(base_url: str, path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:19494")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n-predict", type=int, default=512)
    parser.add_argument("--prompt", action="append", choices=tuple(PROMPTS))
    args = parser.parse_args()

    rows = []
    passed = True
    selected = set(args.prompt or PROMPTS)
    for name, prompt in PROMPTS.items():
        if name not in selected:
            continue
        messages = [
            {"role": "system", "content": "Reasoning strength: low"},
            {"role": "user", "content": prompt},
        ]
        rendered = post(args.base_url, "/apply-template", {"messages": messages})["prompt"]
        results = {}
        for mode in ("none", "draft-dflash"):
            result = post(
                args.base_url,
                "/completion",
                {
                    "prompt": rendered,
                    "n_predict": args.n_predict,
                    "temperature": 0,
                    "seed": 1,
                    "cache_prompt": False,
                    "return_tokens": True,
                    "backend_sampling": True,
                    "samplers": ["temperature"],
                    "speculative.type": mode,
                },
            )
            results[mode] = {
                "tokens": result["tokens"],
                "content": result["content"],
                "content_sha256": hashlib.sha256(result["content"].encode()).hexdigest(),
                "timings": result["timings"],
                "prompt_tokens_cached": result.get("prompt_tokens_cached"),
                "stop_type": result.get("stop_type"),
            }
        token_exact = results["none"]["tokens"] == results["draft-dflash"]["tokens"]
        content_exact = results["none"]["content"] == results["draft-dflash"]["content"]
        passed &= token_exact and content_exact
        rows.append(
            {
                "prompt": name,
                "token_exact": token_exact,
                "content_exact": content_exact,
                "no_spec": results["none"],
                "dflash": results["draft-dflash"],
            }
        )

    result = {
        "passed": passed,
        "n_predict": args.n_predict,
        "policy": "same fresh server; target-only then DFlash; greedy; cache off; exact token and content equality",
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "passed": passed,
        "rows": [
            {
                "prompt": row["prompt"],
                "token_exact": row["token_exact"],
                "content_exact": row["content_exact"],
                "sha256": row["dflash"]["content_sha256"],
            }
            for row in rows
        ],
    }, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
