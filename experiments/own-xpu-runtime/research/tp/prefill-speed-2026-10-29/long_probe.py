#!/usr/bin/env python3
"""The 121,854-token / 512-output long request (research/tp/prefill-speed-2026-10-29) against a lab service at 131072.

The request body is the retained HTTP body research/pp4-review-2026-10-28/inputs/long-body.json.gz (one user message,
434,339 characters), with max_tokens 512 (the long512 screens' natural cap). Before sending, the prompt is tokenized
with the lab chat.py (pinned template and tokenizer) and must equal the long512 screens' prompt.i32 token for token
(121,854 ids). Records the service's prompt_wall_ms (prompt reading until the first output token), decode_tok_s
((output_tokens - 1) / first-to-last generated token, the screens' all-511 definition for 512 outputs), client wall,
MTP counts and the 512 output ids, and compares the ids with both retained long512 references:
- default routing (3+1 262K AOT screen aot-cold-gate/3plus1-262k-long512-r1-evidence, also the 2+1 128K screens):
  sha256(json ids) prefix bf1f0867d1bd;
- reference-route tie sort (cut16 screen control/cut16, equal16): ee09ec505382.
Usage: long_probe.py --url URL --out OUT.json [--dry-run]   (env: SC117_CONTEXT=131072, SC117_RANK_BDFS of the service)"""
import argparse, gzip, hashlib, importlib.util, json, os, time, urllib.request
from pathlib import Path
D = Path(__file__).resolve().parent
PP4 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/pp4-review-2026-10-28')
BODY = PP4 / 'inputs/long-body.json.gz'
BODY_RAW_SHA = '55aef10c32334e0096a35007bec0f39a03e43163ef6882c2ccace112c84ece94'
PROMPT_I32 = D / 'evidence/long512-prompt.i32'   # copy of /dev/shm/sc117-aot-bmg-3plus1-262k-long512-20261028-r1/prompt.i32
REFS = {'default_routing_3plus1_262k': PP4 / 'aot-cold-gate/3plus1-262k-long512-r1-evidence/output/tokens.jsonl.gz',
        'reference_route_tie_sort_cut16_control': PP4 / 'cut16-prefill-screen/control/control-output-tokens.jsonl.gz'}


def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def ids_sha(ids):
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


ap = argparse.ArgumentParser(); ap.add_argument('--url'); ap.add_argument('--out', type=Path); ap.add_argument('--max-tokens', type=int, default=512)
ap.add_argument('--dry-run', action='store_true')
a = ap.parse_args()
raw = gzip.open(BODY, 'rb').read()
if hashlib.sha256(raw).hexdigest() != BODY_RAW_SHA: raise SystemExit('long body hash differs from the retained manifest')
body = json.loads(raw); body['max_tokens'] = a.max_tokens
C = load(D / 'lab/chat.py', 'long_probe_chat'); chat = C.Chat()
ids = C.parse(body, chat)['prompt_ids']
ref_prompt = list(memoryview(PROMPT_I32.read_bytes()).cast('i'))
if ids != ref_prompt: raise SystemExit(f'tokenized prompt ({len(ids)}) differs from the long512 prompt.i32 ({len(ref_prompt)})')
refs = {k: [json.loads(l)['token'] for l in gzip.open(p, 'rt') if l.strip()] for k, p in REFS.items()}
row = dict(source=str(BODY), body_raw_sha256=BODY_RAW_SHA, prompt_tokens=len(ids), prompt_sha256=ids_sha(ids),
           prompt_equals_long512_prompt_i32=True, max_tokens=a.max_tokens, references={k: dict(path=str(REFS[k]), ids_sha256=ids_sha(v), n=len(v)) for k, v in refs.items()})
if a.dry_run:
    print(json.dumps(row, indent=1)); raise SystemExit(0)
data = json.dumps(body).encode()
t0 = time.monotonic()
with urllib.request.urlopen(urllib.request.Request(a.url, data=data, headers={'Content-Type': 'application/json'}), timeout=3600) as r:
    res = json.load(r)
wall = time.monotonic() - t0
o = res['ownrt']; cached = res['usage']['prompt_tokens_details']['cached_tokens']
if cached != 0: raise SystemExit('cached_tokens must be 0')
out = o.get('output_token_ids') or []
cmp = {}
for k, v in refs.items():
    first = next((i for i in range(min(len(out), len(v))) if out[i] != v[i]), None)
    cmp[k] = dict(equal=out == v, first_differ=first if first is not None else (None if len(out) == len(v) else min(len(out), len(v))))
row.update(cached_tokens=cached, prompt_wall_ms=o['prompt_wall_ms'], decode_wall_ms=o.get('decode_wall_ms'), decode_tok_s=o.get('decode_tok_s'),
           wall_s=wall, output_tokens=o['output_tokens'], finish=res['choices'][0]['finish_reason'], mtp=o.get('mtp'),
           prefill_rows=o.get('prefill_rows'), output_token_ids=out, output_ids_sha256=ids_sha(out),
           output_sha256=hashlib.sha256(res['choices'][0]['message']['content'].encode()).hexdigest(), compare=cmp)
a.out.write_text(json.dumps(row, indent=1) + '\n')
print(json.dumps({k: v for k, v in row.items() if k not in ('output_token_ids', 'references')}))
