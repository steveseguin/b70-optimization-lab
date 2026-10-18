"""Reject every changed kernel with any spill metadata before engine build."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 rows=[]
 for tu in ('p60_submit','p49d_expert_submit'):
  report=json.loads((P/f'register-report-{tu}.json').read_text())
  for row in report['kernels']:
   name=row['name']
   if 'p73hc' in name or 'gate_mix_kernel' in name or ('p65' in name and 'ELb0ELb1' in name):rows.append(row)
 assert len(rows)==8,len(rows)
 for row in rows:
  assert not row['spill_metadata'] and not row['scratch_messages'],row['name']
 (P/'register-report.json').write_text(json.dumps(dict(passed=True,device_executed=False,kernels=rows,scope='Linked SYCL device libraries, offline BMG-G31; static counts, not measured occupancy, DRAM traffic or speed'),indent=2)+'\n')
 print('PASS: all 8 selected HC/expert kernels have no spill metadata or spill/fill messages')
if __name__=='__main__':main()
