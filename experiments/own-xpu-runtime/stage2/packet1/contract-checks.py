#!/usr/bin/env python3
"""CPU-only Flash-Next identity, complete header directory and oracle validation.
Original lab code using the Stage 1 packet 1 checked parser (no runtime imports).
Offline by default. --local additionally rechecks LOCAL headers, never payloads.
"""
import argparse
from collections import Counter, defaultdict
import datetime
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import socket
import statistics
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
META=HERE/'metadata'
LANE='experiments/qwen38-flash-next-fp8-b70'
GUIDE='repro/qwen38-flash-next-fp8-tp4-mtp1-exactgdn-b70-47tps-20260913'
REV='bcd9f01ddc9cff2316eb84281bebcd5b058bddce'
PERF=LANE+'/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json'
SUITE='repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
TEMPLATE=ROOT/'experiments/own-xpu-runtime/stage1/packet1/contract-checks.py'
spec=importlib.util.spec_from_file_location('packet1_parser',TEMPLATE)
parser=importlib.util.module_from_spec(spec); spec.loader.exec_module(parser)
parser.WIDTH['I64']=8
sha=parser.sha
require=parser.require
read=parser.read
WIDTH=parser.WIDTH

def raw(path):
    p=Path(path); b=p.read_bytes()
    return gzip.decompress(b) if p.suffix=='.gz' else b

def pin(path):
    p=Path(path); p=p if p.is_absolute() else ROOT/p
    b=p.read_bytes(); return dict(path=str(p.relative_to(ROOT)),sha256=sha(b),bytes=len(b))

def encoded(obj, compact=False):
    # One tensor per line keeps the complete 152k-entry directory reviewable.
    if compact:
        rest={k:v for k,v in obj.items() if k!='tensors'}
        body=json.dumps(rest,sort_keys=True,indent=2)[:-2]
        return (body+',\n  "tensors": [\n'+',\n'.join('    '+json.dumps(t,sort_keys=True,separators=(',',':')) for t in obj['tensors'])+'\n  ]\n}\n').encode()
    return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()

def expected_shapes(config):
    """Config-derived Flash graph, independent of shard tensor descriptions."""
    c=config['text_config']; v=config['vision_config']; h=c['hidden_size']; hc=c['hc_count']; low=c['hc_lowrank']; f=c['moe_intermediate_size']
    expected={}
    def add(n,s,d='BF16'): expected[n]=(s,d)
    def norm(n,s): add(n+'.weight',[s])
    def mix(p,inject=False):
        norm(p+'hc_norm',hc*h)
        add(p+'input_mix_weight_down.weight',[low,hc*h]); add(p+'input_mix_weight_up.weight',[hc*h,low])
        if inject: add(p+'block_inject_weight.weight',[hc,hc*h])
    def block(p,kind):
        mix(p+'attn_hyper_connection.',True);mix(p+'mlp_hyper_connection.',True)
        add(p+'mlp.gate.weight',[c['num_experts'],h]);add(p+'mlp.shared_expert_gate.weight',[1,h])
        for e in range(c['num_experts']):
            for name,shape in [('gate',[f,h]),('up',[f,h]),('down',[h,f])]:
                n=p+f'mlp.experts.{e}.{name}_proj.weight';add(n,shape,'F8_E4M3');add(n+'_scale_inv',[(x+127)//128 for x in shape])
        for name,shape in [('gate',[c['shared_expert_intermediate_size'],h]),('up',[c['shared_expert_intermediate_size'],h]),('down',[h,c['shared_expert_intermediate_size']])]: add(p+f'mlp.shared_expert.{name}_proj.weight',shape)
        if kind=='linear_attention':
            k=c['linear_num_key_heads']*c['linear_key_head_dim']; val=c['linear_num_value_heads']*c['linear_value_head_dim']; q=p+'linear_attn.'
            for name in ['A_log','dt_bias']: add(q+name,[c['linear_num_value_heads']])
            add(q+'conv1d.weight',[2*k+val,1,c['linear_conv_kernel_dim']]);norm(q+'norm',c['linear_value_head_dim'])
            for name,shape in [('in_proj_a',[c['linear_num_value_heads'],h]),('in_proj_b',[c['linear_num_value_heads'],h]),('in_proj_qkv',[2*k+val,h]),('in_proj_z',[val,h]),('out_proj',[h,val])]: add(q+name+'.weight',shape)
        else:
            d=c['head_dim'];q=c['num_attention_heads']*d;kv=c['num_key_value_heads']*d;p+='self_attn.'
            for name,shape in [('q',[2*q,h]),('k',[kv,h]),('v',[kv,h]),('o',[h,q])]: add(p+name+'_proj.weight',shape)
            for name in ['q','k']:norm(p+name+'_norm',d)
            add(p+'indexer.index_qk_proj.weight',[(c['indexer_n_heads']+c['indexer_kv_heads'])*c['indexer_head_dim'],h])
            for name in ['q','k']:norm(p+'indexer.'+name+'_layernorm',c['indexer_head_dim'])
    for l,kind in enumerate(c['layer_types']):block(f'model.language_model.layers.{l}.',kind)
    mix('model.language_model.hyper_connection_mixer.')
    add('model.language_model.embed_tokens.weight',[c['vocab_size'],h]);add('lm_head.weight',[c['vocab_size'],h])
    require(c['ple_layer_ids']==[2], 'one-based PLE layer contract')
    p='model.language_model.layers.1.ple.'
    add(p+'key_proj.weight',[hc*h,h]);add(p+'value_proj.weight',[h,h]);add(p+'conv1d.weight',[hc*h,1,c['ple_conv_kernel_size']])
    for n in ['norm_conv','norm_key','norm_query']:norm(p+n,hc*h)
    # Exact hashed table row padding is frozen separately from nominal 20M vocab.
    for i in range(c['split_ngram_parts']):add(p+f'ple_embedding.ngram_embedding.shard_{i}.weight',[2500012,h//((c['ngram_size']-1)*c['heads_per_ngram'])],'F8_E4M3')
    add(p+'ple_embedding.ngram_embedding.weight_scale',[1])
    add(p+'ple_embedding.layer_multipliers',[c['ngram_size']],'I64')
    for n in ['ngram_heads_offsets','ngram_heads_vocab_sizes']:add(p+'ple_embedding.'+n,[(c['ngram_size']-1)*c['heads_per_ngram']],'I64')
    block('mtp.layers.0.','full_attention');mix('mtp.hyper_connection_mixer.')
    norm('mtp.pre_fc_norm_embedding',h);norm('mtp.pre_fc_norm_hidden',hc*h)
    for n in ['fc_embedding','fc_hidden']:add('mtp.'+n+'.weight',[h,h])
    vh=v['hidden_size'];vf=v['intermediate_size']; merged=vh*v['spatial_merge_size']**2
    def affine(n,o,i):add(n+'.weight',[o,i]);add(n+'.bias',[o])
    for i in range(v['depth']):
        p=f'model.visual.blocks.{i}.'
        for n,o,k in [('attn.proj',vh,vh),('attn.qkv',3*vh,vh),('mlp.linear_fc1',vf,vh),('mlp.linear_fc2',vh,vf)]:affine(p+n,o,k)
        for n in ['norm1','norm2']:
            for s in ['weight','bias']:add(p+n+'.'+s,[vh])
    affine('model.visual.merger.linear_fc1',merged,merged);affine('model.visual.merger.linear_fc2',v['out_hidden_size'],merged)
    for s in ['weight','bias']:add('model.visual.merger.norm.'+s,[vh])
    add('model.visual.patch_embed.proj.weight',[vh,v['in_channels'],v['temporal_patch_size'],v['patch_size'],v['patch_size']]);add('model.visual.patch_embed.proj.bias',[vh]);add('model.visual.pos_embed.weight',[v['num_position_embeddings'],vh])
    return expected

def owner(n):
    if n.startswith('model.visual.'):return 'vision_excluded'
    if '.mlp.experts.' in n:return 'routed_experts'
    if '.ple.ple_embedding.' in n:return 'ple_lookup'
    if '.ple.' in n:return 'ple_projection'
    if 'norm' in n:return 'norms'
    if 'hyper_connection' in n:return 'hyperconnections'
    if '.linear_attn.' in n:return 'gdn'
    if '.self_attn.indexer.' in n:return 'qsa_indexer'
    if '.self_attn.' in n:return 'qsa_attention'
    if '.mlp.shared_expert.' in n:return 'shared_experts'
    if '.mlp.' in n:return 'routers'
    if n.endswith('embed_tokens.weight'):return 'embedding'
    if n=='lm_head.weight':return 'target_head'
    if n.startswith('mtp.fc_'):return 'mtp_merge'
    raise ValueError('unowned tensor '+n)

def read_local_header(path, expected_length):
    with path.open('rb',buffering=0) as f:
        prefix=f.read(8); require(len(prefix)==8,'local prefix')
        length=struct.unpack('<Q',prefix)[0]
        require(2<=length<=parser.MAX_HEADER and length==expected_length,'local header length')
        body=f.read(length);require(len(body)==length,'local truncated header')
        require(f.tell()==8+length,'payload read guard')
        return body


def local_reader_fixtures():
    # A synthetic stream raises immediately if any payload byte is requested.
    import io
    class Guard(io.BytesIO):
        def read(self,n=-1):
            require(n>=0 and self.tell()+n<=self.bound,'payload read attempted')
            self.calls.append(n)
            return super().read(n)
    class File:
        def __init__(self,data,bound):self.data=data;self.bound=bound
        def open(self,mode,buffering):
            require(mode=='rb' and buffering==0,'unbuffered read required')
            f=Guard(self.data);f.bound=self.bound;f.calls=[];self.stream=f;return f
    body=b'{"__metadata__":{}}'
    path=File(struct.pack('<Q',len(body))+body+b'FORBIDDEN',8+len(body))
    require(read_local_header(path,len(body))==body,'header read fixture')
    require(path.stream.calls==[8,len(body)],'exact read requests')
    tests=[dict(name='unbuffered two-read payload boundary',passed=True)]
    for name,payload,bound,want in [('oversized length',struct.pack('<Q',2**63),8,len(body)),('truncated prefix',b'abc',8,len(body)),('truncated header',struct.pack('<Q',len(body))+b'{}',8+len(body),len(body))]:
        try:read_local_header(File(payload,bound),want)
        except ValueError:pass
        else:raise ValueError('negative reader fixture accepted '+name)
        tests.append(dict(name=name,passed=True))
    i64=b'{"x":{"dtype":"I64","shape":[3],"data_offsets":[0,24]}}'
    require(parser.parse_header(i64,8+len(i64)+24,len(i64))['x']['dtype']=='I64','I64 PLE metadata support')
    tests.append(dict(name='I64 PLE metadata header',passed=True))
    return tests


def tensor_contract(config,local=False):
    receipt=read(META/'local-metadata-receipt.json');hf=read(META/'hf-model-info.json')
    require(sha((META/'hf-model-info.json').read_bytes())==receipt['hf_sha256'],'HF snapshot hash')
    require(hf['sha']==REV and hf['id']=='Qwen/Qwen3.8-Flash-Next-FP8','HF revision/repository')
    siblings={s['rfilename']:s for s in hf['siblings']};expected=expected_shapes(config)
    index=parser.parse_json(raw(META/'model.safetensors.index.json.gz'))
    require(set(siblings)=={r['name'] for r in receipt['files']},'HF/local file coverage')
    tensors=[];shards=[];names=set(); elements=Counter(); comps=defaultdict(Counter); kinds=defaultdict(Counter); dtype=Counter(); scale_bytes=Counter()
    for r in receipt['files']:
        s=siblings[r['name']]; require(s['size']==r['file_bytes'],'HF file size '+r['name'])
        dm=r['download_metadata'].splitlines();require(dm[0]==REV and dm[1]==s.get('lfs',{}).get('sha256',s['blobId']),'download revision/etag '+r['name'])
        if not r['name'].endswith('.safetensors'):
            require(r['snapshot_sha256']==s['lfs']['sha256'] if 'lfs' in s else r['git_blob_sha1']==s['blobId'],'local metadata content identity '+r['name'])
            if r['snapshot']:require(sha(raw(META/r['snapshot']))==r['snapshot_sha256'],'metadata snapshot hash')
            continue
        body=raw(META/r['snapshot']); require(sha(body)==r['snapshot_sha256'],'header snapshot hash')
        if local:
            path=Path(receipt['source'])/r['name']; require(path.stat().st_size==r['file_bytes'],'local shard size')
            require(read_local_header(path,len(body))==body,'local header differs')
        h=parser.parse_header(body,r['file_bytes'],len(body))
        shards.append(dict(name=r['name'],file_bytes=r['file_bytes'],header_bytes=len(body),header_sha256=sha(body),payload_bytes=r['file_bytes']-8-len(body),publisher_sha256=s['lfs']['sha256'],payload_authenticated=False))
        for n,t in sorted(h.items()):
            require(n not in names and index['weight_map'].get(n)==r['name'],'duplicate/index mismatch '+n);names.add(n)
            require(n in expected and (t['shape'],t['dtype'])==expected[n],'independent shape/dtype mismatch '+n)
            size=t['data_offsets'][1]-t['data_offsets'][0];o=owner(n); component='native_mtp' if n.startswith('mtp.') else o
            match=re.search(r'(?:language_model|mtp)\.layers\.(\d+)\.',n);layer=int(match[1]) if match else None
            kind='native_mtp_qsa' if n.startswith('mtp.') else ('vision_excluded' if o=='vision_excluded' else config['text_config']['layer_types'][layer] if layer is not None else 'target_global')
            format_name='FP8_E4M3_128x128_BF16_block_scale' if '.experts.' in n and t['dtype']=='F8_E4M3' else 'FP8_E4M3_global_BF16_scale' if '.ngram_embedding.shard_' in n else 'block_scale_multiplier' if n.endswith('_scale_inv') else t['dtype']
            item=dict(name=n,dtype=t['dtype'],format=format_name,shape=t['shape'],bytes=size,shard=r['name'],data_offsets=t['data_offsets'],file_offset=8+len(body)+t['data_offsets'][0],component=component,subcomponent=o,layer=layer)
            tensors.append(item);comps[component]['bytes']+=size;comps[component]['tensors']+=1;kinds[kind]['bytes']+=size;kinds[kind]['tensors']+=1;dtype[t['dtype']]+=size;elements[t['dtype']]+=math.prod(t['shape'])
            if '_scale' in n:scale_bytes[t['dtype']]+=size
    tensors.sort(key=lambda t:t['name'])
    mtp_subcomponents=Counter()
    for t in tensors:
        if t['component']=='native_mtp':mtp_subcomponents[t['subcomponent']]+=t['bytes']
    require(names==set(expected)==set(index['weight_map']),'complete graph/index/header coverage')
    totals=dict(payload=sum(dtype.values()),headers_and_prefixes=sum(8+s['header_bytes'] for s in shards),shard_files=sum(s['file_bytes'] for s in shards),all_root_files=sum(r['file_bytes'] for r in receipt['files']))
    require(totals['payload']==index['metadata']['total_size'],'index payload total')
    require(totals['payload']+totals['headers_and_prefixes']==totals['shard_files']==185523317458,'lane shard byte total')
    require(totals['all_root_files']==185563783127,'lane root byte total')
    # HF excludes all scale elements, including the one PLE global scale.
    hf_delta={k:elements[k]-hf['safetensors']['parameters'].get(k,0) for k in elements}
    block_scales=sum(t['bytes']//WIDTH[t['dtype']] for t in tensors if '_scale' in t['name'])
    require(hf_delta=={'BF16':block_scales,'F8_E4M3':0,'I64':0},'HF parameter reconciliation')
    active=defaultdict(int);perlayer=defaultdict(Counter)
    for t in tensors:
        if t['component']=='vision_excluded':continue
        if t['subcomponent']=='routed_experts':
            # Exact rational top-10/512 count; sum first, then divide.
            b=t['bytes']*10
            key='mtp' if t['component']=='native_mtp' else 'target'
            active[key+'_routed_numerator']+=b
            if t['name'].endswith('_scale_inv'):active[key+'_routed_scale_numerator']+=b
            perlayer[key+':'+str(t['layer'])]['routed_all_bytes']+=t['bytes']
        elif t['component']=='embedding':active['embedding_lookup_bytes']=config['text_config']['hidden_size']*WIDTH[t['dtype']]
        elif '.ngram_embedding.shard_' in t['name']:pass
        elif t['subcomponent']=='ple_lookup':active['ple_metadata_bytes']+=t['bytes']
        else:
            key='mtp' if t['component']=='native_mtp' else 'target'
            active[key+'_dense_bytes']+=t['bytes']
            if t['layer'] is not None:perlayer[key+':'+str(t['layer'])]['dense_bytes']+=t['bytes']
    for key in ['target','mtp']:
        active[key+'_routed_bytes']=active.pop(key+'_routed_numerator')//512
        active[key+'_routed_scale_bytes']=active.pop(key+'_routed_scale_numerator')//512
    active['ple_selected_row_bytes']=config['text_config']['hidden_size'] # 16 * 160 FP8
    active['target_decode_weight_read_bytes']=sum(active[k] for k in ['target_dense_bytes','target_routed_bytes','embedding_lookup_bytes','ple_metadata_bytes','ple_selected_row_bytes'])
    active['mtp_proposal_weight_read_bytes']=active['mtp_dense_bytes']+active['mtp_routed_bytes']+active['embedding_lookup_bytes']+comps['target_head']['bytes']
    active['target_plus_one_proposal_bytes']=active['target_decode_weight_read_bytes']+active['mtp_proposal_weight_read_bytes']
    active['stored_fp32_scale_bytes']=0
    active['target_fp32_scale_expansion_extra_bytes']=active['target_routed_scale_bytes']+2
    active['mtp_fp32_scale_expansion_extra_bytes']=active['mtp_routed_scale_bytes']
    active['fp32_scale_expansion_scope']='Conditional arithmetic only: widening all expert scales BF16 to FP32 doubles their stored byte count; the one PLE global scale adds two bytes. Activation scales/workspaces are additional and not checkpoint tensors.'
    for prefix in ['target','mtp']:
        replicated=sum(t['bytes'] for t in tensors if t['name'].endswith(('input_mix_weight_down.weight','input_mix_weight_up.weight')) and (t['component']=='native_mtp')==(prefix=='mtp'))
        active[prefix+'_hc_projection_replica_bytes_per_extra_rank']=replicated
    active['tp4_target_weight_reads_with_hc_replication_floor_bytes']=active['target_decode_weight_read_bytes']+3*active['target_hc_projection_replica_bytes_per_extra_rank']
    active['tp2_target_weight_reads_with_hc_replication_floor_bytes']=active['target_decode_weight_read_bytes']+active['target_hc_projection_replica_bytes_per_extra_rank']
    for l,d in perlayer.items():d['top10_bytes']=d['routed_all_bytes']*10//512;d['active_bytes']=d['top10_bytes']+d['dense_bytes']
    return dict(schema='own-xpu-runtime.stage2.packet1.tensor-contract.v1',tensor_count=len(tensors),shard_count=len(shards),target_layer_kind_schedule=config['text_config']['layer_types'],totals_bytes=totals,components=dict(comps),mtp_subcomponent_bytes=dict(mtp_subcomponents),layer_kinds=dict(kinds),dtype_bytes=dict(dtype),stored_scale_bytes=dict(scale_bytes),hf_parameter_element_delta=hf_delta,ple=dict(config_layer_id=2,tensor_layer_index=1,indexing='one-based config; zero-based tensor name',split_tables=128,rows_per_table=2500012,total_rows=320001536,lookup_heads=16,bytes_per_row=160),active_bytes_per_decode=active,per_layer_active_bytes=dict(perlayer),active_scope='One target token, top-10 unique experts per each of 48 layers, dense weights once, one embedding row, 16 PLE rows plus small lookup metadata; no cache credit. MTP is separately one proposal with full shared head. Excludes KV/state/activation/scratch/collective traffic and runtime scale widening; not measured bandwidth or bytes per emitted speculative token.',shards=shards,tensors=tensors)

def oracle_and_identity(contract):
    guide=read(ROOT/GUIDE/'identity.json');perf=read(ROOT/PERF);suite=read(ROOT/SUITE);att=read(ROOT/guide['record']['attestation'])
    require(pin(PERF)['sha256']==guide['record']['performance_evidence_sha256']==att['performance_evidence']['sha256'],'certified performance hash')
    require(pin(SUITE)['sha256']==guide['record']['suite_sha256']==att['identity']['suite_sha256'],'suite hash')
    for e in att['quality_evidence']: require(pin(e['path'])['sha256']==e['sha256'],'quality evidence hash')
    rows=[];rates=defaultdict(list)
    require(len(perf['rows'])==len(suite['prompts'])==12,'12-row full oracle')
    for p,r in zip(suite['prompts'],perf['rows']):
        ids=r['token_ids'];require(p['id']==r['prompt_id'] and sha(p['prompt'].encode())==r['prompt_sha256'],'oracle prompt order/hash')
        require(len(ids)==r['completion_tokens']==r['stream_token_id_count'] and 100<=len(ids)<=512,'oracle token length')
        require(all(type(t)is int and 0<=t<248320 for t in ids),'oracle token bounds')
        require(sha(r['text'].encode())==r['sha256'] and r['cached_tokens']==0,'text hash/cache zero')
        offsets=r['token_id_offsets_s'];rate=99/(offsets[99]-offsets[0]);require(math.isclose(rate,r['tok_s_1_100_intervals_after_ttft'],rel_tol=1e-12),'99 intervals metric');rates[r['prompt_class']].append(rate)
        rows.append(dict(prompt_id=r['prompt_id'],prompt_class=r['prompt_class'],prompt_sha256=r['prompt_sha256'],text_sha256=r['sha256'],token_ids=ids,length=len(ids),token_ids_sha256=sha(json.dumps(ids,separators=(',',':')).encode()),metric=dict(event_count=100,interval_count=99,numerator=99,first_generated_token=1,last_generated_token=100,first_offset_s=offsets[0],last_offset_s=offsets[99],tok_s=rate)))
    rate=statistics.median(statistics.median(v) for v in rates.values());require(math.isclose(rate,46.85424994838007,rel_tol=1e-12),'certified class-balanced rate')
    arrays=dict(schema='own-xpu-runtime.stage2.packet1.oracle.v1',source=pin(PERF),suite=pin(SUITE),rows=rows,total_tokens=sum(r['length'] for r in rows),arrays_sha256=sha(json.dumps([r['token_ids'] for r in rows],separators=(',',':')).encode()))
    deps=[GUIDE+'/identity.json',GUIDE+'/evidence/a367-run.sha256',guide['model']['contract'],guide['record']['attestation'],PERF,SUITE,guide['configuration']['expert_host_placement']['file'],guide['runtime']['kernel_stage_manifest'],LANE+'/tools/launch-tp4-mtp1-4352-ple-only-a367-fullgraphdet-w13n32.sh',LANE+'/tools/launch-tp4-ep4-eager-mtp0-long-context-base.sh',LANE+'/reopen-20261008/CALIBRATION.md',LANE+'/reopen-20261008/rescued-calibration.json',LANE+'/reopen-20261008/placement_plan.py',LANE+'/tools/rewrite-q38-a338-to-diag-mtp1-step-timing.py',LANE+'/data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json',LANE+'/notes/2026-10-08-host-memory-reduction-design.md',LANE+'/notes/2026-09-13-a375-a376-32k-context-ladder-prereg.md',str(TEMPLATE.relative_to(ROOT))]+[e['path'] for e in att['quality_evidence']]
    config=read(META/'config.json');require(sha((META/'config.json').read_bytes())==guide['model']['config_sha256'],'certified config hash');require(sha(raw(META/'model.safetensors.index.json.gz'))==guide['model']['safetensors_index_sha256'],'certified index hash')
    command=shlex.split((HERE/'evidence/server-command.shell.txt').read_text())
    identity=dict(schema='own-xpu-runtime.stage2.packet1.identity.v1',publisher='Qwen',repository=guide['model']['repository'],revision=REV,local_checkpoint=read(META/'local-metadata-receipt.json')['source'],revision_confirmation='144 local download revision/etag and file sizes match official HF revision; local metadata contents verified against Git blob/LFS identities; retained unbuffered local shard headers validated. Payloads not read or authenticated.',config=config,tokenizer=dict(requirements=read(META/'tokenizer_config.json'),generation_defaults=read(META/'generation_config.json'),required_files=[r for r in read(META/'local-metadata-receipt.json')['files'] if r['name'] in ['tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','chat_template.jinja','generation_config.json']],input_policy='A367 uses chat: one user message, no system prompt, enable_thinking=false, publisher chat template; temperature=0, top_p=1, seed=20260609, max_tokens=512, generation-config=vllm. Do not substitute the Stage 1 raw-completions suite. Tokenization execution/parity remains untested.'),certified_line=guide,request_identity=perf['run_identity'],benchmark_summary=perf['summary'],cache_policy=perf['fresh_response_validity'],server_argv=command,hardware=read(HERE/'evidence/xpu-discovery.json'),source_pins=[pin(d) for d in deps],metadata_pins=[pin(p) for p in sorted(META.rglob('*')) if p.is_file()],archive_pins=[pin(p) for p in sorted((HERE/'evidence').glob('*')) if p.is_file()],oracle=dict(path='oracle-token-ids.json',sha256=sha(encoded(arrays)),rows=12,total_tokens=arrays['total_tokens'],arrays_sha256=arrays['arrays_sha256']),tensor_contract=dict(path='tensor-contract.json',sha256=sha(encoded(contract,True))),runtime_arithmetic=dict(activation_dtype='BF16',kv_dtype='BF16 (auto follows bfloat16)',checkpoint_scale_dtype='BF16',ple_runtime_global_scale='FP32 in historical loader; stored BF16',gdn_state='Certified exact verifier passes state through BF16 cache between rows; DESIGN/config FP32 state is a proposal, not certified parity.',target_weights_unchanged=True,moe='certified Triton dynamic FP8 activation/block FP8 expert path; dense excluded projections BF16; do not transplant 27B W8A16'),unavailable_historical_fields=dict(boot_id=None,umd_version=None,firmware_version=None,reason='Not established by the retained A367 identity/metadata evidence; never fill with current-host values. Launch-source pins retain declared environment; no complete process environment snapshot is present.'),limitations=['Header-only checkpoint audit does not reauthenticate tensor payload SHA256s.','No tokenizer execution, dequantization, runtime parity, GPU placement, bandwidth or performance measurement.','No new promotion; the historical line and its quality caveats remain unchanged.'])
    return arrays,identity

def placement(contract):
    ts=contract['tensors'];guide=read(ROOT/GUIDE/'identity.json');mask=read(ROOT/guide['configuration']['expert_host_placement']['file'])
    text=sum(t['bytes'] for t in ts if t['component']!='vision_excluded')
    ple=sum(t['bytes'] for t in ts if '.ngram_embedding.shard_' in t['name']);embed=contract['components']['embedding']['bytes']
    replicated=sum(t['bytes'] for t in ts if t['name'].endswith(('input_mix_weight_down.weight','input_mix_weight_up.weight')))
    expert_bytes=3*2560*640;expert_scale_bytes=3*5*20*2
    ranks=[]
    for r in range(4):
        count=sum(len(ids) for ids in mask[str(r)].values());require(count==[543,587,550,586][r],'certified placement counts')
        host=ple//4+embed//4+count*expert_bytes
        floor=(text+3*replicated)//4-host
        ranks.append(dict(rank=r,host_experts=count,host_ple_bytes=ple//4,host_embedding_bytes=embed//4,host_expert_weights_bytes=count*expert_bytes,host_tensor_bytes=host,optimistic_device_weight_floor_bytes=floor,kv_budget_bytes=376569856,historical_model_load_delta_gib=[29.57,29.37,29.54,29.38][r]))
    cap=34242297856 # historical rank0 only; reused solely as declared capacity scenario
    nonlookup=text-ple-embed
    gap=nonlookup+replicated-2*cap
    # Keep dense weights, host PLE/embed; whole experts may be placed, all 49 blocks retained.
    experts=sum(t['bytes'] for t in ts if t['subcomponent']=='routed_experts')
    dense=nonlookup-experts
    return dict(schema='own-xpu-runtime.stage2.packet1.placement-arithmetic.v1',scope='Arithmetic lower bounds, not measured allocation/fit. TP+EP dense partition optimistically balanced except proven replicated HC down/up. Other replicas, padding, state, scratch, graph/runtime overhead can only increase residency.',text_payload_bytes=text,ple_table_bytes=ple,input_embedding_bytes=embed,replicated_hc_projection_bytes=replicated,expert_weight_bytes=expert_bytes,expert_stored_scale_bytes=expert_scale_bytes,certified_tp4_ep4=ranks,certified_host_tensor_bytes=sum(r['host_tensor_bytes'] for r in ranks),two_card=dict(capacity_scenario_per_card_bytes=cap,capacity_is_historical_rank0_not_current_measurement=True,nonlookup_text_payload_bytes=nonlookup,optimistic_all_resident_weight_floor_bytes=nonlookup+replicated,weight_only_gap_bytes=gap,nominal_32gib_per_card_weight_gap_bytes=nonlookup+replicated-2*32*2**30,extra_gap_after_reusing_certified_host_experts_bytes=gap-sum(r['host_expert_weights_bytes'] for r in ranks),with_same_kv_budget_per_rank_gap_bytes=gap+2*376569856,minimum_whole_experts_offloaded_with_scales=math.ceil(gap/(expert_bytes+expert_scale_bytes)),minimum_whole_experts_offloaded_keep_scales_on_device=math.ceil(gap/expert_bytes),all_experts_with_scales_bytes=experts,dense_resident_floor_bytes=dense+replicated,all_experts_streaming_bytes_per_target_token=48*10*(expert_bytes+expert_scale_bytes),all_experts_streaming_bytes_per_mtp_proposal=10*(expert_bytes+expert_scale_bytes),actual_host_streaming_per_token='Depends on routed IDs and admitted resident mask; range zero to full selected-expert budget, not inferred from static gap. Whole-expert symmetric placement leaves more than 10 host experts/layer, so zero host hits cannot be guaranteed.',optimistic_host_backing_minimum_bytes=ple+embed+gap,all_experts_host_plus_ple_embedding_bytes=experts+ple+embed,host_plus_device_weights_if_each_device_byte_has_one_host_shadow_bytes=text+replicated))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write-contracts',action='store_true');ap.add_argument('--receipt',type=Path);ap.add_argument('--local',action='store_true');a=ap.parse_args()
    require(os.environ.get('OMP_NUM_THREADS')=='2' and os.getpriority(os.PRIO_PROCESS,0)==19,'require nice19 OMP_NUM_THREADS=2')
    require(subprocess.check_output(['ionice','-p',str(os.getpid())],text=True).strip()=='idle','require ionice -c 3')
    fixtures=parser.fixture_checks()+local_reader_fixtures()
    c=tensor_contract(read(META/'config.json'),a.local);arrays,identity=oracle_and_identity(c);place=placement(c)
    products={'tensor-contract.json':encoded(c,True),'oracle-token-ids.json':encoded(arrays),'identity.json':encoded(identity),'placement-arithmetic.json':encoded(place)}
    # Independently rebuild complete directory, totals and all manifests once more.
    c2=tensor_contract(read(META/'config.json'));o2,i2=oracle_and_identity(c2)
    require(products=={'tensor-contract.json':encoded(c2,True),'oracle-token-ids.json':encoded(o2),'identity.json':encoded(i2),'placement-arithmetic.json':encoded(placement(c2))},'deterministic regeneration')
    for name,b in products.items():
        if a.write_contracts:(HERE/name).write_bytes(b)
        require((HERE/name).read_bytes()==b,'derived contract differs: '+name)
    # Validate every extracted archive file against the pre-existing certified run manifest.
    pins={line.split()[1]:line.split()[0] for line in (ROOT/GUIDE/'evidence/a367-run.sha256').read_text().splitlines()}
    for r in read(HERE/'evidence/archive-provenance.json'):require(sha((HERE/r['path']).read_bytes())==r['sha256']==pins[Path(r['path']).name],'archive evidence hash')
    receipt=dict(schema='own-xpu-runtime.stage2.packet1.check-receipt.v1',verdict='PASS',gate='CPU identity, complete header/shape contract, oracle and placement arithmetic only',stage2_runtime_qualified=False,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=socket.gethostname(),command='nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 python3 -B '+shlex.join(sys.argv),local_headers_rechecked=a.local,tensor_payload_bytes_read=0,files=[pin(HERE/n) for n in products]+[pin(HERE/'contract-checks.py'),pin(HERE/'capture-metadata.py'),pin(TEMPLATE),pin(TEMPLATE.parent/'parser-fixtures.json'),pin(HERE/'README.md'),pin(HERE/'placement-census.md'),pin(HERE.parent/'README.md')],parser_fixtures=fixtures,tensors=c['tensor_count'],totals_bytes=c['totals_bytes'],components=c['components'],active_bytes_per_decode=c['active_bytes_per_decode'],two_card=place['two_card'],checks=['144 revision/etag/size and metadata Git blob/LFS identities against pinned HF','complete shard-index/config shape/dtype/name coverage including 49x512 experts','bounded headers, checked sizes and offsets, no duplicate/overlap/gap','BF16 expert scale shape pairing and PLE global scale','12 full cold chat oracle arrays, prompt/text/hash/range/length and class-balanced 99-interval rate','quality attestation evidence hashes and archived run hashes','deterministic rebuild of four products','TP4 mask counts and TP2 residency/streaming arithmetic'],limitations=identity['limitations'])
    if a.receipt:a.receipt.write_bytes(encoded(receipt))
    print(json.dumps({k:receipt[k] for k in ['verdict','tensors','totals_bytes','components','active_bytes_per_decode','two_card']},indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError) as e:print('FAIL: '+str(e),file=sys.stderr);sys.exit(1)
