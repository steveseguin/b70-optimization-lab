"""Packet189 local incremental build (packet188's compile path); compiler turns use the ops arbiter.

Packet191 recompiles the three entry TUs from packet191 sources and relinks them against the 78
packet136/103 parent objects (`immutable-binaries.json`), which stay linked unchanged and are
verified byte for byte (sha256 pins) before every link:
  * entry-main  <- v5/native-src/entry-main.cpp (main.cpp: the packet191 site recorder replaces packet65's expert-only
                   recorder under the same namespace (v5/native/p191_sites.hpp), finish() retains sampled events for the
                   drain-time timestamp read, attribution_row writes the packet191.site.v1 row; rank.hpp tags the half
                   phase; v5/native: engine_bracket.hpp (sites key: domain, in-load switch, sites_on flag),
                   v3_boundary.hpp (boundary phase tag); everything else is packet189's k3x code byte for byte);
  * p49d_submit <- native-base/.../p49d_submit.cpp (new key sites off|on; 19- or 20-key k3-storage selections);
  * s1_submit   <- native-base/.../s1_submit.cpp (unchanged packet183 TU; recompiled as packet183/186/188/189 did).
No new device kernel and no new transfer: the instrumentation reads event timestamps on the host after the half's
own final drain. Every other device kernel object is the pinned parent. Every compile/link log must contain zero warnings. Root free space must stay >= 27 GB.

Coordinator rule (2026-10-22, packet188/189/191): poll `systemctl --user` for active/activating `window-*` and
`lanequeue-*` units before each compile batch and hold (60 s polls, deadline 90 min, then refuse) while any is
active; the observed states are recorded in evidence/compile-poll.json.
"""
import hashlib,importlib.util,json,os,resource,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;LOCAL=P.parent;ROOT=P.parents[4];STAGE=P.parents[1];BASE=LOCAL;B=P/'build'
CHECKED=LOCAL/'build/checked'/LOCAL.relative_to(ROOT)
FLOOR=27_000_000_000  # coordinator rule for this packet: keep df / >= 27 GB
UNITS=('window-*','lanequeue-*')
NATIVE=('engine_bracket.hpp','draft_bracket.hpp','bracket_boundary.hpp','probe_exchange.hpp','split_timing.hpp','v3_boundary.hpp','v3_controller.hpp','kernel_io.hpp','p191_sites.hpp')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=FLOOR,'root free below the 27 GB floor'
 size=sum(f.stat().st_size for f in LOCAL.rglob('*') if f.is_file() and not f.is_symlink() and 'build' in f.parts and not f.is_relative_to(P/'evidence'))
 assert size<=300_000_000,size
 return size
def compiler_turn():
 import sys
 if str(LOCAL) not in sys.path:sys.path.append(str(LOCAL))
 spec=importlib.util.spec_from_file_location('ops_compile_turn',STAGE.parent/'ops/compile_turn.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.turn()
def warnings(log):
 return sum('warning' in line.lower() for line in Path(log).read_text(errors='replace').splitlines())
def run(cmd,name):
 limits();t=time.monotonic()
 with compiler_turn(),(B/(name+'.log')).open('w') as log:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
 count=warnings(B/(name+'.log'));assert count==0,f'{name}: {count} warning line(s); see {B/(name+".log")}'
 print(name,'PASS',flush=True);return dict(name=name,command=list(map(str,cmd)),seconds=time.monotonic()-t,warning_lines=0)
def poll_window(deadline_s=5400,period_s=60):
 """Never compile while any window driver unit is active/activating (coordinator rule, read-only query)."""
 rows=[];start=time.time()
 while True:
  r=subprocess.run(['systemctl','--user','list-units','--no-legend','--plain','--state=active,activating',*UNITS],capture_output=True,text=True,timeout=30)
  units=sorted(line.split()[0] for line in r.stdout.splitlines() if line.strip());rows.append(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),active=units,rc=r.returncode))
  if r.returncode==0 and not units:return dict(unit=list(UNITS),proceeded='no window-* or lanequeue-* unit active or activating',observations=rows)
  if time.time()-start>=deadline_s:raise SystemExit('compile hold: window-*/lanequeue-* units still active after 90 min: '+', '.join(units))
  time.sleep(period_s)
def main():
 limits();(LOCAL/'build').mkdir(exist_ok=True);B.mkdir(exist_ok=True)
 if not (LOCAL/'build/checked').exists():(LOCAL/'build/checked').symlink_to('../native-base',target_is_directory=True)
 poll=poll_window();history=P/'evidence/compile-poll.json'
 prior=json.loads(history.read_text()).get('history',[]) if history.exists() else []
 save(history,dict(poll,history=prior+[dict(proceeded=poll['proceeded'],observations=poll['observations'])]));print('compile poll:',poll['proceeded'],flush=True)
 pinned=json.loads((LOCAL/'immutable-binaries.json').read_text())
 prior=json.loads((LOCAL/'lineage-inputs/packet136-history/engine-commands.json').read_text());commands=[];artifacts={};inherited={}
 for mode in ('gnu-host','device'):
  dest=B/mode;dest.mkdir(exist_ok=True)
  args=list(next(r['command'] for r in prior if r['name']==mode+'-entry-main'));args=args[:args.index('-o')]
  args=[v for v in args if not v.startswith(('-I','-O'))]+['-O2','-I'+str(CHECKED),'-I'+str(LOCAL)]
  for stem in ('entry-main','p49d_submit','s1_submit'):
   src=P/'native-src/entry-main.cpp' if stem=='entry-main' else CHECKED/(stem+'.cpp')
   cmd=[*args,'-c',src,'-o',dest/(stem+'.o')]
   commands.append(run(cmd,mode+'-'+stem))
  link=list(next(r['command'] for r in prior if r['name']==mode+'-link'));link[link.index('-o')+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(link):
   if not arg.endswith('.o'):continue
   stem=next((s for s in ('entry-main','p49d_submit') if Path(arg).name.endswith((s+'.o',s+'.cpp.o'))),None)
   if stem:link[i]=str(dest/(stem+'.o'))+('\0'+str(dest/'s1_submit.o') if stem=='p49d_submit' else '')
   else:
    src=Path(arg);assert sha(src)==pinned[str(src.resolve())],'frozen parent object changed: '+str(src)
    target=dest/'inherited'/src.name;target.parent.mkdir(exist_ok=True)
    if not target.exists():target.symlink_to(src.resolve())
    assert sha(src)==sha(target);inherited[str(src.resolve().relative_to(ROOT))]=sha(target);link[i]=str(target)
  link=[x for a in link for x in a.split('\0')];assert link.count(str(dest/'s1_submit.o'))==1
  commands.append(run(link,mode+'-link'));artifacts[str((dest/'own-rt-iq3').relative_to(ROOT))]=sha(dest/'own-rt-iq3')
  save(P/'engine-commands.json',commands)
 assert len(inherited)==78,len(inherited)
 sources={str(f.relative_to(ROOT)):sha(f) for f in [*[P/'native'/n for n in NATIVE],*P.glob('native-src/*'),CHECKED/'p49d_submit.cpp',CHECKED/'s1_submit.cpp',P/'p191_v5_build_engine.py'] if f.is_file()}
 sources.update(inherited)
 save(P/'evidence/build.json',dict(passed=True,device_executed=False,rebuilt=True,compiler_runs=len(commands),warning_lines=0,
  binary_sha256=artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))],compile_poll=poll,
  changed_tus=['entry-main (v5/native-src/main.cpp: packet191 site recorder + row writer; v5/native-src/rank.hpp: half phase tag; v5/native/engine_bracket.hpp: sites key; v5/native/v3_boundary.hpp: boundary phase tag; v5/native/p191_sites.hpp: the recorder)',
               'p49d_submit (sites off|on key; 19/20-key k3-storage selections)','s1_submit (unchanged source, recompiled)'],
  inherited_parent_objects=len(inherited),sources=sources,artifacts=artifacts,commands=commands,
  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,build_bytes=limits()))
 print('build PASS: device',artifacts[str((B/'device/own-rt-iq3').relative_to(ROOT))][:16],'parent objects',len(inherited))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
