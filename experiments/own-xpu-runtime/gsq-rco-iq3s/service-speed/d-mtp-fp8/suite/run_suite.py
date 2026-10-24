#!/usr/bin/env python3
"""Run the fixed 12-prompt realistic suite once each (cold, 512 cap, greedy) through the LAN service; record MTP stats."""
import argparse, hashlib, importlib.util, json, sys, time, urllib.request
from pathlib import Path
R = Path('/home/steve/llm-optimizations'); L = R / 'experiments/own-xpu-runtime/gsq-rco-iq3s'
SUITE = R / 'experiments/own-xpu-runtime/stage2/suite-inputs-20261012'
def load(p, n):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
C = load(L / 'serving/lan/chat.py', 'suite_chat'); chat = C.Chat()
ap = argparse.ArgumentParser(); ap.add_argument('--url', default='http://192.168.2.44:18160/v1/chat/completions'); ap.add_argument('--label', required=True); ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
manifest = json.loads((SUITE / 'suite-manifest.json').read_text())
rows = []
for p in manifest['prompts']:
    ids = list(map(int, (SUITE / p['prompt_id'] / 'tokens.txt').read_text().split()))
    text = chat.tok.decode(ids, skip_special_tokens=False)
    user = text.split('<|im_start|>user\n', 1)[1].split('<|im_end|>', 1)[0]
    msgs = [{'role': 'user', 'content': user}]
    if 'system\n' in text.split('<|im_start|>user', 1)[0]:
        msgs.insert(0, {'role': 'system', 'content': text.split('<|im_start|>system\n', 1)[1].split('<|im_end|>', 1)[0]})
    req = C.parse({'messages': msgs, 'max_tokens': 512}, chat)
    assert req['prompt_ids'] == ids, p['prompt_id'] + ': re-rendered prompt differs from the frozen suite tokens'
    body = json.dumps({'messages': msgs, 'max_tokens': 512}).encode()
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(a.url, data=body, headers={'Content-Type': 'application/json'}), timeout=900) as r:
        res = json.load(r)
    o = res['ownrt']; content = res['choices'][0]['message']['content']
    rows.append(dict(prompt_id=p['prompt_id'], prompt_tokens=len(ids), output_tokens=o['output_tokens'], finish=res['choices'][0]['finish_reason'],
                     mtp=o['mtp'], acceptance=o['mtp']['hits'] / o['mtp']['guesses'] if o['mtp']['guesses'] else None,
                     decode_tok_s=o['decode_tok_s'], prompt_wall_ms=o['prompt_wall_ms'], wall_s=time.time() - t0,
                     output_sha256=hashlib.sha256(content.encode()).hexdigest()))
    print(json.dumps(rows[-1]), flush=True)
g = sum(r['mtp']['guesses'] for r in rows); h = sum(r['mtp']['hits'] for r in rows)
summary = dict(label=a.label, url=a.url, prompts=len(rows), pooled_acceptance=h / g, guesses=g, hits=h,
               median_decode_tok_s=sorted(r['decode_tok_s'] for r in rows)[len(rows) // 2], rows=rows,
               scope='one cold request per frozen suite prompt, 512 cap, greedy; service observation, not a certified benchmark')
a.out.write_text(json.dumps(summary, indent=1) + '\n'); print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}))
