"""Actual owner retirement under GNU/Intel with delayed foreground and fills."""
import json,os,resource,subprocess
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn

def main():
    limits();rows=[]
    env={**os.environ,'OMP_NUM_THREADS':'2','LD_LIBRARY_PATH':json.loads((P/'library-path.json').read_text())['LD_LIBRARY_PATH']}
    receipt=json.loads((P/'evidence/build.json').read_text())
    original=next(r['command'] for r in receipt['commands'] if r['name']=='gnu-host-owner')
    flags=original[1:original.index('-MMD')]
    for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary=B/(compiler+'-ordered-test')
        cmd=[cxx,*flags,'-I'+str(P/'native'),str(P/'native/ordered_test.cpp'),str(P/'sources/owner.cpp'),str(P/'sources/owner_retire.cpp'),'-o',str(binary)]
        with compiler_turn(),(B/(compiler+'-ordered-build.log')).open('w') as out:
            subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=600)
        for repeat in range(2):
            cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=60,env=env)
            row=json.loads(cp.stdout);assert row['passed'] and not row['device_executed']
            rows.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),**row))
            print(compiler,repeat,'ordered foreground retirement PASS',flush=True)
    backend=(P/'sources/single_device.cpp').read_text()
    assert 'return record(copied,true)' in backend and 'foreground_tails_.record(event)' in backend
    assert 'foreground_tails_.clear()' in backend and 'foreground_tails_.complete(' in backend
    files=[P/'retirement_gate.py',P/'native/ordered_test.cpp',P/'native/ordered_retirement.hpp',P/'native/engine_bracket.hpp',*P.glob('sources/*.cpp')]
    save(P/'evidence/retirement-gates.json',dict(passed=True,device_executed=False,records=rows,
        sources={str(f.relative_to(ROOT)):sha(f) for f in files},
        scope='Two in-order foreground queues; separate maintenance queue remains owned through shutdown. Device arithmetic/speed pending.'))
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
