"""Packet183 expected-gain pricing for S1 (CPU arithmetic on recorded numbers only).

Inputs, each labelled:
  measured-structure  S1 site counts per rank at production shape (this packet's
                      evidence/full-shape.json: which issue sites run p183 kernels)
  measured            packet110 roofline.json per-class device time and runtime
                      weight bytes (synthetic complete layer, 2 fresh owners)
  measured            packet160 interval reconstruction of the 58.798109 record
                      (via packet177 options.json inputs): hit/miss means, A/B/D
  format              Q6_K expanded fetched bytes per 256 weights: 256 codes + 64 B
                      FP32 words (production) vs 256 codes + 18 B metadata (S1)
Scenarios (no device result is implied):
  floor       only the removed bytes' time at the 590 GB/s streaming-read ceiling
              disappears; every inefficiency and overhead of the kernel stays
  proportional the S1 kernel keeps the production kernel's achieved bandwidth,
              so class time falls by the byte cut (head/draft at 63% of 590, the
              measured R5 full-vocabulary head efficiency)
Break-even: the share of the floor saving that S1 must realize for +2.0%.
Writes evidence/expected-gain.json.
"""
import json,resource
from p183_v5_build_engine import P,ROOT,sha,save,limits

READ_GBS=590.0      # measured streaming-read ceiling (SCOREBOARD "589-593 GB/s, rounded to 590")
HEAD_EFF=0.63       # measured R5 full-vocabulary head, 371 GB/s = 63% of 590 (SCOREBOARD)
CUT=1-(256+18)/(256+64)   # 0.14375: fetched bytes per 256 Q6 weights, S1 vs production
PREFIX,DRAFT_PREFIX,K=202240,80128,2560
S2='experiments/own-xpu-runtime/stage2/'

def prov(rel):return dict(name=rel.rsplit('/',1)[-1],parent_relpath=rel,parent_digest=sha(ROOT/rel))

def main():
 limits()
 cov=json.loads((P/'evidence/full-shape.json').read_text())['s1_coverage']
 roof=json.loads((ROOT/S2/'packet110-class-roofline/roofline.json').read_text())
 opts=json.loads((ROOT/S2/'packet177-twocard-structural/options.json').read_text())['inputs']
 v=lambda k:opts[k]['value']
 # packet110 rows at context 128: GDN layer 4, QSA layer 3
 def row(kind,site):
  r=[x for x in roof['rows'] if x['kind']==kind and x['site']==site and x['context']==128];assert len(r)==1,(kind,site);return r[0]
 cls={'gdn.qkv':row('GDN','gdn.qkv'),'gdn.z':row('GDN','gdn.z'),'qsa.qgate':row('QSA','qsa.qgate'),
      'attention':row('GDN','attention'),'router':row('GDN','small.ffn.q6')}
 q6_bytes={c:r['runtime_weight_read_bytes'] for c,r in cls.items()}
 # small.ffn.q6 = F32 router + Q6 shared gate/up + F32 shared router: only the two Q6 members change
 q6_bytes['router']=2*640*(K+4*K//16)
 assert q6_bytes['gdn.qkv']==10240*3200 and q6_bytes['qsa.qgate']==12288*3200 and q6_bytes['attention']==2560*(6144+4*6144//16)
 per_rank={}
 for rank in (0,1):
  conv=cov[f'rank{rank}']['converted'];floor=prop=0.0;rows=[]
  for c,n in conv.items():
   if c=='logits':
    b=PREFIX*3200;f=CUT*b/READ_GBS/1e6;p=CUT*b/(READ_GBS*HEAD_EFF)/1e6
   else:
    b=q6_bytes[c];f=CUT*b/READ_GBS/1e6
    t=cls[c]['measured_us']/1e3
    p=CUT*t*(q6_bytes[c]/cls[c]['runtime_weight_read_bytes']) if c=='router' else CUT*t
   floor+=n*f;prop+=n*p;rows.append(dict(cls=c,sites=n,q6_bytes_per_site=b,floor_ms_per_site=f,proportional_ms_per_site=p))
  per_rank[rank]=dict(floor_ms=floor,proportional_ms=prop,classes=rows)
 d_floor=CUT*DRAFT_PREFIX*3200/READ_GBS/1e6;d_prop=CUT*DRAFT_PREFIX*3200/(READ_GBS*HEAD_EFF)/1e6
 assert cov['rank1']['draft']['converted']==1
 hits,misses=v('hits'),v('misses');T_hit,T_miss=v('T_hit_ms'),v('T_miss_ms');A,B=v('A_ms'),v('B_ms')
 base=(hits*T_hit+misses*T_miss)/(hits+misses)
 logits_floor=next(x['floor_ms_per_site'] for x in per_rank[1]['classes'] if x['cls']=='logits')
 logits_prop=next(x['proportional_ms_per_site'] for x in per_rank[1]['classes'] if x['cls']=='logits')
 def scenario(key,dkey,share=1.0):
  r0=per_rank[0][key]*share;r1=per_rank[1][key]*share;dd=(d_floor if dkey=='floor' else d_prop)*share
  cap=(B-A)+r0                     # B can fall until rank0's A (+offset>=0) becomes the longer half
  dB=min(r1,cap)
  hit=T_hit-dd-dB
  # miss: rank0 redoes A (C, no head suffix) then the halves race again
  head=(logits_floor if key=='floor_ms' else logits_prop)*share
  miss=T_miss-r0-min(r1,cap)
  mean=(hits*hit+misses*miss)/(hits+misses)
  return dict(rank0_ms=r0,rank1_ms=r1,draft_ms=dd,hit_ms=hit,miss_ms=miss,pooled_ms=mean,gain_percent=100*(base/mean-1),
              projected_tok_s=v('record_tok_s')*base/mean,rank1_head_part_ms=head)
 floor=scenario('floor_ms','floor');prop=scenario('proportional_ms','prop')
 lo,hi=0.0,1.0
 for _ in range(60):
  mid=(lo+hi)/2
  if scenario('floor_ms','floor',mid)['gain_percent']<2.0:lo=mid
  else:hi=mid
 save(P/'evidence/expected-gain.json',dict(passed=True,device_executed=False,diagnostic_only=True,
  note='planning numbers from recorded measurements; not a speed. The v5 bracket is the measurement.',
  byte_cut=CUT,read_ceiling_GBs=READ_GBS,head_efficiency=HEAD_EFF,base_pooled_ms=base,record_tok_s=v('record_tok_s'),
  per_rank=per_rank,draft_head=dict(rows=DRAFT_PREFIX,floor_ms=d_floor,proportional_ms=d_prop),
  scenarios=dict(floor=floor,proportional=prop),break_even_floor_share_for_2pct=hi,
  packet177_reference=dict(s1a_dense_lane_only_ceiling_percent=3.7,assumption='f=0.85 of non-HC dense_hc census time (packet168 v3 11.532 ms), HC share 0.29 transferred; head and draft not counted'),
  risks=['packet175b D1: a same-byte scale-path change in the same lane measured dense B/A 1.0665 (-6.65%); extra per-step lane work is not free',
         'packet74: packed Q6 dense lost -0.8/-2.4/-2.9% because a per-weight 6-bit unpack cost more than its bytes; S1 adds no unpack, one integer half conversion + one multiply per 8 weights',
         'packet175 D2: L2-warm dense GEMVs were only 15%/5.5% faster (L0/L3), so these kernels are not purely DRAM-bound'],
  provenance=[prov(S2+'packet110-class-roofline/roofline.json'),prov(S2+'packet177-twocard-structural/options.json'),prov(S2+'packet175b-twocard-d1-micro/DO-NOT-REPEAT.md')],
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'price_s1.py',P/'evidence/full-shape.json')}))
 print(f"expected gain: floor {floor['gain_percent']:.2f}% ({floor['projected_tok_s']:.2f} tok/s), proportional {prop['gain_percent']:.2f}% ({prop['projected_tok_s']:.2f}); +2% needs {100*hi:.0f}% of the floor saving")
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));main()
