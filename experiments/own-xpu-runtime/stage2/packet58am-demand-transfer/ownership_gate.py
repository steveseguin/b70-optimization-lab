import json,subprocess
from prepare import P,sha,save
from build_engine import run,compiler_turn
def main():
    records=[]
    for compiler,cxx in [('GNU','/usr/bin/g++'),('Intel','/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary=P/'build'/f'{compiler}-ownership'
        run([cxx,'-std=c++20','-O2',str(P/'native/ownership_test.cpp'),'-o',str(binary)],compiler+'-ownership')
        for repeat in range(2):
            with compiler_turn():cp=subprocess.run([str(binary)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
            result=json.loads(cp.stdout);assert result['passed']
            records.append(dict(compiler=compiler,repeat=repeat,binary_sha256=sha(binary),result=result))
    save(P/'evidence/ownership.json',dict(passed=True,records=records,device_executed=False))
    print('All 1024 masks across all 48 layers and delayed leases PASS')
if __name__=='__main__':main()
