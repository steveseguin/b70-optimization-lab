#!/usr/bin/env python3
"""End-to-end long-context check through the LAN service: needle recall, continuation vs fresh read."""
import json, sys, time, urllib.request
from pathlib import Path
URL = 'http://192.168.2.44:18160/v1/chat/completions'
R = Path('/home/steve/llm-optimizations')
docs = [R / 'CURRENT.md', R / 'docs/sc117-engine-review.md', R / 'experiments/own-xpu-runtime/research/2026-10-25-decode-roofline.md',
        R / 'experiments/own-xpu-runtime/research/2026-10-24-exact-multicard-design.md']
target_chars = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
frozen = Path(__file__).with_name(f'doc-{target_chars}.txt')
if frozen.exists():
    text = frozen.read_text()
else:
    text = ''
    for d in docs:
        text += d.read_text()
        if len(text) > target_chars: break
    text = text[:target_chars]
    frozen.write_text(text)
needle = 'IMPORTANT NOTE FOR LATER: the vault access code is 7341-ORCHID.'
body_text = text[:2000] + '\n\n' + needle + '\n\n' + text[2000:]
def post(messages, max_tokens=80, reuse=True):
    body = json.dumps({'messages': messages, 'max_tokens': max_tokens, 'sc117_reuse': reuse}).encode()
    t0 = time.monotonic()
    with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'}), timeout=3600) as r:
        res = json.load(r)
    o = res['ownrt']
    return res, dict(wall_s=round(time.monotonic() - t0, 1), prompt_tokens=res['usage']['prompt_tokens'],
                     cached=res['usage']['prompt_tokens_details']['cached_tokens'], prompt_ms=round(o.get('prompt_wall_ms', 0)),
                     decode_tok_s=round(o.get('decode_tok_s') or 0, 2), out=res['choices'][0]['message']['content'][:160])
q1 = [{'role': 'user', 'content': 'Here is a long document.\n\n' + body_text + '\n\nQuestion: what is the vault access code mentioned in the document? Answer with the code only.'}]
r1, s1 = post(q1); print('turn1', json.dumps(s1))
q2 = q1 + [{'role': 'assistant', 'content': r1['choices'][0]['message']['content']},
           {'role': 'user', 'content': 'In one sentence, what is the main topic of the document?'}]
r2c, s2c = post(q2); print('turn2 continued', json.dumps(s2c))
post([{'role': 'user', 'content': 'Say OK.'}], 4)  # different conversation: parks this one (sessions on)
r2f, s2f = post(q2, reuse=False); print('turn2 fresh', json.dumps(s2f))  # sc117_reuse false: no continuation, no parked session
same = r2c['ownrt'].get('output_token_ids') == r2f['ownrt'].get('output_token_ids')
print(json.dumps(dict(needle_found='7341' in s1['out'], continued_equals_fresh=same, continued_cached=s2c['cached'], fresh_cached=s2f['cached'])))
if len(sys.argv) > 2:
    json.dump(dict(turn1=r1['ownrt'].get('output_token_ids'), turn2=r2f['ownrt'].get('output_token_ids'), stats=[s1, s2c, s2f]), open(sys.argv[2], 'w'), indent=1)
