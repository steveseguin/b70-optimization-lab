"""Pin the current proposal without granting readiness or editing a live queue."""
import json
from pathlib import Path
from build_engine import P,ROOT,sha,limits

def main():
 limits()
 native=P/'build/micro-device'
 sources={str(p.relative_to(ROOT)):sha(p) for p in P.rglob('*') if p.is_file() and p.suffix in ('.hpp','.cpp','.py') and 'build' not in p.relative_to(P).parts and 'evidence' not in p.relative_to(P).parts}
 assets=json.loads((P/'evidence/runtime-assets.json').read_text())['assets']
 (P/'evidence/source-seal.json').write_text(json.dumps(dict(sources=sources,assets=assets),indent=2)+'\n')
 provenance=json.loads((P/'lineage/native-provenance.json').read_text())
 for row in provenance:
  row['derived_sha256']=sha(P/row['copy'])
 (P/'evidence/derived-provenance.json').write_text(json.dumps(dict(snapshot='lineage/native-provenance.json',transform='include rewrites; optional first-row state/history validation stores in private p82b_recurrence.hpp and kernels.hpp',records=provenance),indent=2)+'\n')
 command=[str(native),'--rank','0','--mode','device','--weights','real','--oracle',str(P/'evidence/real-oracle.tsv'),'--repeats','200','--coordinator-admitted-device-window']
 row=dict(name='packet166-causal-m2-layer-micro-B1',lane='B',argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--run','--lane','B','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py',planned_write_bytes=32*1024**2,
  plan=dict(diagnostic_only=True,expected_seconds=900,watchdog_seconds=7200,minimum_root_free_bytes=25_000_000_000,host_required_available_bytes=12*1024**3,entry_rehearsal=dict(kind='micro',binaries=[dict(path=str(native.relative_to(ROOT)),sha256=sha(native),args=['--help'],contains='--mode cpu|device')],prepare_probe=dict(command=command,rank_argv=command,sha256=sha(native),contains='PASS CPU preparation before first device call',sources=sources))))
 proposal=P.parents[1]/'ops/lane-queue/proposed-p166-micro-B.txt';proposal.write_text(json.dumps(row)+'\n')
 print(proposal.relative_to(ROOT))
if __name__=='__main__':main()
