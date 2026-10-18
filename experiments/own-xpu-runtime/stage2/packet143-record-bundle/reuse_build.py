from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def verify_native():
 row=json.loads((P/'v5/evidence/build.json').read_text());assert row['passed']
 for group in ('sources','artifacts'):
  for n,h in row[group].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 return row
