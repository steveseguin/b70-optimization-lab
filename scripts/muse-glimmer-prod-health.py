#!/usr/bin/env python3
"""Health check for the Muse Glimmer BF16 fleet (reasoning-aware).

Checks /v1/models, a greedy code canary (content must contain 'class' and
'def get'), and a 224x224 solid-color vision canary. Reasoning strength is
pinned low and budgets sized so reasoning cannot starve content.
"""
import argparse
import base64
import json
import struct
import sys
import time
import urllib.request
import zlib


def png(w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def call(url, payload=None, timeout=600):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--model", default="muse-glimmer-30b-bf16")
    ap.add_argument("--output-json", default="")
    ap.add_argument("--skip-vision", action="store_true")
    args = ap.parse_args()

    out = {"base_url": args.base_url, "model": args.model,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "errors": [], "checks": {}}

    try:
        models = call(f"{args.base_url}/v1/models")
        ids = [m["id"] for m in models["data"]]
        out["checks"]["models"] = ids
        if args.model not in ids:
            out["errors"].append(f"model {args.model} not in {ids}")
    except Exception as e:
        out["errors"].append(f"models: {e}")

    try:
        r = call(f"{args.base_url}/v1/chat/completions", {
            "model": args.model, "temperature": 0, "max_tokens": 512,
            "messages": [
                {"role": "system", "content": "Reasoning strength: low"},
                {"role": "user", "content": "Implement an LRU cache class in "
                 "Python with O(1) get and put. Include a method named get."}]})
        content = r["choices"][0]["message"]["content"]
        u = r["usage"]
        out["checks"]["code_canary"] = {
            "completion_tokens": u["completion_tokens"],
            "cached_tokens": u.get("prompt_tokens_details", {}).get("cached_tokens"),
            "has_class": "class" in content, "has_get": "def get" in content}
        if "class" not in content or "def get" not in content:
            out["errors"].append("code canary content check failed")
    except Exception as e:
        out["errors"].append(f"code canary: {e}")

    if not args.skip_vision:
        try:
            url = "data:image/png;base64," + base64.b64encode(png(224, 224, (255, 0, 0))).decode()
            r = call(f"{args.base_url}/v1/chat/completions", {
                "model": args.model, "temperature": 0, "max_tokens": 400,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": "What color is this image? One word."}]}]})
            content = r["choices"][0]["message"]["content"].lower()
            out["checks"]["vision_canary"] = content[:40]
            if "red" not in content:
                out["errors"].append(f"vision canary expected red, got {content[:40]!r}")
        except Exception as e:
            out["errors"].append(f"vision canary: {e}")

    out["ok"] = not out["errors"]
    text = json.dumps(out, indent=1)
    print(text)
    if args.output_json:
        with open(args.output_json, "w") as f:
            f.write(text + "\n")
    sys.exit(0 if out["ok"] else 1)


if __name__ == "__main__":
    main()
