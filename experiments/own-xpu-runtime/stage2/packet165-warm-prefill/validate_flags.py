"""Proposal wrapper flags and actual captured native flags against built help."""
import ast,importlib.util,json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,sha,save
for name,lanes in [('one-card','A'),('two-card','AB')]:
 p=P/name;r=json.loads((p/'evidence/preparation-probe.json').read_text());assert r['passed']
 env=r['environment'];cp=subprocess.run(['/usr/bin/python3','-B',str(p/'entry.py'),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 rows=[]
 for lane in lanes:
  proposal=ROOT/'experiments/own-xpu-runtime/ops/lane-queue'/f'proposed-p165-{name}-{lane}.txt'
  for text in proposal.read_text().splitlines():
   if not text or text.startswith('#'):continue
   job=json.loads(text);flags=[v for v in job['argv']if v.startswith('--')];assert all(v in cp.stdout for v in flags)
   rows.append(dict(name=job['name'],flags=flags))
 assert all(x['all_flags_in_built_help']for x in r['probes'])
 helps={}
 for leaf in ['worker.py','screen.py']+(['pipeline.py'] if name=='two-card' else []):
  help_run=subprocess.run(['/usr/bin/python3','-B',str(p/leaf),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  helps[leaf]=help_run.stdout
 assert all(flag in helps['worker.py'] for flag in ('--output','--lane'))
 # Each native command flag was checked above. The internal Python pipeline
 # parser also has a real --help path; check its complete literal argv flags.
 if name=='two-card':
  tree=ast.parse((p/'worker.py').read_text())
  calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='parse_args' and node.args and isinstance(node.args[0],ast.List)]
  assert len(calls)==1
  internal=[node.value for node in calls[0].args[0].elts if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value.startswith('--')]
  assert all(flag in helps['pipeline.py'] for flag in internal)
 else:internal=[]
 save(p/'evidence/flags.json',dict(passed=True,device_executed=False,wrapper_help=cp.stdout,rows=rows,internal_help=helps,internal_pipeline_flags=internal,native_probe_sha256=sha(p/'evidence/preparation-probe.json'),native_flag_source='actual Transport command builder or one-card native_command; built executable --help'))
 print(name,'flags PASS')
