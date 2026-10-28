#!/usr/bin/env python3
"""Fixed cold244-token target-only observation; saved CPU output is never a runtime oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time
import colocated_control as C
BASE=C.base
HERE=Path(__file__).resolve().parent
INPUT=HERE.parent/'reference-one-row/input.json'
PREPARED=HERE.parent/'reference-one-row/prepared-plan.json'
IDENTITY=HERE.parent/'reference-one-row/identity.json'

def make_plan(config):
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    p=json.loads(PREPARED.read_text());identity=json.loads(IDENTITY.read_text());tokens=json.loads(INPUT.read_text())['tokens']
    BASE.require(len(tokens)==244 and BASE.digest(INPUT)==identity['input_json_sha256'],'exact saved244token input')
    BASE.require(hashlib.sha256(b''.join(struct.pack('<i',t) for t in tokens)).hexdigest()==identity['prefix_le_i32_sha256'],'packed token identity')
    out=Path(cfg['output']).resolve();BASE.require(not out.exists(),'fresh exclusive output')
    receipt=json.loads(Path(cfg['build_receipt']).read_text())
    BASE.require(receipt['binary_sha256']==p['binary_sha256'],'same prepared native binary')
    for stage in p['stages']:
        rank=stage['id'];native=out/f'native/rank{rank}'
        stage['argv']=BASE.replace_options(stage['argv'],{'--context':4096,'--max-new':1,'--retain-steps':1,'--shared':out/'transport/shared.bin','--output':native},{'--draft-rank'})
        BASE.require(not any(x.startswith('--draft') or x.startswith('--oracle') or x.startswith('--provider') or x.startswith('--pipeline') for x in stage['argv']),'target-only no oracle/draft/pipeline arguments')
        stage['native_output']=str(native)
        for key,value in stage['environment'].items():
            if key in ('SYCL_CACHE_DIR','NEO_CACHE_DIR','XDG_CACHE_HOME'):stage['environment'][key]=str(out/f'cache{rank}'/key)
    p.update(schema='ownrt.reference-one-row-plan.v1',config=str(config),output=str(out),context=4096,max_new=1,prompt_tokens=tokens,
        eos_token_ids=[],execution_ready=True,mode='target-only-none',live_draft=False,use_proposals=False,
        diagnostic_only=True,limits='Single244token target-only observation at4096context; saved CPU16568 is comparison only, no runtime oracle, quality or speed claim.')
    for path in (Path(__file__).resolve(),HERE/'colocated_control.py',config,INPUT,PREPARED,IDENTITY,Path(cfg['build_receipt'])):p['pins'][str(path)]=BASE.digest(path)
    return p

def request(a,transport,plan,began):
    result=a.NativeController(transport,a.BASE.Draft('none'),False,False,prefill=0,start=0).run(plan['prompt_tokens'],1,())
    BASE.require(len(result['tokens'])==1 and result['stats']['guesses']==0,'exact one target-only output/no guesses')
    rows=result['rank_trace']
    for rank in (0,1):
        selected=[r for r in rows if r['rank']==rank and r['op']==a.BASE.HALF]
        BASE.require([r['position'] for r in selected]==list(range(244)) and all(r['speculative'] is False for r in rows),'all244serial positions per rank')
    layers=[]
    for stage in plan['stages']:
        directory=Path(stage['native_output'])/'step1';files=sorted(directory.glob('layer-*.bf16'))
        BASE.require({f.name for f in files}=={f'layer-{n:02d}.bf16' for n in range(stage['begin'],stage['end'])},'actual rank-owned capture inventory')
        for f in files:
            BASE.require(f.is_file() and not f.is_symlink() and f.stat().st_size==40960,'actual F32 capture extent40960')
            layers.append(dict(path=str(f),bytes=40960,dtype='F32 little-endian',sha256=BASE.digest(f)))
    BASE.require(len(layers)==48,'all48 layer captures')
    result.update(actual_output_ids=result['tokens'],reference_cpu_argmax=16568,historical_engine_token=6343,
        matches_saved_cpu_argmax=result['tokens']==[16568],layer_captures=layers,context=4096,
        evidence_label='Independent-reference diagnostic observation; mismatch is a finding, not native lifecycle failure.',
        request_started_monotonic_s=began,request_finished_monotonic_s=time.monotonic())
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');a=ap.parse_args()
    if not a.run:BASE.save(a.plan,make_plan(a.config));return
    p=json.loads(a.plan.read_text());BASE.require(p==make_plan(p['config']),'exact diagnostic plan/source pins')
    BASE.require(a.admission and a.unit,'admission and owning unit');ad=json.loads(a.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(a.plan),'admission plan SHA')
    C.execute(p,ad,a.unit,request=request)
if __name__=='__main__':main()
