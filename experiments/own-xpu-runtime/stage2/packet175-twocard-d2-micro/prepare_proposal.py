"""Pin the lane-A and lane-B proposals without granting readiness or editing a live queue."""
import json
from pathlib import Path
from build_engine import P,ROOT,sha,limits
import run_micro

NAMES={'A':'packet175-d2-warm-ahead-micro-A1','B':'packet175-d2-warm-ahead-micro-B1'}


def main():
 limits()
 native=P/'build/d2-micro-device'
 sources={str(p.relative_to(ROOT)):sha(p) for p in P.rglob('*') if p.is_file() and p.suffix in ('.hpp','.cpp','.py') and 'build' not in p.relative_to(P).parts and 'evidence' not in p.relative_to(P).parts}
 assets=json.loads((P/'evidence/runtime-assets.json').read_text())['assets']
 (P/'evidence/source-seal.json').write_text(json.dumps(dict(sources=sources,assets=assets),indent=2)+'\n')
 provenance=json.loads((P/'lineage/native-provenance.json').read_text())
 for row in provenance:
  row['derived_sha256']=sha(P/row['copy'])
 (P/'evidence/derived-provenance.json').write_text(json.dumps(dict(snapshot='lineage/native-provenance.json (packet166 private native closure, copied unchanged)',transform='none in native/; micro.cpp adds the warm-ahead and evict kernels',records=provenance),indent=2)+'\n')
 command=run_micro.native_command()[2:]
 for lane,name in NAMES.items():
  row=dict(name=name,lane=lane,argv=['/usr/bin/python3','-B',str((P/'run_micro.py').relative_to(ROOT)),'--run','--lane',lane,'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py',planned_write_bytes=64*1024**2,
   plan=dict(diagnostic_only=True,expected_seconds=900,watchdog_seconds=7200,minimum_root_free_bytes=25_000_000_000,host_required_available_bytes=12*1024**3,entry_rehearsal=dict(kind='micro',binaries=[dict(path=str(native.relative_to(ROOT)),sha256=sha(native),args=['--help'],contains='--mode cpu|device')],prepare_probe=dict(command=command,rank_argv=command,sha256=sha(native),contains='PASS CPU preparation before first device call',sources=sources))))
  proposal=run_micro.PROPOSALS[lane];proposal.write_text(json.dumps(row)+'\n')
  print(proposal.relative_to(ROOT))
if __name__=='__main__':main()
