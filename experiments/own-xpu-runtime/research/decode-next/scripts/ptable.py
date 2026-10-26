#!/usr/bin/env python3
# Per-site device table for rank 1 (layers SPLIT..47 + head): us per token (mean over non-cancelled halves after 2),
# weight bytes per token from placement.tsv, time at 600 and 335 GB/s, and the measured fraction of each floor.
import json,collections,sys
P='/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/loader/placement.tsv'
SPLIT=int(sys.argv[2]) if len(sys.argv)>2 else 23
T={0:'F32',8:'Q8_0',12:'Q4_K',13:'Q5_K',14:'Q6_K',18:'IQ3_XXS',20:'IQ4_NL',21:'IQ3_S',22:'IQ2_S',23:'IQ4_XS',30:'BF16',42:'Q2_0'}
ROLE={'hc_attn_down':'hc.a.low','hc_attn_up':'hc.a.gate','hc_attn_inject':'hc.a.inject','hc_ffn_down':'hc.f.low','hc_ffn_up':'hc.f.gate','hc_ffn_inject':'hc.f.inject',
 'attn_output':'attention','ssm_out':'attention','attn_qkv':'gdn.qkv','attn_gate':'gdn.z','ssm_alpha':'gdn.a','ssm_beta':'gdn.b','attn_q':'qsa.qgate','attn_k':'qsa.k','attn_v':'qsa.v',
 'indexer.q_proj':'qsa.iq','indexer.k_proj':'qsa.ik','ffn_gate_inp':'router','ffn_gate_inp_shexp':'shared_gate','ffn_gate_shexp':'shexpgate','ffn_up_shexp':'shexpup','ffn_down_shexp':'shexpdown',
 'ffn_gate_exps':'expsgate','ffn_up_exps':'expsup','ffn_down_exps':'expsdown'}
B=collections.defaultdict(int)
for line in open(P):
    f=line.split('\t') if '\t' in line else line.split()
    name=f[1];t=int(f[3]);by=int(f[5])
    if name.startswith('blk.'):
        layer=int(name.split('.')[1])
        if layer<SPLIT:continue
        stem=name.split('.',2)[2].rsplit('.weight',1)[0]
        if stem not in ROLE:continue
        role=ROLE[stem];routed=stem.endswith('_exps')
        key=('routed_gemv:' if routed else 'gemv:')+T.get(t,str(t))+':'+role
        B[key]+=by*10//512 if routed else by
    elif name=='output.weight':B['gemv:Q6_K:logits']+=by
    elif name=='output_hc_down.weight':B['gemv:BF16:final.low']+=by
    elif name=='output_hc_up.weight':B['gemv:BF16:final.gate']+=by
L=[json.loads(l) for l in open(sys.argv[1])];L=[l for l in L if not l['cancelled']][2:]
acc=collections.defaultdict(list);span=[]
for l in L:
    span.append(l['span_us'])
    for k,v in l['sites'].items():
        if '#' not in k:acc[k].append((v['count'],v['busy_us']))
rows=[]
for k,v in acc.items():
    us=sum(x[1] for x in v)/len(v);n=v[0][0];b=B.get(k,0)
    rows.append(dict(site=k,launches=n,us=round(us,1),us_per_launch=round(us/n,2),bytes=b,floor600_us=round(b/600e3,1) if b else None,floor335_us=round(b/335e3,1) if b else None,
      pct_of_600=round(100*b/600e3/us,1) if b else None,pct_of_335=round(100*b/335e3/us,1) if b else None))
rows.sort(key=lambda r:-r['us'])
out=dict(halves=len(L),span_us_median=sorted(span)[len(span)//2],busy_us=round(sum(r['us'] for r in rows),1),
  gemv_bytes=sum(r['bytes'] for r in rows),rows=rows)
if len(sys.argv)>3:json.dump(out,open(sys.argv[3],'w'),indent=1)
print('halves %d span %.0f busy %.0f weight MB %.1f'%(out['halves'],out['span_us_median'],out['busy_us'],out['gemv_bytes']/1e6))
print('%-34s %4s %8s %7s %8s %7s %7s %6s %6s'%('site','n','us','us/l','MB','f600','f335','%600','%335'))
for r in rows:
    print('%-34s %4d %8.1f %7.2f %8.2f %7s %7s %6s %6s'%(r['site'],r['launches'],r['us'],r['us_per_launch'],r['bytes']/1e6,r['floor600_us'] or '',r['floor335_us'] or '',r['pct_of_600'] or '',r['pct_of_335'] or ''))
