#!/usr/bin/env python3
"""Max-model-len boundary probe (2026-09-13): does a request that generates exactly to max_model_len survive
speculative decoding? For prompt lengths L in a range, request max_tokens = max_model_len - L with ignore_eos, N
repeats, greedy. Reports HTTP errors, degenerate walls, and (optionally) exact token identity against an oracle
JSON produced by the same probe on a no-speculation server. Motivated by the cookbook's patch_mtp_boundary.py
(partial final speculative group at the boundary).
usage: max-len-boundary-probe.py --base URL --model M --max-model-len 256 --min-len 8 --max-len 24 --iters 3 [--oracle out.json] --out out.json"""
import argparse, json, re, sys, time, urllib.request, urllib.error
ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--model',required=True); ap.add_argument('--max-model-len',type=int,default=256)
ap.add_argument('--min-len',type=int,default=8); ap.add_argument('--max-len',type=int,default=24); ap.add_argument('--iters',type=int,default=3); ap.add_argument('--oracle'); ap.add_argument('--concurrency',type=int,default=1,help='submit all (L, iter) requests through a pool of this size so several requests reach the boundary while others are mid-group (mixed spec widths in one batch)'); ap.add_argument('--out',required=True); a=ap.parse_args()
def post(path,payload,timeout=600):
    req=urllib.request.Request(a.base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
def tokcount(text): return post('/tokenize',{'model':a.model,'prompt':text}).get('count')
words='the quick brown fox jumps over the lazy dog while seven wizards juggle bright lanterns near a quiet river bank at dawn'.split()
def prompt_of_len(L):
    for n in range(1,80):
        t=' '.join((words*4)[:n]); c=tokcount(t)
        if c==L: return t
        if c>L: break
    return None
rows=[]; oracle=json.load(open(a.oracle)) if a.oracle else None
def is_degenerate(txt): return bool(re.search(r'(.)\1{7,}',txt))
def one(L,p,i):
    mt=a.max_model_len-L; t0=time.time()
    try:
        r=post('/v1/completions',{'model':a.model,'prompt':p,'max_tokens':mt,'temperature':0,'ignore_eos':True,'seed':1,'logprobs':None})
        text=r['choices'][0]['text']; fr=r['choices'][0]['finish_reason']; n=r['usage']['completion_tokens']
        row={'L':L,'iter':i,'max_tokens':mt,'completion_tokens':n,'finish_reason':fr,'degenerate':is_degenerate(text[-64:]),'sha':__import__('hashlib').sha256(text.encode()).hexdigest()[:16],'tail':text[-40:],'s':round(time.time()-t0,2)}
    except urllib.error.HTTPError as e:
        row={'L':L,'iter':i,'max_tokens':mt,'http_error':e.code,'body':e.read().decode()[:300]}
    except Exception as e:
        row={'L':L,'iter':i,'max_tokens':mt,'error':str(e)[:300]}
    if oracle and 'sha' in row:
        o=[x for x in oracle['rows'] if x.get('L')==L and 'sha' in x]
        row['oracle_exact']=(o[0]['sha']==row['sha']) if o else None
    return row
jobs=[]
for L in range(a.min_len,a.max_len+1):
    p=prompt_of_len(L)
    if p is None: rows.append({'L':L,'skip':'no prompt of that length'}); continue
    jobs+=[(L,p,i) for i in range(a.iters)]
if a.concurrency>1:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for row in ex.map(lambda j: one(*j), jobs): rows.append(row); print(json.dumps(row)[:200]); sys.stdout.flush()
else:
    for j in jobs: row=one(*j); rows.append(row); print(json.dumps(row)[:200]); sys.stdout.flush()
json.dump({'base':a.base,'model':a.model,'max_model_len':a.max_model_len,'concurrency':a.concurrency,'rows':rows},open(a.out,'w'),indent=1)
bad=[r for r in rows if 'http_error' in r or 'error' in r or r.get('degenerate') or (r.get('completion_tokens') is not None and r['completion_tokens']!=r['max_tokens'])]
print(f"rows={len(rows)} problems={len(bad)} oracle_mismatch={sum(1 for r in rows if r.get('oracle_exact') is False)}")
