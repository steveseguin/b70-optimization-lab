"""Generate the unchanged runtime fixture with explicit incumbent/candidate dispatch."""
import argparse, hashlib, json, os, resource, shutil, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/"build/gemv"; R=P.parent/"packet29-merged"
IC="/opt/intel/oneapi/compiler/2026.0/bin/icpx"
FLAGS=["-std=c++20","-O2","-Werror=return-type","-fno-fast-math","-ffp-contract=off","-fdenormal-fp-math=ieee","-foffload-fp32-prec-div","-foffload-fp32-prec-sqrt","-fsycl"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(s,a,b):
 if s.count(a)!=1:raise ValueError((a[:80],s.count(a)))
 return s.replace(a,b)
def generate():
 B.mkdir(parents=True,exist_ok=True)
 s=(R/"gemv_timing.cpp").read_text()
 s="#include \"expert_submit.hpp\"\n#include \"parallel.hpp\"\n#include \"../packet33-codegen/p33_submit.hpp\"\n#include \"stop.hpp\"\n"+s
 s=replace(s,"constexpr auto& shapes=p28::shapes;","constexpr std::array shapes{p28::shapes[0],p28::shapes[1],p28::shapes[2],p28::shapes[10]};")
 # fourth element below is verified against registry by build before compilation.
 a=s.index("  auto candidates=");b=s.index("\n  auto fp32=",a)
 s=s[:a]+"  auto candidates=s.type==iq3::Type::IQ4_NL?std::vector<std::string>{\"p42.down.select_vector\",\"p42.down.bank_scalar\"}:s.paired?std::vector<std::string>{\"p42.gate.packed\"}:std::vector<std::string>{\"p42.dense.fourparts\"};"+s[b:]
 a=s.index("auto launched=variant&&candidate_available?");b=s.index(";if(prep.first)",a)
 s=s[:a]+"auto launched=variant?(s.paired||s.type==iq3::Type::IQ4_NL?p42expert::submit(r.device,current,selected,s.paired,v):p42parallel::submit_dense(r.device,current,selected,s.paired,v)):(s.type==iq3::Type::IQ4_NL?p33::submit(r.device,current,\"p33.down.select\",false,v):p28::submit(r.device,current,s.paired?\"p28.paired.wg32\":\"p28.dense.wg32\",s.paired,v))"+s[b:]
 s=s.replace("try{fixture_validation::inject_failure", "try{p42::check_stop();fixture_validation::inject_failure")
 s=s.replace("catch(const std::exception& e){if(!timing", "catch(const std::exception& e){if(p42::stopping)throw;if(!timing")
 # Exact native bytes always compared with the registered R5 CPU arithmetic.
 # The CONTROL uses selected runtime p28/p33 submission rather than R5.
 s=s.replace('selected:"r5"', 'selected:(s.type==iq3::Type::IQ4_NL?"p33.down.select":s.paired?"p28.paired.wg32":"p28.dense.wg32")')
 s=s.replace('std::string("runtime.r5:")', 'std::string("runtime.selected:")')
 s=s.replace("std::ofstream events(out/\"events.jsonl\",std::ios::app),fixture_bytes;", "std::ofstream events(out/\"events.jsonl\",std::ios::app),fixture_bytes;events.exceptions(std::ios::badbit|std::ios::failbit);")
 s=s.replace("auto launched=variant?", "auto host_start=std::chrono::steady_clock::now();auto launched=variant?")
 s=s.replace("r.finish(launched.last);std::vector", "r.finish(launched.last);double host_us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-host_start).count();std::vector")
 s=s.replace('<<",\\"stage_count\\":"<<times.size()','<<",\\"host_wall_us\\":"<<host_us<<",\\"stage_count\\":"<<times.size()')
 # Binding-only twins retain every warm-up, measurement, postflight and rotation.
 s='#include "gate_mode.hpp"\n'+s
 s=s.replace("fixture_validation::only", "p42gate::bindings_only")
 s=s.replace("timing&&!p42gate::bindings_only?216u:1u", "timing?216u:1u")
 s=s.replace("timing&&!p42gate::bindings_only&&iteration", "timing&&iteration")
 (B/"gemv_generated.cpp").write_text(s)
 return B/"gemv_generated.cpp"
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--generate-only",action="store_true");a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
 if shutil.disk_usage("/").free<8_000_000_000:raise RuntimeError("root below8GB")
 resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
 src=generate()
 (B/"tmp").mkdir(exist_ok=True);os.environ["TMPDIR"]=str(B/"tmp")
 if a.generate_only:return
 includes=[P,R,R/"../../stage1/packet3-prep/src",R/"../packet2/kernels",R/"../packet2/loader"]
 commands=[];objects=[]
 # Compile sequentially; one reserved compile slot.
 for source in [src,P/"gemv_main.cpp",P/"expert_submit.cpp",P/"parallel_submit.cpp",P.parent/"packet33-codegen/p33_submit.cpp"]:
  obj=B/(source.stem+".o");argv=[IC,*FLAGS,*["-I"+str(x) for x in includes],"-c",str(source),"-o",str(obj)]
  with (B/(source.stem+".log")).open("w") as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
  commands.append(dict(argv=argv,returncode=r.returncode))
  if r.returncode:raise RuntimeError(str(source)+" failed")
  objects.append(str(obj))
 old=json.loads((P.parent/"packet33-codegen/link-command.json").read_text())
 old=[x for x in old if x.endswith(".o") and not any(t in x for t in ("k2-fixtures-entry", "/gemv_timing.cpp.o"))]
 binary=B/"p42-gemv";spv=B/"spv";spv.mkdir(exist_ok=True)
 argv=[IC,*FLAGS,*objects,*old,"-o",str(binary),"-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib:/usr/lib/x86_64-linux-gnu","/usr/lib/x86_64-linux-gnu/libcrypto.so","-lze_loader","-fsycl-dump-device-code="+str(spv)]
 with (B/"link.log").open("w") as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
 commands.append(dict(argv=argv,returncode=r.returncode))
 receipt=dict(device_executed=False,commands=commands,external_objects={x:sha(Path(x)) for x in old},source_sha256=sha(src))
 if r.returncode==0:receipt["binary_sha256"]=sha(binary)
 (P/"gemv-build.json").write_text(json.dumps(receipt,indent=2)+"\n")
 if r.returncode:raise RuntimeError("link.log")
 print(receipt["binary_sha256"])
if __name__=="__main__":main()
