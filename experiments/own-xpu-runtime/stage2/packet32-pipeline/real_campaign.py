"""Four CPU-only oracle modes, bounded aggregate anonymous-memory watch."""
import os,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ["OMP_NUM_THREADS"]=="2"
compiler=sys.argv[1] if len(sys.argv)>1 else "gnu-host"
assert compiler in ("gnu-host","icpx-host")
children=[];logs=[]
for mode in ("none","ngram","hit","miss"):
 log=(P/"build"/("final-real-"+compiler+"-"+mode+".log")).open("w");logs.append(log)
 children.append(subprocess.Popen([sys.executable,"-B",str(P/"gates.py"),"real",mode,"--compiler",compiler],stdout=log,stderr=subprocess.STDOUT))
peak=0
while any(c.poll() is None for c in children):
 anon=0
 for proc in Path("/proc").iterdir():
  if not proc.name.isdigit():continue
  try:
   cmd=(proc/"cmdline").read_bytes()
   if b"packet32-pipeline" not in cmd:continue
   for line in (proc/"status").read_text().splitlines():
    if line.startswith("RssAnon:"):anon+=int(line.split()[1])*1024
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 peak=max(peak,anon)
 if anon>9*1024**3:
  for c in children:
   if c.poll() is None:c.send_signal(15) # cooperative CPU coordinators, never ranks
  raise RuntimeError("packet anonymous memory above9GiB; coordinators requested to stop")
 time.sleep(1)
for f in logs:f.close()
result=dict(passed=all(c.returncode==0 for c in children),returncodes=[c.returncode for c in children],peak_packet_anonymous_bytes=peak,device_executed=False)
(P/("real-campaign.json" if compiler=="gnu-host" else "real-campaign-icpx-host.json")).write_text(json.dumps(result,indent=2)+"\n")
assert result["passed"],result
