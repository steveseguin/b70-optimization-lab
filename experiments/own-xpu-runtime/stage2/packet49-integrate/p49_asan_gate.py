"""Sanitizer execution of actual split32 owner bridge, in two fresh processes."""
import json,os,subprocess,time
from pathlib import Path
import build
from cpu_gates import host
from storage import digest
from p49_cpu_gate import summarize_receipt
P=Path(__file__).resolve().parent;B=P/'build'
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    root=B/('asan-fixtures-'+str(time.time_ns()));root.mkdir()
    binary=B/'asan/p49-qsa-fixtures';host(binary)
    mode=json.loads((P/'build-asan-receipt.json').read_text())
    assert mode['compiled_sources_sha256']==build.compiled_sources()
    rows=[]
    for repeat in range(2):
        out=root/str(repeat)
        with (root/f'{repeat}.log').open('w') as log:
            run=subprocess.run([str(binary),'--output',str(out)],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        assert run.returncode==0,str(root/f'{repeat}.log')
        receipt=json.loads((out/'receipt.json').read_text())
        assert receipt['passed'] and receipt['reference_exact'] and not receipt['device_executed'] and receipt['checks']==88
        rows.append(dict(output=str(out),binary_sha256=digest(binary),output_sha256=digest(out/'output.bin'),native_receipt_sha256=digest(out/'receipt.json'),receipt=summarize_receipt(receipt)))
    assert rows[0]['output_sha256']==rows[1]['output_sha256']
    (P/'p49-asan-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,rows=rows),indent=2)+'\n')
    print('ASAN/UBSAN split32: 176 checks passed')
if __name__=='__main__':main()
