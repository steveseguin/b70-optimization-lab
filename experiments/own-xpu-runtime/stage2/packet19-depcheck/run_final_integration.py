#!/usr/bin/env python3
"""Repeat original 13 CPU gates against separately built final fatal-owner overlay."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
P16=HERE.parent/"packet16-decode"
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 build=HERE/"build/final-patched";old=HERE/"build/patched";binary=build/"depcheck-runtime"
 dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
 assert not any(x in dynamic.lower() for x in ("libsycl","libze_loader","libur_loader","libopencl"))
 source_rows=[]
 for name in ("main.cpp","adapter.cpp","performance.cpp","core.cpp","instrument.hpp"):
  a=(old/name).read_bytes();b=(build/name).read_bytes()
  aa=a.replace(str(old).encode(),b"<BUILD>");bb=b.replace(str(build).encode(),b"<BUILD>")
  source_rows.append(dict(name=name,raw_equal=a==b,relocated_equal=aa==bb,old_sha256=hashlib.sha256(a).hexdigest(),new_sha256=hashlib.sha256(b).hexdigest(),old_relocated_sha256=hashlib.sha256(aa).hexdigest(),new_relocated_sha256=hashlib.sha256(bb).hexdigest()))
 assert all(x["relocated_equal"] for x in source_rows),source_rows
 proof=dict(device_executed=False,normalization="Replace only the absolute containing build directory with <BUILD>; no code normalization.",files=source_rows,all_relocated_equal=True)
 common=[]
 for path in sorted(old.iterdir()):
  if path.suffix not in (".cpp",".hpp") or not (build/path.name).exists():continue
  aa=path.read_bytes().replace(str(old).encode(),b"<BUILD>");bb=(build/path.name).read_bytes().replace(str(build).encode(),b"<BUILD>")
  common.append(dict(file=path.name,equal=aa==bb,old_relocated_sha256=hashlib.sha256(aa).hexdigest(),new_relocated_sha256=hashlib.sha256(bb).hexdigest()))
 assert all(row["equal"] for row in common)
 proof.update(all_common_generated_sources=common,all_common_generated_sources_equal=True,added_generated_sources=[p.name for p in build.iterdir() if p.suffix in (".cpp",".hpp") and not (old/p.name).exists()])
 (HERE/"final-source-equivalence.json").write_text(json.dumps(proof,indent=2)+"\n")
 source=(P16/"test.py").read_text()
 target="(HERE/'memory-plan.json')"
 assert source.count(target)==1
 source=source.replace(target,"Path("+repr(str(build/"memory-plan.json"))+")")
 ns={"__file__":str(P16/"test.py"),"__name__":"packet16_final_tests"}
 exec(compile(source,str(P16/"test.py"),"exec"),ns)
 rows=[];scratch=HERE/"build/scratch";scratch.mkdir(exist_ok=True)
 before=sha(HERE/"integration-gates.json")
 for seed in (0,1,17,73):
  for mode in ("parallel","core"):
   path=scratch/f"final-integration-{seed}-{mode}"
   assert not path.exists(),path
   report=build/f"final-integration-{seed}-{mode}-sanitizer.json"
   os.environ["DEPCHECK_SEED"]=str(seed);os.environ["DEPCHECK_REPORT"]=str(report)
   result=ns["run"](binary,path,P16/"build/input",mode)
   assert result["passed"] and len(result["tests"])==13
   rows.append(dict(seed=seed,mode=mode,result=result))
   print("final integration",seed,mode,"13/13 PASS",flush=True)
   shutil.rmtree(path)
 assert sha(HERE/"integration-gates.json")==before
 result=dict(passed=True,device_executed=False,original_test_sha256=sha(P16/"test.py"),cases_per_mode=13,seeds=[0,1,17,73],binary_sha256=sha(binary),build_manifest_sha256=sha(build/"build.json"),build_manifest=json.loads((build/"build.json").read_text()),source_equivalence_sha256=sha(HERE/"final-source-equivalence.json"),original_integration_gates_sha256=before,runs=rows)
 (HERE/"final-integration-gates.json").write_text(json.dumps(result,indent=2)+"\n")
 print("final integration: 104/104 case runs passed; device_executed=false",flush=True)
if __name__=="__main__":main()
