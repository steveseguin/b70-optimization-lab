#!/usr/bin/env python3
"""Prefix-caching (APC) x speculative-decoding identity probe (2026-09-13).
Motivation: the community cookbook ports three upstream fixes for prefix caching + MTP on hybrid (GDN/Mamba) models
(vLLM PR #53919, issue #53505, PR #48375). Our published runs never enable APC, so this probe asks whether R304 is
correct WITH it on, so we know whether those ports matter here.
Prompts: the exact-depth fixture's real-content token-ID prompts (classes x depths), plus a 'tail' variant per case
(same prompt with its last 64 tokens replaced by another class's last 64 tokens -> partial-prefix hit). Phases:
  cold: every base prompt once, sequential          repeat: every base prompt again (full-prefix hit)
  tail: every tail variant, sequential (partial hit)   conc: all prompts at concurrency C, R rounds
Every request is greedy, 128 tokens, ignore_eos; usage.prompt_tokens_details.cached_tokens is recorded per request.
--oracle compares every output text to the same prompt key in a probe JSON from a cache-off no-spec server."""
import argparse, json, hashlib, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--model',required=True)
ap.add_argument('--fixture',required=True); ap.add_argument('--depths',default='2048,4096,8192,16384,32768')
ap.add_argument('--max-tokens',type=int,default=128); ap.add_argument('--concurrency',type=int,default=8); ap.add_argument('--conc-rounds',type=int,default=2)
ap.add_argument('--oracle'); ap.add_argument('--out',required=True); a=ap.parse_args()
def post(path,payload,timeout=1800):
    req=urllib.request.Request(a.base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=timeout))
def is_degenerate(txt): return bool(re.search(r'(.)\1{7,}',txt))
fx=json.load(open(a.fixture)); depths={int(x) for x in a.depths.split(',')}
cases=[c for c in fx['cases'] if c['depth'] in depths]; classes=sorted({c['class'] for c in cases})
prompts={}
for c in cases:
    prompts[c['id']]=c['prompt_token_ids']
    other=[o for o in cases if o['depth']==c['depth'] and o['class']!=c['class']]
    if other: prompts[c['id']+'-tail']=c['prompt_token_ids'][:-64]+other[0]['prompt_token_ids'][-64:]
def one(key,phase,slot=None):
    t0=time.time()
    try:
        r=post('/v1/completions',{'model':a.model,'prompt':prompts[key],'max_tokens':a.max_tokens,'temperature':0,'ignore_eos':True,'seed':1})
        ch=r['choices'][0]; text=ch['text']; u=r['usage']; det=u.get('prompt_tokens_details') or {}
        row={'key':key,'phase':phase,'slot':slot,'prompt_tokens':u.get('prompt_tokens'),'cached_tokens':det.get('cached_tokens'),'completion_tokens':u.get('completion_tokens'),
             'finish_reason':ch['finish_reason'],'degenerate':is_degenerate(text[-64:]),'sha':hashlib.sha256(text.encode()).hexdigest()[:16],'tail':text[-40:],'s':round(time.time()-t0,2)}
    except urllib.error.HTTPError as e: row={'key':key,'phase':phase,'slot':slot,'http_error':e.code,'body':e.read().decode()[:300]}
    except Exception as e: row={'key':key,'phase':phase,'slot':slot,'error':str(e)[:300]}
    return row
oracle=None
if a.oracle:
    od=json.load(open(a.oracle)); oracle={}
    for r in od['rows']:
        if 'sha' in r: oracle.setdefault(r['key'],set()).add(r['sha'])
rows=[]
def add(row):
    if oracle is not None and 'sha' in row:
        o=oracle.get(row['key']); row['oracle_exact']=(row['sha'] in o) if o else None; row['oracle_ambiguous']=(len(o)>1) if o else None
    rows.append(row); print(json.dumps(row)[:220]); sys.stdout.flush()
base_keys=[c['id'] for c in sorted(cases,key=lambda c:(c['depth'],c['class']))]; tail_keys=[k+'-tail' for k in base_keys if k+'-tail' in prompts]
for k in base_keys: add(one(k,'cold'))
for k in base_keys: add(one(k,'repeat'))
for k in tail_keys: add(one(k,'tail'))
allk=base_keys+tail_keys
for rnd in range(a.conc_rounds):
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for row in ex.map(lambda kv: one(kv[1],f'conc{a.concurrency}-r{rnd}',kv[0]%a.concurrency), enumerate(allk)): add(row)
ok=[r for r in rows if 'sha' in r]; summ={'rows':len(rows),'errors':len(rows)-len(ok),'degenerate':sum(r['degenerate'] for r in ok),
   'cached_nonzero':sum(1 for r in ok if (r['cached_tokens'] or 0)>0),'phases':{}}
for ph in sorted({r['phase'] for r in rows}):
    pr=[r for r in ok if r['phase']==ph]; summ['phases'][ph]={'n':len(pr),'cached_nonzero':sum(1 for r in pr if (r['cached_tokens'] or 0)>0),
        'oracle_exact':sum(1 for r in pr if r.get('oracle_exact')) if oracle is not None else None,'mismatch':[r['key'] for r in pr if r.get('oracle_exact') is False] if oracle is not None else None}
# within-run consistency: same key across phases
from collections import defaultdict
bykey=defaultdict(set)
for r in ok: bykey[r['key']].add(r['sha'])
summ['keys_with_internal_variance']=sorted(k for k,s in bykey.items() if len(s)>1)
print('SUMMARY',json.dumps(summ)); json.dump({'base':a.base,'model':a.model,'fixture':a.fixture,'oracle':a.oracle,'summary':summ,'rows':rows},open(a.out,'w'),indent=1)
