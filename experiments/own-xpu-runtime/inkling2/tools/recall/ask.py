# prefill the haystack once (saved as a library prompt), then ask for each fact; every question loads the saved prompt
import json, sys, time, urllib.request, urllib.error
B = sys.argv[1]; MODEL = sys.argv[2] if len(sys.argv) > 2 else 'inkling-2-mini-chat'; TAG = sys.argv[3] if len(sys.argv) > 3 else 'chat'
D = '/home/steve/inkling-work/recall'
def post(path, body, timeout=7200):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.load(r)
    except urllib.error.HTTPError as e: print('HTTP', e.code, e.read()[:300], flush=True); raise
hay = open(f'{D}/haystack.txt').read(); nd = json.load(open(f'{D}/needles.json'))['needles']
sysm = {'role': 'system', 'content': 'Below are archived documents. Answer questions about them.\n\n' + hay}
lib = json.load(urllib.request.urlopen(B + '/admin/library'))
if not any(p['name'] == 'recall480' for p in lib['prompts']):
    t0 = time.time(); p = post('/admin/prefill', {'name': 'recall480', 'model': MODEL, 'messages': [sysm]})
    print('prefill', p['tokens'], 'tokens in %.0f s, saved %.1f GB in %.1f s' % (time.time() - t0, p['bytes'] / 1e9, p['seconds']), flush=True)
qs = [(n['name'], n['code'], n['depth']) for n in nd] + [('Zephyr', None, None)]
res = []
for name, code, depth in qs:
    q = f'What is the vault combination for project {name}? Reply with the five-digit number only, or "not found".'
    t0 = time.time()
    r = post('/v1/chat/completions', {'model': MODEL, 'messages': [sysm, {'role': 'user', 'content': q}], 'max_tokens': 3000})
    m = r['choices'][0]['message']; t = r['timings']; a = (m['content'] or '').strip()
    ok = (str(code) in a) if code else ('not found' in a.lower())
    res.append({'name': name, 'code': code, 'depth': depth, 'answer': a, 'ok': ok, 'think_chars': len(m.get('reasoning_content') or ''),
                'read': t['read_tokens'], 'prompt': t['prompt_tokens'], 'secs': round(time.time() - t0, 2), 'answer_tok_s': t['answer_tok_per_s']})
    print(f"{name:9s} depth {depth if depth is not None else '-':>4} {'RIGHT' if ok else 'WRONG'} {a[:40]!r:44s} read {t['read_tokens']} of {t['prompt_tokens']} in {time.time() - t0:.1f} s", flush=True)
print('right', sum(r['ok'] for r in res), 'of', len(res), flush=True)
json.dump(res, open(f'{D}/results-{TAG}.json', 'w'), indent=1)
