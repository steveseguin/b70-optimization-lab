#!/usr/bin/env python3
"""CPU numeric gates, real metadata and weights; all output stays in packet19."""
import argparse, gzip, hashlib, importlib.util, json, os, shutil, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
P16=HERE.parent/"packet16-decode"
ROOT=HERE.parents[3]
INPUT=P16/"build/input"
ORACLE=ROOT/"experiments/qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v1-parallel-20261011/incident-retrospective"
SCRATCH=HERE/"build/scratch"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(HERE/name).write_text(json.dumps(obj,indent=2)+"\n")
def cpu(binary):
 dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
 assert not any(s in dynamic.lower() for s in ("libsycl","libze_loader","libur_loader","libopencl"))
def integration():
 # Invoke the original test body; redirect its one packet-local write.
 source=(P16/"test.py").read_text().replace("(HERE/\x27memory-plan.json\x27)",repr(str(HERE/"build/memory-plan.json")))
 # The expression above needs Path rather than a plain string.
 source=source.replace(repr(str(HERE/"build/memory-plan.json")),"Path("+repr(str(HERE/"build/memory-plan.json"))+")")
 ns={"__file__":str(P16/"test.py"),"__name__":"packet16_tests"};exec(compile(source,str(P16/"test.py"),"exec"),ns)
 binary=HERE/"build/patched/depcheck-runtime";cpu(binary);rows=[]
 for seed in (0,1,17,73):
  for mode in ("parallel","core"):
   os.environ["DEPCHECK_SEED"]=str(seed);os.environ["DEPCHECK_REPORT"]=str(HERE/"build/last-integration-sanitizer.json")
   result=ns["run"](binary,SCRATCH/f"integration-{seed}-{mode}",INPUT,mode)
   rows.append(dict(seed=seed,mode=mode,result=result))
   print("integration",seed,mode,len(result["tests"]),"PASS",flush=True)
 write("integration-gates.json",dict(passed=True,original_test_sha256=sha(P16/"test.py"),cases_per_mode=13,seeds=[0,1,17,73],runs=rows))

def run(name,mode,seed,tokens,max_new,trace=False):
 binary=HERE/"build"/mode/"depcheck-runtime";cpu(binary)
 out=SCRATCH/name;report=SCRATCH/(name+"-sanitizer.json");log=SCRATCH/(name+".log")
 model=json.loads((INPUT/"input.json").read_text())["model_dir"]
 args=[str(binary),"--card","0","--cards","2","--memory","resident","--stage","decode","--nongemv","parallel","--gemv","frozen","--context","256","--seconds","10800","--max-new",str(max_new),"--input",str(tokens),"--model-dir",model,"--plan",str(INPUT/"plan.tsv"),"--identity",str(INPUT/"identity.tsv"),"--output",str(out)]
 env=dict(os.environ,DEPCHECK_SEED=str(seed),DEPCHECK_REPORT=str(report))
 if trace:env["DEPCHECK_TRACE"]=str(SCRATCH/(name+".jsonl"))
 else:env.pop("DEPCHECK_TRACE",None)
 before={str(binary):sha(binary),str(tokens):sha(tokens),str(INPUT/"plan.tsv"):sha(INPUT/"plan.tsv"),str(INPUT/"identity.tsv"):sha(INPUT/"identity.tsv")}
 print("START",name,flush=True);start=time.monotonic()
 with log.open("w") as f:p=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env,timeout=10900)
 receipt=json.loads((out/"receipt.json").read_text());san=json.loads(report.read_text())
 fixtures={str(f.relative_to(out)):sha(f) for f in sorted(out.glob("step*/layer-*.bf16"))}
 result=dict(name=name,mode=mode,seed=seed,argv=args,returncode=p.returncode,wall_seconds=time.monotonic()-start,bindings=before,receipt={**receipt,"teardown":[{k:v for k,v in t.items() if k!="sequence"} for t in receipt["teardown"]]},sanitizer=san,fixtures=fixtures)
 assert all(sha(Path(f))==v for f,v in before.items()),"input changed"
 if trace:
  raw=SCRATCH/(name+".jsonl");dest=HERE/(name+"-submissions.jsonl.gz")
  with raw.open("rb") as f,gzip.open(dest,"wb",compresslevel=9) as g:shutil.copyfileobj(f,g)
  result["trace"]=dict(path=dest.name,sha256=sha(dest),uncompressed_bytes=raw.stat().st_size)
 write(name+".json",result)
 assert receipt["passed"] and not receipt["device_executed"],result
 assert p.returncode==(2 if san["violations"] else 0),result
 if mode=="patched":assert not san["violations"],san
 print("END",name,"seconds",round(result["wall_seconds"],1),"violations",len(san["violations"]),flush=True)
 return result

def real_short():
 # Two original prompt tokens exercise position0 with the prefill head omitted;
 # max-new2 also executes a genuine model-generated token input at position2.
 tokens=SCRATCH/"short-tokens.txt";tokens.write_text("\n".join((INPUT/"tokens.txt").read_text().split()[:2])+"\n")
 shutil.copyfile(INPUT/"vocab.bin",SCRATCH/"vocab.bin")
 results=[run("real-short-shipped","shipped",0,tokens,2,True)]
 for seed in (0,1,17,73):results.append(run(f"real-short-patched-{seed}","patched",seed,tokens,2,seed==1))
 expected=results[0]
 for r in results[1:]:
  assert r["fixtures"]==expected["fixtures"] and r["receipt"]["tokens"]==expected["receipt"]["tokens"]
 write("real-short-gates.json",dict(passed=True,prompt_tokens=2,generated_tokens=2,positions=3,layer_hashes_per_run=len(expected["fixtures"]),seeds=[0,1,17,73],tokens=expected["receipt"]["tokens"],runs=[r["name"] for r in results],note="Truncated-prefix safety gate, not full prompt oracle or performance evidence."))

def real_full():
 r=run("real-first-token-patched","patched",17,INPUT/"tokens.txt",1)
 layers=[]
 for layer in range(48):
  name=f"step1/layer-{layer:02}.bf16";expected=sha(ORACLE/name)
  layers.append(dict(layer=layer,sha256=r["fixtures"].get(name),oracle_sha256=expected,exact=r["fixtures"].get(name)==expected))
 expected=json.loads((ORACLE/"result.json").read_text())["tokens"][:1]
 result=dict(passed=all(x["exact"] for x in layers) and r["receipt"]["tokens"]==expected,layer_matches=sum(x["exact"] for x in layers),layers=layers,tokens=r["receipt"]["tokens"],expected_tokens=expected,oracle_result_sha256=sha(ORACLE/"result.json"),device_executed=False)
 write("real-oracle-gate.json",result);assert result["passed"]

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
 p=argparse.ArgumentParser();p.add_argument("gate",choices=["integration","real-short","real-full","all"]);a=p.parse_args();SCRATCH.mkdir(parents=True,exist_ok=True)
 for name,fn in (("integration",integration),("real-short",real_short),("real-full",real_full)):
  if a.gate in (name,"all"):fn()
if __name__=="__main__":main()
