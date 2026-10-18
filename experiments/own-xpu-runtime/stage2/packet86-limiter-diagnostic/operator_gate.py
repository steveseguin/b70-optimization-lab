import json, subprocess
from build_engine import P, B, ROOT, sha, save, limits

def main():
    limits();d=B/'operators';d.mkdir(exist_ok=True);rows=[]
    for name,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary=d/name
        cmd=[cxx,'-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parent/'packet2/loader'),str(P/'operator_test.cpp'),'-o',str(binary)]
        with (d/(name+'-build.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
        for repeat in (1,2):
            r=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=60);r.check_returncode();result=json.loads(r.stdout);assert result['passed'];rows.append(dict(compiler=name,repeat=repeat,result=result,binary_sha256=sha(binary)))
        print(name,'operator controls and intentional mismatches PASS',flush=True)
    save(P/'evidence/operators.json',dict(passed=True,device_executed=False,diagnostic_nonexact=True,rows=rows,sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('operator_test.cpp','operator_gate.py','p86_expert.hpp','p86_hc.hpp')}))
if __name__=='__main__':main()
