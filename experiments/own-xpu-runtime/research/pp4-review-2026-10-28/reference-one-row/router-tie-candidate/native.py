#!/usr/bin/env python3
"""General tie-order target-only diagnostic; full state is retained, not declared neutral."""
import argparse,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('router_tie_candidate_plan',HERE/'candidate_plan.py');P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)
R,C,BASE=P.R,P.C,P.BASE

def make_plan(config):
 p=P.make_plan(config)
 for s in p['stages']:
  assert 'OWNRT_L4_RAW_HISTORY' not in s['environment'] and 'OWNRT_L4_PREP_HISTORY' not in s['environment']
 p.update(schema='ownrt.router-tie-reference244-candidate.v1',selection_identity_changed=p['reference_tie_diagnostic'],expected_saved_cpu_argmax=16568,require_old_native_state_equality=False,retain_full_state=True,limits='One fixed244-prefix/1-output diagnostic; general reference tie-order treatment. Retain both full DUMP4 bundles. CPU16568 is posthoc comparison only, not runtime oracle or quality proof.')
 p['pins'][str(Path(__file__).resolve())]=BASE.digest(__file__)
 reader=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py');p['pins'][str(reader)]=BASE.digest(reader)
 return p

def request(a,transport,plan,began):
 r=R.request(a,transport,plan,began)
 journals=[]
 for stage in plan['stages']:
  path=Path(stage['native_output'])/'router-tie-diagnostic.jsonl'
  if not plan['reference_tie_diagnostic']:
   BASE.require(not path.exists(),'default OFF has no diagnostic journal')
   continue
  rows=[json.loads(line)for line in path.read_text().splitlines()]
  expected={(position,layer)for position in range(244)for layer in range(stage['begin'],stage['end'])}
  BASE.require(len(rows)==len(expected) and {(x['position'],x['layer'])for x in rows}==expected,'one diagnostic per actual layer/token')
  for row in rows:
   BASE.require(row['schema']=='ownrt.router-tie-diagnostic.v1' and row['verified_upload'] is True,'actual checked diagnostic record')
   BASE.require(row['weights_before_sha256']==row['weights_after_sha256'],'native selected weights unchanged')
   BASE.require(len(row['old_ids'])==len(row['new_ids'])==10 and len(set(row['new_ids']))==10,'unique ten selected IDs')
   BASE.require(row['changed_slots']==sum(a!=b for a,b in zip(row['old_ids'],row['new_ids'])),'actual changed slot accounting')
   words=row['changed_raw_words']
   BASE.require(len(words)==row['changed_slots'] and {x['slot']for x in words}=={i for i,(a,b)in enumerate(zip(row['old_ids'],row['new_ids']))if a!=b} and all(x['old_word']==x['new_word']for x in words),'actual equal-word evidence for every changed slot')
  journals.append(dict(path=str(path),sha256=BASE.digest(path),rows=len(rows),changed_rows=sum(bool(x['changed_slots'])for x in rows),changes=[x for x in rows if x['changed_slots']]))
 r['router_tie_journals']=journals
 assert not any(transport.pending)
 for rank in (0,1):transport.call(rank,4,position=244)
 reader_path=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/state-bundle/reader.py')
 spec=importlib.util.spec_from_file_location('router_tie_candidate_reader',reader_path);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
 sealed={}
 for stage in plan['stages']:
  transport.check();sealed[str(stage['id'])]=reader.read_state(Path(stage['native_output'])/'state-244')
 r['verified_full_state_sources']=sealed
 r.update(selection_identity_changed=plan['reference_tie_diagnostic'],old_native_state_equality_required=False,full_state_paths=[str(Path(s['native_output'])/'state-244')for s in plan['stages']])
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--run',action='store_true');ap.add_argument('--admission',type=Path);ap.add_argument('--unit');x=ap.parse_args()
 if not x.run:BASE.save(x.plan,make_plan(x.config));return
 p=json.loads(x.plan.read_text());BASE.require(p==make_plan(p['config']),'exact candidate plan/source pins');ad=json.loads(x.admission.read_text());BASE.require(ad['plan_sha256']==BASE.digest(x.plan),'admission plan SHA');C.execute(p,ad,x.unit,request=request)
if __name__=='__main__':main()
