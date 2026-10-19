"""Execute the CPU preparation backend with the real intercepted rank argv."""
import json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from chain_adapter import P,O,ROOT,sha

def main():
 log=O/'evidence/arguments-WS128.log'
 row=json.loads(next(x.removeprefix('ARGUMENT_RESULT=') for x in log.read_text().splitlines() if x.startswith('ARGUMENT_RESULT=')))
 from confirm136 import LIBRARIES
 outputs=[];specs=[]
 for rank,item in enumerate(row['argv']):
  a=item['argv'];a=a[next(i for i,x in enumerate(a) if x.endswith('/own-rt-iq3')):]
  original=list(a)
  replacements={'--plan':P/'build/input/plan.tsv','--identity':P/'build/input/identity.tsv','--dispatch':P/'dispatch-speed6.json'}
  for flag,path in replacements.items():a[a.index(flag)+1]=str(path)
  # These are the same metadata bytes materialized by the real chain. Only
  # paths in disposable output scratch change; flags and selections stay exact.
  spec=dict(command=[str(P/'build/preparation155/probe'),*a[1:]],rank_argv=a,sha256=sha(P/'build/preparation155/probe'),contains='PASS CPU device-branch preparation first decode',output_env='ENTRY_PREPARE_OUTPUT',metadata=[str(P/'build/input/plan.tsv'),str(P/'selection.json'),str(P/'dispatch-speed6.json')],sources={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),P/'selection.json',P/'dispatch-speed6.json',P/'build/input/plan.tsv']})
  spec.update(legacy_receipt=str(O/'evidence/preparation-build.json'),rotary_source=str(P.with_name('packet136-record-bundle')/'rope.bf16'))
  specs.append(spec)
  with tempfile.TemporaryDirectory(prefix='p155-prepare-',dir=P/'build') as tmp:
   env=dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2',LD_LIBRARY_PATH=LIBRARIES,ENTRY_PREPARE_OUTPUT=tmp)
   cp=subprocess.run(spec['command'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
   (O/'evidence'/f'preparation-rank{rank}.log').write_text(cp.stdout+cp.stderr)
   assert cp.returncode==0 and spec['contains'] in cp.stdout,cp.stderr[-2500:]
   census=json.loads((Path(tmp)/'census.json').read_text())
   outputs.append(dict(rank=rank,passed=True,device_executed=False,real_entry_argv=original,probe_argv=a,numerical_allocation_totals=census['totals']))
 (O/'evidence/preparation.json').write_text(json.dumps(dict(passed=True,device_executed=False,model_read=False,runs=outputs,probes=specs,substitutions=['CPU numerical Host transport','weight payload elision','nice19 observation','temporary metadata/output paths'],device_defines_active_in_engine=True,peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
 print('both rank preparation/first-position probes PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
