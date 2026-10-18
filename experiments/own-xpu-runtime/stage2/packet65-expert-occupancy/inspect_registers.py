#!/usr/bin/env python3
"""Offline Xe2 assembly for the actual prepared expert translation unit; no device."""
import gzip,json,os,re,resource,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 out=B/"offline";out.mkdir(exist_ok=False)
 evidence=P/"evidence/registers";evidence.mkdir(parents=True,exist_ok=True)
 compiler=Path("/opt/intel/oneapi/compiler/2026.0/bin/icpx");translator=compiler.parent/"compiler/llvm-spirv"
 source=B/"checked"/P.relative_to(ROOT)/"p49d_expert_submit.cpp"
 flags=["-fsycl","-fsycl-device-only","-O2","-std=c++20","-fno-fast-math","-ffp-contract=off","-fdenormal-fp-math=ieee","-foffload-fp32-prec-div","-foffload-fp32-prec-sqrt"]
 commands=[[str(compiler),*flags,"-c",str(source),"-o",str(out/"kernels.bc")],
 [str(translator),"--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers",str(out/"kernels.bc"),"-o",str(out/"kernels.spv")],
 ["/usr/bin/ocloc","compile","-spirv_input","-file",str(out/"kernels.spv"),"-device","bmg-g31","-out_dir",str(out/"aot")]]
 env={**os.environ,"OMP_NUM_THREADS":"1","OMP_THREAD_LIMIT":"1","IGC_ShaderDumpEnable":"1","IGC_DumpToCustomDir":str(out/"igc"),"IGC_ShowFullVectorsInShaderDumps":"1"}
 for i,cmd in enumerate(commands):
  with (evidence/f"compile-{i}.log").open("w") as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env=env,check=True,timeout=600)
  print("offline stage",i,"PASS",flush=True)
 kernels=[]
 for i,p in enumerate(sorted((out/"igc").glob("*entry_*.asm"))):
  data=p.read_text();name=data.splitlines()[0]
  if "p65" not in name and "p49dvirtual" not in name:continue
  artifact=evidence/f"kernel-{i}.asm.gz";artifact.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
  grf=re.search(r"numGRF=(\d+)",data)
  kernels.append(dict(name=name,configured_grf=int(grf[1]) if grf else None,spill_metadata=[l for l in data.splitlines()[:40] if l.startswith("//.spill")],scratch_messages=[l for l in data.splitlines() if "scratch" in l.lower() and not l.lstrip().startswith("//")],assembly=str(artifact.relative_to(ROOT)),sha256=sha(artifact)))
 assert len(kernels)==10,len(kernels)
 save(P/"register-report.json",dict(schema="packet65.offline-registers.v1",passed=True,device_executed=False,scope="Offline BMG-G31 same prepared expert TU; configured GRFs and spill metadata, not resident occupancy or installed-driver JIT",commands=commands,kernels=kernels,tools={str(p):sha(p) for p in (compiler,translator,Path("/usr/bin/ocloc"))},source_sha256=sha(source),max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print(json.dumps(kernels,indent=2))
if __name__=="__main__":main()
