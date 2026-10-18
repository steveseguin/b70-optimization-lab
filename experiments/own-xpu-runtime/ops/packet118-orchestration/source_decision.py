"""Fixed owner-authorized composition, never a benchmark-driven prefix search."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet118-record-bundle'
SOURCE_RULE='packet118.fixed-prefix80128.v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def read_sources():
 rows={n:dict(path=str((O/'inputs'/n).relative_to(ROOT)),sha256=sha(O/'inputs'/n)) for n in ('bundle6-decision.json','prefix-preregistration.json','prefix-selection.json')}
 parent=json.loads((O/'inputs/bundle6-decision.json').read_text())
 prefix=json.loads((O/'inputs/prefix-selection.json').read_text())
 assert parent['candidate']['other_fusion']=='fused' and parent['candidate']['target_head']=='split'
 assert prefix['draft_vocab_rows']==80128 and prefix['preregistration_sha256']==rows['prefix-preregistration.json']['sha256']
 assert sha(O/'inputs/prefix-selection.json')==sha(P/'prefix-calibration/selection.json')
 return rows
def decide(sources):
 assert sources==read_sources(),'fixed source snapshot changed'
 return dict(other_fusion='fused',target_head='split',draft_prefix='80128')
def selections():
 parent=json.loads((O/'inputs/bundle6-decision.json').read_text())
 return parent['control'],dict(parent['candidate'],draft_prefix='80128')
def control_view():
 control,_=selections()
 # Immutable packet103 selection directory, not its mutable active metadata.
 keys=('dense','hc','experts','host','route','norm','recurrence','draft_head','head','hc_norm','down','draft_attention')
 return STAGE/'packet103-record-bundle/selections'/('--'.join(control[k] for k in keys)+'--placement-1')
def main():
 sources=read_sources();control,candidate=selections();lineage=control_view()
 row=dict(schema='packet118.source-decision.v1',source_rule=SOURCE_RULE,evidence_rule='identical-selection-v1',threshold_ratio=1.01,control=control,candidate=candidate,sources=sources,device_executed=False,extra_dimension_selected=True,control_lineage=str(lineage.relative_to(ROOT)),control_seal_sha256=sha(lineage/'screen-seal.json'),prefix_rule='80128 fixed by packet114 non-benchmark preregistration; never retune from benchmark data')
 ident=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]
 (O/'decisions').mkdir(exist_ok=True);path=O/'decisions'/(ident+'.json')
 if path.exists():assert json.loads(path.read_text())==row
 else:save(path,row)
 save(O/'decision.json',dict(path=str(path.relative_to(ROOT)),sha256=sha(path),identity=ident))
 print(json.dumps(dict(decision=ident,control='packet103 bundle5',candidate='bundle6 + prefix80128',threshold_ratio=1.01)))
if __name__=='__main__':main()
