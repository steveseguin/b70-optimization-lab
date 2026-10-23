"""Packet194 local incremental build (packet189's compile path); compiler turns use the ops arbiter.

Packet194 recompiles FOUR TUs from packet194 sources and relinks them against the 76 remaining packet136/103 (38 per mode)
parent objects (`immutable-binaries.json`), which stay linked unchanged and are verified byte for byte (sha256
pins) before every link:
  * entry-main        <- v5/native-src/entry-main.cpp (main.cpp: `expert_gateup_for` passes the key per expert site;
                         v5/native/engine_bracket.hpp: the expert_gateup key: domain, in-load switch, expert_diet flag
                         and counters; everything else is packet189's k3x code byte for byte);
  * p49d_submit       <- native-base/.../p49d_submit.cpp (new key expert_gateup production|diet; 20-key k3-storage
                         selections beside the 19-key record selection);
  * s1_submit         <- native-base/.../s1_submit.cpp (unchanged packet183 TU; recompiled as packet183/186/188/189 did);
  * p49d_expert_submit<- native-base/.../p49d_expert_submit.cpp (THE ONE TU THE NEW KERNEL TOUCHES: packet193's
                         p193_diet.hpp, pinned copy aab37609..., registered as Arm 13 beside the production
                         p90exp::Kernel<IQ2_S,2560,WG64,wide> and selected by the six-argument p49d::expert).
                         This TU was a pinned parent object in packet189 (packet103's build); it is rebuilt here with
                         packet103's recorded flags. Its production kernels are compiled from the same pinned headers
                         with the same compiler and flags; the per-kernel device-IR identity is checked separately
                         (`kernel_identity.py`).
Every compile/link log must contain zero warnings. Root free space must stay >= 27 GB; build tree <= 2 GB.

Unit rule (brief 2026-10-23): poll `systemctl --user list-units 'window-*' 'lanequeue-*' 'packet*'` before each
compile batch; nothing may be active apart from the owner's qwen38-* endpoints and an endpoint restore
(a window-* unit whose ExecStart argv ends in a '...-restore<N>' token). Everything else holds (60 s polls,
deadline 90 min, then refuse); observed states go to evidence/compile-poll.json.
"""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;LOCAL=P.parent;ROOT=P.parents[4];STAGE=P.parents[1];BASE=LOCAL;B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
FLOOR=27_000_000_000  # brief rule for this packet: keep df / >= 27 GB
BUILD_LIMIT=2_000_000_000
UNITS=('window-*','lanequeue-*','packet*')
NATIVE=('engine_bracket.hpp','draft_bracket.hpp','bracket_boundary.hpp','probe_exchange.hpp','split_timing.hpp','v3_boundary.hpp','v3_controller.hpp','kernel_io.hpp')
REBUILT=('entry-main','p49d_submit','s1_submit','p49d_expert_submit')
P103=STAGE/'packet103-record-bundle/engine-commands.json'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def build_bytes():
 return sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts and not f.is_relative_to(P/'evidence'))
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=FLOOR,'root free below the 27 GB floor'
 size=build_bytes();assert size<=BUILD_LIMIT,size
 return size
def compiler_turn():
 import sys
 if str(LOCAL) not in sys.path:sys.path.append(str(LOCAL))
 spec=importlib.util.spec_from_file_location('ops_compile_turn',STAGE.parent/'ops/compile_turn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def warnings(log):
 return sum('warning' in line.lower() for line in Path(log).read_text(errors='replace').splitlines())
def run(cmd,name):
 limits();t=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
 count=warnings(B/(name+'.log'));assert count==0,f'{name}: {count} warning line(s); see {B/(name+".log")}'
 print(name,'PASS',flush=True);return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-t,warning_lines=0)
def units_now():
 r=subprocess.run(['systemctl','--user','list-units','--no-legend','--plain','--state=active,activating',*UNITS],capture_output=True,text=True,timeout=30,stdin=subprocess.DEVNULL)
 active=sorted(line.split()[0] for line in r.stdout.splitlines() if line.strip());allowed=[]
 for unit in active:
  desc=subprocess.run(['systemctl','--user','show',unit,'-p','Description','--value'],capture_output=True,text=True,timeout=30,stdin=subprocess.DEVNULL).stdout.strip()
  last=desc.split()[-1] if desc.split() else ''
  if unit.startswith('window-') and '-restore' in last:allowed.append(dict(unit=unit,description=desc))
 blocking=[u for u in active if u not in [a['unit'] for a in allowed]]
 return dict(rc=r.returncode,active=active,endpoint_restore_units=allowed,blocking=blocking)
def poll_window(deadline_s=5400,period_s=60):
 """Never compile while any window/lanequeue/packet unit is active, apart from the owner's endpoint restore (read-only query)."""
 rows=[];start=time.time()
 while True:
  u=units_now();rows.append(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**u))
  if u['rc']==0 and not u['blocking']:return dict(unit=list(UNITS),proceeded='no blocking window-*/lanequeue-*/packet* unit active or activating (endpoint-restore windows tolerated)',observations=rows)
  if time.time()-start>=deadline_s:raise SystemExit('compile hold: units still active after 90 min: '+', '.join(u['blocking']))
  time.sleep(period_s)
def expert_submit_args(mode):
 """packet103's recorded compile flags for p49d_expert_submit (the pinned parent object's build), includes re-rooted here."""
 prior=json.loads(P103.read_text());cmd=next(r['command'] for r in prior if r['name']==mode+'-p49d_expert_submit')
 flags=[a for a in cmd[:cmd.index('-o')] if not a.startswith('-I')]
 return flags+['-I'+str(CHECKED),'-I'+str(LOCAL)]
def main():
 limits();(LOCAL/'build').mkdir(exist_ok=True);B.mkdir(exist_ok=True)
 if not (LOCAL/'build/checked').exists():(LOCAL/'build/checked').symlink_to('../native-base',target_is_directory=True)
 poll=poll_window();history=P/'evidence/compile-poll.json'
 prior_poll=json.loads(history.read_text()).get('history',[]) if history.exists() else []
 save(history,dict(poll,history=prior_poll+[dict(proceeded=poll['proceeded'],observations=poll['observations'])]));print('compile poll:',poll['proceeded'],flush=True)
 pinned=json.loads((LOCAL/'immutable-binaries.json').read_text())
 prior=json.loads((LOCAL/'lineage-inputs/packet136-history/engine-commands.json').read_text());commands=[];artifacts={};inherited={};replaced={}
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=list(next(r['command'] for r in prior if r['name']==mode+'-entry-main'));args=args[:args.index('-o')]
  args=[v for v in args if not v.startswith(('-I','-O'))]+['-O2','-I'+str(CHECKED),'-I'+str(LOCAL)]
  for stem in REBUILT:
   src=P/'native-src/entry-main.cpp' if stem=='entry-main' else CHECKED/(stem+'.cpp')
   cmd=[*(expert_submit_args(mode) if stem=='p49d_expert_submit' else args),'-c',src,'-o',dest/(stem+'.o')]
   commands.append(run(cmd,mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in ('entry-main','p49d_submit','p49d_expert_submit') if Path(arg).name.endswith((s+'.o',s+'.cpp.o'))),None)
   if stem:
    if stem=='p49d_expert_submit':
     src=Path(arg);assert sha(src)==pinned[str(src.resolve())],'frozen parent object changed: '+str(src)
     replaced[str(src.resolve().relative_to(ROOT))]=dict(parent_sha256=sha(src),rebuilt=str((dest/(stem+'.o')).relative_to(ROOT)))
    link[i]=str(dest/(stem+'.o'))+('\0'+str(dest/'s1_submit.o') if stem=='p49d_submit' else '')
   else:
    src=Path(arg);assert sha(src)==pinned[str(src.resolve())],'frozen parent object changed: '+str(src)
    target=dest/'inherited'/src.name;target.parent.mkdir(exist_ok=True)
    if not target.exists():target.symlink_to(src.resolve())
    assert sha(src)==sha(target);inherited[str(src.resolve().relative_to(ROOT))]=sha(target);link[i]=str(target)
  link=[x for a in link for x in a.split('\0')];assert link.count(str(dest/'s1_submit.o'))==1 and link.count(str(dest/'p49d_expert_submit.o'))==1
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(ROOT))]=sha(dest/'own-rt-iq3')
  for stem in REBUILT:artifacts[str((dest/(stem+'.o')).relative_to(ROOT))]=sha(dest/(stem+'.o'))
  save(P/'engine-commands.json',commands)
 assert len(inherited)==76,len(inherited)  # 78 parent objects (both modes) minus the two p49d_expert_submit objects now rebuilt
 assert len(replaced)==2,replaced
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*[P/'native'/n for n in NATIVE],*P.glob('native-src/*'),CHECKED/'p49d_submit.cpp',CHECKED/'p49d_submit.hpp',CHECKED/'s1_submit.cpp',CHECKED/'p49d_expert_submit.cpp',CHECKED/'p193_diet.hpp',CHECKED/'p90_expert.hpp',CHECKED/'p100_down.hpp',P/'p194_v5_build_engine.py'] if f.is_file()}
 sources.update(inherited)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,rebuilt=True,compiler_runs=len(commands),warning_lines=0,
  binary_sha256=artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))],compile_poll=poll,
  changed_tus=['entry-main (v5/native-src/main.cpp: expert_gateup_for per expert site; v5/native/engine_bracket.hpp: expert_gateup key, expert_diet flag, counters)',
               'p49d_submit (expert_gateup production|diet key; 20-key k3-storage selections beside the 19-key record selection)','s1_submit (unchanged source, recompiled)',
               'p49d_expert_submit (packet193 p193_diet.hpp aab37609... registered as Arm 13 = p193diet::GateUp beside p90exp::Kernel<IQ2_S,2560,64,false,true>; six-argument p49d::expert)'],
  diet_header_sha256=sha(CHECKED/'p193_diet.hpp'),diet_header_pin_source='experiments/own-xpu-runtime/stage2/packet193-expert-diet/p193_diet.hpp',
  parents=[dict(name='packet103 recorded compile flags for p49d_expert_submit (read in place, provenance, never a pin)',parent_relpath=str(P103.relative_to(ROOT)),parent_digest=sha(P103))],
  inherited_parent_objects=len(inherited),replaced_parent_objects=replaced,sources=sources,artifacts=artifacts,commands=commands,
  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,build_bytes=limits()))
 print('build PASS: device',artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))][:16],'parent objects',len(inherited),'replaced',len(replaced))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
