#!/usr/bin/env python3
"""Long-prompt TTFT probe for the service-ready suite: one cold request whose prompt is ttft-doc.txt (the first
10,000 characters of research/context-64k/doc-40000.txt, a frozen extract of the lab's own notes) and one question.
64-token cap, greedy (the service's only mode). Records the service's prompt_wall_ms (prompt reading until the first
output token), prompt length, output ids and hashes. Usage: ttft_probe.py --url URL --out OUT.json [--dry-run]"""
import argparse, hashlib, importlib.util, json, time, urllib.request
from pathlib import Path
R = Path('/home/steve/llm-optimizations'); L = R / 'experiments/own-xpu-runtime/gsq-rco-iq3s'
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ap = argparse.ArgumentParser(); ap.add_argument('--url'); ap.add_argument('--out', type=Path); ap.add_argument('--max-tokens', type=int, default=64); ap.add_argument('--dry-run', action='store_true')
a = ap.parse_args()
C = load(L / 'serving/lan/chat.py', 'probe_chat'); chat = C.Chat()
doc = (Path(__file__).resolve().parent / 'ttft-doc.txt').read_text()
msgs = [{'role': 'user', 'content': 'Here is a long document.\n\n' + doc + '\n\nQuestion: in two sentences, what is this document about?'}]
ids = C.parse({'messages': msgs, 'max_tokens': a.max_tokens}, chat)['prompt_ids']
row = dict(source='ttft-doc.txt', doc_sha256=hashlib.sha256(doc.encode()).hexdigest(), prompt_tokens=len(ids),
           prompt_sha256=hashlib.sha256(json.dumps(ids).encode()).hexdigest(), max_tokens=a.max_tokens)
if a.dry_run:
    print(json.dumps(row)); raise SystemExit(0)
body = json.dumps({'messages': msgs, 'max_tokens': a.max_tokens}).encode()
t0 = time.monotonic()
with urllib.request.urlopen(urllib.request.Request(a.url, data=body, headers={'Content-Type': 'application/json'}), timeout=900) as r:
    res = json.load(r)
wall = time.monotonic() - t0
o = res['ownrt']; cached = res['usage']['prompt_tokens_details']['cached_tokens']
if cached != 0: raise SystemExit('cached_tokens must be 0')
row.update(cached_tokens=cached, prompt_wall_ms=o['prompt_wall_ms'], wall_s=wall, output_tokens=o['output_tokens'],
           decode_tok_s=o.get('decode_tok_s'), mtp=o.get('mtp'), output_token_ids=o.get('output_token_ids'),
           output_sha256=hashlib.sha256(res['choices'][0]['message']['content'].encode()).hexdigest(),
           prefill_rows=o.get('prefill_rows'))
a.out.write_text(json.dumps(row, indent=1) + '\n')
print(json.dumps({k: v for k, v in row.items() if k != 'output_token_ids'}))
