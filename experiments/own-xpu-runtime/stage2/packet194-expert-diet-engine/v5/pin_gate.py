"""Run the live coordinator pin rule against both rows of the packet189 proposal file, read-only."""
import importlib.util,json,sys
from p194_v5_build_engine import P,LOCAL,ROOT,sha,save

def main():
 path=LOCAL.parents[1]/'ops/lane-queue/pin_guard.py';snapshot=LOCAL/'lineage-inputs/queue/pin_guard.py'
 assert sha(path)==sha(snapshot),'queue guard changed after temporary planning; repeat plans'
 spec=importlib.util.spec_from_file_location('pin_guard_live149',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 rows=[]
 plan=json.loads((P/'evidence/queue-plan.json').read_text());f=ROOT/plan['proposal_name'];assert sha(f)==plan['sha256']
 for line in f.read_text().splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  row=m.check_job(json.loads(line));assert row['passed'];rows.append(row)
 from bracket_config import ROWS
 assert len(rows)==len(ROWS)
 save(P/'evidence/pin-guard.json',dict(passed=True,device_executed=False,rows=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'pin_gate.py',snapshot)}))
if __name__=='__main__':main()
