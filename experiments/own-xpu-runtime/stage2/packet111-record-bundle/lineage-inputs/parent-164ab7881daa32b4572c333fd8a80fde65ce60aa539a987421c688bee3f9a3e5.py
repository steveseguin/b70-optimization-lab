#!/usr/bin/env python3
"""CPU-only serial incremental build from packet64; never execute device output."""
import hashlib,json,os,subprocess,resource
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];B=P/"build";BASE=P.parent/"packet64-record-bundle"
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for data in iter(lambda:f.read(1024*1024),b""):h.update(data)
 return h.hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n")
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get("OMP_NUM_THREADS")=="2"
def main():
 limits();assert not (P/"build-device-receipt.json").exists(),"fresh build only"
 (B/"tmp").mkdir(exist_ok=True);os.environ["TMPDIR"]=str(B/"tmp")
 # Serial compilation; hard address-space ceiling is inherited by every compiler.
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 if not (B/"fusion-rope.hpp").exists():os.link(BASE/"build/fusion-rope.hpp",B/"fusion-rope.hpp")
 sources={};artifacts={};commands=[];inherited=[]
 def bind(f):sources[str(f.relative_to(ROOT))]=sha(f)
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(name=name,command=cmd,cwd=str(ROOT)))
  with (B/(name+".log")).open("w") as log:subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,stdin=subprocess.DEVNULL)
  print(name,"PASS",flush=True)
 parent=json.loads((BASE/"build-device-receipt.json").read_text())
 for n,h in parent["sources"].items():assert sha(ROOT/n)==h,n
 sources.update(parent["sources"]);bind(BASE/"build-device-receipt.json")
 from kernel_gate import mirror
 from math_gate import closure,check
 check();mapping=mirror()
 for f in closure():bind(f);bind(mapping[f])
 local=B/"engine";local.mkdir(exist_ok=True)
 (local/"entry-main.cpp").write_text("#define main packet26_model_entry\n#include "+json.dumps(str(mapping[P/"main.cpp"]))+"\n#undef main\n")
 prior=json.loads((BASE/"engine-commands.json").read_text())
 for mode in ("gnu-host","device"):
  dest=B/mode;dest.mkdir(exist_ok=True)
  base=next(r["command"] for r in prior if r["name"]==mode+"-entry-main")
  base=base[:base.index("-o")];base=[x.replace(str(BASE),str(P)) if x.startswith("-I") else x for x in base]
  for stem,src in [("entry-main",local/"entry-main.cpp"),("p49d_submit",mapping[P/"p49d_submit.cpp"]),("p49d_expert_submit",mapping[P/"p49d_expert_submit.cpp"])]:
   run([*base,"-o",dest/(stem+".o"),"-c",src],mode+"-"+stem)
  link=list(next(r["command"] for r in prior if r["name"]==mode+"-link"));link[link.index("-o")+1]=str(dest/"own-rt-iq3")
  replacements=0
  for i,arg in enumerate(link):
   if not arg.endswith(".o"):continue
   if arg==str(BASE/"build"/mode/"entry-main.o"):link[i]=str(dest/"entry-main.o");replacements+=1
   elif arg==str(BASE/"build"/mode/"p49d_submit.o"):link[i]=str(dest/"p49d_submit.o");replacements+=1
   elif arg.endswith("-p49d_expert_submit.cpp.o"):link[i]=str(dest/"p49d_expert_submit.o");replacements+=1
   else:
    src=Path(arg);bind(src);target=dest/"inherited"/(hashlib.sha256(str(src).encode()).hexdigest()[:12]+"-"+src.name);target.parent.mkdir(exist_ok=True)
    if not target.exists():os.link(src,target)
    assert sha(src)==sha(target)
    inherited.append(dict(parent=str(src.relative_to(ROOT)),current=str(target.relative_to(ROOT)),sha256=sha(src)));link[i]=str(target)
  assert replacements==3,(mode,replacements)
  run(link,mode+"-link");artifacts[str((dest/"own-rt-iq3").relative_to(P))]=sha(dest/"own-rt-iq3")
 for f in (local/"entry-main.cpp",P/"build_engine.py",P/"parent-source-manifest.json",P/"kernel_gate.py",P/"math_gate.py",P/"kernel_overlay.py",P/"submission_overlay.py",P/"kernel_guard.hpp",P/"rope.bf16",P/"mtp-manifest.tsv"):bind(f)
 save(P/"engine-commands.json",commands);bind(P/"engine-commands.json")
 save(P/"evidence/object-identity.json",dict(passed=True,objects=inherited,rebuilt=["entry-main.o","p49d_submit.o","p49d_expert_submit.o"]))
 bind(P/"evidence/object-identity.json")
 size=sum(f.stat().st_size for f in B.rglob("*") if f.is_file());assert size<500_000_000
 save(P/"build-device-receipt.json",dict(schema="packet65.cpu-build.v1",passed=True,device_executed=False,sources=sources,artifacts=artifacts,build_logical_bytes=size,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
 print("CPU build complete; no GPU execution; bytes",size,flush=True)
if __name__=="__main__":main()
