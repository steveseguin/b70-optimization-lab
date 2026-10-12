"""CPU-only identity seal. Never invoke native benchmark binaries."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
BINARIES={"floor":"build/launch/p42-launch-floor","gemv":"build/gemv/p42-gemv","parallel":"build/parallel/parallel-native","route":"build/route42/p42-route","tiny":"build/tiny/p42-tiny","extras":"build/extras/p42-extras"}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
 if shutil.disk_usage("/").free<8_000_000_000:raise RuntimeError("root free below8GB")
 total=sum(f.stat().st_size for f in (P/"build").rglob("*") if f.is_file())
 if total>=2_000_000_000:raise RuntimeError("packet build exceeds2GB")
 binary={path:sha(P/path) for path in BINARIES.values()}
 sources={f.name:sha(f) for f in sorted(P.iterdir()) if f.is_file() and f.suffix in (".py",".cpp",".hpp",".inc")}
 windows={"K0":[dict(name=name,binary=path,args=["--compile-smoke","--repetitions","200"]) for name,path in BINARIES.items()],"T1":[dict(name="floor",binary=BINARIES["floor"],args=["--repetitions","200"])],"K2":[dict(name=name,binary=path,args=["--repetitions","200"]) for name,path in BINARIES.items() if name!="floor"]}
 dependencies={}
 for base in (P.parent/"packet29-merged",P.parent/"packet33-codegen"):
  for f in sorted(base.rglob("*")):
   if "build" in f.relative_to(base).parts or not f.is_file():continue
   if f.suffix in (".cpp",".hpp",".inc",".py"):
    dependencies[str(f.relative_to(P.parent))]=sha(f)
 for base in [P.parent.parent/"stage1/packet3-prep/src", *[P.parent/name for name in ("packet2","packet3","packet6-kopt","packet7-kopt2","packet8-kopt3","packet9-kopt4","packet10-kopt5")]]:
  for f in sorted(base.rglob("*")):
   if "build" not in f.relative_to(base).parts and f.is_file() and f.suffix in (".cpp",".hpp",".inc"):
    dependencies[os.path.relpath(f,P.parent)]=sha(f)
 for f in sorted((P.parent/"packet29-merged/build/fusion-fixtures").glob("*.fixture")):
  dependencies[str(f.relative_to(P.parent))]=sha(f)
 for path in (P.parent/"packet29-merged/rope.bf16",P.parent/"packet29-merged/receipts-cards01-20261012-chain/w2c-r29/class-times.json",P.parent/"packet37-merged2/dispatch-incumbent.json",P.parent/"packet37-merged2/receipts-cards23-20261012-chain/k2-r37/dispatch-measured.json"):
  dependencies[str(path.relative_to(P.parent))]=sha(path)
 gate_files=["expert-gates.json","parallel-gates.json","route42-gates.json","tiny-cpu-gates.json","extras-cpu-gates.json","tiny-build-receipt.json","extras-build-receipt.json","protocol-tests.json"]
 gates={name:sha(P/name) for name in gate_files}
 row=dict(schema="packet42.build.v1",device_executed=False,device_discovery=False,branch="main",base_repository_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=P,text=True).strip(),cpu_affinity=sorted(os.sched_getaffinity(0)),native_binary_sha256=binary,source_sha256=sources,readonly_dependency_sha256=dependencies,gate_sha256=gates,windows=windows,root_free_bytes=shutil.disk_usage("/").free,build_bytes=total,host_constraints=dict(nice=19,ionice_class=3,OMP_NUM_THREADS=2,max_compile_jobs=2,max_cpu_processes=4,anonymous_memory_limit_bytes=8_000_000_000),qualification="CPU preparation only; no device parity or timing claim")
 (P/"build-receipt.json").write_text(json.dumps(row,indent=2,ensure_ascii=False)+"\n")
 print(json.dumps({"binaries":binary,"build_bytes":total},indent=2))
if __name__=="__main__":main()
