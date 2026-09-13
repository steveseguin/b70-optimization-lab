#!/usr/bin/env python3
"""Follow-up to max-len-boundary-probe.py (2026-09-13): for one prompt length L, fetch the greedy completion WITH per-token
strings (logprobs=1) so two arms (e.g. depth 0 vs depth 3, or max-model-len 256 vs 512) can be diffed token by token and the
first divergent index located. Same prompt construction as the boundary probe (word list repeated, exact L via /tokenize)."""
import argparse, json, hashlib, sys, time, urllib.request
ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--model',required=True)
ap.add_argument('--len',type=int,required=True); ap.add_argument('--max-tokens',type=int,required=True); ap.add_argument('--iters',type=int,default=2)
ap.add_argument('--out',required=True); a=ap.parse_args()
def post(path,payload,timeout=600):
    req=urllib.request.Request(a.base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=timeout))
def tokcount(text): return post('/tokenize',{'model':a.model,'prompt':text}).get('count')
words='the quick brown fox jumps over the lazy dog while seven wizards juggle bright lanterns near a quiet river bank at dawn'.split()
def prompt_of_len(L):
    for n in range(1,80):
        t=' '.join((words*4)[:n]); c=tokcount(t)
        if c==L: return t
        if c>L: break
    return None
p=prompt_of_len(a.len); assert p is not None, 'no prompt of that length'
rows=[]
for i in range(a.iters):
    t0=time.time()
    r=post('/v1/completions',{'model':a.model,'prompt':p,'max_tokens':a.max_tokens,'temperature':0,'ignore_eos':True,'seed':1,'logprobs':1})
    ch=r['choices'][0]; text=ch['text']; toks=ch['logprobs']['tokens']; lps=ch['logprobs']['token_logprobs']
    rows.append({'iter':i,'completion_tokens':r['usage']['completion_tokens'],'finish_reason':ch['finish_reason'],'sha':hashlib.sha256(text.encode()).hexdigest()[:16],
                 'tokens':toks,'logprobs':lps,'s':round(time.time()-t0,2)})
    print(json.dumps({k:v for k,v in rows[-1].items() if k not in ('tokens','logprobs')})); sys.stdout.flush()
json.dump({'base':a.base,'model':a.model,'L':a.len,'prompt':p,'max_tokens':a.max_tokens,'rows':rows},open(a.out,'w'),indent=1)
