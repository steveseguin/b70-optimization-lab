"""Run the repository scanner and bind its result; never modify frozen copies."""
import json
from pathlib import Path
import subprocess
import sys
from seal import sha

P=Path(__file__).resolve().parent
ROOT=P.parents[3]


def main():
    scanner=ROOT/'scripts/check_drain_fix.py'
    run=subprocess.run([sys.executable,'-B',str(scanner),str(P),'--json'],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
    row=json.loads(run.stdout)
    assert row['passed'] and row['counts']=={'FIXED':2,'UNFIXED':0}
    row.update(device_executed=False,sources={str(f.relative_to(ROOT)):sha(f) for f in
        (Path(__file__),scanner,P/'drain_gate.py',P/'screen-reader/drain_gate.py')})
    (P/'evidence/drain-fix.json').write_text(json.dumps(row,indent=2)+'\n')
    print('2 copied drain gates FIXED; 0 UNFIXED')


if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
