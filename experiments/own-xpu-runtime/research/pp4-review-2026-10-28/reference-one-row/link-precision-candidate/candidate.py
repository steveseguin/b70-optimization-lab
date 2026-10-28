#!/usr/bin/env python3
"""Changed-arithmetic target-only diagnostic; full state is retained, not declared neutral."""
import argparse,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('precision_candidate_plan',HERE/'candidate_plan.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
R,C,BASE=P.R,P.C,P.BASE

def make_plan(config):
 p=P.make_plan(config)
 for s in p['stages']:
  assert 'OWNRT_L4_RAW_HISTORY' not in s['environment'] and 'OWNRT_L4_PREP_HISTORY' not in s['environment']
 p.update(schema='ownrt.precise-link-reference244-candidate.v1',arithmetic_identity_changed=True,expected_saved_cpu_argmax=16568,require_old_native_state_equality=False,retain_full_state=True,limits='One fixed244-prefix/1-output diagnostic; changed link precision. Retain both full DUMP4 bundles. CPU16568 is posthoc comparison only, not runtime oracle or quality proof.')
 p['pins'][str(Path(__file__).resolve())]=BASE.digest(__file__)
 reader=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py');p['pins'][str(reader)]=BASE.digest(reader)
 return p

def request(a,transport,plan,began):
 r=R.request(a,transport,plan,began)
 assert not any(transport.pending)
 for rank in (0,1):transport.call(rank,4,position=244)
 reader_path=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py')
 spec=importlib.util.spec_from_file_location('precision_candidate_reader',reader_path);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 sealed={}
 for stage in plan['stages']:
  transport.check();sealed[str(stage['id'])]=reader.read_state(Path(stage['native_output'])/'state-244')
 r['verified_full_state_sources']=sealed
 r.update(arithmetic_identity_changed=True,old_native_state_equality_required=False,full_state_paths=[str(Path(s['native_output'])/'state-244')for s in plan['stages']])
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');x=ap.parse_args()
 if not x.run:BASE.save(x.plan,make_plan(x.config));return
 p=json.loads(x.plan.read_text());BASE.require(p==make_plan(p['config']),'exact candidate plan/source pins');ad=json.loads(x.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(x.plan),'admission plan SHA');C.execute(p,ad,x.unit,request=request)
if __name__=='__main__':main()
