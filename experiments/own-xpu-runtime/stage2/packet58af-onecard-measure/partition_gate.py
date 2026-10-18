"""CPU partition arithmetic and exact production subgroup geometry; no payload reads."""
import json,os,resource,subprocess
from build_engine import P,ROOT,sha,save,turn,limits

def main():
    limits();base=P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    checked=base/'build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    rows=[]
    for tag,compiler in [('gnu','/usr/bin/g++'),('intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary=P/'build'/('partition-'+tag)
        cmd=[compiler,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-Wno-unknown-pragmas','-I'+str(checked),'-I'+str(base),
            str(P/'native/partition_cpu.cpp'),'-o',str(binary)]
        with turn():
            cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        (P/'evidence'/('partition-'+tag+'-build.log')).write_text(cp.stdout+cp.stderr)
        if cp.returncode:raise RuntimeError(cp.stderr[-2000:])
        repeats=[]
        for _ in range(2):
            cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
            if cp.returncode:raise RuntimeError(cp.stderr[-2000:])
            assert len(cp.stdout.splitlines())==24;repeats.append(cp.stdout)
        assert repeats[0]==repeats[1]
        (P/'evidence'/('partition-'+tag+'.log')).write_text(repeats[0])
        rows.append(dict(compiler=tag,passed=True,cases=24,repeats=2,binary_sha256=sha(binary),command=cmd))
    geometry=[]
    for name,n,V,SG in [('gate',640,8,8),('down',2560,16,2)]:
        paired=name=='gate';streams=2 if paired else 1;groups=n*10//(V*SG//streams)
        visits={}
        for group in range(groups):
            for sub in range(SG):
                logical=[(group*(SG//streams)+sub//streams)*V+lane//(32//V) for lane in range(32)]
                assert len({i//n for i in logical})==1
                for row in set(logical):
                    key=(sub%streams,row);visits[key]=visits.get(key,0)+1
        assert len(visits)==n*10*streams and set(visits.values())=={1}
        geometry.append(dict(kernel=name,groups=groups,subgroup_uniform_slot=True,every_output_once=True))
    save(P/'evidence/partition-cpu.json',dict(passed=True,device_executed=False,synthetic_only=True,rows=rows,geometry=geometry,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
