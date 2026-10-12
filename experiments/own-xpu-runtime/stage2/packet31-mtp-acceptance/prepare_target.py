"""Build a CPU-only instrumented copy of the frozen v2 oracle; no original edits."""
from pathlib import Path
import hashlib, json, os, subprocess, sys, struct
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; S=P.parent
B=P/"build"; OLD=S/"packet17-detmath"
def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def ensure_rope():
    # Quote includes find this private fallback when packet17 build/ is absent.
    # The tracked BF16 bytes, never a fresh libm evaluation, are authoritative.
    raw=(OLD/"rope.bf16").read_bytes()
    assert hashlib.sha256(raw).hexdigest()=="ccdfe87fa7360fc6b4aa7c999fa7b920f791f5635010cf303ae76f4d01dca058"
    values=struct.unpack("<"+"H"*(len(raw)//2),raw)
    header="#pragma once\nnamespace rope_constants {\ninline constexpr int positions=4096;\ninline constexpr uint16_t table[]={\n"+",\n".join(",".join(str(v) for v in values[i:i+32]) for i in range(0,len(values),32))+"\n};\n}\n"
    dest=B/"build/rope_table.hpp";dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(header)
    assert sha(dest)=="90cecf716358c8bc10d8bc166d3257eeacef783b0ef882ad9be0beb9efc83885"
    old=OLD/"build/rope_table.hpp"
    if old.exists():assert sha(old)==sha(dest)
    return sha(dest)
def check_frozen_sources():
    frozen=ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/receipt.json"
    sources=json.loads(frozen.read_text())["arithmetic"]["arithmetic_sources"]
    for name,digest in sources.items():
        path=B/"build/rope_table.hpp" if name.endswith("packet17-detmath/build/rope_table.hpp") else ROOT/name
        assert sha(path)==digest,("frozen oracle dependency changed",name)
    (P/"source-identity-gate.json").write_text(json.dumps(dict(passed=True,reference_receipt_sha256=sha(frozen),sources=sources),indent=2)+"\n")
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    B.mkdir(exist_ok=True)
    os.environ["TMPDIR"]=str(B)
    rope_sha256=ensure_rope()
    check_frozen_sources()
    source=(OLD/"oracle.cpp").read_text().replace("#include \"runtime_main.cpp\"",f"#include \"{OLD}/runtime_main.cpp\"")
    source=source.replace("==\"2\",\"two numeric threads\"","==\"5\",\"five numeric threads\"")
    source=source.replace("a.context=192", "a.context=512")
    source=source.replace("if(capture==0 && (l.label.starts_with(\"final.\") || l.label==\"logits\" || l.label==\"argmax\"))continue;", "// All positions include the head to record their greedy prediction.")
    needle="          if(hashes.is_open()) {"
    addition="""          if(layer==47) {
            auto raw=engine->readback(0,engine->buffers[0].at("streams").id,4*p.g.h*2);
            std::ofstream b(out/("streams-"+std::to_string(position)+".bf16"),std::ios::binary);
            b.write(reinterpret_cast<char*>(raw.data()),raw.size());
          }
"""
    assert source.count(needle)==1;source=source.replace(needle,addition+needle)
    source=source.replace("      double seconds=Engine::ms(t)/1000;", """      std::ofstream predictions(out/"predictions.jsonl",std::ios::app);
      predictions<<"{\\\"position\\\":"<<position<<",\\\"input_token\\\":"<<token
        <<",\\\"target_token\\\":"<<engine->integer(0,"next_token")<<"}\\n";
      double seconds=Engine::ms(t)/1000;""")
    source=source.replace("if(step==a.tokens){status=\"token-cap\";break;}","if(step==a.tokens){forward(next,step+1,input.size()+step-1);status=\"token-cap\";break;}")
    (B/"oracle.cpp").write_text(source)
    perf=(OLD/"performance.cpp").read_text().replace("num_threads(2)","num_threads(5)")
    (B/"performance.cpp").write_text(perf)
    owner=S.parent/"stage1/packet3-prep/src"
    flags=["g++","-std=c++20","-O2","-mfma","-fno-fast-math","-ffp-contract=off","-DOWN_RT_HOST_ONLY","-fopenmp"]
    inc=["-I"+str(q) for q in (B,owner,S/"packet2/kernels",S/"packet2/loader",OLD)]
    sources=[B/"oracle.cpp",B/"performance.cpp",OLD/"runtime_kernels.cpp",S/"packet4/owner_retire.cpp",S/"packet2/loader/gguf.cpp",owner/"owner.cpp"]
    cmd=flags+inc+list(map(str,sources))+["-lcrypto","-o",str(B/"target-cpu")]
    subprocess.run(cmd,check=True)
    deps=subprocess.check_output(["readelf","-d",str(B/"target-cpu")],text=True)
    assert not any(s in deps.lower() for s in ("libsycl","ze_loader","opencl","cuda"))
    dependencies=set()
    for src in sources:
        raw=subprocess.check_output(flags+inc+["-MM",str(src)],text=True).replace("\\\n"," ")
        dependencies.update(Path(n).resolve() for n in raw.split()[1:] if Path(n).is_file())
    receipt=dict(command=cmd,dynamic_dependencies=deps,binary_sha256=sha(B/"target-cpu"),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(dependencies)},
        private_rope_header_sha256=rope_sha256,source_oracle_sha256=sha(OLD/"oracle.cpp"),arithmetic="iq3-p17-detmath-v2",threads=5,device_executed=False)
    (P/"target-build-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    sys.path.insert(0,str(S/"packet13-integrate"));from prepare import prepare
    os.environ["OMP_NUM_THREADS"]="2"
    for name in ("incident-retrospective","code-review","customer-email","benchmark-analysis"):
        prepare(B/("input-"+name),ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/prompts"/(name+".txt"))
if __name__=="__main__":main()
