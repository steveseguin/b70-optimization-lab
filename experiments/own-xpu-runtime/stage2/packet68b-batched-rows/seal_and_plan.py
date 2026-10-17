"""Lean CPU seal; no GPU, services or host configuration changes."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];SCREEN=P.parent/'screen'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 audit_sources={str((P/name).relative_to(ROOT)):sha(P/name) for name in ('rank.hpp','batch_probe.hpp','main.cpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','screen_bridge.py','screen_probe.py','screen_worker.py','memory-plan.json')}
 audit=dict(placement='1',draft_rank=1,target_split=0,layer_boundary=24,binary_sha256=sha(P/'build/device/own-rt-iq3'),dispatch_sha256=sha(P/'dispatch-speed6.json'),sources=audit_sources,additional_device_bytes_per_rank=512*1024**2,description='Packet64 production target and draft, 24/24. Three private row images bounded by 512 MiB per rank, including status; READY census includes them.')
 (P/'placement-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 sys.path.insert(0,str(SCREEN));from seal import create
 out=P/'screen-seal.json'
 create(P,'tp2',P/'build-device-receipt.json',P/'fixture/receipt.json',P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',out)
 row=json.loads(out.read_text());row['sources'].update(audit_sources)
 for name in ('placement-audit.json','seal_and_plan.py','coordinator_probe.sh','analyze_probe.py'):
  row['sources'][str((P/name).relative_to(ROOT))]=sha(P/name)
 row['diagnostic_probe']=dict(sample_generated_positions=[8,16,32],ranks=[0,1],placement='1',rows=2,row_kind='discarded duplicate, independent state',model_speed_claim=False,device_measurement_pending=True)
 out.write_text(json.dumps(row,indent=2)+'\n')
 cmd=[sys.executable,'-B',str(P/'screen_probe.py'),'--profile','tp2','--lane','B','--placement','1','--lineage',str(P),'--seal',str(out),'--binary',str(P/'build/device/own-rt-iq3'),'--dispatch',str(P/'dispatch-speed6.json'),'--output',str(SCREEN/'v3-packet64-lanes/evidence/packet68b-batched-B-01'),'--plan']
 r=subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 (P/'evidence/probe-plan.json').write_text(r.stdout);(P/'evidence/probe-plan.stderr').write_text(r.stderr);r.check_returncode()
 plan=json.loads(r.stdout);assert plan['supported'] and plan['physical_cards']==[2,3] and plan['watchdog_seconds']>=4*480
 assert 'screen_worker.py' in ' '.join(plan['command'])
 print('PASS: sealed 24/24 lane-B batched row probe; device execution false; watchdog',plan['watchdog_seconds'])
if __name__=='__main__':main()
