"""Five serial CPU-only oracle modes, aggregate anonymous memory guard."""
import os,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
compiler=sys.argv[1] if len(sys.argv)>1 else 'gnu-host';results=[];peak=0
for mode in ('none','ngram','hit','miss','mtp'):
 with (P/'build'/('final-real-'+compiler+'-'+mode+'.log')).open('w') as log:
  child=subprocess.Popen([sys.executable,'-B',str(P/'gates.py'),'real',mode,'--compiler',compiler],stdout=log,stderr=subprocess.STDOUT)
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
    child.send_signal(15);raise RuntimeError('CPU coordinator cooperative stop: anonymous memory above9GiB')
   time.sleep(1)
  results.append(dict(mode=mode,returncode=child.returncode));print(mode,child.returncode,flush=True)
  if child.returncode:break
result=dict(passed=len(results)==5 and all(r['returncode']==0 for r in results),rows=results,peak_packet_anonymous_bytes=peak,device_executed=False)
(P/('real-campaign-'+compiler+'.json')).write_text(json.dumps(result,indent=2)+'\n')
assert result['passed'],result
