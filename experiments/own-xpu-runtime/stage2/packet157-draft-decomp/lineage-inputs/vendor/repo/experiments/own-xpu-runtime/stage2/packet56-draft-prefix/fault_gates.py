#!/usr/bin/env python3
"""CPU-only failure/stall gates using the rebuilt packet32 host rank executable."""
import argparse
import json
import os
from pathlib import Path
import time
import pipeline as p

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    p.require(os.getpriority(os.PRIO_PROCESS,0)==19,"nice 19 required")
    p.require(os.environ.get("OMP_NUM_THREADS")=="2","OMP_NUM_THREADS=2 required")
    p.require(args.binary.resolve().parent.name in ("host","gnu-host","clang-host") and args.binary.resolve().parent.parent.name=="build","only known host build path admitted")
    p.require(not args.output.exists(),"new output directory required")
    args.output.mkdir(parents=True)
    cases=[]
    for name,opcode in (("rank-failure",p.FAIL),("rank-stall",p.STALL)):
        out=args.output/name;out.mkdir()
        a=p.parser().parse_args(["--binary",str(args.binary.resolve()),"--output",str(out),"--mini","--seconds","120","--wait-seconds","1"])
        t=None;failure=None;begin=time.monotonic()
        try:
            t=p.Transport.__new__(p.Transport);t.__init__(a,out)
            try:t.call(0,opcode)
            except (ValueError,ConnectionError,OSError) as exc:failure=str(exc)
            p.require(failure is not None,"injected rank fault went unnoticed")
            t.stop(failure);t.close(False)
            ownership=json.loads((out/"ownership.json").read_text())
            receipts=[json.loads((out/f"rank{i}/receipt.json").read_text()) for i in range(2)]
            p.require(not ownership["retained_pids"] and ownership["signals_sent"]==0,"fault did not drain both without signals")
            p.require(all(c.poll()==1 for c in t.children),"both ranks should exit their cooperative failure paths")
            p.require(all(not r["passed"] and not r["device_executed"] for r in receipts),"native host fault receipt mismatch")
            p.require(all(len(r["teardown"])==1 and r["teardown"][0]["safe_to_exit"] and not r["teardown"][0]["in_flight"] and not r["teardown"][0]["live_bytes"] for r in receipts),"unsafe native teardown")
            first=out/"failure-before-teardown.json"
            p.require(first.exists(),"missing failure-before-teardown receipt")
            p.require(first.stat().st_mtime_ns <= (out/"rank1/receipt.json").stat().st_mtime_ns,"peer teardown receipt preceded stop receipt")
            cases.append(dict(name=name,passed=True,observed_failure=failure,elapsed_seconds=time.monotonic()-begin,signals_sent=0))
        except Exception as exc:
            cases.append(dict(name=name,passed=False,error=str(exc),elapsed_seconds=time.monotonic()-begin))
            if t is not None and hasattr(t,"stop_write"):
                t.stop(exc)
                try:t.close(False)
                except Exception as close:cases[-1]["teardown_error"]=str(close)
        print(json.dumps(cases[-1]),flush=True)
    result=dict(passed=all(row["passed"] for row in cases),device_executed=False,binary_sha256=p.sha(args.binary),cases=cases)
    p.save(args.output/"receipt.json",result)
    return 0 if result["passed"] else 1
if __name__=="__main__":raise SystemExit(main())
