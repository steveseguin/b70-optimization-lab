#!/usr/bin/env python3
"""Offline tensor census and exact stored-byte arithmetic; no model execution."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
PARSER = LANE / 'stage1/packet1b/loaders/headers.py'
spec = importlib.util.spec_from_file_location('headers', PARSER)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
CAPACITY = 68_484_595_712
KV = 753_139_712


def sha(b):
    return hashlib.sha256(b).hexdigest()


def mapping():
    """Explicit architecture map: same disjoint owners as packet 1."""
    d = {}
    def add(n, shape, comp, official, layer=None, replica=False):
        assert n not in d
        d[n] = dict(shape=shape, component=comp, official_correspondence=official,
                    layer=layer, hc_projection_replicated=replica)
    add('token_embd.weight',[248320,2560],'embedding','model.language_model.embed_tokens.weight')
    add('output.weight',[248320,2560],'target_head','lm_head.weight')
    add('per_layer_token_embd.weight',[320001536,160],'ple_lookup',
        'model.language_model.layers.1.ple.ple_embedding.ngram_embedding.shard_{0..127}.weight (concatenated)',1)
    for short, long, shape in [('down','input_mix_weight_down',[320,10240]),
                              ('up','input_mix_weight_up',[10240,320]),('norm','hc_norm',[10240])]:
        add(f'output_hc_{short}.weight',shape,'norms' if short=='norm' else 'hyperconnections',
            f'model.language_model.hyper_connection_mixer.{long}.weight',replica=short!='norm')
    for l in range(48):
        p=f'blk.{l}.'; o=f'model.language_model.layers.{l}.'
        def item(n,shape,comp,suffix,replica=False):
            add(p+n,shape,comp,o+suffix,l,replica)
        for proj,shape in [('gate',[640,2560]),('up',[640,2560]),('down',[2560,640])]:
            item(f'ffn_{proj}_exps.weight',[512]+shape,'routed_experts',f'mlp.experts.{{0..511}}.{proj}_proj.weight (stacked; FP8 scales replaced by GGUF blocks)')
            item(f'ffn_{proj}_shexp.weight',shape,'shared_experts',f'mlp.shared_expert.{proj}_proj.weight')
        item('ffn_gate_inp.weight',[512,2560],'routers','mlp.gate.weight')
        item('ffn_gate_inp_shexp.weight',[2560],'routers','mlp.shared_expert_gate.weight (singleton squeezed)')
        for short,long in [('attn','attn_hyper_connection'),('ffn','mlp_hyper_connection')]:
            for part,suffix,shape in [('down','input_mix_weight_down',[320,10240]),('up','input_mix_weight_up',[10240,320]),
                                      ('inject','block_inject_weight',[4,10240]),('norm','hc_norm',[10240])]:
                item(f'hc_{short}_{part}.weight',shape,'norms' if part=='norm' else 'hyperconnections',
                     f'{long}.{suffix}.weight',part in ('down','up'))
        if l%4 != 3:
            for n,shape,suffix in [('attn_gate.weight',[6144,2560],'in_proj_z.weight'),('attn_qkv.weight',[10240,2560],'in_proj_qkv.weight'),
                 ('ssm_a',[48],'A_log'),('ssm_alpha.weight',[48,2560],'in_proj_a.weight'),('ssm_beta.weight',[48,2560],'in_proj_b.weight'),
                 ('ssm_conv1d.weight',[10240,4],'conv1d.weight (singleton squeezed)'),('ssm_dt.bias',[48],'dt_bias'),
                 ('ssm_norm.weight',[128],'norm.weight'),('ssm_out.weight',[2560,6144],'out_proj.weight')]:
                item(n,shape,'norms' if n=='ssm_norm.weight' else 'gdn','linear_attn.'+suffix)
        else:
            for short,long,shape in [('q','q_proj',[12288,2560]),('k','k_proj',[512,2560]),('v','v_proj',[512,2560]),
                                      ('output','o_proj',[2560,6144]),('q_norm','q_norm',[256]),('k_norm','k_norm',[256])]:
                item('attn_'+short+'.weight',shape,'norms' if short.endswith('norm') else 'qsa_attention','self_attn.'+long+'.weight')
            for side,width in [('q',512),('k',128)]:
                item(f'indexer.{side}_proj.weight',[width,2560],'qsa_indexer',f'self_attn.indexer.index_qk_proj.weight ({side} slice)')
                item(f'indexer.{side}_norm.weight',[128],'norms',f'self_attn.indexer.{side}_layernorm.weight')
        if l==1:
            for short,long,shape in [('key','key_proj',[10240,2560]),('value','value_proj',[2560,2560]),
                 ('conv1d','conv1d',[10240,4]),('norm_conv','norm_conv',[10240]),('norm_key','norm_key',[10240]),('norm_query','norm_query',[10240])]:
                item('ple_'+short+'.weight',shape,'ple_projection','ple.'+long+'.weight'+(' (singleton squeezed)' if short=='conv1d' else ''))
    return d


def build():
    receipt = json.loads((HERE/'fetch-receipt.json').read_text())
    hf_raw = gzip.decompress((HERE/'hf-metadata.json.gz').read_bytes())
    hf = json.loads(hf_raw)
    assert sha(hf_raw)==receipt['api']['sha256']
    assert hf['sha']==receipt['revision']
    siblings={s['rfilename']:s for s in hf['siblings']}
    official=json.loads((HERE.parent/'packet1/tensor-contract.json').read_text())
    components=set(official['components'])
    expected=mapping()
    assert len(expected)==1224
    variants={}
    grouped=defaultdict(list)
    for f in receipt['files']:grouped[f['path'].split('/')[0]].append(f)
    assert set(grouped)=={'UD-IQ3_XXS','UD-IQ4_XS','UD-Q3_K_XL'}
    for variant,files in sorted(grouped.items()):
        parsed=[]; tensors=[]; file_records=[]
        for f in files:
            raw=gzip.decompress((HERE/f['header_path']).read_bytes())
            assert sha(raw)==f['header_sha256']
            assert len(raw)==f['header_bytes_fetched']<64_000_000
            sib=siblings[f['path']]
            assert sib['size']==sib['lfs']['size']==f['hf_file_bytes']
            assert sib['lfs']['sha256']==f['hf_lfs_sha256']
            cursor=0
            for r in f['requests']:
                start,end=map(int,r['range'].removeprefix('bytes=').split('-'))
                assert start==cursor and end-start+1==r['bytes_fetched']
                assert r['content_range']==f"bytes {start}-{end}/{f['hf_file_bytes']}"
                assert sha(raw[start:end+1])==r['sha256']
                cursor=end+1
            assert cursor==len(raw)
            p=h.gguf_header(io.BytesIO(raw),f['hf_file_bytes'])
            assert p['header_bytes_read']==len(raw)<=p['data_start']
            parsed.append(p)
            if not p['tensors']:
                meta=p['metadata']
                assert meta['qwen4exp.block_count']==48 and meta['qwen4exp.expert_count']==512 and meta['qwen4exp.expert_used_count']==10
                # PLE hash/offset arrays are metadata, no longer I64 tensors.
                metadata_arrays={}
                for key in ['layer_multipliers','head_offsets','head_vocab_sizes']:
                    name='qwen4exp.ple.'+key
                    pos=raw.index(name.encode())+len(name)
                    kind,subtype,count=struct.unpack_from('<IIQ',raw,pos)
                    assert kind==9 and subtype in (4,5,10,11)
                    metadata_arrays[name]=dict(subtype=subtype,count=count,bytes=count*(8 if subtype in (10,11) else 4),values=meta[name])
            for name,t in p['tensors'].items():
                e=expected[name]
                assert t['shape']==e['shape'], (name,t['shape'],e['shape'])
                assert e['component'] in components
                tensors.append({'name':name,**t,**e,'shard':f['path']})
            end=p['data_start'];pad=p['data_start']-len(raw)
            for t in sorted(p['tensors'].values(),key=lambda x:x['data_offset']):
                assert t['file_offsets'][0]==(end+31)//32*32
                pad+=t['file_offsets'][0]-end;end=t['file_offsets'][1]
            # File extent includes only normal GGUF alignment, no unexplained gaps.
            assert 0<=p['file_bytes']-end<32
            pad+=p['file_bytes']-end
            file_records.append(dict(path=f['path'],file_bytes=p['file_bytes'],header_bytes=len(raw),
                alignment_padding_bytes=pad,tensor_bytes=sum(t['bytes'] for t in p['tensors'].values())))
        assert h.gguf_shards(parsed)==set(expected)
        tensors.sort(key=lambda t:t['name'])
        totals={comp:dict(tensors=0,bytes=0,types={}) for comp in sorted(components)}
        nonexpert_types=defaultdict(lambda:defaultdict(lambda:dict(bytes=0,tensors=[])))
        layers={str(l):dict(expert_banks_bytes=0,expert_triplet_bytes=0,top10_expert_bytes=0,dense_bytes=0,expert_types={}) for l in range(48)}
        for t in tensors:
            c=totals[t['component']];c['tensors']+=1;c['bytes']+=t['bytes']
            c['types'][t['type']]=c['types'].get(t['type'],0)+t['bytes']
            l=layers[str(t['layer'])] if t['layer'] is not None else None
            if t['component']=='routed_experts':
                assert t['shape'][0]==512 and t['bytes']%512==0
                t['bytes_per_expert']=t['bytes']//512
                t['decode_read_bytes']=t['bytes_per_expert']*10
                l['expert_banks_bytes']+=t['bytes'];l['expert_triplet_bytes']+=t['bytes_per_expert']
                l['top10_expert_bytes']+=t['decode_read_bytes'];l['expert_types'][t['name'].split('.')[2]]=t['type']
            else:
                d=nonexpert_types[t['component']][t['type']];d['bytes']+=t['bytes'];d['tensors'].append(t['name'])
                if t['component'] in ('embedding','ple_lookup'):
                    assert t['bytes']%t['shape'][0]==0
                    t['decode_read_bytes']=t['bytes']//t['shape'][0]*(16 if t['component']=='ple_lookup' else 1)
                else:
                    t['decode_read_bytes']=t['bytes']
                    if l is not None:l['dense_bytes']+=t['bytes']
        payload=sum(t['bytes'] for t in tensors)
        all_files=sum(f['file_bytes'] for f in file_records)
        assert all_files==payload+sum(f['header_bytes']+f['alignment_padding_bytes'] for f in file_records)
        experts=totals['routed_experts']['bytes']
        top10=sum(l['top10_expert_bytes'] for l in layers.values())
        offdevice=totals['embedding']['bytes']+totals['ple_lookup']['bytes']
        hc_extra=sum(t['bytes'] for t in tensors if t['hc_projection_replicated'])
        dense=payload-experts-offdevice
        metadata_bytes=sum(a['bytes'] for a in metadata_arrays.values())
        lookup=sum(t['decode_read_bytes'] for t in tensors if t['component'] in ('embedding','ple_lookup'))
        weight_reads=dense+top10+lookup
        device=payload-offdevice+hc_extra
        planned_grid={'UD-IQ3_XXS':98,'UD-IQ4_XS':136,'UD-Q3_K_XL':110}[variant]
        triplet=3*2560*640//256*planned_grid
        homogeneous=triplet*512*49+10_115_855_898
        variants[variant]=dict(tensor_count=len(tensors),file_bytes=all_files,tensor_bytes=payload,
            header_bytes_fetched=sum(f['header_bytes_fetched'] for f in files),files=file_records,
            components=totals,nonexpert_type_inventory=dict(nonexpert_types),per_layer=layers,
            ple_metadata_arrays=metadata_arrays,native_mtp=dict(present=False,tensors=0,bytes=0,
                proposal_read_bytes=None,reason='All 1224 names are target-only; no MTP block or merge. No 49th expert bank.'),
            active_bytes_per_decode=dict(top10_expert_bytes=top10,dense_bytes=dense,selected_lookup_bytes=lookup,
                tensor_weight_bytes=weight_reads,ple_metadata_value_bytes=metadata_bytes,
                including_ple_metadata_bytes=weight_reads+metadata_bytes,
                hc_replica_extra_bytes=hc_extra,tp2_with_hc_replication_bytes=weight_reads+metadata_bytes+hc_extra),
            two_card=dict(capacity_scenario_bytes=CAPACITY,host_ple_and_embedding_bytes=offdevice,
                all_48_expert_banks_bytes=experts,nonexpert_device_single_copy_bytes=dense,
                hc_extra_copy_bytes=hc_extra,actual_nonexpert_floor_bytes=dense+hc_extra,
                resident_tensor_bytes=device,with_ple_metadata_bytes=device+metadata_bytes,
                weight_only_headroom_bytes=CAPACITY-device,
                full_16bit_kv_scenario_bytes=KV,headroom_after_kv_and_metadata_bytes=CAPACITY-device-KV-metadata_bytes,
                balanced_bytes_per_card=device//2,balanced_is_not_a_rank_allocation=True),
            comparison=dict(planned_triplet_bytes=triplet,planned_expert_bytes_per_target=triplet*48*10,
                planned_decode_bytes_with_official_nonexperts=8_624_006_682+triplet*48*10,
                planned_all49_expert_bytes=triplet*512*49,matched_homogeneous_all48_expert_bytes=triplet*512*48,
                planned_nonexpert_floor_bytes=10_115_855_898,planned_resident_bytes=homogeneous,
                resident_correction_bytes=device-homogeneous),tensors=tensors)
    return dict(schema='own-xpu-runtime.stage2.packet1c.ud-census.v1',repository=receipt['repository'],revision=receipt['revision'],
        scope='Exact stored tensor/packed-grid arithmetic from headers. Target-only, 48 layers, top10 distinct experts/layer, all dense weights once, one embedding row, 16 PLE rows. PLE metadata separately charged. No KV/state/activation/scratch/dequantization/collective traffic. Two-card placement offloads PLE/input embeddings, partitions experts/dense optimistically, and duplicates HC down/up once. Other replicas/padding/repacking/graphs are additional; no actual device allocation or speed claim.',
        components_authority='../packet1/tensor-contract.json',parser_sha256=sha(PARSER.read_bytes()),variants=variants)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--write',action='store_true');a=ap.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19 or os.environ.get('OMP_NUM_THREADS')!='2':raise SystemExit('nice 19 and OMP_NUM_THREADS=2 required')
    result=build();path=HERE/'ud-census.json'
    table=comparison(result)
    if a.write:
        path.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        (HERE/'comparison.md').write_text(table)
    else:
        assert json.loads(path.read_text())==result
        assert (HERE/'comparison.md').read_text()==table
    for v,d in result['variants'].items():
        print(v,json.dumps(dict(resident=d['two_card']['resident_tensor_bytes'],decode=d['active_bytes_per_decode'],headers=d['header_bytes_fetched'],components=d['components'])))


def comparison(result):
    vs=result['variants'];names=list(vs)
    lines=['# Planned grids versus actual UD tensors','',
        'Exact bytes; arithmetic only. “Planned” preserves STAGE2-PLAN’s homogeneous',
        'grid and official nonexpert floor. “Actual” uses all packed tensors from',
        'the three real shards, offloads PLE/input embeddings and adds one HC',
        'down/up replica. It is not a measured allocation. Actual files have **48',
        'expert banks and no MTP**; planned totals included 49 banks plus MTP dense.',
        '', '| Variant | Planned resident B | Actual resident B | Correction B | Headroom B | After KV + metadata B |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for v,d in vs.items():
        p=d['comparison'];a=d['two_card']
        lines.append(f"| {v} | {p['planned_resident_bytes']:,} | {a['resident_tensor_bytes']:,} | {p['resident_correction_bytes']:+,} | {a['weight_only_headroom_bytes']:,} | {a['headroom_after_kv_and_metadata_bytes']:,} |")
    lines+=['','Capacity: **68,484,595,712 B**. KV scenario: **753,139,712 B**, full 16-bit.',
        'PLE control metadata: **280 B**; extra replicas, state, graphs and working',
        'space remain additional. No per-card fit is established by the balanced sum.',
        '', '| Variant | Planned top10 experts B/token | Actual top10 experts B/token | Dense B/token | Selected lookup B/token | Actual total B/token |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for v,d in vs.items():
        p=d['comparison'];a=d['active_bytes_per_decode']
        lines.append(f"| {v} | {p['planned_expert_bytes_per_target']:,} | {a['top10_expert_bytes']:,} | {a['dense_bytes']:,} | {a['selected_lookup_bytes']:,} | {a['including_ple_metadata_bytes']:,} |")
    lines+=['','Actual total = top10 experts + dense + selected lookups + 280 metadata bytes.',
        'This is one target-only decode token, with each dense tensor once; it',
        'excludes TP2 extra HC reads, KV/state traffic and collectives. TP2 HC',
        'adds **675,430,400 B/token** in every variant. No MTP proposal rate exists.',
        '', '| Variant | Planned all49 experts B | Same grid, 48 banks B | Actual all48 experts B | Planned nonexpert floor B | Actual nonexpert floor B |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for v,d in vs.items():
        p=d['comparison'];a=d['two_card']
        lines.append(f"| {v} | {p['planned_all49_expert_bytes']:,} | {p['matched_homogeneous_all48_expert_bytes']:,} | {a['all_48_expert_banks_bytes']:,} | {p['planned_nonexpert_floor_bytes']:,} | {a['actual_nonexpert_floor_bytes']:,} |")
    lines+=['','Both nonexpert floors include the extra HC copy and exclude host PLE/input',
        'embedding tables. The planned one includes MTP dense; the actual one cannot.',
        '', '## Component tensor bytes', '', '| Component | '+' | '.join(names)+' |', '| --- | '+' | '.join(['---:']*len(names))+' |']
    for comp in next(iter(vs.values()))['components']:
        lines.append('| '+comp+' | '+' | '.join(f"{vs[v]['components'][comp]['bytes']:,}" for v in names)+' |')
    lines+=['| **Tensor total** | '+' | '.join(f"{vs[v]['tensor_bytes']:,}" for v in names)+' |',
        '| **GGUF file total** | '+' | '.join(f"{vs[v]['file_bytes']:,}" for v in names)+' |',
        '| **Unique fetched headers** | '+' | '.join(f"{vs[v]['header_bytes_fetched']:,}" for v in names)+' |',
        '', 'Tensor totals include the host PLE/input tables. File totals add headers',
        'and alignment padding. The fetch receipt separately counts the discarded',
        '15,039-byte IQ3 discovery prefix, so transfer bytes exceed unique headers.',
        '', '## Real expert grids by layer', '', '| Variant | Projection | GGUF type | Zero-based layers |', '| --- | --- | --- | --- |']
    for v,d in vs.items():
        groups=defaultdict(list)
        for l,entry in d['per_layer'].items():
            for proj,kind in entry['expert_types'].items():groups[(proj,kind)].append(int(l))
        for (proj,kind),layers in sorted(groups.items()):
            label='all 0–47' if len(layers)==48 else ', '.join(map(str,sorted(layers)))
            lines.append(f'| {v} | {proj} | {kind} | {label} |')
    lines+=['','## Nonexpert storage types', '', '| Component | '+' | '.join(names)+' |','| --- | '+' | '.join(['---']*len(names))+' |']
    for comp in next(iter(vs.values()))['components']:
        if comp in ('routed_experts','native_mtp','vision_excluded'):continue
        lines.append('| '+comp+' | '+' | '.join(', '.join(sorted(vs[v]['components'][comp]['types'])) for v in names)+' |')
    lines+=['','Every tensor name behind these groups is in `nonexpert_type_inventory` in',
        '[ud-census.json](ud-census.json). IQ3 remains first for capacity; IQ4’s',
        'previous weight-only rejection is withdrawn. No quant quality ranking',
        'or runtime qualification follows from these tables.','']
    return '\n'.join(lines)


if __name__=='__main__':main()
