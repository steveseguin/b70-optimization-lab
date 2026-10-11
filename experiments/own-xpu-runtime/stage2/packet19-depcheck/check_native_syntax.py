#!/usr/bin/env python3
"""Parse patched SYCL sources without linking/running a device executable."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
BUILD = HERE / "build/native-syntax"

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get("OMP_NUM_THREADS") == "2"
    BUILD.mkdir(parents=True, exist_ok=True)
    staged, hashes = {}, {}
    def stage(original):
        original = original.resolve()
        if original in staged:
            return staged[original]
        relative = original.relative_to(BASE)
        dest = BUILD / str(relative).replace("/", "__")
        staged[original] = dest
        patch = HERE / "patched" / relative
        target = patch if patch.exists() else original
        hashes[str(target)] = hashlib.sha256(target.read_bytes()).hexdigest()
        def include(match):
            name = match.group(1)
            source = (original.parent / name).resolve()
            if not source.exists():
                for folder in (BASE / "packet16-decode", BASE.parent / "stage1/packet3-prep/src",
                               BASE / "packet2/kernels", BASE / "packet2/loader"):
                    trial = folder / name
                    if trial.exists():
                        source = trial.resolve()
                        break
            if source.exists():
                if source.is_relative_to(BASE):
                    source = stage(source)
                else:
                    hashes[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
                return "#include " + json.dumps(str(source))
            return match.group(0)
        dest.write_text(re.sub(r'#include "([^"]+)"', include, target.read_text()))
        return dest
    files = [stage(BASE / name) for name in ("packet16-decode/backend.hpp", "packet16-decode/adapter.cpp",
                                             "packet15-nongemv/native.cpp", "packet4/kernels.cpp")]
    unit = BUILD / "check_backend.cpp"
    unit.write_text("#include " + json.dumps(str(files[0])) + "\n")
    files[0] = unit
    rows = []
    for source in files:
        command = ["/opt/intel/oneapi/compiler/latest/bin/icpx", "-std=c++20", "-fsycl", "-fsyntax-only",
                   "-fno-fast-math", "-ffp-contract=off", "-fdenormal-fp-math=ieee"]
        command += ["-I" + str(path) for path in (BASE / "packet16-decode", BASE.parent / "stage1/packet3-prep/src",
                                                 BASE / "packet2/kernels", BASE / "packet2/loader")]
        command += [str(source)]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        rows.append(dict(command=["nice", "-n", "19", "ionice", "-c", "3", "env", "OMP_NUM_THREADS=2", *command],
                         exit_code=result.returncode, output=result.stdout))
        print(source.name, "exit", result.returncode, flush=True)
    passed = all(row["exit_code"] == 0 for row in rows)
    (HERE / "native-syntax-receipt.json").write_text(json.dumps(dict(device_executed=False,
        compiler_action="fsyntax-only; no native executable linked or launched", passed=passed,
        sources=hashes, checks=rows), indent=2) + "\n")
    raise SystemExit(0 if passed else 1)

if __name__ == "__main__":
    main()
