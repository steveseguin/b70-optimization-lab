import json
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.parent
for n,file in [('two',S/'packet136-record-bundle/engine-commands.json'),('one',S/'packet58aj-onecard-resident/lineage/58ag-build-commands.json')]:
 rows=json.loads(file.read_text())
 for r in rows:
  if r['name'] in ('device-entry-main','device-own-rt-iq3'):print(n,r['name'],r['command'])
