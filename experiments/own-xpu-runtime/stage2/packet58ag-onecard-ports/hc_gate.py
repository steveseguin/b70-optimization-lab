"""Real-shape primitive and actual Engine capture checks, GNU and Intel CPU only."""
import json,resource,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits,compiler_turn
from hc_source import prepare
from launch_env import environment

def run(cmd,log):
    with log.open('w') as f:subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600,env=environment())
def main():
    limits();prepare()
    build=json.loads((P/'evidence/build.json').read_text());commands=build['commands'];rows=[];hashes={}
    sources=dict(build['sources']);sources[str((P/'hc_gate.py').relative_to(ROOT))]=sha(P/'hc_gate.py')
    assert all(sha(ROOT/name)==digest for name,digest in sources.items())
    base=next(x['command'] for x in commands if x['name']=='gnu-host-entry-main')
    base=base[:base.index('-MMD')]
    link=next(x['command'] for x in commands if x['name']=='gnu-host-own-rt-iq3')
    for name in ('fixture.cpp','integrated_fixture.cpp'):
        text=(P/'native'/name).read_text()
        (B/'native'/name).write_text(text)
    metadata=P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/suite-inputs-20261012/incident-retrospective/plan.tsv'
    for tag,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        submit=B/(tag+'-p60_submit.o')
        with compiler_turn():run([compiler,*base[1:],'-o',submit,'-c',B/'native/p60_submit.cpp'],B/(tag+'-submit-compile.log'))
        for kind in ('fixture','integrated_fixture'):
            binary=B/(tag+'-'+kind);obj=B/(tag+'-'+kind+'.o')
            cmd=[compiler,*base[1:],'-o',str(obj),'-c',str(B/'native'/(kind+'.cpp'))]
            with compiler_turn():run(cmd,B/(tag+'-'+kind+'-compile.log'))
            if kind=='fixture':ln=[compiler,str(obj),'-o',str(binary)]
            else:
                ln=[a for a in link if not a.endswith('/own-rt-iq3-entry.cpp.o')]
                ln=[str(obj) if a==str(B/'gnu-host/entry-main.o') else a for a in ln]
                ln[0]=compiler
                ln=[str(submit) if a==str(B/'gnu-host/p60_submit.o') else a for a in ln]
                ln[ln.index('-o')+1]=str(binary)
            with compiler_turn():run(ln,B/(tag+'-'+kind+'-link.log'))
            for repeat in range(2):
                with tempfile.TemporaryDirectory(prefix='hc-',dir=B) as d:
                    out=Path(d);cmd=[binary,out]+([metadata,P/'dispatch-speed6.json'] if kind=='integrated_fixture' else [])
                    log=P/'evidence'/f'{tag}-{kind}-{repeat}.log';run(cmd,log)
                    a=out/'expected.bin';b=out/'actual.bin';assert a.read_bytes()==b.read_bytes(),log
                    native=json.loads(log.read_text().splitlines()[-1]);assert native['passed'] and not native['device_executed']
                    rows.append(dict(compiler=tag,fixture=kind,repeat=repeat,passed=True,bytes_compared=a.stat().st_size,
                        expected_sha256=sha(a),actual_sha256=sha(b),binary_sha256=sha(binary),native=native))
                    hashes[tag,kind,repeat]=sha(a)
                print(tag,kind,repeat,'PASS',flush=True)
            assert hashes[tag,kind,0]==hashes[tag,kind,1]
    assert all(hashes['gnu',k,0]==hashes['intel',k,0] for k in ('fixture','integrated_fixture'))
    save(P/'evidence/hc-gates.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,sources=sources,
        build_evidence_sha256=sha(P/'evidence/build.json'),
        cross_compiler={k:hashes['gnu',k,0]==hashes['intel',k,0] for k in ('fixture','integrated_fixture')},
        cases=['finite','last position','NaN','Inf','signed zero','sticky error','inactive','out of range','nonfinite gain/inject'],
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<4*1024**3
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
