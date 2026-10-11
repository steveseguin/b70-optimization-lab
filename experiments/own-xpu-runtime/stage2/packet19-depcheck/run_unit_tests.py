#!/usr/bin/env python3
"""CPU unit gates; no accelerator compiler/runtime invocation."""
import hashlib,json,os,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
rows=[]
for source,name,sanitize in (("tests.cpp","checker-tests",False),("test_bounds.cpp","test-bounds",True),("test_core_bounds.cpp","test-core-bounds",True)):
 binary=HERE/"build"/name
 flags=["-std=c++20","-O1" if sanitize else "-O2","-g","-DOWN_RT_HOST_ONLY","-fno-fast-math","-ffp-contract=off","-I"+str(HERE.parent/"packet16-decode"),"-I"+str(HERE.parent/"packet4"),"-I"+str(HERE.parent.parent/"stage1/packet3-prep/src")]
 if sanitize:flags += ["-fsanitize=address,undefined,float-cast-overflow","-fno-omit-frame-pointer"]
 inputs=[str(HERE/source)]
 if name=="test-bounds":inputs.append(str(HERE.parent/"packet16-decode/owner.cpp"))
 command=["g++",*flags,*inputs,"-o",str(binary)]
 subprocess.run(command,check=True)
 dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
 assert not any(s in dynamic.lower() for s in ("libsycl","libze_loader","libur_loader","libopencl"))
 result=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
 print(result.stdout,end="",flush=True)
 rows.append(dict(source=source,command=command,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),source_sha256=hashlib.sha256((HERE/source).read_bytes()).hexdigest()))
(HERE/"unit-gates.json").write_text(json.dumps(dict(passed=True,device_executed=False,checker_cases=33,index_cases=46,tests=rows),indent=2)+"\n")
