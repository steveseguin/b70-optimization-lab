"""Run actual protocol/publication and owner code with delayed CPU events."""
import json,resource,subprocess
from build_engine import P,BASE,ROOT,compiler_turn,limits,sha,save

def main():
    limits();records=[]
    for stem in ('protocol_test','owner_async_test'):
        binary=P/'build'/stem
        cmd=['g++','-std=c++20','-O2','-DOWN_RT_HOST_ONLY','-I'+str(BASE),'-I'+str(P/'native'),
             '-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),
             '-I'+str(P.parent/'packet2/loader'),str(P/'native'/(stem+'.cpp'))]
        if stem=='owner_async_test':cmd += [str(P/'build/gnu-host/owner.o'),str(P/'build/gnu-host/owner_retire.o')]
        cmd += ['-o',str(binary)]
        with compiler_turn():
            r=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        (P/'evidence'/(stem+'-build.log')).write_text(r.stdout+r.stderr)
        assert r.returncode==0,r.stderr[-4000:]
        for repeat in range(2):
            r=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60)
            assert r.returncode==0,r.stderr
            row=json.loads(r.stdout);assert row['passed'];row.update(repeat=repeat,binary_sha256=sha(binary));records.append(row)
        print(stem,'PASS',flush=True)
    save(P/'evidence/protocol-gates.json',dict(passed=True,device_executed=False,records=records,
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'protocol_gate.py',P/'async_source.py',*P.glob('native/*.hpp'),*P.glob('native/*test.cpp')]}))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
