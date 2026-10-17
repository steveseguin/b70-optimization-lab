#!/usr/bin/env python3
"""Header-only, CPU roofline accounting; never open a tensor payload or device."""
import collections
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import statistics

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
BASE = P.parent / 'packet70-record-bundle'
RAW = P.parent / 'screen/v3-attr/evidence/packet64-attribution-B-a/run'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    spec=importlib.util.spec_from_file_location('headers',P.parents[1]/'stage1/packet1b/loaders/headers.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    model=Path(json.loads((BASE/'build/input/input.json').read_text())['model_dir'])
    tensors={};headers=[]
    census={t['name']:t for t in json.loads((ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json').read_text())['tensors']}
    for path in sorted(model.glob('*.gguf')):
        with path.open('rb') as f:
            h=mod.gguf_header(f,path.stat().st_size);f.seek(0);digest=hashlib.sha256(f.read(h['header_bytes_read'])).hexdigest()
        headers.append(dict(path=str(path),bytes=path.stat().st_size,header_bytes=h['header_bytes_read'],header_sha256=digest))
        for name,t in h['tensors'].items():
            assert all(t[k]==census[name][k] for k in ('type','dimensions','bytes'))
            tensors[name]=t
    assert set(tensors)==set(census)
    save(P/'header-census.json',dict(schema='packet72.header-census.v1',headers=headers,payload_bytes_read=0,tensors=tensors))
    calls=collections.defaultdict(list);rawpins={}
    for path in sorted((RAW/'attribution').glob('*/rank*/sites.jsonl')):
        rawpins[str(path.relative_to(ROOT))]=sha(path)
        for line in path.open():
            r=json.loads(line)
            if r['speculative']:continue
            calls[(path.parent.parent.name,r['rank'],r['fixture'],r['label'])].append(r)
    bysite=collections.defaultdict(list)
    for (prompt,rank,fixture,label),events in calls.items():
        if label.startswith('blk.') and int(label.split('.')[1]) in (22,23,24,27):
            bysite[rank,label].append(dict(us=sum((r['end_ns']-r['start_ns'])/1000 for r in events),
                events=len(events),position=events[0]['position']))
    def weights(names,active=1):
        selected=[tensors[n] for n in names]
        packed=sum(t['bytes']*active for t in selected)
        read=0
        for t in selected:
            n=math.prod(t['dimensions'])*active
            read+=n*(1+4/16 if t['type']=='Q6_K' else 1+4/32 if t['type']=='Q8_0' else 0) if t['type'] in ('Q6_K','Q8_0') else t['bytes']*active
        return int(packed),int(read),[dict(name=n,type=tensors[n]['type'],dimensions=tensors[n]['dimensions']) for n in names]
    def account(layer,site,pos):
        pre=f'blk.{layer}.';names=[];fraction=1;ar=aw=0;note='';n=pos+1
        direct={'gdn.qkv':'attn_qkv.weight','gdn.z':'attn_gate.weight','qsa.qgate':'attn_q.weight',
          'qsa.k':'attn_k.weight','qsa.v':'attn_v.weight','qsa.iq':'indexer.q_proj.weight','qsa.ik':'indexer.k_proj.weight',
          'shexpdown':'ffn_down_shexp.weight','attention':'ssm_out.weight' if layer%4!=3 else 'attn_output.weight'}
        if site in direct:
            names=[pre+direct[site]];t=tensors[names[0]];k,rows=t['dimensions'];ar=k*2;aw=rows*2
            if site=='attention':
                # Split4 FP32 scratch written then read by final BF16+combine stage.
                ar+=rows*4*4+rows*4*2+8;aw+=rows*4*4+rows*4*2
                note='two kernels: GEMV partials + BF16 output/stream combine'
            if site=='qsa.ik':ar+=rows*16;aw+=rows*16;note='two kernels; Split4 scratch retained'
        elif site.startswith('hc.'):
            side='attn' if site.split('.')[1]=='a' else 'ffn';kind=site.split('.')[2];p=pre+'hc_'+side+'_'
            if kind=='norm':names=[p+'norm.weight'];ar=20480;aw=20480+1280;note='unique streams once; production reduction rereads streams per ten output tiles'
            if kind=='low':names=[p+'down.weight',p+'inject.weight'];ar=20480;aw=640+640+8+64;note='fused low + activation + inject; preserved inject split scratch'
            if kind=='gate':names=[p+'up.weight'];ar=640+20480;aw=20480+5120;note='fused gate + four-stream mix; no separate mix event'
        elif site=='gdn.a':names=[pre+'ssm_alpha.weight',pre+'ssm_beta.weight'];ar=5120;aw=192;note='alpha/beta tuple'
        elif site=='gdn.conv':names=[pre+'ssm_conv1d.weight'];ar=20480+61440;aw=20480+61440
        elif site=='gdn.recurrence':names=[pre+'ssm_a',pre+'ssm_dt.bias'];ar=20480+192+1572864;aw=12288+1572864;note='BF16 state read/write; head normalization repeated per four rows; no FP32 state carry'
        elif site=='gdn.gated':names=[pre+'ssm_norm.weight'];ar=24576;aw=12288
        elif site=='router':
            names=[pre+n for n in ('ffn_gate_inp.weight','ffn_gate_shexp.weight','ffn_up_shexp.weight','ffn_gate_inp_shexp.weight')]
            ar=5120;aw=(512+640+640+1)*2;note='four-member tuple: router + shared gate/up + shared router'
        elif site=='expsgate':names=[pre+'ffn_gate_exps.weight',pre+'ffn_up_exps.weight'];fraction=10/512;ar=5120+120;aw=2*640*10*2+80;note='packet65-owned; ten selected experts, paired gate/up + status'
        elif site=='expsdown':names=[pre+'ffn_down_exps.weight'];fraction=10/512;ar=640*10*2+120;aw=2560*10*2+40;note='packet65-owned; ten selected experts'
        elif site=='expsact':ar=640*10*4;aw=640*10*2
        elif site=='shexpact':ar=640*4;aw=640*2
        elif site=='route':ar=4392;aw=2664;note='four stages; input twice, max/sum/exp scratch, final probability read/write and route copies'
        elif site=='moe':ar=2560*10*2+10*4+5120+4+2+5120;aw=5120*2;note='two kernels: ordered mixture + shared branch combination'
        elif site=='ffn.combine':ar=20480+5120+8;aw=20480
        elif site=='qsa.prepare':names=[pre+x for x in ('attn_q_norm.weight','attn_k_norm.weight','indexer.q_norm.weight')];ar=(12288+512+512)*2+128;aw=(6144*2+512+512)*2;note='includes 32 cos + 32 sin BF16 RoPE row'
        elif site=='qsa.pool':names=[pre+'indexer.k_norm.weight'] if n%4==0 else [];ar=2304+(768+128 if n%4==0 else 0);aw=2304+(256 if n%4==0 else 0);note='historical raw rows, norm and RoPE read only on every fourth token'
        elif site=='qsa.select':ar=512*2+(n//4)*128*2+(n//4)*4;aw=(2048+3)*4+(n//4)*4;note='context-dependent index scores and selected-id scratch; padded ids extent'
        elif site=='qsa.attention':
            m=4*min(n//4,512)+n%4;partial=24*((m+31)//32)*258*4
            ar=6144*4+m*2048+4*(m+1)+partial+4;aw=6144*2+partial+4
            note='three kernels; packet49 split32 partial scratch and count written/read; full16 KV; N=position+1'
        else:raise ValueError('unaccounted '+site)
        packed,wr,ts=weights(names,fraction) if names else (0,0,[])
        # Small controls logically once per call; cache/issue duplication deliberately not HBM traffic.
        return dict(gguf_weight_bytes=packed,runtime_weight_read_bytes=wr,activation_state_read_bytes=ar,
                    read_bytes=wr+ar,write_bytes=aw,tensors=ts,notes=note)
    rows=[]
    for (rank,label),samples in sorted(bysite.items()):
        layer=int(label.split('.')[1]);site='.'.join(label.split('.')[2:]);kind='QSA' if layer%4==3 else 'GDN';occ=6 if kind=='QSA' else 18
        counts=[account(layer,site,s['position']) for s in samples];b=counts[0]
        for field in ('read_bytes','write_bytes','activation_state_read_bytes','runtime_weight_read_bytes','gguf_weight_bytes'):b[field]=statistics.median(c[field] for c in counts)
        us=statistics.median(s['us'] for s in samples);total=b['read_bytes'];floor=total/555000
        rows.append(dict(rank=rank,layer=layer,kind=kind,site=site,calls=len(samples),events_per_call=sorted(set(s['events'] for s in samples)),
           positions=[min(s['position'] for s in samples),max(s['position'] for s in samples)],measured_call_median_us=us,
           occurrences_per_half=occ,roofline_us=floor,effective_GBs=total/us/1000,
           excess_us=us-floor,excess_us_per_half=(us-floor)*occ,**b))
    # Keep type rows, and rank common sites by 18*GDN + 6*QSA once (no double counting).
    top=[]
    for rank in (0,1):
        for site in sorted({r['site'] for r in rows}):
            members=[r for r in rows if r['rank']==rank and r['site']==site]
            top.append(dict(rank=rank,site=site,excess_us_per_half=sum(r['excess_us_per_half'] for r in members),
                 measured_us_per_half=sum(r['measured_call_median_us']*r['occurrences_per_half'] for r in members)))
    top.sort(key=lambda r:(r['rank'],-r['excess_us_per_half']))
    # Inventory every actual layer too: layer0 is not the sampled layer22.
    # Do not manufacture per-layer timings for its different tensor formats.
    inventory=[]
    for layer in range(48):
        rank=layer//24;kind='QSA' if layer%4==3 else 'GDN'
        for sample in (r for r in rows if r['rank']==rank and r['kind']==kind):
            pos=int(statistics.median(sample['positions']));v=account(layer,sample['site'],pos)
            inventory.append(dict(rank=rank,layer=layer,site=sample['site'],position_for_context_bytes=pos,
                measured_call_median_us=sample['measured_call_median_us'] if layer==sample['layer'] else None,**v))
    save(P/'all-layer-bytes.json',dict(schema='packet72.all-layer-bytes.v1',rows=inventory,
        scope='all48 actual GGUF tensor types; unsampled layer times are null; context-dependent bytes use representative sampled position, no unmeasured speed points'))
    outside=[]
    def out(rank,site,names,ar,aw,note,host=False):
        packed,wr,ts=weights(names) if names else (0,0,[])
        outside.append(dict(rank=rank,site=site,gguf_weight_bytes=packed,runtime_weight_read_bytes=wr,
          read_bytes=wr+ar,write_bytes=aw,tensors=ts,measured_call_median_us=None,effective_GBs=None,excess_us_per_half=None,
          roofline_us=None if host else (wr+ar+aw)/540000,notes=note))
    out(0,'embedding lookup',[],2100,5120,'one Q6_K packed row on CPU; not HBM; BF16 output uploaded',True)
    out(0,'streams broadcast',[],5120,20480,'one per rank0 half')
    out(0,'speculative capture',[],48627432,48627432,'per capture from speculative-snapshot telemetry; excludes corrected-only execution')
    out(0,'corrected redo restore',[],19025640,19025640,'per miss redo; not every half; accepted speculative result needs no restore')
    out(0,'PLE lookup',[],1440,5120,'16 IQ4_NL packed rows on CPU; not HBM; singleton blk.1 work omitted by sampled layers',True)
    out(0,'PLE key', ['blk.1.ple_key.weight'],5120,20480,'singleton blk.1; timing absent')
    out(0,'PLE value', ['blk.1.ple_value.weight'],5120,5120,'singleton blk.1; timing absent')
    out(0,'PLE three norms', ['blk.1.ple_norm_'+x+'.weight' for x in ('key','query','conv')],3*(20480+1280),3*(20480+1280),'three two-stage norms')
    out(0,'PLE convolution', ['blk.1.ple_conv1d.weight'],20480+184320,20480+184320,'nine BF16 history rows; four taps, dilation three')
    out(0,'PLE gate and add',[],20480*5+5120,20480*2,'gate reads key/query/value; add reads streams/gated/conv')
    out(0,'PLE hash/history',[],4+16+280,128+16,'CPU token/history/metadata; not HBM',True)
    out(1,'final norm',['output_hc_norm.weight'],20480+1280,20480+1280,'two-stage original final HC norm')
    out(1,'final low + activation',['output_hc_down.weight'],20480,640+640,'local Split4 partials; fused activation retains BF16 boundary')
    out(1,'final gate',['output_hc_up.weight'],640,20480,'final HC is not target-layer p60 fusion')
    out(1,'final mix',[],40960,5120,'four-stream ordered mix')
    out(1,'target logits',['output.weight'],5120,496640,'full 248320 rows; draft-only prefix never applies here')
    out(1,'target argmax',[],496640+1944+486,1944+4,'243 chunks; scratch+selected BF16 candidate logits reread by final stage')
    out(1,'rank handoff',[],20480+4,20480+4,'PCIe/host stream+token handoff, not same-card 540 GB/s',True)
    report=json.loads((RAW/'attribution-summary.json').read_text())
    result=dict(schema='packet72.roofline.v1',roofline_GBs=555,device_executed=False,raw_event_files=rawpins,
       byte_definition='useful global bytes, each distinct weight/input once per kernel; intermediate traffic explicitly included; not measured DRAM or instruction-issued bytes',
       caveats=['sampled layers only; occurrence scaling is an analytical estimate, never an unmeasured performance point',
         'sum all events of a site call before median; event medians mixing stages are invalid call latency',
         'controls, codebook residency, cache line overfetch/reloads and PCIe/host overhead not measured; 540 is memory-only not an attainable compute floor'],rows=rows,ranking=top,
       outside_layer_work=outside,measured_outside_remainders=report['outside_layers'],draft_breakdown=report['draft_breakdown'])
    lines=['# Packet72 in-engine bandwidth audit', '',
      'Measured packet64 lane-B site times, recomputed from the raw events. No GPU or model run. Read numerator uses the real runtime representation of every tensor, plus distinct activation/state and inter-kernel scratch reads. Writes are retained separately in JSON and excluded from this read-bandwidth denominator.', '',
      '**This is effective read bandwidth in the engine, not a hardware DRAM counter.** sites.jsonl contains timestamps, not memory transactions. Actual cache misses, repeated loads served by cache, line overfetch and physical DRAM bytes cannot be recovered on CPU. The distinction matters: counting every source-level activation load against a DRAM ceiling would yield impossible rates above that ceiling. No claim of measured physical DRAM traffic is made.', '',
      'The independently regrouped timing sums all events per (prompt, rank, fixture, label), then takes the call median. Only corrected/target, non-speculative calls are included. Rank0 samples are miss-conditioned. The trace samples layers22/23 and24/27, not all48 layers. The all-layer inventory preserves actual tensor types and leaves unsampled times null. Occurrence-weighted half costs are estimates from those samples, not directly measured half totals.', '',
      '555 GB/s is the requested reference, not a proven achievable floor for these compute-heavy sites. Headroom = occurrences * (call_us - read_bytes / 555000). Qualify only >=300 us in at least one half, retaining both ranks separately. No averaging ranks to manufacture qualification.', '',
      'Q6_K is expanded to signed8 codes plus one F32 scale per16 elements; Q8_0 uses one per32. For example QKV reads32.768 MB of runtime weights, not21.504 MB of packed GGUF. Most dense projections are already around500 GB/s. Source layout: packet70 p49b_gemv.hpp, p49c_kernel.hpp and p60_kernels.hpp. Byte formulas are retained from and reviewed against packet67 audit.py, with read-only denominator corrected here; they are minimum distinct reads, not issued-load counts.', '',
      '| Rank | Site | Read GB/s (weighted) | Reference % | ms/half | Headroom ms/half | Qualifies |',
      '| ---: | --- | ---: | ---: | ---: | ---: | --- |']
    for r in top:
        members=[v for v in rows if v['rank']==r['rank'] and v['site']==r['site']]
        rate=sum(v['read_bytes']*v['occurrences_per_half'] for v in members)/r['measured_us_per_half']/1000
        r.update(effective_read_GBs=rate,reference_fraction=rate/555,qualifies=r['excess_us_per_half']>=300)
        lines.append(f"| {r['rank']} | {r['site']} | {rate:.2f} | {100*rate/555:.1f} | {r['measured_us_per_half']/1000:.4f} | {r['excess_us_per_half']/1000:.4f} | {'yes' if r['qualifies'] else 'no'} |")
    lines += ['', '## Every measured layer site', '', '| Rank/layer | Site | Runtime weight read B | Other read B | Writes B | Call us | Read GB/s |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for r in rows:
        lines.append(f"| {r['rank']}/{r['layer']} | {r['site']} | {r['runtime_weight_read_bytes']:,.0f} | {r['activation_state_read_bytes']:,.0f} | {r['write_bytes']:,.0f} | {r['measured_call_median_us']:.3f} | {r['effective_GBs']:.2f} |")
    lines += ['', '## Selection', '',
      'QKV, Z and Q-gate fail the0.3 ms threshold and get no candidate. Attention output qualifies on rank1 only, narrowly, when the GDN and QSA occurrences of the same output kernel are combined. Its two event stages must be summed: the roughly23 us mixed-event median is not a call time. The proposed class is all attention outputs, with a shared Q6_K6144 Split4 arithmetic body; neither subtype alone qualifies.', '',
      'HC gates, recurrence and route numerically qualify. Packet67 already tested the HC/recurrence geometry changes and lost on every arm; this table supplies no new device counter evidence to reopen those mechanisms. Route has no raw packed code/scale loop to which wide64 applies. Experts are already wide64 in packet70; packet64 expert times are historical, not packet70 times. Those classes get no speculative replacement here.', '',
      'Only attention-output raw-code/scale sharing proceeds. It retains the original Split4 scratch and final stream-combine kernel. The combined view equals this sole qualifying new mechanism; the production control is packet70 including wide64 experts, batch rollback and draft-HC.', '',
      'Outside-layer time cannot be assigned bandwidth from these events: target head/final norm/argmax lack separate site timings here. Packet69 owns that attribution. All unsampled times and actual DRAM bandwidth stay null.', '',
      '[JSON with event hashes and formulas](BANDWIDTH.json), [all-layer tensor inventory](all-layer-bytes.json), [header pins](header-census.json), [CPU reproducer](bandwidth.py).']
    result['ranking']=top
    result['schema']='packet72.bandwidth.v1'
    result['actual_dram_bytes']=None
    result['actual_dram_GBs']=None
    result['caveats']=[x.replace('540','555') for x in result['caveats']]
    save(P/'BANDWIDTH.json',result)
    (P/'BANDWIDTH.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps([r for r in top if r['site'] in ('gdn.qkv','gdn.z','qsa.qgate','attention')],indent=2))
if __name__=='__main__':main()
