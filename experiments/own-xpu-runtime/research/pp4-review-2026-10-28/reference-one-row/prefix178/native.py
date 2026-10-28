#!/usr/bin/env python3
"""Prefix178 target-only diagnostic; full state is retained, not declared neutral."""
import argparse,importlib.util,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('precision_candidate_plan',HERE/'current_plan.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
R,C,BASE=P.R,P.C,P.BASE

def make_plan(config):
 p=P.make_plan(config)
 for s in p['stages']:
  assert 'OWNRT_LOOKUP_VIEW' not in s['environment'],'mapping must be absent, including value0'
  assert 'OWNRT_L4_RAW_HISTORY' not in s['environment'] and 'OWNRT_L4_PREP_HISTORY' not in s['environment']
 p.update(schema='ownrt.reference-prefix178-candidate.v1',arithmetic_identity_changed=False,expected_saved_cpu_argmax=None,require_old_native_state_equality=False,retain_full_state=True,limits='First178 tokens of fixed244 prefix; bare-link mapping OFF. Retain both full DUMP4 bundles. No saved argmax oracle exists for this prefix.')
 p['pins'][str(Path(__file__).resolve())]=BASE.digest(__file__)
 reader=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py');p['pins'][str(reader)]=BASE.digest(reader)
 return p

def request(a,transport,plan,began):
    result=a.NativeController(transport,a.BASE.Draft('none'),False,False,prefill=0,start=0).run(plan['prompt_tokens'],1,())
    BASE.require(len(result['tokens'])==1 and result['stats']['guesses']==0,'exact one target-only output/no guesses')
    rows=result['rank_trace']
    for rank in (0,1):
        selected=[r for r in rows if r['rank']==rank and r['op']==a.BASE.HALF]
        BASE.require([r['position'] for r in selected]==list(range(178)) and all(r['speculative'] is False for r in rows),'all178serial positions per rank')
    layers=[]
    for stage in plan['stages']:
        directory=Path(stage['native_output'])/'step1';files=sorted(directory.glob('layer-*.bf16'))
        BASE.require({f.name for f in files}=={f'layer-{n:02d}.bf16' for n in range(stage['begin'],stage['end'])},'actual rank-owned capture inventory')
        for f in files:
            BASE.require(f.is_file() and not f.is_symlink() and f.stat().st_size==40960,'actual F32 capture extent40960')
            layers.append(dict(path=str(f),bytes=40960,dtype='F32 little-endian',sha256=BASE.digest(f)))
    BASE.require(len(layers)==48,'all48 layer captures')
    result.update(actual_output_ids=result['tokens'],reference_cpu_argmax=None,historical_engine_token=None,
        matches_saved_cpu_argmax=None,layer_captures=layers,context=4096,
        evidence_label='Independent-reference diagnostic observation; mismatch is a finding, not native lifecycle failure.',
        request_started_monotonic_s=began,request_finished_monotonic_s=time.monotonic())
    assert not any(transport.pending)
    for rank in (0,1):transport.call(rank,4,position=178)
    result['full_state_paths']=[str(Path(stage['native_output'])/'state-178')for stage in plan['stages']]
    reader_path=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py')
    spec=importlib.util.spec_from_file_location('prefix178_bundle_reader',reader_path)
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    result['verified_full_state_sources']={}
    for stage,path in zip(plan['stages'],result['full_state_paths']):
        transport.check()
        result['verified_full_state_sources'][str(stage['id'])]=reader.read_state(Path(path))
    result['retained_complete_dumps']=True
    return result


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');x=ap.parse_args()
 if not x.run:BASE.save(x.plan,make_plan(x.config));return
 p=json.loads(x.plan.read_text());BASE.require(p==make_plan(p['config']),'exact candidate plan/source pins');ad=json.loads(x.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(x.plan),'admission plan SHA');C.execute(p,ad,x.unit,request=request)
if __name__=='__main__':main()
