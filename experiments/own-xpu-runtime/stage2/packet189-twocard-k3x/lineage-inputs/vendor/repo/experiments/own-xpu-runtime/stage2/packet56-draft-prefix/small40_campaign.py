"""Serial remaining inherited CPU gates; explicit phase ledgers, no retries."""
import json,os,subprocess,sys,time
from pathlib import Path
from storage import admit,discard
P=Path(__file__).resolve().parent;PY=sys.executable;B=P/'build'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
steps=[]
for mode in ('gnu-host','icpx-host','asan'):
 steps.append(('mini-'+mode,['gates.py','mini',mode],[f'mini-{mode}.json'],None))
 steps.append(('mtp-'+mode,['mtp_gates.py',mode],[f'mtp-gates-{mode}.json'],None))
steps += [('resident',['resident_host_gate.py'],['resident-host-gates.json'],None),
 ('extra-native',['qualification_extra40.py','native'],[],None),
 ('extra-p38k2',['qualification_extra40.py','p38k2'],['p38-k2-selection-tests.json'],None),
 ('native-mini',['native_mini_gate.py','--binary',str(B/'gnu-host/own-rt-iq3'),'--output',str(P/'native-mini-cpu.json')],['native-mini-cpu.json'],None),
 ('suite-gates',['suite_gates.py','--output',str(B/'suite-gates-current')],['suite-gate-results.json','receipt-metadata-gates.json'],B/'suite-gates-current')]
for mode in ('fixtures','models'):
 out=B/('window-cpu-'+mode+'-current')
 steps.append(('window-cpu-'+mode,['window_cpu_gate.py','--phase',mode,'--output',str(out)],['window-cpu-'+mode+'.json'],out))
rows=[]
start=sys.argv[1] if len(sys.argv)>1 else steps[0][0]
assert start in [r[0] for r in steps]
steps=steps[[r[0] for r in steps].index(start):]
for name,args,receipts,scratch in steps:
 admit(550_000_000)
 cmd=['nice','-n','19','ionice','-c','3',PY,'-B',str(P/'seal40.py'),'--record-phase',name]
 for receipt in receipts:cmd += ['--receipt',receipt]
 cmd += ['--',PY,'-B',str(P/args[0]),*args[1:]]
 began=time.monotonic();r=subprocess.run(cmd)
 row=dict(phase=name,returncode=r.returncode,seconds=time.monotonic()-began,command=cmd)
 if r.returncode==0 and scratch and scratch.exists():row['scratch_archive']=discard(scratch)
 rows.append(row)
 (P/'small40-campaign.json').write_text(json.dumps(dict(passed=r.returncode==0 and len(rows)==len(steps),device_executed=False,rows=rows),indent=2)+'\n')
 print(name,r.returncode,flush=True)
 if r.returncode:raise SystemExit(r.returncode)
