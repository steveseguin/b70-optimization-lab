#!/usr/bin/env python3
"""Boundary tail probe (2026-09-13): reproduce the max_model_len boundary with a few generated tokens. Given an
oracle token dump (max-len-divergence-probe.py output: prompt text + greedy tokens), send prompt + the first n oracle
tokens as text and ask for the remaining tokens with ignore_eos; the scheduler's clamp (max_model_len - computed - 1)
then makes the final speculative step a group of width max_model_len - (L + n) - 1... i.e. the last step's width is
controlled by n. Reports, per n, whether the generated tail equals the oracle tail, token by token."""
import argparse, json, sys, urllib.request
ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--model',required=True)
ap.add_argument('--oracle',required=True); ap.add_argument('--ns',default='236,237,238,239,240,241'); ap.add_argument('--iters',type=int,default=2); ap.add_argument('--out',required=True); a=ap.parse_args()
def post(path,payload,timeout=600):
    req=urllib.request.Request(a.base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=timeout))
o=json.load(open(a.oracle)); prompt=o['prompt']; toks=o['rows'][0]['tokens']; L=o['L']; total=L+len(toks)
rows=[]
for n in [int(x) for x in a.ns.split(',')]:
    p=prompt+''.join(toks[:n]); cnt=post('/tokenize',{'model':a.model,'prompt':p})['count']; mt=total-cnt
    for i in range(a.iters):
        r=post('/v1/completions',{'model':a.model,'prompt':p,'max_tokens':mt,'temperature':0,'ignore_eos':True,'seed':1,'logprobs':1})
        got=r['choices'][0]['logprobs']['tokens']; want=toks[n:]
        row={'n':n,'iter':i,'prompt_tokens':cnt,'max_tokens':mt,'got':got,'want':want,'exact':got==want,'first_diff':next((k for k in range(min(len(got),len(want))) if got[k]!=want[k]),None)}
        rows.append(row); print(json.dumps(row)[:220]); sys.stdout.flush()
print('SUMMARY', json.dumps({n:[r['exact'] for r in rows if r['n']==n] for n in {r['n'] for r in rows}}))
json.dump({'base':a.base,'oracle':a.oracle,'rows':rows},open(a.out,'w'),indent=1)
