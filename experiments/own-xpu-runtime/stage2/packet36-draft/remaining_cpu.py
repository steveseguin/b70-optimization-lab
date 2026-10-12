"""Complete deferred CPU captures after one compiler campaign frees rank slots."""
import json,os,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
PY='/home/steve/.venvs/vllm-xpu/bin/python'
def size():
 return sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
baseline=size();budget=512*1024**2;peak=0;rows=[]
def execute(script,*args):
 global peak
 assert size()-baseline<budget,'remaining write budget exceeded'
 name=script.removesuffix('.py')+'-'+('-'.join(args) or 'run')
 with (B/(name+'.log')).open('w') as log:
  child=subprocess.Popen([PY,'-B',str(P/script),*args],stdout=log,stderr=subprocess.STDOUT)
  while child.poll() is None:
   anon=0
   for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
     if b'packet36-draft' not in (proc/'cmdline').read_bytes():continue
     for line in (proc/'status').read_text().splitlines():
      if line.startswith('RssAnon:'):anon+=int(line.split()[1])*1024
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
   peak=max(peak,anon)
   if anon>9*1024**3:
    child.send_signal(15)
    raise RuntimeError('CPU-only child stop: packet anonymous memory above9GiB')
   time.sleep(2)
  rows.append(dict(stage=name,returncode=child.returncode))
  print(name,child.returncode,flush=True)
  assert child.returncode==0,name
 assert size()-baseline<budget,'remaining write budget exceeded'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
while True:
 # The eight non-MTP modes must retire first. The two remaining MTP modes
 # share an exclusive lock, so at most two native ranks can then be active.
 paths=[P/f'real-{prefix}{mode}.json' for prefix in ('','icpx-host-') for mode in ('none','ngram','hit','miss')]
 if all(f.exists() for f in paths):
  assert all(json.loads(f.read_text())['passed'] for f in paths)
  break
 time.sleep(5)
# At most two native ranks remain; one compile/capture process is <=3 active.
execute('reference_reproduce.py','prepare')
execute('reference_reproduce.py','target','benchmark-analysis')
execute('capture_cpu.py','benchmark-analysis')
execute('reference_reproduce.py','reference','benchmark-analysis')
execute('compare_draft.py','benchmark-analysis')
for name in ('incident-retrospective','code-review'):
 execute('capture_cpu.py',name)
 execute('rebind_agreement.py',name)
result=dict(passed=True,device_executed=False,stages=rows,peak_packet_anonymous_bytes=peak,
 remaining_logical_bytes=size()-baseline,write_budget_bytes=budget,
 authority='Explicit user authorization for private packet36 builds/captures and regeneration; earlier cleanup reclaimed1753423290 bytes, no outside write.')
(P/'remaining-cpu-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
