#!/usr/bin/env python3
"""Serial CPU-only ownership-model builds; all scratch deleted after success/failure."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
FLAGS=["-std=c++20", "-O1", "-g", "-fno-fast-math", "-ffp-contract=off", "-fno-omit-frame-pointer"]
def call(argv, **kwargs):
    return subprocess.run(["nice", "-n", "19", "ionice", "-c", "3", *map(str,argv)],
        env={**os.environ,"OMP_NUM_THREADS":"2"},check=True,**kwargs)
def main():
    build=HERE/"build";build.mkdir(exist_ok=True)
    rows=[]
    with tempfile.TemporaryDirectory(prefix="lifetime-",dir=build) as tmp:
        for compiler in ("g++","/opt/intel/oneapi/compiler/2026.0/bin/icpx"):
            path=shutil.which(compiler)
            if path is None: raise RuntimeError("required compiler absent: "+compiler)
            for sanitize in (False,True):
                flags=FLAGS+(["-fsanitize=address,undefined"] if sanitize else [])
                binary=Path(tmp)/(Path(compiler).name+("-san" if sanitize else ""))
                # Flags appear on the single compile-and-link driver command.
                command=[path,*flags,HERE/"lifetime_test.cpp","-o",binary]
                call(command,capture_output=True,text=True)
                digest=hashlib.sha256(binary.read_bytes()).hexdigest()
                for fresh in range(2):
                    run=call([binary],capture_output=True,text=True)
                    row=json.loads(run.stdout)
                    if not row.get("passed"): raise RuntimeError("lifetime model failed")
                    rows.append(dict(compiler=path,sanitizers=sanitize,fresh_process=fresh+1,
                        flags=flags,binary_sha256=digest,**row))
    receipt=dict(schema="own-runtime.packet34.lifetime-tests.v1",passed=True,device_executed=False,
                 total_checks=sum(r["checks"] for r in rows),runs=rows,scratch_deleted=True)
    (HERE/"lifetime-tests.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(dict(passed=True,runs=len(rows),checks=receipt["total_checks"])))
if __name__=="__main__":main()
