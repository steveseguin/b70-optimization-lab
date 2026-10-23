"""Packet193 shared CPU helpers: limits, hashing, paths. Never a device."""
import hashlib,json,os,resource,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];OPS=P.parents[1]/'ops';STAGE=P.parent
P192=STAGE/'packet192-expert-issue-floor';P189=STAGE/'packet189-twocard-k3x';P100B=STAGE/'packet100b-route-capture';P162=STAGE/'packet162-iq2-lookup';P100=STAGE/'packet100-down-locality';P110=STAGE/'packet110-class-roofline'
NATIVE=P/'native-pinned';EV=P/'evidence';BUILD=P/'build';LINEAGE=P/'lineage-inputs'
CPU_DISK_FLOOR=27_000_000_000   # CPU preparation floor (this brief); the device floor is the shared 25 GB
BUILD_LIMIT=2_000_000_000       # build tree ceiling (this brief)
ADDRESS_SPACE=4*1024**3
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19,'run under nice -n 19'
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),'run on cores 8-15,24-31'
 assert shutil.disk_usage('/').free>=CPU_DISK_FLOOR,'CPU preparation disk floor 27 GB'
 resource.setrlimit(resource.RLIMIT_AS,(ADDRESS_SPACE,ADDRESS_SPACE))
 assert build_bytes()<=BUILD_LIMIT,'build tree above 2 GB'
def build_bytes():
 return sum(p.stat().st_size for p in BUILD.rglob('*') if p.is_file()) if BUILD.exists() else 0
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=1)+'\n')
def rel(p):return str(Path(p).resolve().relative_to(ROOT))
def units_idle():
 """Poll before each compile batch: no window/lanequeue/packet unit may be active, apart from the owner's
 endpoint restore (brief 2026-10-23: 'an endpoint restore is running now and is fine'), recognised by a
 window-* unit whose ExecStart argv ends in a '...-restore<N>' token. Everything else refuses the compile."""
 text=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating','--no-legend','--plain','window-*','lanequeue-*','packet*'],text=True,stdin=subprocess.DEVNULL)
 active=[l.split()[0] for l in text.splitlines() if l.strip()]
 allowed=[]
 for unit in active:
  desc=subprocess.check_output(['systemctl','--user','show',unit,'-p','Description','--value'],text=True,stdin=subprocess.DEVNULL).strip()
  if unit.startswith('window-') and desc.split()[-1:] and '-restore' in desc.split()[-1]:allowed.append(dict(unit=unit,description=desc))
 blocking=[u for u in active if u not in [a['unit'] for a in allowed]]
 assert not blocking,'active device units: '+str(blocking)
 return dict(active_units=active,endpoint_restore_units=allowed,checked=True)
def parent(name,path):
 """Cross-packet file read in place: never a pin, only provenance (pin-guard rule)."""
 return dict(name=name,parent_relpath=rel(path),parent_digest=sha(path),bytes=Path(path).stat().st_size)
