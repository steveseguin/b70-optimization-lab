"""Write only the two inert p58am proposal files; never enqueue or launch."""
import json,pathlib,hashlib
P=pathlib.Path(__file__).resolve().parent;R=P.parents[3];S=P/'screen';Q=R/'experiments/own-xpu-runtime/ops/lane-queue'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for kind in ('smoke','v5'):
 v=json.loads((P/f'proposals/{kind}.json').read_text());library=json.loads((S/'library-path.json').read_text())['LD_LIBRARY_PATH']
 v['environment']['LD_LIBRARY_PATH']=library
 (P/f'proposals/{kind}.json').write_text(json.dumps(v,indent=2)+'\n')
 row=dict(name=v['job_name'],lane='A',argv=['/usr/bin/python3','-B',str((S/'queue_runner.py').relative_to(R)),'--arm',kind,'--output',v['output'],'--cache-maintenance','overlap','--fault-review','{REVIEW}','--library-path',library,'--authorized-device-window'],review=str((S/'fault_review.py').relative_to(R)),env_extra={},planned_write_bytes=v['storage']['planned_outstanding_write_bytes']+2*8093428,plan=dict(entry_rehearsal=dict(binaries=[dict(path=str((P/'build/device/own-rt-iq3').relative_to(R)),sha256=sha(P/'build/device/own-rt-iq3'),args=['--help'],returncode=0,contains='--lookups'),dict(path=str((P/'build/device/p58-cache-fixtures-cli').relative_to(R)),sha256=sha(P/'build/device/p58-cache-fixtures-cli'),args=['--help'],returncode=0,contains='--iterations')],preparation_probe_note='Separate real-argv CPU preparation under the closed device environment. Shared probe adapter requires --rank, absent in this one-card ABI. See evidence/p58an-preparation.json; Resident-parent real argv and stream checks are bound by READY.')))
 path=Q/f'proposed-p58am-{kind}-A.txt';path.write_text('# PROPOSAL ONLY; not queued. Coordinator retains PAUSE-B and whole-host hold through K1a/K1b/WSCREEN.\n# Inert proposal; coordinator admission and CPU-ready marker required.\n'+json.dumps(row)+'\n')
 print(kind,row['name'],'screen-'+row['name'],path)
