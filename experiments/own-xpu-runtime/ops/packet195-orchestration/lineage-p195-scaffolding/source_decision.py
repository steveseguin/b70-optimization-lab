"""Preregister exactly bundle7 and bundle7 plus banked rollback."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet195-record-bundle-diet'
SOURCE_RULE='packet136.bundle7-plus-p131b-snapshot-banks.v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def parent_decision():return json.loads((O/'inputs/bundle7-decision.json').read_text())
def read_sources():
 names=('bundle6-decision.json','prefix-preregistration.json','prefix-selection.json','bundle7-decision.json','bundle7-selection.json','bundle7-memory-plan.json','banks-native.json')
 rows={n:dict(path=str((O/'inputs'/n).relative_to(ROOT)),sha256=sha(O/'inputs'/n)) for n in names}
 prefix=json.loads((O/'inputs/prefix-selection.json').read_text())
 assert prefix['draft_vocab_rows']==80128 and prefix['preregistration_sha256']==rows['prefix-preregistration.json']['sha256']
 assert sha(O/'inputs/prefix-selection.json')==sha(P/'prefix-calibration/selection.json')
 return rows
def decide(sources):
 assert sources==read_sources(),'fixed source snapshot changed'
 return selections()[1]
def selections():
 base=parent_decision()['candidate']
 return dict(base,rollback_state='copy'),dict(base,rollback_state='banks')
def control_view():
 from composite_jobs import view
 return view(selections()[0])
def parent_candidate_view():return STAGE/'packet131b-snapshot-banks/selections/candidate'
def main():
 control,candidate=selections()
 row=dict(schema='packet136.source-decision.v1',source_rule=SOURCE_RULE,evidence_rule='identical-native-selection-both-v4-lanes-v1',threshold_ratio=1.005,control=control,candidate=candidate,sources=read_sources(),device_executed=False,composition_kind='bundle7+snapshot-banks',prefix_rule='80128 fixed by packet114 non-benchmark preregistration; never retune',supersedes='cmvdx8urg0068rf01vvb32bcs',record_tok_s=58.223834,protocol='v4 C/X/C/X/C; fresh allocation per load')
 ident=hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:16]
 (O/'decisions').mkdir(exist_ok=True);path=O/'decisions'/(ident+'.json')
 if path.exists():assert json.loads(path.read_text())==row
 else:save(path,row)
 save(O/'decision.json',dict(path=str(path.relative_to(ROOT)),sha256=sha(path),identity=ident))
 print('Two compositions preregistered; device evidence pending')
if __name__=='__main__':main()
