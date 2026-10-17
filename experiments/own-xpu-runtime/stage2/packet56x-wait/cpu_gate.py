#!/usr/bin/env python3
"""Existing controller/fault gates, plus one parent/candidate byte fixture."""
import json
import os
from pathlib import Path
import subprocess
import sys
from build_spin import P, ROOT, B, sha, save

def gate(mode):
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    fixture = P/'fixture'/mode
    fixture.mkdir(exist_ok=True, parents=True)
    gate_cmd = [sys.executable, '-B', str(P/'native_controller_gate.py'),
                '--binary', str(B/('native_controller_test-'+mode)),
                '--output', str(P/('evidence/controller-'+mode+'.json'))]
    subprocess.run(gate_cmd, check=True)
    faults = subprocess.check_output([str(B/('native_mailbox_fault_test-'+mode))], text=True)
    fault_row = json.loads(faults)
    assert fault_row['passed'] and fault_row['gates'] == 5
    save(P/('evidence/mailbox-faults-'+mode+'.json'), fault_row)
    wait_row = json.loads(subprocess.check_output([str(B/('host_wait_test-'+mode))], text=True))
    assert wait_row['passed'] and wait_row['checks']==7 and wait_row['sleep20']==(mode=='sleep20')
    save(P/('evidence/wait-'+mode+'.json'),wait_row)
    # Fixed mixed proposal path, including no-guess, misses, accepts and rollback.
    # Compare target tokens AND committed recurrent/history/fixture bytes.
    source = '2 12 1 0 5 11 0 1 2 1 2 3 -1 0 1 2 3 4 5 6 7 8 9\n'
    (fixture/'input.txt').write_text(source)
    fields = ('tokens','state','fixtures','guess_sequence')
    rows = []
    for label, binary in [('expected',B/'parent-controller'),('actual',B/('native_controller_test-'+mode))]:
        run = subprocess.run([str(binary)], input=source, capture_output=True, text=True, check=True, timeout=30)
        row = json.loads(run.stdout)
        save(fixture/(label+'-raw.json'), row)
        stable = {key:row[key] for key in fields}
        stable['counts'] = {key:row['stats'][key] for key in ('guesses','hits','misses','no_guess')}
        raw = json.dumps(stable,sort_keys=True,separators=(',',':')).encode()
        (fixture/(label+'.bin')).write_bytes(raw)
        rows.append(raw)
    assert rows[0] == rows[1] and rows[0]
    sources = [P/'host_wait_test.cpp',P/'host_wait_mode.cpp',P/('evidence/wait-'+mode+'.json'),P/'cpu_gate.py', P/'build_spin.py', P/'native_controller_gate.py',
               P/'pipeline.py',P/'test_state_machine.py', P/'native_controller_test.cpp',
               P/'native_mailbox_fault_test.cpp',P/'native_controller.hpp',P/'host_spin.hpp',
               P/('evidence/controller-'+mode+'.json'),P/('evidence/mailbox-faults-'+mode+'.json'),fixture/'input.txt',
               fixture/'expected-raw.json',fixture/'actual-raw.json']
    save(fixture/'receipt.json', dict(schema='own-runtime.screen.byte-fixture.v1',
         passed=True, device_executed=False,
         changed_class='host mailbox/event waiting; unchanged controller target tokens and committed state',
         command=[sys.executable,'-B',str(P/'cpu_gate.py')],
         build_receipt_sha256=sha(P/('build-'+mode+'-receipt.json')),
         sources={str(x.relative_to(ROOT)):sha(x) for x in sources},
         compared_fields=list(fields)+['counts'], compared_bytes=len(rows[0]),
         expected=dict(path='fixture/'+mode+'/expected.bin',sha256=sha(fixture/'expected.bin')),
         actual=dict(path='fixture/'+mode+'/actual.bin',sha256=sha(fixture/'actual.bin'))))
    print('CPU byte fixture PASS:',len(rows[0]),'bytes',flush=True)

if __name__ == '__main__':
    for mode in ('spin','sleep20'): gate(mode)
