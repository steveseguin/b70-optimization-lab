"""Source-derived useful global-byte floors, no historical timings.

Formula lineage: packet67/audit.py, re-audited against packet107/current and
packet110 copied production. Counts are unique useful arrays/weight fields;
cache overfetch, repeated issued loads and resident lookup tables are excluded.
"""
import math
from pathlib import Path
P=Path(__file__).resolve().parent
DIRECTORY=P.parent/'packet34-replay-bench/directory.tsv'
tensors={}
for line in DIRECTORY.read_text().splitlines():
    name,kind,shape,size,*rest=line.split()
    tensors[name]=dict(type=kind,dimensions=list(map(int,shape.split(','))),bytes=int(size))
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
    elif site in ('gdn.a','small.gdn.ab'):names=[pre+'ssm_alpha.weight',pre+'ssm_beta.weight'];ar=5120;aw=192;note='alpha/beta tuple'
    elif site=='gdn.conv':names=[pre+'ssm_conv1d.weight'];ar=20480+61440;aw=20480+61440
    elif site=='gdn.recurrence':names=[pre+'ssm_a',pre+'ssm_dt.bias'];ar=20480+192+1572864;aw=12288+1572864;note='BF16 state read/write; head normalization repeated per four rows; no FP32 state carry'
    elif site=='gdn.gated':names=[pre+'ssm_norm.weight'];ar=24576;aw=12288
    elif site=='small.ffn.q6':
        names=[pre+n for n in ('ffn_gate_inp.weight','ffn_gate_shexp.weight','ffn_up_shexp.weight','ffn_gate_inp_shexp.weight')]
        ar=5120;aw=(512+640+640+1)*2;note='four-member tuple: router + shared gate/up + shared router'
    elif site=='expsgate':names=[pre+'ffn_gate_exps.weight',pre+'ffn_up_exps.weight'];fraction=10/512;ar=5120+120;aw=2*640*10*2+80;note='p90 half-cache IQ2: 840 useful bytes/row, ten experts, both gate/up, status'
    elif site=='expsdown':names=[pre+'ffn_down_exps.weight'];fraction=10/512;ar=640*10*2+120;aw=2560*10*2+40;note='p49d IQ4 planar bank: 360 bytes per K640 row; ten experts; output/status'
    elif site=='expsact':ar=640*10*4;aw=640*10*2
    elif site=='shexpact':ar=640*4;aw=640*2
    elif site=='route':ar=4392;aw=2664;note='p78 route-fast single event; input twice, global max/sum/exp scratch and route/probability outputs; local sort scratch excluded'
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
    if site=='expsgate':
        assert all(t['type']=='IQ2_S' for t in ts)
        wr=2*10*640*(2560//4+2560//32+2560//32+4*(2560//256))
    # Small controls logically once per call; cache/issue duplication deliberately not HBM traffic.
    return dict(gguf_weight_bytes=packed,runtime_weight_read_bytes=wr,activation_state_read_bytes=ar,
                read_bytes=wr+ar,write_bytes=aw,tensors=ts,notes=note)
