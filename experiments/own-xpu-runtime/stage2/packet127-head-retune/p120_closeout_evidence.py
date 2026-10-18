"""Retain packet120's incomplete trailing-control lifecycle, without changing it."""
import json,resource
from pathlib import Path
from selection_evidence import main as collect,P,S,ROOT,sha

def main():
 collect()
 output=P/'evidence/selection-evidence.json';row=json.loads(output.read_text())
 root=S/'screen/v4-lanes/evidence/p120-B-grid-2-production'
 path=root/'run/teardown.json'
 if path.exists():
  raw=path.read_bytes();retained=P/'evidence/p120-trailing-teardown.json';retained.write_bytes(raw)
  teardown=json.loads(raw)
  row['packet120_trailing_lifecycle']=dict(passed=False,gate_refused=teardown.get('gate_refused'),reason=teardown.get('reason'),own_ranks_exited=teardown.get('own_ranks_exited'),retained_path=str(retained.relative_to(ROOT)),source_path=str(path.relative_to(ROOT)),source_sha256=sha(path),scope='Observed failure receipt, not a completed speed control')
  row['sources'][str(retained.relative_to(ROOT))]=sha(retained)
 row['sources'][str(Path(__file__).resolve().relative_to(ROOT))]=sha(Path(__file__))
 output.write_text(json.dumps(row,indent=2)+'\n')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
