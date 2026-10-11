#!/usr/bin/env python3
"""Port packet19's checker and malformed-index tests to the packet18 bindings."""
from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent
P19=HERE.parent/'packet19-depcheck'
BUILD=HERE/'build/guard-tests'
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
BUILD.mkdir(exist_ok=True)
rows=[]
for source,name,sanitize in (('tests.cpp','checker-tests',False),('test_bounds.cpp','bounds',True),('test_core_bounds.cpp','core-bounds',True)):
    original=P19/source;text=original.read_text()
    if name=='bounds':
        text=text.replace('"patched/packet16-decode/adapter.cpp"',json.dumps(str(HERE/'adapter.cpp')))
        text=text.replace('packet16::','packet18::').replace('std::array<std::vector<uint32_t>,16>','std::array<std::vector<uint32_t>,19>')
        text=text.replace('j<16','j<19').replace('args.i(15)[1]=1','args.i(18)[0]=1').replace('args.i(15)[2]','args.i(15)[0]')
    elif name=='core-bounds':
        text=text.replace('"patched/packet4/core.hpp"',json.dumps(str(HERE/'core_v2.hpp')))
    else:
        text=text.replace('"depcheck.hpp"',json.dumps(str(P19/'depcheck.hpp')))
    staged=BUILD/source;staged.write_text(text);binary=BUILD/name
    flags=['-std=c++20','-O1' if sanitize else '-O2','-g','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-I'+str(HERE),
           '-I'+str(HERE.parent.parent/'stage1/packet3-prep/src')]
    if sanitize:flags+=['-fsanitize=address,undefined,float-cast-overflow','-fno-omit-frame-pointer','-fno-sanitize-recover=all']
    inputs=[str(staged)]
    if name=='bounds':inputs += [str(HERE/'owner.cpp'),str(HERE/'owner_retire.cpp')]
    cmd=['g++',*flags,*inputs,'-o',str(binary)]
    subprocess.run(cmd,check=True)
    dynamic=subprocess.check_output(['readelf','-d',str(binary)],text=True)
    assert not any(s in dynamic.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
    result=subprocess.run([str(binary)],capture_output=True,text=True)
    row=dict(source=source,original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),ported_sha256=hashlib.sha256(staged.read_bytes()).hexdigest(),
             command=cmd,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    rows.append(row)
    (HERE/'sanitizer-unit.json').write_text(json.dumps(dict(passed=result.returncode==0,device_executed=False,tests=rows),indent=2)+'\n')
    print(name,result.stdout,result.stderr,flush=True)
    assert result.returncode==0 and "runtime error:" not in result.stderr and "ERROR: AddressSanitizer" not in result.stderr
