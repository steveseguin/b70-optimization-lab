#!/usr/bin/env python3
"""Recheck complete one-card receipts; never promote a two-card win by analogy."""
import json,hashlib,math
from pathlib import Path
import window as W
import queue_runner as Q
import suite_driver as S
from views import digest
P=Path(__file__).resolve().parent
STAGES=(('production-before','production'),('port','port'),('production-after','production'))
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
RECORD=24.338653323339745

def decision(rows):
 W.require(len(rows)==3,'complete production/port/production bracket required')
 rates=[r[METRIC]['median'] for r in rows]
 W.require(all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in rates),'invalid speed')
 signatures=[[(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in row['requests']] for row in rows]
 W.require(signatures[0]==signatures[1]==signatures[2],'bracket output identity differs')
 drift=max(rates[0],rates[2])/min(rates[0],rates[2])-1
 return dict(passed=rates[1]>max(rates[0],rates[2],RECORD) and drift<=0.03,
             rates=rates,control_drift=drift,control_drift_limit=0.03,
             gain_over_slower_control=rates[1]/min(rates[0],rates[2])-1,
             gain_over_faster_control=rates[1]/max(rates[0],rates[2])-1,
             previous_record=RECORD,policy='Port must beat both controls and the saved one-card record; controls within 3%. No retry or best-of selection.',
             device_quality='same unchanged p49 oracle, tokens and full retained layer checks',
             strict_512_gate=False,external_submission_authorized=False)

def verify_chain(root,view):
 root=Path(root).resolve();W.require(root.is_relative_to(P/'evidence'),'chain outside packet evidence')
 q=S.read(root/'queue.json');W.require(q.get('passed') is True and q.get('completed')==list(Q.ORDER) and q.get('view')==view,'incomplete/wrong-view chain')
 pins={str(root/'queue.json'):S.sha(root/'queue.json')};boot=None
 for name in Q.ORDER:
  path=root/name/'window.json';r=Q.verify_success(name,root,0,0)
  W.require(r.get('view')==view and r.get('selection_sha256')==digest(view),'window selection differs')
  W.require(r.get('build_receipt_sha256')==S.sha(P/'build-receipt.json'),'window sealed build differs')
  W.prerequisite(path,'K1' if name.startswith('K1') else name,r)
  if boot is None:boot=r['boot_id']
  W.require(r['boot_id']==boot,'chain boot changed')
  pins[str(path)]=S.sha(path)
 manifest=S.oracle_inputs();summary=S.summarize(root/'WS128/run','WS128',manifest)
 stored=S.read(root/'WS128/run/summary.json')
 W.require(stored[METRIC]==summary[METRIC] and stored.get('view')==view,'summary differs from native outputs')
 for f in (root/'WS128/run/summary.json',root/'WS128/run/run/receipt.json'):
  pins[str(f)]=S.sha(f)
 summary['miss_path']=r['miss_path']
 return summary,pins,boot

def compare(root):
 W.build_gate();rows=[];pins={};boots=[]
 for folder,view in STAGES:
  row,files,boot=verify_chain(Path(root)/folder,view);rows.append(row);pins.update(files);boots.append(boot)
 W.require(len(set(boots))==1,'matched bracket must share boot')
 W.require(len({row['miss_path'] for row in rows})==1,'matched bracket miss path differs')
 result=decision(rows);result.update(schema='packet58j.bracket.v1',sources=pins,build_receipt_sha256=S.sha(P/'build-receipt.json'))
 return result

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);args=ap.parse_args();print(json.dumps(compare(args.root),indent=2))
