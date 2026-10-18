"""Frozen lean seal and lane-B cost screen admission, CPU only."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SCREEN=P.parent/'screen';V=SCREEN/'v3-packet64-lanes'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 sys.path.insert(0,str(SCREEN));from seal import create
 out=P/'screen-seal.json'
 create(P,'tp2',P/'build-device-receipt.json',P/'fixture/receipt.json',P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',out)
 row=json.loads(out.read_text())
 for name in ('seal_and_plan.py','coordinator_probe.sh','analyze_probe.py'):
  row['sources'][str((P/name).relative_to(ROOT))]=sha(P/name)
 row['diagnostic_probe']=dict(extra_target_row_discarded=True,sample_generated_positions=[8,16,32],rank=0,placement='1-split23',batched_verifier=False,measurement_pending=True)
 out.write_text(json.dumps(row,indent=2)+'\n')
 cmd=[sys.executable,'-B',str(V/'screen.py'),'--profile','tp2','--lane','B','--placement','1-split23','--lineage',str(P),'--seal',str(out),'--binary',str(P/'build/device/own-rt-iq3'),'--dispatch',str(P/'dispatch-speed6.json'),'--output',str(V/'evidence/packet68-cost-B-01'),'--plan']
 r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 (P/'evidence/probe-plan.json').write_text(r.stdout);(P/'evidence/probe-plan.stderr').write_text(r.stderr);r.check_returncode()
 plan=json.loads(r.stdout);assert plan['supported'] and plan['physical_cards']==[2,3] and plan['watchdog_seconds']>=4*300
 print('PASS: sealed lane-B cost probe; no device execution; watchdog',plan['watchdog_seconds'])
if __name__=='__main__':main()
