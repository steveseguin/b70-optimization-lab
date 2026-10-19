"""Small host-only byte gates. No wall-clock timeout: the agent may be frozen."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
from capture import P, ROOT, S, guard


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    guard()
    build=P/'build';build.mkdir(exist_ok=True)
    (build/'tmp').mkdir(exist_ok=True)
    os.environ['TMPDIR']=str(build/'tmp')
    base=S/'packet141-transfer-gap'
    # p141's archived p28 directory is absent. Its route arithmetic headers are
    # byte-identical to p97; use that complete type tree, never mix two owners.
    include=build/'include';include.mkdir(exist_ok=True)
    (include/'p109_route.hpp').write_bytes((base/'p109_route.hpp').read_bytes())
    same={}
    for name in ('route42.hpp','p49d_route.hpp','p49c_kernel.hpp','detmath.hpp','arithmetic.hpp'):
        assert (base/name).read_bytes()==(S/'packet97-record-bundle'/name).read_bytes(), name
        same[str((base/name).relative_to(ROOT))]=sha(base/name)
    same[str((base/'p109_route.hpp').relative_to(ROOT))]=sha(base/'p109_route.hpp')
    modes={'gnu':'/usr/bin/g++','intel':'/opt/intel/oneapi/compiler/latest/bin/icpx'}
    receipts=[]
    for mode,compiler in modes.items():
        flags=['-std=c++20','-O3','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY']
        if mode=='gnu':flags+=['-march=native']
        else:flags+=['-fdenormal-fp-math=ieee']
        includes=[include, S/'packet97-record-bundle', ROOT/'experiments/own-xpu-runtime/stage1/packet3-prep/src',S/'packet2/kernels',S/'packet2/loader']
        commands=[];deps=dict(same);objects=[]
        for stem in ('oracle','cpu_gate'):
            obj=build/f'{mode}-{stem}.o';dep=build/f'{mode}-{stem}.d'
            cmd=[compiler,*flags,*['-I'+str(p) for p in includes],'-MMD','-MF',str(dep),'-c',str(P/(stem+'.cpp')),'-o',str(obj)]
            commands.append(cmd)
            with (P/'evidence'/f'compile-{mode}-{stem}.log').open('w') as log:
                subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
            for name in shlex.split(dep.read_text().replace('\\\n',' ').split(':',1)[1]):
                path=Path(name).resolve()
                if path.is_relative_to(ROOT):deps[str(path.relative_to(ROOT))]=sha(path)
            objects.append(str(obj))
        binary=build/f'gate-{mode}'
        cmd=[compiler,*objects,'-o',str(binary)]
        commands.append(cmd)
        subprocess.run(cmd,stdin=subprocess.DEVNULL,check=True)
        for repeat in (1,2):
            result=subprocess.run([str(binary),str(build/f'{mode}-{repeat}.bytes')],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
            row=json.loads(result.stdout)
            row.update(compiler=mode,repeat=repeat,output_sha256=sha(build/f'{mode}-{repeat}.bytes'),binary_sha256=sha(binary))
            (P/'evidence'/f'cpu-{mode}-{repeat}.json').write_text(json.dumps(row,indent=2)+'\n')
            receipts.append(row)
        (P/'evidence'/f'build-{mode}.json').write_text(json.dumps(dict(
            commands=commands,version=subprocess.check_output([compiler,'--version'],stdin=subprocess.DEVNULL,text=True),
            sources=deps,binary_sha256=sha(binary),device_executed=False),indent=2)+'\n')
    assert len({r['output_sha256'] for r in receipts})==1
    assert len({r['pid'] for r in receipts})==4
    assert all(r['passed'] and r['cases']==2304 and r['nonfinite']==256 and r['invalid_abi']==18 and r['invalid_selected_routes']==5 for r in receipts)
    maxrss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    assert maxrss*1024<4_000_000_000
    (P/'evidence/cpu.json').write_text(json.dumps(dict(passed=True,records=receipts,max_rss_kib=maxrss,
        scope='route epilogue specification, real 512/10/640/2560 shapes; no router GEMV/device integration'),indent=2)+'\n')
    print('GNU and Intel, two fresh processes each: 2304 byte cases, 18 pre-write ABI refusals, 5 invalid selected routes per process; all hashes equal.')


if __name__=='__main__':main()
