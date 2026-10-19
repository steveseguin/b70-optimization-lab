import hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
for row in json.loads((P/'restore-inputs.json').read_text())['records']:
 source=Path(row['original']);dest=P/row['destination']
 assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==row['digest']
 if dest.exists():assert hashlib.sha256(dest.read_bytes()).hexdigest()==row['digest'];continue
 target=dest.resolve();target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
print('Verified/restored unchanged inputs; run build_engine.py under CPU placement constraints')
