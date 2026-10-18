#!/usr/bin/env python3
"""Use the frozen lean seal contract; verify the frozen lane-B screen plan."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SCREEN=P.parent/'screen';V=SCREEN/'v3-packet64-lanes'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 sys.path.insert(0,str(SCREEN));from seal import create
 assert not (P/'screen-seal.json').exists()
 base=P/'screen-seal.base.json'
 create(P,'tp2',P/'build-device-receipt.json',P/'fixture/receipt.json',P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',base)
 row=json.loads(base.read_text())
 for name in ('seal_and_plan.py','analyze.py','cost_model.py','cost-model.json','test_analysis.py','coordinator_screen.sh','prepare_memory.py','evidence/memory.json','retain_fixture.py','fixture/retention.json','verify_fixture_traces.py','evidence/proposal-repeat.json'):
  row['sources'][str((P/name).relative_to(ROOT))]=sha(P/name)
 row['diagnostic_probe']=dict(second_draft_discarded=True,extra_allocation_bound_bytes=32*1024**2,scope='lane B, 23/25, draft rank1, context4096',measurement_pending=True)
 (P/'screen-seal.json').write_text(json.dumps(row,indent=2)+'\n')
 cmd=[sys.executable,'-B',str(V/'screen.py'),'--profile','tp2','--lane','B','--placement','1-split23','--lineage',str(P),'--seal',str(P/'screen-seal.json'),'--binary',str(P/'build/device/own-rt-iq3'),'--dispatch',str(P/'dispatch-speed6.json'),'--output',str(V/'evidence/packet66-B-01'),'--plan']
 result=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 (P/'evidence/screen-plan.json').write_text(result.stdout);(P/'evidence/screen-plan.stderr').write_text(result.stderr);result.check_returncode()
 plan=json.loads(result.stdout);assert plan['supported'] and plan['physical_cards']==[2,3] and plan['watchdog_seconds']>=4*240
 print('Sealed lane B; watchdog',plan['watchdog_seconds'],'seconds; no device executed')
if __name__=='__main__':main()
