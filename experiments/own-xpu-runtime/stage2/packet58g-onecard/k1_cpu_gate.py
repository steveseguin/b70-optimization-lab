#!/usr/bin/env python3
"""Run K1's actual p28 IQ3 pointer path against unchanged direct p39 bytes."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    binary=P/'build/gnu-host/p58-cache-fixtures'
    with tempfile.TemporaryDirectory(prefix='k1-58g-',dir=P/'build') as tmp:
        out=Path(tmp)/'run'
        run=subprocess.run([str(binary),'--output',str(out),'--iterations','1'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180,env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
        (P/'evidence/k1-cpu-58g.log').write_text(run.stdout+run.stderr)
        assert run.returncode==0,run.stdout+run.stderr
        row=json.loads((out/'k1.json').read_text())
        parent=json.loads((P.parent/'packet58f-onecard/k1-cpu.json').read_text())
        assert row['passed'] and not row['device_executed'] and row['checks']==24
        assert row['exact_output_sha256']==parent['exact_output_sha256']
        row.update(binary_sha256=sha(binary),parent_output_sha256=parent['exact_output_sha256'],
                   iq3_path='actual p28 paired indirect submit versus unchanged direct p39 arithmetic; VRAM, host, mixed, streamed',
                   source_sha256=sha(P/'p58_native_fixture.cpp'))
        (P/'k1-cpu.json').write_text(json.dumps(row,indent=2)+'\n')
        (P/'k1-cpu-cases.jsonl').write_bytes((out/'k1-cases.jsonl').read_bytes())
    print(json.dumps({k:row[k] for k in ('passed','checks','exact_output_sha256','device_executed')}))
if __name__=='__main__':main()
