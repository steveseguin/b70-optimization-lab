"""Offline BMG-G31 compiler audit; no device enumeration or kernel execution."""
import gzip,json,os,re,resource,shlex,shutil,subprocess,sys
from collections import Counter
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
from compile_turn import turn

def guard():
 free=shutil.disk_usage(ROOT).free
 if free<12*1024**3:raise RuntimeError(f"root free below 12 GiB: {free}")
 size=sum(p.stat().st_size for p in B.rglob("*") if p.is_file())
 if size>1_000_000_000:raise RuntimeError(f"build exceeds 1 GB: {size}")

def main():
 limits();guard();report_only=sys.argv[1:]==["--report-only"];out=B/"offline";out.mkdir(exist_ok=report_only)
 evidence=P/"evidence/offline";evidence.mkdir(parents=True,exist_ok=True)
 compiler=Path("/opt/intel/oneapi/compiler/2026.0/bin/icpx");translator=compiler.parent/"compiler/llvm-spirv"
 flags=["-fsycl","-fsycl-device-only","-O2","-std=c++20","-fno-fast-math","-ffp-contract=off","-fdenormal-fp-math=ieee","-foffload-fp32-prec-div","-foffload-fp32-prec-sqrt"]
 source=P/"offline_decode.cpp"
 commands=[[str(compiler),*flags,"-MMD","-MF",str(out/"kernels.d"),"-c",str(source),"-o",str(out/"kernels.bc")],
 [str(translator),"--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers",str(out/"kernels.bc"),"-o",str(out/"kernels.spv")],
 ["/usr/bin/ocloc","compile","-spirv_input","-file",str(out/"kernels.spv"),"-device","bmg-g31","-out_dir",str(out/"aot")]]
 env={**os.environ,"OMP_NUM_THREADS":"1","OMP_THREAD_LIMIT":"1","IGC_ShaderDumpEnable":"1","IGC_DumpToCustomDir":str(out/"igc"),"IGC_ShowFullVectorsInShaderDumps":"1","TMPDIR":str(out)}
 if not report_only:
  with turn():
   for i,cmd in enumerate(commands):
    guard()
    with (evidence/f"compile-{i}.log").open("w") as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=600)
    print("offline stage",i,"PASS",flush=True)
 kernels=[]
 for i,p in enumerate(sorted((out/"igc").glob("*entry_*.asm"))):
  data=p.read_text();name=data.splitlines()[0]
  if "Packet93OfflineHead" not in name:continue
  artifact=evidence/f"kernel-{i}.asm.gz";artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
  grf=re.search(r"numGRF=(\d+)",data)
  instructions=[l for l in data.splitlines() if re.match(r"^\s*\([A-Za-z0-9]",l)]
  active=[l.strip() for l in data.splitlines() if l.strip() and not l.lstrip().startswith("//")]
  opcodes=Counter(m[1] for l in active if (m:=re.match(r"^(?:\([^)]*\)\s*)?([a-z][\w.]*)\s+\(",l)))
  kernels.append(dict(name=name,opcode_counts=dict(sorted(opcodes.items())),configured_grf=int(grf[1]) if grf else None,spill_metadata=[l for l in data.splitlines()[:100] if l.startswith("//.spill")],scratch_messages=[l for l in active if "scratch" in l.lower()],instruction_count=int(re.search(r"//\.instCount (\d+)",data)[1]),instruction_count_definition="IGC //.instCount whole-kernel static count",static_load_lines=[l for l in active if "load." in l],send_lines=[l for l in active if re.search(r"\b(send|sends|load\.|store\.)",l)],assembly=str(artifact.relative_to(ROOT)),sha256=sha(artifact)))
 assert len(kernels)==4,[(r["name"],r["configured_grf"]) for r in kernels]
 deps=shlex.split((out/"kernels.d").read_text().replace("\\\n"," ").split(":",1)[1])
 sources={str(Path(n).resolve().relative_to(ROOT)):sha(n) for n in deps if Path(n).is_file() and Path(n).resolve().is_relative_to(ROOT)}
 sources[str((P/"inspect_decode.py").relative_to(ROOT))]=sha(P/"inspect_decode.py")
 save(evidence/"report.json",dict(schema="packet93.offline-decode.v1",passed=True,device_executed=False,kernels=kernels,commands=commands,sources=sources,max_rss_kib=(json.loads((evidence/"report.json").read_text())["max_rss_kib"] if report_only else resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),scope="Offline BMG-G31; identical SG32 WG32 geometry, full head shape. Static compiler metrics, not installed-driver occupancy or DRAM counters.",mode_map={"0":"production-p33","1":"packet74-packed","2":"head-plane","3":"head-transpose"}))
 guard();print([(r["name"],r["configured_grf"],r["instruction_count"],len(r["static_load_lines"])) for r in kernels],flush=True)
if __name__=="__main__":main()
