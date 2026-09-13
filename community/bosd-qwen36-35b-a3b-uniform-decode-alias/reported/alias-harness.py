#!/usr/bin/env python3
"""alias-harness — on-demand reproduction of the vLLM-XPU shape-aliased-prefill
GDN state-loss bug (upstream vllm #53051), the lab's open question #1.

Theory: with spec decode, uniform_decode_query_len = 1 + num_spec_tokens.
A *fresh* request whose prompt tokenizes to exactly that many tokens has, on its
prefill step (idle server, num_reqs=1): max_num_scheduled_tokens == that value ==
uniform_decode_query_len AND num_tokens == value*num_reqs -> stock _is_uniform_decode
returns True -> prefill misdispatched into the spec-decode uniform-decode cudagraph
-> stale/null GDN recurrent-state indices -> zeroed state -> degenerate logits.

So: send greedy (temp 0) completions whose prompts tokenize to exactly K tokens,
for K in {alias point, controls}, and measure the degenerate-output rate.
Degenerate = a single-token repetition wall (!!!!!, 0000, oooo, ||||, etc).

Uses the OpenAI-compatible endpoint + vLLM's /tokenize to *measure* prompt token
counts and pick real K-token prompts (no tokenizer dependency locally).

Usage:
  python3 alias-harness.py --base http://localhost:PORT/v1 --model NAME \
      --spec-tokens 1 --iters 30 [--tag stock|patched]
"""
import argparse, json, re, sys, time, urllib.request, urllib.error

def _post(url, payload, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer sk-local"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer sk-local"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

# Degenerate = >=8 of the same char in a row, or a run that is >=70% one char,
# for the "wall" signatures. Whitespace-only excluded.
WALL = re.compile(r"(.)\1{7,}")
def is_degenerate(txt):
    t = txt.strip()
    if not t:
        return True, "empty"
    m = WALL.search(t)
    if m:
        return True, f"repeat:{m.group(1)!r}x{len(m.group(0))}"
    # dominant-char check
    from collections import Counter
    c = Counter(t)
    ch, n = c.most_common(1)[0]
    if len(t) >= 12 and n / len(t) >= 0.7 and not ch.isalnum():
        return True, f"dominant:{ch!r}={n}/{len(t)}"
    return False, ""

def tokcount(base, model, text):
    try:
        r = _post(base.rsplit("/v1", 1)[0] + "/tokenize",
                  {"model": model, "prompt": text}, timeout=30)
        return r.get("count") or len(r.get("tokens", []))
    except Exception:
        return None

def find_k_token_prompt(base, model, k, pool):
    """Return a prompt string that tokenizes to exactly k tokens, or None."""
    for s in pool:
        if tokcount(base, model, s) == k:
            return s
    return None

# candidate short strings; we measure their real token counts on the server
POOL = ["Hi", "Hi.", "ok", "OK!", "1", "12", "1+1", "2+2", "cat", "the",
        "Hello", "Hello!", "Yes", "No", "A B", "x y z", "one two",
        "Count:", "Q:", "sum 3 4", "print hi", "def f", "a", "an apple",
        "The quick brown fox jumps over the lazy dog and then keeps running"]

def run_shape(base, model, label, prompt, iters, max_tokens=24):
    bad = 0; samples = []
    for i in range(iters):
        try:
            r = _post(base + "/completions",
                      {"model": model, "prompt": prompt, "max_tokens": max_tokens,
                       "temperature": 0, "seed": 12345}, timeout=120)
            out = r["choices"][0]["text"]
        except Exception as e:
            out = f"<ERROR {e}>"
        deg, why = is_degenerate(out)
        if deg:
            bad += 1
            if len(samples) < 3:
                samples.append((why, out[:60]))
    return {"label": label, "prompt": repr(prompt), "iters": iters,
            "degenerate": bad, "rate": round(bad / iters, 3), "samples": samples}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--spec-tokens", type=int, default=1,
                    help="num_speculative_tokens the server runs (MTP depth)")
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    model = args.model
    if not model:
        model = _get(base + "/models")["data"][0]["id"]
    print(f"# target={base} model={model} spec_tokens={args.spec_tokens} tag={args.tag}")

    alias_k = 1 + args.spec_tokens               # the aliasing prompt length
    controls = sorted({1, 2, 3, alias_k} - {alias_k})  # neighbors that must NOT alias

    shapes = []
    pa = find_k_token_prompt(base, model, alias_k, POOL)
    if pa is None:
        print(f"!! could not find a {alias_k}-token prompt in POOL; check /tokenize", file=sys.stderr)
    else:
        shapes.append((f"ALIAS k={alias_k} (=1+spec)", pa))
    for k in controls:
        pc = find_k_token_prompt(base, model, k, POOL)
        if pc:
            shapes.append((f"control k={k}", pc))
    # a long normal prompt (never aliases: max_num_scheduled_tokens != alias_k)
    long_p = POOL[-1]
    shapes.append((f"control long ({tokcount(base, model, long_p)}tok)", long_p))

    results = []
    for label, prompt in shapes:
        res = run_shape(base, model, label, prompt, args.iters)
        results.append(res)
        print(f"{res['label']:28} prompt={res['prompt']:30} "
              f"degenerate={res['degenerate']:>3}/{res['iters']} rate={res['rate']}"
              + ("  e.g. " + str(res['samples'][0]) if res['samples'] else ""))

    out = {"base": base, "model": model, "spec_tokens": args.spec_tokens,
           "tag": args.tag, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "results": results}
    print("\n=== JSON ===")
    print(json.dumps(out))

if __name__ == "__main__":
    main()
