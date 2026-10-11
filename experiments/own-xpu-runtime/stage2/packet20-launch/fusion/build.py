import hashlib,json,os,shlex,shutil,subprocess,time,sys,re
from pathlib import Path
P=Path(__file__).resolve().parent;B=P.parent/"build";S=P.parent.parent/"packet17-detmath"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):subprocess.run(list(map(str,args)),check=True,timeout=900)
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
B.mkdir(exist_ok=True)
scratch=B/"fusion-scratch";scratch.mkdir(exist_ok=True);os.environ["TMPDIR"]=str(scratch)
fixtures=B/"fusion-fixtures"
if not fixtures.exists():run(["/home/steve/.venvs/vllm-xpu/bin/python","-B",P/"fixtures.py","--output",fixtures])
# Exact table bytes are versioned as packet17 rope.bf16; no generated source
# dependency on its mutable build tree remains.
import struct
values=struct.unpack("<262144H",(S/"rope.bf16").read_bytes())
(B/"fusion-rope.hpp").write_text("#pragma once\nnamespace rope_constants { inline constexpr int positions=4096; inline constexpr uint16_t table[]={"+",".join(map(str,values))+"};}\n")
receipt={"device_executed":False,"fixtures":{},"builds":{}}
for tag,compiler in [("gnu","g++"),("icpx","/opt/intel/oneapi/compiler/2026.0/bin/icpx")]:
 build=B/("fusion-"+tag);run(["cmake","-S",P,"-B",build,"-DCMAKE_CXX_COMPILER="+compiler,"-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"]);run(["cmake","--build",build,"-j1"])
 if tag=="gnu":
  with (P/"dag.json").open("w") as out:subprocess.run([str(build/"fusion-plan")],check=True,stdout=out,timeout=20)
  run([sys.executable,"-B",P/"counts.py"])
 binary=build/"fusion-host";deps=subprocess.check_output(["readelf","-d",str(binary)],text=True);assert not any(x in deps for x in ["libsycl","libze_loader","libur_loader","libOpenCL"])
 receipt["builds"][tag]={"binary_sha256":sha(binary),"compiler":subprocess.check_output([compiler,"--version"],text=True).splitlines()[0]}
 if tag=="icpx":
  link=(build/"CMakeFiles/fusion-device.dir/link.txt").read_text();required=["-fsycl","-fno-fast-math","-ffp-contract=off","-fdenormal-fp-math=ieee","-foffload-fp32-prec-div","-foffload-fp32-prec-sqrt"]
  assert all(x in shlex.split(link) for x in required);commands=json.loads((build/"compile_commands.json").read_text());assert all(all(x in shlex.split(c["command"]) for x in required) for c in commands if c["file"].endswith("device.cpp"))
  receipt["device_link"]=link.strip();receipt["device_sha256"]=sha(build/"fusion-device")
 for repeat in range(2):
  out=P/(tag+"-"+str(repeat)+".json");raw=B/(tag+"-"+str(repeat)+".outputs");start=time.monotonic();run([binary,fixtures,out,raw]);r=json.loads(out.read_text());r["output_sha256"]=sha(raw);r["elapsed_s"]=time.monotonic()-start;out.write_text(json.dumps(r,indent=2)+"\n");receipt["fixtures"][tag+str(repeat)]=r;raw.unlink()
assert len({r["output_sha256"] for r in receipt["fixtures"].values()})==1
receipt["fixture_input_sha256"]={x.name:sha(x) for x in fixtures.glob("*.fixture")};receipt["fixture_reference_sha256"]=sha(P.parent.parent/"packet1b/reference.py");receipt["passed"]=True;receipt["sources"]={str(x.relative_to(P)):sha(x) for x in P.rglob("*") if x.is_file() and x.suffix in (".hpp",".cpp",".py",".txt")};receipt["rope_sha256"]=sha(S/"rope.bf16")
closure={};pending=[P/"gate.cpp",P/"device.cpp",P/"plan.cpp"]
while pending:
 path=pending.pop().resolve()
 if str(path) in closure:continue
 closure[str(path)]=sha(path)
 for name in re.findall(r'^\s*#include\s*"([^"]+)"',path.read_text(),re.M):
  child=(path.parent/name).resolve()
  if child.is_file():pending.append(child)
receipt["include_closure_sha256"]=closure
(P/"build-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")

shutil.rmtree(scratch)
shutil.rmtree(fixtures)
