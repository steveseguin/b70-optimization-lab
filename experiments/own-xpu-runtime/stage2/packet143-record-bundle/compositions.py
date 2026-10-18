"""Sixteen fixed-load compositions; no benchmark evidence is implicit in a seal."""
import hashlib,itertools,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
DIMENSIONS=('attention_layout','expert_gate_up_layout','hc_layout','token_input')
DOMAINS=(('production','order600'),)*3+(('original','both'),)
BASE=dict(zip(DIMENSIONS,('production','production','production','original')))
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,row):path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(row,indent=2)+'\n')
def validate(row):
 if set(row)!=set(DIMENSIONS) or any(row[k] not in d for k,d in zip(DIMENSIONS,DOMAINS)):raise ValueError('exactly four registered dimensions required')
 return dict(row)
def key(row):
 validate(row);return '--'.join(row[k] for k in DIMENSIONS)
def all_compositions():return [dict(zip(DIMENSIONS,v)) for v in itertools.product(*DOMAINS)]
def path(row):return P/'selections'/key(row)
def native(row):
 validate(row);s=read(P/'lineage-inputs/bundle8-selection.json');s['choices'].update(row)
 table=read(P/'lineage-inputs/token-table-receipt.json')
 s['choices'].update(token_table_path=table['path'],token_table_sha256=table['sha256'])
 return s
def selected():
 row=validate(read(P/'active-composition.json'));assert read(P/'selection.json')==native(row),'active native selection mismatch';return row
