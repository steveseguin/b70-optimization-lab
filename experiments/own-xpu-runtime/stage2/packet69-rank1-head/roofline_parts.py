"""Existing draft per-site times and tensor-byte floors, CPU metadata only."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,statistics as st
P=Path(__file__).resolve().parent
BASE=P.parent/'screen/v3-attr/evidence/packet64-attribution-B-a/run/attribution'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    groups=defaultdict(float);positions=defaultdict(list);sources={}
    for f in sorted(BASE.glob('*/rank1/sites.jsonl')):
        sources[str(f)]=sha(f)
        for line in f.read_text().splitlines():
            e=json.loads(line)
            if e.get('schema')!='packet57.event.v1' or not e['label'].startswith('draft.'):continue
            groups[(f.parent.parent.name,e['position'],e['label'])]+=e['device_ms']*1000
    measured=defaultdict(list)
    for (_,pos,label),v in groups.items():measured[label].append(v);positions[label].append(pos)
    tensors={}
    for line in (P/'mtp-manifest.tsv').read_text().splitlines():
        fields=line.split();tensors[fields[0]]=dict(stored_bytes=int(fields[3]),type=fields[4],rows=int(fields[5]),columns=int(fields[6]),sha256=fields[7])
    mapping={}
    for short,weight in [('qgate','q_proj'),('k','k_proj'),('v','v_proj')]:mapping['draft.blk.0.qsa.'+short]='mtp.layers.0.self_attn.'+weight+'.weight'
    mapping['draft.blk.0.attention']='mtp.layers.0.self_attn.o_proj.weight'
    for label,scope in [('blk.0.hc.a','mtp.layers.0.attn_hyper_connection'),('blk.0.hc.f','mtp.layers.0.mlp_hyper_connection'),('final','mtp.hyper_connection_mixer')]:
        for suffix,weight in [('low','input_mix_weight_down'),('gate','input_mix_weight_up')]:mapping['draft.'+label+'.'+suffix]=scope+'.'+weight+'.weight'
        if label!='final':mapping['draft.'+label+'.inject']=scope+'.block_inject_weight.weight'
    for label,weight in [('merge.projected','fc_hidden'),('merge.embedding_projected','fc_embedding')]:mapping['draft.'+label]='mtp.'+weight+'.weight'
    result=[]
    for label,values in sorted(measured.items()):
        time=st.mean(values);n=None;basis='not assigned: fused/elementwise/control site without a complete byte model'
        tensor=None
        if label in mapping:
            tensor=dict(name=mapping[label],**tensors[mapping[label]])
            assert tensor['type']=='BF16';n=tensor['stored_bytes'];basis='one unique BF16 weight tensor read; activation traffic excluded; repeated row/batch reads may hit cache'
        elif label=='draft.logits':n=91392*3200;basis='resident expanded Q6_K prefix: int8 plus F32 scale/16 (packed GGUF is 191923200 bytes)'
        elif label=='draft.argmax':n=91392*2;basis='BF16 prefix logits read once; reduction workspace traffic excluded'
        elif label=='draft.blk.0.qsa.attention':
            assert max(positions[label])<2048
            n=st.mean((pos+1)*2*256*2*2 + 3*24*256*2 for pos in positions[label]);basis='unique BF16 K/V cache plus Q/gate/output lower bound; all sampled contexts below selection budget; excludes score/probability scratch and repeated per-head reads'
        elif label=='draft.transfer.hidden':n=4*2560*2;basis='same-card BF16 hidden copy payload; not a host PCIe bandwidth measurement'
        elif label in ('draft.transfer.proposal','draft.transfer.status'):n=4;basis='int32 readback payload; zero-duration timestamps cannot yield bandwidth'
        row=dict(label=label,count=len(values),measured_mean_us=time,tensor=tensor,logical_bytes=n,basis=basis,
                 logical_GB_s=n/time/1000 if n is not None and time>0 else None,
                 floor_us_at_540=n/540000 if n is not None else None,floor_us_at_590=n/590000 if n is not None else None)
        result.append(row)
    packet=dict(passed=True,device_executed=False,measured_here=False,sources=sources,manifest_sha256=sha(P/'mtp-manifest.tsv'),
                bandwidth_reference_GB_s=[540,590],sites=result,
                caveat='Logical operand floors, not measured DRAM traffic. Small reductions and attention are not necessarily bandwidth limited. Missing target sites remain pending the attribution screen.')
    (P/'evidence/draft-site-roofline.json').write_text(json.dumps(packet,indent=2)+'\n')
    lines=['# Packet69 draft site roofline','','Existing packet64 raw device means; no new device run. GB/s uses the stated logical byte model, not hardware traffic counters.','','| Site | µs | Logical bytes | GB/s | 590–540 GB/s floor (µs) |','| --- | ---: | ---: | ---: | ---: |']
    for r in result:
        if r['logical_bytes'] is None:continue
        rate=f"{r['logical_GB_s']:.2f}" if r['logical_GB_s'] is not None else 'unresolved timer'
        lines.append(f"| {r['label']} | {r['measured_mean_us']:.3f} | {r['logical_bytes']:.0f} | {rate} | {r['floor_us_at_590']:.2f}–{r['floor_us_at_540']:.2f} |")
    lines+=['','The full JSON retains the byte definition and official draft tensor identity for each site. Matrix rows count a single weight read; attention counts unique BF16 operands only. These are lower-bound byte models. No bandwidth is invented for zero-time copies, host waits, or target sites absent from packet64.','', 'Target head: 794,624,000 expanded resident bytes, 1,346.82–1,471.53 µs bandwidth floor; measured time pending. Final HC/norm, target argmax and outside transfers are named in the new measurement report; host submission/waits remain a separately reported residual.']
    (P/'ROOFLINE.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__':main()
