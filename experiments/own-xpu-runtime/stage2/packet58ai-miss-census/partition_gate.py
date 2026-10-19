"""Synthetic exact partition byte tests; no model or full-shape input reads."""
import json,resource,subprocess
from build_engine import P,sha,save,turn,limits

def main():
    limits();source=P/'native/partition_cpu.cpp'
    # Point at the same header compiled into this packet's expert TU.
    import re
    expert=next((P/'sources').glob('*-p49d_expert_submit.cpp'))
    down=Path(re.search(r'#include "([^"\n]*p100_down.hpp)"',expert.read_text())[1])
    source.write_text(source.read_text().replace('#include "p100_down.hpp"','#include "'+str(down)+'"'))
    rows=[];outputs=[]
    for tag,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary=P/'build'/('partition-'+tag)
        cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-Wno-unknown-pragmas',str(source),'-o',str(binary)]
        with turn():cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        (P/'evidence'/('partition-'+tag+'-build.log')).write_text(cp.stdout+cp.stderr)
        if cp.returncode:raise RuntimeError(cp.stderr[-2500:])
        result=[]
        for _ in range(2):
            cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
            if cp.returncode:raise RuntimeError(cp.stderr[-2000:])
            assert len(cp.stdout.splitlines())==24;result.append(cp.stdout)
        assert result[0]==result[1];outputs.append(result[0])
        (P/'evidence'/('partition-'+tag+'.log')).write_text(result[0])
        rows.append(dict(compiler=tag,passed=True,cases=24,repeats=2,binary_sha256=sha(binary),command=cmd))
        print(tag,'partition byte test PASS',flush=True)
    assert outputs[0]==outputs[1]
    save(P/'evidence/partition-cpu.json',dict(passed=True,device_executed=False,synthetic_only=True,records=rows,cross_compiler_exact=True,peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
if __name__=='__main__':
    from pathlib import Path
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
