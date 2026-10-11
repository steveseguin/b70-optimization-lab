#!/usr/bin/env python3
"""Compile CPU overlays only. Original packet sources remain read-only."""
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
LOCAL=Path(__file__).resolve().parent
HERE=LOCAL.parent/"packet19-depcheck"
STAGE=HERE.parent

def cpu_owner_overlay(text):
 # CPU process memory is reclaimable after a refused shutdown. The production
 # owner retains native devices indefinitely; never alter its checked-in code.
 pattern=r"(\[\[noreturn\]\] void hold_for_supervisor\(\) \{).*?(\n\}\n)(?=void forget_event_queues)"
 text,count=re.subn(pattern,lambda m:m[1]+"\n  depcheck::fatal_cpu_exit();"+m[2],text,flags=re.S)
 if count!=1:raise RuntimeError("CPU owner retention anchor changed")
 return '#include '+json.dumps(str(HERE/"fatal_cpu.hpp"))+"\n"+text

def main():
 p=argparse.ArgumentParser();p.add_argument("--patched",action="store_true");p.add_argument("--source",type=Path,default=LOCAL);p.add_argument("--tag",default=None);a=p.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
 mode=a.tag or ("patched" if a.patched else "shipped")
 if not re.fullmatch(r"[A-Za-z0-9_-]+",mode):raise ValueError("build tag")
 build=LOCAL/"build"/mode;build.mkdir(parents=True,exist_ok=True)
 (build/"depcheck-runtime").unlink(missing_ok=True)
 source=a.source.resolve();manifest={};staged={}
 if (source/"runtime_kernels.cpp").exists():
  import shutil
  asset=source/"rope.bf16";shutil.copyfile(asset,build/asset.name)
  manifest[str(asset)]=hashlib.sha256(asset.read_bytes()).hexdigest()
 def stage(path):
  if path in staged:return staged[path]
  dest=build/(str(path.relative_to(STAGE)).replace("/","__"));staged[path]=dest
  dest.write_text(read(path));return dest
 def read(path):
  original=path.resolve();relative=original.relative_to(STAGE)
  patch=HERE/"patched"/relative
  target=patch if a.patched and patch.exists() else original
  text=target.read_text();
  if target.name=="canary.hpp":text=text.replace("auto compiled=raw->canary_bundle();", "int compiled=0;")
  manifest[str(target)]=hashlib.sha256(target.read_bytes()).hexdigest()
  # Resolve quoted includes back to original source directory, selectively using
  # our patched dependencies. Never populate/edit another packet build tree.
  def inc(m):
   name=m.group(1);p=(original.parent/name).resolve()
   if original in (HERE/"instrument.hpp",HERE/"instrument18.hpp",LOCAL/"instrument21.hpp"):
    if name=="../packet16-decode/performance.hpp":p=source/"performance.hpp"
    if name=="../packet15-nongemv/kernels.hpp" and (source/"runtime_kernels.cpp").exists():p=source/"kernels.hpp"
   if not p.exists():
    for folder in (source, STAGE.parent/"stage1/packet3-prep/src", STAGE/"packet2/kernels", STAGE/"packet2/loader"):
     candidate=(folder/name).resolve()
     if candidate.exists():p=candidate;break
   if p.exists():
    if p.is_relative_to(STAGE):p=stage(p)
    return "#include "+json.dumps(str(p))
   return m.group(0)
  return re.sub(r'#include "([^"]+)"',inc,text)
 texts={n:read(source/n) for n in ("main.cpp","performance.cpp","adapter.cpp","gemv_batch.cpp")}
 # Replace only the host mock, preserving Engine, plan, arithmetic and owner.
 m=texts["main.cpp"]
 anchors={"    (void)c;":1,"auto id=dev(c).arena.allocate(\"card\"+std::to_string(c)+\":\"+name, bytes, m, cat, life);":1,"      std::memcpy(dev(c).arena.row(slab[c]).pointer,":1,"    lookup_ids.clear();":1,"int main(int argc, char **argv) {":1}
 for anchor,minimum in anchors.items():
  if m.count(anchor)!=minimum:raise RuntimeError("instrumentation anchor changed: "+anchor)

 begin=m.index("class Host final :");end=m.index("#endif",begin)
 m=m[:begin]+"using Host = depcheck::Backend;\n"+m[end:]
 m=m.replace("    (void)c;","    depcheck::card=c;")
 m=m.replace("auto id=dev(c).arena.allocate(\"card\"+std::to_string(c)+\":\"+name, bytes, m, cat, life);", "auto id=dev(c).arena.allocate(\"card\"+std::to_string(c)+\":\"+name, bytes, m, cat, life);\n    depcheck::checker.locate(dev(c).arena.row(id).pointer,bytes)->second.name=\"card\"+std::to_string(c)+\":\"+name;")
 m=m.replace("      std::memcpy(dev(c).arena.row(slab[c]).pointer,", "      depcheck::checker.host_write(dev(c).arena.row(slab[c]).pointer,k);\n      std::memcpy(dev(c).arena.row(slab[c]).pointer,")
 m=m.replace("    lookup_ids.clear();","    ++depcheck::position; depcheck::checker.site=\"position=\"+std::to_string(depcheck::position)+\":lookup-upload\";\n    lookup_ids.clear();")
 m=m.replace("    int c = l.card;", "    int c = l.card; depcheck::checker.site=\"position=\"+std::to_string(depcheck::position)+\":\"+l.label;")
 m=m.replace("    drain();\n    auto started=std::chrono::steady_clock::now();\n    std::vector<uint8_t> b(n);", "    depcheck::checker.site=\"position=\"+std::to_string(depcheck::position)+\":readback:\"+dev(c).arena.row(src).label;\n    drain();\n    auto started=std::chrono::steady_clock::now();\n    std::vector<uint8_t> b(n);")
 m=m.replace("int main(int argc, char **argv) {", "int packet_main(int argc, char **argv) {")
 m+="\nint main(int argc,char**argv){depcheck::setup();return depcheck::report(packet_main(argc,argv));}\n"
 texts["main.cpp"]=m
 texts["core.cpp"]=read(source/"runtime_kernels.cpp" if (source/"runtime_kernels.cpp").exists() else STAGE/"packet4/kernels.cpp")
 (build/"instrument.hpp").write_text(read(LOCAL/"instrument21.hpp"))
 for name,t in texts.items():
  if name!="main.cpp":
   if not (t.count("d.compute(")+t.count("device.compute(")):raise RuntimeError("compute interception missing: "+name)
   t=t.replace("d.compute(","depcheck::submit(d, ").replace("device.compute(","depcheck::submit(device, ")
  (build/name).write_text("#include "+json.dumps(str(build/"instrument.hpp"))+"\n"+t)
 owner=build/"owner.cpp";owner.write_text(cpu_owner_overlay(read(source/"owner.cpp")));src=[build/n for n in texts]+[owner,source/"owner_retire.cpp",STAGE/"packet2/loader/gguf.cpp"]
 flags=["-std=c++20","-MMD","-O3","-march=native","-fopenmp","-fno-fast-math","-ffp-contract=off","-DOWN_RT_HOST_ONLY","-I"+str(STAGE.parent/"stage1/packet3-prep/src"),"-I"+str(source),"-I"+str(STAGE/"packet2/kernels"),"-I"+str(STAGE/"packet2/loader")]
 if (source/"runtime_kernels.cpp").exists():flags.append("-DDEPCHECK_PACKET18")
 # Two compile processes maximum; caller inherits nice/ionice/thread limit.
 import concurrent.futures
 def compile(src):
  obj=build/(src.stem+".o");cmd=["g++",*flags,"-c",str(src),"-o",str(obj)];subprocess.run(cmd,check=True);return obj
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:objects=list(pool.map(compile,src))
 binary=build/"depcheck-runtime";subprocess.run(["g++","-fopenmp","-fno-fast-math","-ffp-contract=off",*map(str,objects),"-lcrypto","-o",str(binary)],check=True)
 dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
 assert not any(x in dynamic.lower() for x in ("libsycl","libze_loader","libur_loader","libopencl"))
 for depfile in build.glob("*.d"):
  for name in depfile.read_text().replace("\\\n"," ").split()[1:]:
   path=Path(name)
   if path.is_file():manifest[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
 for name,digest in list(manifest.items()):
  if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise RuntimeError("source changed during build: "+name)
 manifest[str(LOCAL/"depcheck_build.py")]=hashlib.sha256((LOCAL/"depcheck_build.py").read_bytes()).hexdigest()
 (build/"build.json").write_text(json.dumps(dict(mode=mode,compiler=subprocess.check_output(["g++","--version"],text=True).splitlines()[0],sources=manifest,binary=str(binary),sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),flags=flags,device_executed=False),indent=2)+"\n")
 print(binary,flush=True)
if __name__=="__main__":main()
