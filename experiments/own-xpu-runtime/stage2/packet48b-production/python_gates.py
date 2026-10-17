#!/usr/bin/env python3
"""CPU-only coordinator negative tests and sealed script syntax checks."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from preparation import exclusive_cpu_work
HERE=Path(__file__).resolve().parent
def main():
    with exclusive_cpu_work():
        files=sorted(HERE.glob('*.py'));pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        for p in files:ast.parse(p.read_text(),filename=str(p))
        result=subprocess.run(['python3','-B','-m','unittest','-v','test_window'],cwd=HERE,text=True,capture_output=True)
        (HERE/'build/python-tests.log').write_text(result.stdout+result.stderr)
        for p in HERE.glob('*.sh'):subprocess.run(['bash','-n',str(p)],check=True)
        row=dict(passed=result.returncode==0,device_executed=False,tests=8,source_sha256=pins,
                 log_sha256=hashlib.sha256((HERE/'build/python-tests.log').read_bytes()).hexdigest())
        (HERE/'python-gates.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
        if result.returncode:raise SystemExit(result.returncode)
if __name__=='__main__':main()
