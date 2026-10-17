#!/usr/bin/env python3
"""Compile the diagnostic CPU mock once, run twice, validate, and pin receipts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from preparation import exclusive_cpu_work
from validate import read_rows, validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists(): parser.error("new receipt directory required")
    with exclusive_cpu_work(planned_write_bytes=5_000_000) as limits:
        args.output.mkdir(parents=True)
        build=HERE.parent/"build"/"diagnostics"
        build.mkdir(exist_ok=True)
        binary=build/"cpu-mock"
        commands=[]
        def run(command,name):
            start=datetime.now(timezone.utc).isoformat()
            result=subprocess.run(command,cwd=HERE,text=True,capture_output=True,timeout=90,check=False)
            (args.output/(name+".stdout")).write_text(result.stdout)
            (args.output/(name+".stderr")).write_text(result.stderr)
            commands.append(dict(command=list(map(str,command)),started_utc=start,
                finished_utc=datetime.now(timezone.utc).isoformat(),returncode=result.returncode))
            (args.output/"commands.json").write_text(json.dumps(commands,indent=2)+"\n")
            if result.returncode: raise RuntimeError(f"{name} failed: {result.stderr[-1000:]}")
            return result.stdout
        sources=[HERE/name for name in ("trace.hpp","mock_test.cpp","validate.py","cache_report.py","test_validate.py","run_cpu.py")]
        sources.append(HERE.parent/"preparation.py")
        pins={str(p.relative_to(HERE.parent)):sha(p) for p in sources}
        compiler=run(["c++","--version"],"compiler").splitlines()[0]
        run(["c++","-std=c++20","-O0","-Wall","-Wextra","-Werror",str(HERE/"mock_test.cpp"),"-o",str(binary)],"compile")
        first=run([str(binary)],"mock-0")
        second=run([str(binary)],"mock-1")
        if first!=second: raise RuntimeError("fresh-process diagnostic mocks differ")
        gates=[validate(read_rows(args.output/f"mock-{i}.stdout")) for i in range(2)]
        run([sys.executable,"-B",str(HERE/"test_validate.py")],"schema-tests")
        if any(sha(p)!=pins[str(p.relative_to(HERE.parent))] for p in sources):
            raise RuntimeError("diagnostic source changed during gate")
        result=dict(schema="ownrt.packet46.diagnostic-cpu-receipt.v1",passed=True,
                    device_ran=False,model_weights_read=False,limits=limits,
                    compiler=compiler,binary_sha256=sha(binary),source_sha256=pins,
                    fresh_process_repeats_equal=True,validator_results=gates,
                    trace_sha256=sha(args.output/"mock-0.stdout"),
                    finished_utc=datetime.now(timezone.utc).isoformat())
        (args.output/"receipt.json").write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(dict(passed=True,receipt=str(args.output/"receipt.json"))))


if __name__ == "__main__": main()
