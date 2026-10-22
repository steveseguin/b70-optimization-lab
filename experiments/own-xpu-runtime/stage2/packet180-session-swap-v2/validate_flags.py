"""Proposal wrapper flags and actual captured native flags against built help."""
import ast,importlib.util,json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save
for name,lanes in [('one-card','A')]:
 p=P/name;r=json.loads((p/'evidence/preparation-probe.json').read_text());assert r['passed']
 env=r['environment'];cp=subprocess.run(['/usr/bin/python3','-B',str(p/'entry.py'),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 rows=[]
 for lane in lanes:
  proposal=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'/f'proposed-p180-{name}-{lane}.txt'
  for text in proposal.read_text().splitlines():
   if not text or text.startswith('#'):continue
   job=json.loads(text);flags=[v for v in job['argv']if v.startswith('--')];assert all(v in cp.stdout for v in flags)
   rows.append(dict(name=job['name'],flags=flags))
 assert all(x['all_flags_in_built_help']for x in r['probes'])
 helps={}
 for leaf in ['worker.py','screen.py']:
  help_run=subprocess.run(['/usr/bin/python3','-B',str(p/leaf),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  helps[leaf]=help_run.stdout
 assert all(flag in helps['worker.py'] for flag in ('--output','--lane','--kind','--reference'))
 internal=[]
 save(p/'evidence/flags.json',dict(passed=True,device_executed=False,wrapper_help=cp.stdout,rows=rows,internal_help=helps,internal_pipeline_flags=internal,native_probe_sha256=sha(p/'evidence/preparation-probe.json'),native_flag_source='actual one-card native_command and checkpoint_command; built executable --help'))
 print(name,'flags PASS')
