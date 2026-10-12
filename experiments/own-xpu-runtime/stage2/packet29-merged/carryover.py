"""Packet26 copied-source and unchanged arithmetic proof; no device qualification."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 proof=json.loads((P/'source-proof.json').read_text());base=P.parent/'packet27-round2'
 for name,digest in proof['copied_sha256'].items():
  import subprocess
  assert hashlib.sha256(subprocess.check_output(['git','show',proof['commit']+':'+proof['source']+name])).hexdigest()==digest,name
 unchanged=['arithmetic.hpp','core_v2.hpp','detmath.hpp','kernels.hpp','rope.hpp','rope.bf16']
 for name in unchanged:assert H(P/name)==H(base/name),name
 measured=P.parent/'packet26-specialised'/'receipts-card0-20261011-k1-k2/a2-k2/summary.json'
 selected=json.loads(measured.read_text())['selection'];default=json.loads((P/'dispatch-default.json').read_text());registry=json.loads((P/'k2-class-registry.json').read_text())['classes']
 for name,entry in registry.items():
  if name not in selected or not entry.get('dispatch_section'):continue
  section=entry['dispatch_section'];key=entry['dispatch_key'];expected='r5' if section=='gemv' else selected[name]
  keys=["hc.a.norm","hc.f.norm","final.norm","ple.kn","ple.qn","ple.cn"] if name=="norm" else [key]
  for dispatch_key in keys:assert default[section][dispatch_key]==expected,(name,dispatch_key,expected)
 result=dict(passed=True,device_executed=False,source_commit=proof['commit'],copied_files=len(proof['copied_sha256']),unchanged_arithmetic={n:H(P/n) for n in unchanged},measured_selection_source_sha256=H(measured),scope='unchanged arithmetic primitives and pinned packet26 source; new kernels and schedule require fresh gates',qualifies_all_new=False)
 (P/'carryover-proof.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
