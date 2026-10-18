#!/usr/bin/env python3
"""Host-only engine integration, including the actual strict selection parser."""
import json,subprocess,resource,argparse
from pathlib import Path
import pipeline
from build_engine import P,B,ROOT,sha,save,limits

def host(binary):
 links=subprocess.check_output(["readelf","-d",str(binary)],text=True).lower()
 assert not any(s in links for s in ("libsycl","libze_loader","libur_loader","libopencl"))
def run(label,binary,selection=None,timing="token"):
 host(binary);dest=B/("cpu-engine-"+label)
 pipeline.P=P if selection is None else P/"selections"/selection
 args=pipeline.parser().parse_args(["--binary",str(binary),"--output",str(dest),"--mini","--context","256","--tokens","24","--seconds","180","--wait-seconds","120","--native-nice","19","--draft","mtp","--draft-rank","1","--controller","native","--timing","token","--retain-steps","1-24"])
 args.host_memory="resident";args.draft="mtp";args.timing=timing
 if selection:args.selection_sha256=sha(pipeline.P/"selection.json")
 result=pipeline.run(args);assert result["passed"],result.get("error")
 fixtures={str(f.relative_to(dest)):sha(f) for rank in ("rank0","rank1") for f in (dest/rank).glob("step*/layer-*.bf16")};assert len(fixtures)==96
 value=dict(tokens=result["tokens"],fixtures=fixtures);assert len(value["tokens"])==24
 save(P/"evidence"/("engine-"+label+".json"),value)
 print(label,"96 fixtures + 24 tokens PASS",flush=True)
 return value

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 ap=argparse.ArgumentParser();ap.add_argument("--tag",default="");args=ap.parse_args();tag=(args.tag+"-") if args.tag else ""
 parent=run(tag+"packet64",P.parent/"packet64-record-bundle/build/gnu-host/own-rt-iq3")
 for name in ("production","wg64","wg128","prefetch64","wide64"):
  actual=run(tag+name,B/"gnu-host/own-rt-iq3",name);assert actual==parent,"host target integration differs"
 assert run(tag+"attribution",B/"gnu-host/own-rt-iq3","production",timing="attribution")==parent
 # --mini does not hit routed production widths; p65_cpu is the expert oracle.
 save(P/"evidence/engine-integration.json",dict(passed=True,device_executed=False,selection_parser="all five actual selections accepted by full host engine",cases=6,attribution_host_identity=True,fixtures_per_case=96,tokens_per_case=24,scope="mini engine identity only; production expert correctness lives in CPU byte fixture",binary_sha256=sha(B/"gnu-host/own-rt-iq3"),sources={str(f.relative_to(ROOT)):sha(f) for f in (P/"validate_engine.py",P/"pipeline.py")}))
if __name__=="__main__":main()
