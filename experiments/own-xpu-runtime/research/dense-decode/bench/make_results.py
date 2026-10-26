import json,statistics
from pathlib import Path
LAB=Path('/dev/shm/ownrt-lab-dense');OUT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/dense-decode')
def prof(t):
    rows=[json.loads(l) for l in open(LAB/t/'rank1'/'decode-device-profile.jsonl')];rows=[r for r in rows if not r['speculative']]
    return {k:(statistics.median([r['sites'][k]['busy_us'] for r in rows if k in r['sites']]),rows[0]['sites'][k]['count']) for k in rows[0]['sites']},statistics.median([r['span_us'] for r in rows])
a,sa=prof('refP-prof-p4096');b,sb=prof('c3P-prof-on-p4096')
MB=1e6
# weight bytes read per call (expanded = p33 storage: int8 codes + F32 scale per 16 (Q6_K) / 32 (Q8_0) columns)
sizes={'gemv:Q6_K:logits':(248320*2560*1.25,'p33.dense.segment','2560->248320 Q6_K (expanded; raw 521.5 MB)'),
 'gemv:Q8_0:attention':(2560*6144*1.125,'p33.dense.segment','6144->2560 Q8_0 (expanded; raw 16.71 MB)'),
 'gemv:Q6_K:gdn.qkv':(10240*2560*1.25,'p33.dense.segment','2560->10240 Q6_K (expanded; raw 21.50 MB)'),
 'gemv:Q6_K:gdn.z':(6144*2560*1.25,'p33.dense.segment','2560->6144 Q6_K (expanded; raw 12.90 MB)'),
 'gemv:Q6_K:qsa.qgate':(12288*2560*1.25,'p33.dense.segment','2560->12288 Q6_K (expanded; raw 25.80 MB)'),
 'gemv:BF16:hc.a.low':(320*10240*2,'kopt Multiply (fused with hc.a.inject)','10240->320 (+4) BF16'),'gemv:BF16:hc.f.low':(320*10240*2,'kopt Multiply (fused with hc.f.inject)','10240->320 (+4) BF16'),
 'gemv:BF16:hc.a.gate':(10240*320*2,'kopt Multiply','320->10240 BF16'),'gemv:BF16:hc.f.gate':(10240*320*2,'kopt Multiply','320->10240 BF16'),
 'gemv:BF16:final.gate':(10240*320*2,'kopt Multiply','320->10240 BF16'),'gemv:BF16:final.low':(320*10240*2,'kopt Multiply','10240->320 BF16'),
 'gemv:BF16:router':(512*2560*2,'kopt Multiply?','2560->512 BF16'),'gemv:BF16:qsa.iq':(512*2560*2,'kopt Multiply','2560->512 BF16'),'gemv:BF16:gdn.a':(96*2560*2,'kopt Multiply','2560->48x2 BF16'),
 'gemv:Q5_K:gdn.qkv':(10240*2560*0.6875,'denseblock','2560->10240 Q5_K'),'gemv:IQ4_XS:gdn.qkv':(10240*2560*0.53125,'denseblock','2560->10240 IQ4_XS'),'gemv:Q4_K:gdn.qkv':(10240*2560*0.5625,'denseblock','2560->10240 Q4_K'),
 'gemv:Q4_K:gdn.z':(6144*2560*0.5625,'denseblock','2560->6144 Q4_K'),'gemv:Q5_K:gdn.z':(6144*2560*0.6875,'denseblock','2560->6144 Q5_K'),'gemv:IQ4_XS:gdn.z':(6144*2560*0.53125,'denseblock','2560->6144 IQ4_XS'),
 'gemv:Q5_K:qsa.qgate':(12288*2560*0.6875,'gsqn/denseblock','2560->12288 Q5_K'),
 'gemv:Q8_0:shexpdown':(2560*640*1.0625,'kopt Multiply (staged)','640->2560 Q8_0'),
 'gemv:Q6_K:shexpup':(640*2560*0.8203125,'kopt Multiply (staged)','2560->640 Q6_K'),'gemv:Q6_K:shexpgate':(640*2560*0.8203125,'kopt Multiply (staged)','2560->640 Q6_K'),
 'gemv:Q4_K:shexpgate':(640*2560*0.5625,'denseblock','2560->640 Q4_K'),'gemv:Q4_K:shexpup':(640*2560*0.5625,'denseblock','2560->640 Q4_K'),
 'gemv:IQ4_XS:shexpgate':(640*2560*0.53125,'denseblock','2560->640 IQ4_XS'),'gemv:IQ4_XS:shexpup':(640*2560*0.53125,'denseblock','2560->640 IQ4_XS'),
 'gemv:Q5_K:shexpgate':(640*2560*0.6875,'denseblock','2560->640 Q5_K'),'gemv:Q5_K:shexpup':(640*2560*0.6875,'denseblock','2560->640 Q5_K'),
 'gemv:Q6_K:qsa.k':(512*2560*0.8203125,'kopt Multiply (staged)','2560->512 Q6_K'),'gemv:Q6_K:qsa.v':(512*2560*0.8203125,'kopt Multiply (staged)','2560->512 Q6_K')}
BW=600e3 # bytes per us (measured stream read on random data: 602 GB/s)
table=[]
for k,(v,c) in sorted(a.items(),key=lambda kv:-kv[1][0]):
    if not k.startswith('gemv'):continue
    by,kern,shape=sizes.get(k,(None,'?','?'))
    after=b.get(k,(None,c))[0]
    floor=by/BW if by else None
    table.append(dict(site=k,kernel=kern,shape=shape,count=c,weight_mb=round(by/MB,2) if by else None,floor_us=round(floor,1) if floor else None,
      before_us=round(v/c,2),after_us=round(after/c,2) if after is not None else None,before_pct=round(100*floor/(v/c)) if floor else None,
      after_pct=round(100*floor/(after/c)) if floor and after else None,per_half_before_us=round(v,1),per_half_after_us=round(after,1) if after is not None else None))
def run(t):
    r=json.load(open(LAB/t/'lab-result.json'));s=json.load(open(LAB/t/'summary.json'))
    return dict(tag=t,binary=r['binary'],env=r['env'],median_half_ms=round(statistics.median(s['half_ms']),4),rc=r['rc'],dri=r['dri'],fault_lines=len(r['faults']),tokens_equal_ref=s['tokens']==json.load(open(LAB/'ref-p4096'/'summary.json'))['tokens'])
runs=[run(t) for t in ('ref-p4096','c1-on-p4096','c2-on-p4096','c3-on-p4096')]
cmps={t:json.load(open(LAB/f'cmp-{t}.json')) for t in ('c1-on-p4096','c2-on-p4096','c3-on-p4096')}
builds={}
for t,d in (('ref','engine-build-lab-dense-ref'),('c3','engine-build-lab-dense-c3'),('c3P','engine-build-lab-dense-c3P'),('refP','engine-build-lab-dense-refP')):
    rr=json.load(open(Path('/dev/shm')/d/'build-receipt.json'));builds[t]=dict(binary_sha256=rr['binary_sha256'],binary=rr['binary'])
res=dict(schema='ownrt.lab.dense-decode.v1',date='2026-10-26',card='0000:27:00.0',roofline_GBps=600,roofline_note='stream read of 512 MB random data on card 27: 602 GB/s',
 switch={'OWNRT_DENSE_DECODE_V2':'1: kopt BF16 rows (dense_v2.hpp), packed-block Q4_K/Q5_K/IQ4_XS rows (dense_decode_v2.hpp, denseblock + gsqn decode), p33 Q8_0 6144-column rows (p33_dense_v2.hpp)'},
 service_env='OWNRT_ATTN_HEADS=1 OWNRT_ATTN_COMBINE2=1 OWNRT_PREFILL_REUSE2=1 OWNRT_SELECT_TOPK=1 OWNRT_SELECT_FAST=1 OWNRT_RESET_DEVICE_ZERO=1 (all runs)',
 builds=builds,runs=runs,compares=cmps,profile_span_us=dict(ref=sa,c3=sb),roofline_table=table,
 incident=dict(time='2026-10-26 08:50:29',card='0000:27:00.0',lines=['Fault response: Unsuccessful -ENOENT (ASID 3358, address 0x0000d556aa2a0000, bcs, FaultLevel 4)','Engine reset: engine_class=bcs, guc_id=6'],
  context='my microbenchmark bench_quant aborted twice with UR_RESULT_ERROR_OUT_OF_RESOURCES (a bench-only variant requested 209 KB of local memory) and exited abruptly; the second abort coincided with the fault lines, in the same second the decode-experts agent engine (pid 294276) started. sc117-lan halted itself at 08:50:33. No engine run of mine was active. All device work stopped, nothing retried, no recovery action taken.'))
(OUT/'results.json').write_text(json.dumps(res,indent=1)+'\n')
print('span',sa,sb)
for r in table: print('%-24s %-30s %4d  %7s MB floor %6s  %7.2f -> %7s  (%s%% -> %s%%)'%(r['site'],r['kernel'][:30],r['count'],r['weight_mb'],r['floor_us'],r['before_us'],r['after_us'],r['before_pct'],r['after_pct']))
