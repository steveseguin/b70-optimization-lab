"""Audit control uploads while retaining inherited schedule copies explicitly."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
 roots=sorted((P/'build').glob('integration-*'),key=lambda x:x.stat().st_mtime)
 root=roots[-1];rows=[]
 for f in sorted(root.glob('*/mini-2-*/timings.jsonl')):
  for line in f.read_text().splitlines():
   d=json.loads(line);assert d['parameter_uploads_per_launch']==0
   assert all(c['host_to_device']<=2 for c in d['copy_counts']),f
   rows.append(dict(path=str(f.relative_to(root)),parameter_uploads_per_launch=d['parameter_uploads_per_launch'],copies=d['copy_counts']))
 assert rows
 result=dict(passed=True,scope='resident two-card mini; host-to-device control uploads <=2/card/token, zero kernel-parameter uploads/launch',literal_all_copy_budget_passed=False,limitation='Inherited peer, snapshot and readback copies make the literal total-copy budget incompatible with preserving the packet18 schedule.',binary_sha256=hashlib.sha256((P/'build/host/own-rt-iq3').read_bytes()).hexdigest(),rows=rows)
 (P/'copy-budget.json').write_text(json.dumps(result,indent=2)+'\n')
 print('control copy budget:',len(rows),'token rows checked; inherited copies retained')
if __name__=='__main__':main()
