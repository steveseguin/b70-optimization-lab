#!/usr/bin/env python3
import os,json,subprocess,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
assert os.environ['OMP_NUM_THREADS']=='2'
for suffix,tag in [('test','cpu'),('asan','asan'),('tsan-llvm22','tsan')]:
 b=P/'build'/('native-controller-'+suffix)
 subprocess.run(['python3','-B',str(P/'native_controller_gate.py'),'--binary',str(b),'--output',str(P/('native-controller-'+tag+'.json'))],check=True)
 b=P/'build'/('native-mailbox-fault-'+suffix)
 r=subprocess.run([str(b)],text=True,capture_output=True,check=True,timeout=120)
 row=json.loads(r.stdout);assert row['passed'] and row['gates']==5
 row.update(binary_sha256=hashlib.sha256(b.read_bytes()).hexdigest(),stderr=r.stderr)
 (P/('native-mailbox-faults'+('' if tag=='cpu' else '-'+tag)+'.json')).write_text(json.dumps(row,indent=2)+'\n')
