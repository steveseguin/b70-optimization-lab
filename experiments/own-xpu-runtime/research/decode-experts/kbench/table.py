#!/usr/bin/env python3
# Per-site table: rank 1 (layers 24-47) routed expert shapes from placement.tsv, bytes per token, roofline, ref/final us.
import json,collections,sys
P='/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv'
names={18:'IQ3_XXS',20:'IQ4_NL',21:'IQ3_S',22:'IQ2_S',23:'IQ4_XS',42:'Q2_0'}
sites=collections.defaultdict(lambda:{'layers':[],'bytes_per_expert':0,'shape':None})
for line in open(P):
    f=line.split()
    if len(f)<12 or 'exps' not in f[1]:continue
    layer=int(f[1].split('.')[1])
    if layer<24:continue
    role={'ffn_down_exps.weight':'expsdown','ffn_gate_exps.weight':'expsgate','ffn_up_exps.weight':'expsup'}[f[1].split('.',2)[2]]
    t=int(f[3]);key=f'routed_gemv:{names[t]}:{role}'
    s=sites[key];s['layers'].append(layer);s['bytes_per_expert']=int(f[5])//512;s['shape']=[int(f[11]),int(f[10]) if role!='expsdown' else int(f[10])]
    s['rows_cols']=(int(f[10]),int(f[9])) if False else None
def load(run):
    L=[json.loads(l) for l in open(f'/dev/shm/ownrt-lab-dexp/runs/{run}/rank1/decode-device-profile.jsonl')]
    L=[l for l in L if not l['cancelled']][2:]
    acc=collections.defaultdict(list)
    for l in L:
        for k,v in l['sites'].items():
            if '#' not in k:acc[k].append(v['busy_us'])
    return {k:sum(v)/len(v) for k,v in acc.items()}
ref=load(sys.argv[1]);new=load(sys.argv[2])
rows=[]
for k,s in sorted(sites.items()):
    n=len(s['layers']);b=s['bytes_per_expert']*10
    roof=b/537e3
    r=ref.get(k,0)/n;f=new.get(k,0)/n
    rows.append(dict(site=k,layers=n,bytes_per_site=b,roofline_us_537=round(roof,1),ref_us_per_site=round(r,1),final_us_per_site=round(f,1),ref_total_us=round(ref.get(k,0),1),final_total_us=round(new.get(k,0),1)))
for k in ('route','expert_gather','moe_combine','check_status','norm','hc_combine'):
    rows.append(dict(site=k,ref_total_us=round(ref.get(k,0),1),final_total_us=round(new.get(k,0),1)))
print(json.dumps(rows,indent=1))
