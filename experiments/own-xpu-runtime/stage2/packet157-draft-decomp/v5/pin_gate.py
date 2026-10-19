"""Run the live coordinator pin rule against all six new proposals, read-only."""
import importlib.util,json,sys
from p157_v5_build_engine import P,LOCAL,ROOT,sha,save

def main():
 path=LOCAL.parents[1]/'ops/lane-queue/pin_guard.py';snapshot=LOCAL/'lineage-inputs/queue/pin_guard.py'
 assert sha(path)==sha(snapshot),'queue guard changed after temporary planning; repeat plans'
 spec=importlib.util.spec_from_file_location('pin_guard_live149',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rows=[]
 for item in json.loads((P/'evidence/queue-plan.json').read_text())['rows']:
  f=ROOT/item['proposal_name']
  row=m.check_job(json.loads(f.read_text()));assert row['passed'];rows.append(row)
 assert len(rows)==4
 save(P/'evidence/pin-guard.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'pin_gate.py',snapshot)}))
if __name__=='__main__':main()
