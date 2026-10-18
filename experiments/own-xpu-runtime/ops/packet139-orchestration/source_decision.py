"""Review26 preregistration: B five-view bracket and A composed smoke, no A grid."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet139-record-bundle'
SOURCE_RULE='packet139.bundle8-plus-token-input-both.review26.v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,indent=2)+'\n')
def parent_decision():return json.loads((O/'inputs/bundle8-selection.json').read_text())
def read_sources():
 rows=json.loads((O/'inputs/parent-pins.json').read_text())
 for n,h in rows.items():assert sha(ROOT/n)==h,'parent identity changed: '+n
 return rows
def selections():
 base=parent_decision();keys=('dense','hc','experts','host','route','norm','recurrence','draft_head','head','hc_norm','down','draft_attention','other_fusion','target_head','draft_prefix','rollback_state')
 base={k:base[k] for k in keys}
 assert base['rollback_state']=='banks'
 return dict(base,token_input='original'),dict(base,token_input='both')
def main():
 control,candidate=selections()
 row=dict(schema='packet139.source-decision.v1',source_rule=SOURCE_RULE,evidence_rule='review26-B-v5-plus-A-smoke',threshold_ratio=1.005,max_control_drift_percent=1.0,control=control,candidate=candidate,sources=read_sources(),device_executed=False,composition_kind='bundle8+token_input=both',protocol='B original/both/original/both/original one load; A composed 12x64; no second-lane grid',supersedes_policy='Read pinned scripts/packet49_record_threshold.json at submission prepare time; bundle8 record if posted, otherwise current last record',preregistered_before_bundle9_device_data=True)
 ident=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16];path=O/'decisions'/(ident+'.json');save(path,row)
 save(O/'decision.json',dict(path=str(path.relative_to(ROOT)),sha256=sha(path),identity=ident))
if __name__=='__main__':main()
