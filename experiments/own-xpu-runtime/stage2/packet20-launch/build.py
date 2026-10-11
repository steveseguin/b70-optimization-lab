#!/usr/bin/env python3
"""CPU-only build, gates and sealing. Never invoke a device executable."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
ROOT = HERE.parents[3]
PREFIX = ["nice", "-n", "19", "ionice", "-c", "3", "env", "OMP_NUM_THREADS=2"]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,r):p.write_text(json.dumps(r,indent=2)+"\n")
def run(argv, **kwargs):
    return subprocess.run(PREFIX + list(map(str,argv)),check=True,**kwargs)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seal-existing",action="store_true",help="verify existing compiler receipts, rerun CPU harness, seal; no rebuild")
    args=parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
    BUILD.mkdir(exist_ok=True)
    scratch=BUILD/"scratch-root"
    scratch.mkdir(exist_ok=False)
    env=dict(os.environ,TMPDIR=str(scratch),PYTHONDONTWRITEBYTECODE="1")
    env["LD_LIBRARY_PATH"]="/opt/intel/oneapi/compiler/2026.0/lib"+(":"+env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else "")
    started=time.monotonic()
    try:
        if not args.seal_existing:
            run([sys.executable,"-B",HERE/"fusion/build.py"],env=env)
            run([sys.executable,"-B",HERE/"issuing/build.py"],env=env)
        tests=run([sys.executable,"-B",HERE/"test_window.py"],capture_output=True,text=True,env=env)
        (HERE/"evidence/window-tests.txt").write_text(tests.stdout+tests.stderr)
        fusion=read(HERE/"fusion/build-receipt.json")
        issuing=read(HERE/"issuing/build-receipt.json")
        assert fusion["passed"] and issuing["compiled"]
        assert fusion["device_executed"] is False and issuing["device_executed"] is False
        # The issuing builder binds precise compile/link commands and artifacts.
        # Recheck source receipts here, so --seal-existing cannot bless stale code.
        for folder, receipt in (("fusion",fusion),("issuing",issuing)):
            for rel,digest in receipt.get("sources",{}).items():
                p=Path(rel)
                if not p.is_absolute():p=HERE/folder/p
                assert sha(p)==digest, "stale compiler receipt: "+str(p)
        for rel,digest in issuing["sha256"].items():
            p=Path(rel)
            if not p.is_absolute():p=HERE/p
            assert sha(p)==digest, "stale issuing artifact: "+str(p)
        assert sha(BUILD/"fusion-icpx/fusion-device")==fusion["device_sha256"]
        for compiler, entry in fusion["builds"].items():
            assert sha(BUILD/("fusion-"+compiler)/"fusion-host")==entry["binary_sha256"]
        rope=HERE.parent/"packet17-detmath/rope.bf16"
        reference=HERE.parent/"packet1b/reference.py"
        assert sha(rope)==fusion["rope_sha256"]
        assert sha(reference)==fusion["fixture_reference_sha256"]
        binary=BUILD/"issuing/launch-bench"
        preflight=run(["ldd",binary],capture_output=True,text=True,env=env)
        assert "not found" not in preflight.stdout+preflight.stderr
        save(HERE/"evidence/loader-preflight.json",dict(returncode=preflight.returncode,stdout=preflight.stdout,stderr=preflight.stderr,device_executed=False))
        # Bind local tracked inputs plus external source dependencies actually compiled.
        paths=[p for p in HERE.rglob("*") if p.is_file() and BUILD not in p.parents and p.name!="build-receipt.json" and "__pycache__" not in p.parts]
        paths += [rope,reference,HERE.parent/"packet18-decode-v2/census.json",HERE.parent/"packet18-decode-v2/DEADLINES.md",HERE.parent/"packet18-decode-v2/deadline-journal.json",HERE/"fusion/build-receipt.json",HERE/"issuing/build-receipt.json",binary,BUILD/"issuing/raw.spv",BUILD/"fusion-icpx/fusion-device"]
        for dep in list(BUILD.rglob("*.o.d")):
            for token in dep.read_text().replace("\\\n", " ").split():
                candidate=Path(token)
                if candidate.is_absolute() and candidate.is_file() and ROOT in candidate.parents and BUILD not in candidate.parents:
                    paths.append(candidate)
        hashes={os.path.relpath(p,HERE):sha(p) for p in sorted(set(paths))}
        reuse=dict(scope="unchanged fusion oracle/fixture/fresh-repeat gates; issuing recompiled; no device ran",
                   receipts={name:sha(HERE/"fusion"/name) for name in ("build-receipt.json", "gnu-0.json", "gnu-1.json", "icpx-0.json", "icpx-1.json")})
        receipt=dict(reused_cpu_evidence=reuse, schema="own-runtime.packet20.build.v1",passed=True,device_executed=False,arithmetic="iq3-p17-detmath-v2",compiler=issuing.get("compiler_version"),fusion_receipt_sha256=sha(HERE/"fusion/build-receipt.json"),issuing_receipt_sha256=sha(HERE/"issuing/build-receipt.json"),window_tests_sha256=sha(HERE/"evidence/window-tests.txt"),binary="build/issuing/launch-bench",binary_sha256=sha(binary),hashes=hashes,elapsed_seconds=time.monotonic()-started,device_timing_measured=False,opaque_driver_memory_bound_proven=False,healthy_duration_under_60s_proven=False)
        save(HERE/"build-receipt.json",receipt)
        receipt["hashes"]["build-receipt.json"]=sha(HERE/"build-receipt.json")
        save(BUILD/"prepared.json",receipt)
        print("Packet20 CPU gates and seal passed; no device executed.")
    finally:
        shutil.rmtree(scratch)

if __name__=="__main__":main()
