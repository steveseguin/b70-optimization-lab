#!/usr/bin/env python3
"""Explicit sealed262K-to64K/128K capacity equivalence; no device/archive operations."""
import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import stat
import struct
import compare as C
T,D,need=C.T,C.D,C.need
TARGET={f'blk.{layer}.qsa.{kind}.bin':kind for layer in range(3,48,4)
        for kind in ('keys','values','raw','pooled')}
DRAFT={f'card0:draft:blk.0.qsa.{kind}':kind for kind in ('keys','values','raw','pooled')}

def shape(kind,context):
    return [context,2,256] if kind in ('keys','values') else [context//4,128] if kind=='pooled' else [context,128]

def capacity_layout(name,large,small,*,draft=False,candidate_context=65536):
    need(type(candidate_context) is int and candidate_context in (65536,131072),'supported candidate capacity required')
    registry=DRAFT if draft else TARGET
    need(name in registry,'unregistered context-dependent source')
    kind=registry[name];dtype='BF16' if draft else 'f32';width=2 if draft else 4
    for row,context in ((large,262144),(small,candidate_context)):
        need(row['dtype']==dtype and row['shape']==shape(kind,context)
             and row['bytes']==math.prod(row['shape'])*width,'registered context shape/dtype/byte bounds differ')
    need({k:v for k,v in large.items() if k not in ('bytes','shape')}==
         {k:v for k,v in small.items() if k not in ('bytes','shape')},'context-independent layout/role differs')

def index(directory,key):
    raw,receipt=D.small(Path(directory)/'state-index.tsv')
    rows=[line.split('\t') for line in raw.decode().splitlines()[1:]]
    found=[row for row in rows if row[0]==key]
    need(len(found)==1,'exact indexed source required')
    row=found[0];return int(row[1]),int(row[2]),row[3],receipt

def prefix_zero(large_path,large_offset,large_size,large_sha,small_path,small_offset,small_size,small_sha,*,ratio=4):
    """Rehash both actual full extents; no replacement hash or padded fake file."""
    need(type(large_offset)is int and type(small_offset)is int and min(large_offset,small_offset)>=0
         and type(large_size)is int and type(small_size)is int and small_size>0
         and type(ratio) is int and ratio in (2,4)
         and large_size==small_size*ratio,'exact declared2x/4x bounded prefix extents required')
    fds=[]
    try:
        stamps=[]
        for path,offset,size in ((large_path,large_offset,large_size),(small_path,small_offset,small_size)):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);fds.append(fd);s=os.fstat(fd)
            need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and offset+size<=s.st_size,'prefix range/file bounds')
            stamps.append(T.BUNDLE.identity(s));os.lseek(fd,offset,os.SEEK_SET)
        big,small=sha256(),sha256();left=small_size
        while left:
            count=min(65536,left);a=os.read(fds[0],count);b=os.read(fds[1],count)
            need(len(a)==len(b)==count,'prefix truncated');need(a==b,'full candidate-capacity prefix mismatch')
            big.update(a);small.update(b);left-=count
        left=large_size-small_size
        while left:
            count=min(65536,left);data=os.read(fds[0],count)
            need(len(data)==count,'larger tail truncated');need(not any(data),'nonzero reference extra-capacity tail')
            big.update(data);left-=count
        need(big.hexdigest()==large_sha and small.hexdigest()==small_sha,'actual prefix/tail payload hash differs from original seal')
        for fd,path,before in zip(fds,(large_path,small_path),stamps):
            need(before==T.BUNDLE.identity(os.fstat(fd))==T.BUNDLE.identity(os.stat(path,follow_symlinks=False)),
                 'prefix source changed/replaced')
        return dict(reference_full_sha256=large_sha,candidate_full_sha256=small_sha,
                    compared_prefix_bytes=small_size,verified_zero_extra_bytes=large_size-small_size)
    finally:
        for fd in fds:os.close(fd)

def array_proof(name,large,small,large_dump,small_dump,*,draft=False,candidate_context=65536):
    layout=lambda row:row['layout'] if draft else {k:row[k] for k in ('bytes','dtype','shape','role')}
    capacity_layout(name,layout(large),layout(small),draft=draft,candidate_context=candidate_context)
    key=T.BUNDLE.logical_name(name) if draft else name
    a,an,ah,ai=index(large_dump,key);b,bn,bh,bi=index(small_dump,key)
    need((an,ah)==(layout(large)['bytes'],large['sha256']) and
         (bn,bh)==(layout(small)['bytes'],small['sha256']),'indexed bytes/hash differ from sealed canonical source')
    proof=prefix_zero(Path(large_dump)/'state.bundle',a,an,ah,Path(small_dump)/'state.bundle',b,bn,bh,ratio=262144//candidate_context)
    return dict(source_key=name,reference_layout=layout(large),candidate_layout=layout(small),
                reference_dump=str(large_dump),candidate_dump=str(small_dump),indices=[ai,bi],**proof)

def compare_maps(reference,candidate,large_dump,small_dump,*,draft=False,candidate_context=65536):
    registry=DRAFT if draft else TARGET;a=reference['canonical'];b=candidate['canonical']
    need(set(a)==set(b),'cross-context source inventory differs')
    need(registry.keys()<=a.keys(),'registered context arrays missing')
    proofs=[];exact=[]
    for name in sorted(a):
        if name in registry:
            proofs.append(array_proof(name,a[name],b[name],large_dump(name),small_dump(name),draft=draft,candidate_context=candidate_context))
        else:
            fields=('layout','sha256') if draft else ('sha256','bytes','dtype','shape','role')
            need(all(a[name][k]==b[name][k] for k in fields),'unregistered source shape/hash differs: '+name)
            exact.append(name)
    return dict(exact_source_keys=exact,capacity_sources=proofs,source_count=len(a))

def draft_dump(path):
    value,_=C.read(path);return (Path(path).parent/value['dump']).resolve()

def target_dump(spec,name):
    layer=int(T.LAYER.match(name)[1]);owners=[s for s in spec['stages'] if s['begin']<=layer<s['end']]
    need(len(owners)==1,'unique context-array target owner');return Path(owners[0]['dump'])

def draft_identity(reference,candidate,pairhash,*,candidate_context=65536):
    need(type(candidate_context) is int and candidate_context in (65536,131072),'supported candidate capacity required')
    need(type(reference.get('context')) is int and type(candidate.get('context')) is int
         and reference['context']==262144 and candidate['context']==candidate_context,
         'actual draft contexts must match declared capacities')
    need({k:v for k,v in reference.items() if k!='context'}==
         {k:v for k,v in candidate.items() if k!='context'}
         and reference['pair_sequence_sha256']==pairhash,
         'actual draft input/pair identity differs beyond declared context')

def run(path):
    wrapper,ws=C.read(path)
    need(wrapper['schema']=='ownrt.dedicated-cross-context-inputs.v1' and
         wrapper['reference_context']==262144 and type(wrapper['candidate_context']) is int
         and wrapper['candidate_context'] in (65536,131072),
         'explicit supported cross-context opt-in required')
    candidate_context=wrapper['candidate_context']
    spec,ss=C.read(wrapper['inputs']);need(spec['schema']=='ownrt.dedicated-parity-inputs.v1','dedicated parity inputs required')
    reference=Path(spec['reference_request']);plan,ps=C.read(spec['plan']);result,rs=C.driver_result(spec['result'])
    refplan,rps=C.read(reference/'selected-request-plan.json');refresult,rrs=C.read(reference/'result.json')
    need(refplan['context']==262144 and plan['context']==candidate_context and len(plan['stages'])==2,
         'actual contexts/two-target topology differ')
    need(len(plan['prompt_tokens'])==1677 and plan['max_new']==32 and len(result['output_ids'])==32
         and plan['prompt_tokens']==refplan['prompt_tokens'] and result['output_ids']==refresult['output_ids']
         and result['input_position']==1708,'exact1677prompt/32outputs/frontier1708 required')
    target_spec,_=C.read(reference/'target-set.prefill-provenance.json')
    dump_paths=[(reference/stage['dump']).resolve() for stage in target_spec['stages']]
    dump_paths += [Path(stage['dump']) for stage in spec['stages']]
    dump_paths += [draft_dump(reference/'draft-set.json'),draft_dump(spec['draft_set'])]
    # Bind the whole sealed reads and later range reads to the same file versions.
    snapshots={str(d/f):T.BUNDLE.identity(os.stat(d/f,follow_symlinks=False))
               for d in dump_paths for f in T.BUNDLE.FILES}
    rt=T.load_set(reference/'target-set.prefill-provenance.json');identity=rt['input_identity']
    tokenhash=lambda ids:T.sha(b''.join(struct.pack('<I',token) for token in ids))
    need(identity['position']==1708 and tokenhash(plan['prompt_tokens'])==identity['prompt_token_sha256']
         and tokenhash(result['output_ids'])==identity['output_token_sha256']
         and plan['model_identity_sha256']==identity['model_sha256'],'actual sealed input identity differs')
    raw,cs=C.trace_source(spec['commands']);commands=[json.loads(line,object_pairs_hook=T.BUNDLE.pairs) for line in raw.splitlines()]
    pairs,prefix=C.plan_pairs(plan,commands,1708)
    refpairs,rpair=C.read(reference/'canonical-pairs.json');pairhash=T.sha(json.dumps(pairs,sort_keys=True,separators=(',',':')).encode())
    need(len(pairs)==1707 and pairs==refpairs['pairs'] and pairhash==refpairs['sha256'],'actual1707 canonical pairs differ')
    ct=C.target_candidate(dict(spec,request_sha256=plan['request_sha256'],authenticated_bulk=0 if prefix is None else prefix['positions']),identity)
    need(rt['first_stage_host_history']==ct['first_stage_host_history'],'target host history differs')
    rd=D.load_set(reference/'draft-set.json');cd=D.load_set(spec['draft_set'])
    draft_identity(rd['input_identity'],cd['input_identity'],pairhash,candidate_context=candidate_context)
    need(rd['host']==cd['host'],'actual draft host identity differs')
    targets=compare_maps(rt,ct,lambda n:rt['canonical'][n]['dump'],lambda n:target_dump(spec,n),candidate_context=candidate_context)
    drafts=compare_maps(rd,cd,lambda n:draft_dump(reference/'draft-set.json'),lambda n:draft_dump(spec['draft_set']),draft=True,candidate_context=candidate_context)
    need(len(targets['exact_source_keys'])==2017 and len(drafts['exact_source_keys'])==69,'complete exact2017/69 inventory required')
    need(len(set(spec['process_receipts']))==len(spec['process_receipts'])==3,'allthree native process receipts required')
    receipts=[]
    for p in spec['process_receipts']:
        receipt,source=C.read(p)
        need(receipt['passed'] is True and not receipt.get('error') and receipt.get('teardown')
             and all(t['status']=='complete' and t['safe_to_exit'] is True and t['idle_marker_complete'] is True
             and t['in_flight']==t['live_bytes']==0 and not t['error'] for t in receipt['teardown']),
             'clean native process teardown required')
        receipts.append(source)
    for name,before in snapshots.items():
        need(before==T.BUNDLE.identity(os.stat(name,follow_symlinks=False)),'sealed source changed during context comparison')
    return dict(schema='ownrt.dedicated-cross-context-proof.v1',passed=True,
        scope=f'Explicit262K-to{candidate_context//1024}K first-dimension capacity equivalence; original full hashes/layouts/seals preserved, no fake same-context hashes. Not independent model correctness or speed proof.',
        reference_context=262144,candidate_context=candidate_context,input_position=1708,outputs=32,canonical_pairs=1707,
        pair_sequence_sha256=pairhash,target=targets,draft=drafts,
        sources=[ws,ss,ps,rs,rps,rrs,cs,rpair]+([] if prefix is None else prefix['sources'])+rt['sources']+ct['sources']+rd['sources']+cd['sources']+receipts,
        helper_sha256=T.sha(Path(__file__).read_bytes()),sealed_reader_sha256=T.sha(T.READER_PATH.read_bytes()))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    try:result=run(args.manifest)
    except (ValueError,KeyError,OSError,TypeError,struct.error,UnicodeError) as error:result=dict(schema='ownrt.dedicated-cross-context-proof.v1',passed=False,input_error=str(error))
    with args.out.open('x') as file:json.dump(result,file,indent=2);file.write('\n')
    raise SystemExit(0 if result['passed'] else 1)
