"""Bundle8 BASE is byte-identical bundle7; its prefix is never selected from timing."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet124b-record-bundle'
SOURCE_RULE='packet124b.bundle7-identical-k2-projection-drainfix.v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def parent_decision():return json.loads((O/'inputs/bundle7-decision.json').read_text())
def read_sources():
 names=('bundle6-decision.json','prefix-preregistration.json','prefix-selection.json','bundle7-decision.json','bundle7-selection.json','bundle7-memory-plan.json')
 rows={n:dict(path=str((O/'inputs'/n).relative_to(ROOT)),sha256=sha(O/'inputs'/n)) for n in names}
 parent=parent_decision();prefix=json.loads((O/'inputs/prefix-selection.json').read_text())
 assert parent['candidate']['other_fusion']=='fused' and parent['candidate']['target_head']=='split' and parent['candidate']['draft_prefix']=='80128'
 assert prefix['draft_vocab_rows']==80128 and prefix['preregistration_sha256']==rows['prefix-preregistration.json']['sha256']
 assert sha(O/'inputs/prefix-selection.json')==sha(P/'prefix-calibration/selection.json')
 for name,item in parent['sources'].items():assert sha(O/'inputs'/name)==item['sha256']
 return rows
def decide(sources):
 assert sources==read_sources(),'fixed source snapshot changed'
 return dict(other_fusion='fused',target_head='split',draft_prefix='80128')
def selections():
 row=parent_decision();return row['control'],row['candidate']
def control_view():return ROOT/parent_decision()['control_lineage']
def parent_candidate_view():
 from bundle_selection import KEYS,name
 return STAGE/'packet118-record-bundle/selections'/(name(*(selections()[1][k] for k in KEYS))+'--placement-1')
def main():
 sources=read_sources();control,candidate=selections();lineage=control_view()
 row=dict(schema='packet124.source-decision.v1',source_rule=SOURCE_RULE,evidence_rule='bundle7-identical-selection-v1',threshold_ratio=1.01,control=control,candidate=candidate,sources=sources,device_executed=False,composition_kind='bundle7-identical',control_lineage=str(lineage.relative_to(ROOT)),control_seal_sha256=sha(lineage/'screen-seal.json'),prefix_rule='80128 fixed by packet114 non-benchmark preregistration; never retune from benchmark data',inherited_composite_decision_sha256=sha(O/'inputs/bundle7-decision.json'),claim='K2 Python selection projection and inherited drain repair only; no new performance claim. Read original bundle7 smoke/composites; never parent chain state or ready.json.')
 ident=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]
 (O/'decisions').mkdir(exist_ok=True);path=O/'decisions'/(ident+'.json')
 if path.exists():assert json.loads(path.read_text())==row
 else:save(path,row)
 save(O/'decision.json',dict(path=str(path.relative_to(ROOT)),sha256=sha(path),identity=ident))
 print(json.dumps(dict(decision=ident,candidate='bundle8 BASE = bundle7 + drain fix',threshold_ratio=1.01)))
if __name__=='__main__':main()
