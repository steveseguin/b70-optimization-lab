#!/usr/bin/env python3
"""Prepared guarded 244/1 request + two existing DUMP4 calls. Not executed."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
HERE=Path(__file__).resolve().parent
GATE=HERE.parents[1]/'dedicated-gate'
sys.path.insert(0,str(GATE))
sys.path.insert(0,str(HERE.parent/'router-replay'))
import l4_current_plan as P
R=P.R
C,BASE=R.C,R.BASE
READER=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py')
spec=importlib.util.spec_from_file_location('router_sealed_reader',READER)
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
FIELDS={'hc.a.norm': 40960, 'hc.a.low': 1280, 'hc.a.act': 1280, 'hc.a.gate': 40960, 'hc.a.mix': 10240, 'hc.a.inject': 16, 'gdn.qkv': 40960, 'gdn.z': 24576, 'gdn.a': 192, 'gdn.b': 192, 'gdn.conv': 40960, 'gdn.y': 24576, 'gdn.gated': 24576, 'gdn.history': 122880, 'gdn.state': 3145728, 'attention': 10240, 'hc.f.norm': 40960, 'hc.f.low': 1280, 'hc.f.act': 1280, 'hc.f.gate': 40960, 'hc.f.mix': 10240, 'hc.f.inject': 16, 'alternate:gdn.history': 122880, 'alternate:gdn.state': 3145728}
def stamp(p):
 s=p.stat(follow_symlinks=False);return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def extract_layers(directory,root,layers,check):
    # Pin identities across the one whole-owner verification and every selected read.
    before={p:stamp(p) for p in directory.iterdir()}
    def unchanged():
        assert set(directory.iterdir())==set(before),'sealed source inventory changed'
        for p,identity in before.items():assert stamp(p)==identity,'sealed source changed during extraction'
    check();verified=reader.read_state(directory)
    unchanged()
    table={}
    for line in (directory/'state-index.tsv').read_text().splitlines()[1:]:
        name,offset,length,digest=line.split('\t');table[name]=(int(offset),int(length),digest)
    records=[]
    with (directory/'state.bundle').open('rb') as f:
        fs=os.fstat(f.fileno())
        assert (fs.st_dev,fs.st_ino,fs.st_size,fs.st_mtime_ns,fs.st_ctime_ns)==before[directory/'state.bundle']
        for layer in layers:
            names={(f'alternate-blk.{layer}.{k.split(":",1)[1]}.bin' if k.startswith('alternate:') else f'blk.{layer}.{k}.bin'):n for k,n in FIELDS.items()}
            dest=root/f'layer{layer}';assert not dest.exists();dest.mkdir()
            for name,size in names.items():
                check();unchanged();offset,length,digest=table[name]
                assert length==size and verified[name]==digest
                f.seek(offset);data=f.read(size)
                assert len(data)==size and hashlib.sha256(data).hexdigest()==digest
                (dest/name).write_bytes(data)
            unchanged()
            for name in ('state-index.tsv','state.json','state-seal.txt'):shutil.copy2(directory/name,dest/name)
            record=dict(layer=layer,source=str(directory),source_bundle_sha256=(directory/'state-seal.txt').read_text().splitlines()[2],source_seal_sha256=hashlib.sha256((directory/'state-seal.txt').read_bytes()).hexdigest(),
                source_identities={p.name:list(identity) for p,identity in before.items()},
                full_seal_verified=True,selected={name:table[name][2] for name in names},bytes=sum(names.values()),
                scope='L4 transient row243 plus post-row active/spare state and history. Neither state bank is asserted pre-row243. Sequence244 is dump label; earlier transient token history absent.')
            BASE.save(dest/'extraction.json',record);records.append(record)
    unchanged()
    return records

def extract(directory,dest,layer,check):
    # Compatibility for the original single-layer fixture/caller.
    records=extract_layers(directory,dest.parent,[layer],check)
    generated=dest.parent/f'layer{layer}'
    if generated!=dest:generated.rename(dest)
    return records[0]

def make_plan(config):
    p=P.make_plan(config)
    p.update(schema='ownrt.reference-l4-dump4-plan.v1',router_layers=[4],dump_sequence=244,
        prune_verified_full_bundles=True,router_dump_transient_budget_bytes=1024**3,limits='Fixed244/1 target-only plus one DUMP4 per rank after request; selected L4 fields only retained after full sealed verification. Not a timing run.')
    for path in (Path(__file__).resolve(),Path(P.__file__).resolve(),READER):p['pins'][str(path)]=BASE.digest(path)
    return p

def request(a,transport,plan,began):
    result=R.request(a,transport,plan,began)
    assert result['actual_output_ids'] and len(result['actual_output_ids'])==1
    assert not any(transport.pending),'DUMP only after both committed/idle'
    # Budget is a transient-output forecast, not a new storage floor.
    transport.check()
    assert shutil.disk_usage(Path(plan['output']).parent).free>=plan['evidence_floor_bytes']+plan['router_dump_transient_budget_bytes'],'DUMP forecast plus existing evidence floor'
    # Two explicit commands; controller dumps=True would dump rank0 only and repeatedly.
    for rank in (0,1):transport.call(rank,4,position=244)
    assert sum((Path(stage['native_output'])/'state-244/state.bundle').stat().st_size for stage in plan['stages'])<=plan['router_dump_transient_budget_bytes'],'DUMP exceeds forecast; retain incident evidence'
    records=[];root=Path(plan['output'])/'l4-captures';root.mkdir()
    for owner in plan['stages']:
        layers=[layer for layer in plan['router_layers'] if owner['begin']<=layer<owner['end']]
        directory=Path(owner['native_output'])/'state-244'
        records.extend(extract_layers(directory,root,layers,transport.check))
    records.sort(key=lambda x:x['layer'])
    assert [r['layer'] for r in records]==plan['router_layers']
    # Only newly-created complete sealed full dumps are pruned AFTER all requested extracts verify.
    # On ANY failure above full dumps remain available for incident handling.
    if plan['prune_verified_full_bundles']:
        for stage in plan['stages']:
            directory=Path(stage['native_output'])/'state-244'
            assert set(p.name for p in directory.iterdir())==reader.FILES
            for name in sorted(reader.FILES):(directory/name).unlink()
            directory.rmdir()
    result.update(l4_captures=records,l4_capture_bytes=sum(x['bytes'] for x in records),
        quality_scope='L4 post-row intermediates plus active/spare recurrent buffers retained. Neither bank is asserted to be pre-row243; CPU initial state is pre-whole-batch, not pre-row243.')
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');args=ap.parse_args()
    if not args.run:BASE.save(args.plan,make_plan(args.config));return
    p=json.loads(args.plan.read_text());BASE.require(p==make_plan(p['config']),'exact source/config plan pins')
    BASE.require(args.admission and args.unit,'existing admission and unit required');ad=json.loads(args.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(args.plan),'plan admission SHA')
    C.execute(p,ad,args.unit,request=request)
if __name__=='__main__':main()
