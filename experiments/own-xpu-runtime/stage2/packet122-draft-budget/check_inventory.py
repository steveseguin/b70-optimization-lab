"""CPU-only census: every actual draft plan event has a byte-model row."""
import json,resource,subprocess
from pathlib import Path
from build_engine import limits,sha
from compile_turn import turn
from roofline import model
P=Path(__file__).resolve().parent
def main():
 limits();binary=P/'build/class-inventory';command=['g++','-std=c++20','-O1',str(P/'class_inventory.cpp'),'-o',str(binary)]
 with turn(),(P/'evidence/class-inventory-compile.log').open('w') as f:subprocess.run(command,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
 values=json.loads((P/'selection.json').read_text())['draft'];table=P/'build/inventory-selection.txt';table.write_text(''.join(k+' '+v+'\n' for k,v in values.items()))
 # CLI processes always inherit /dev/null; the fixture's explicitly generated
 # selection file is its sole input rather than interactive standard input.
 r=subprocess.run([str(binary),str(table)],stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 labels=r.stdout.splitlines();assert len(labels)==len(set(labels))
 for c in (128,4096):assert set(labels)==set(model(c)),set(labels)^set(model(c))
 receipt=dict(passed=True,device_executed=False,classes=labels,command=command,binary_sha256=sha(binary),selection_sha256=sha(P/'selection.json'),model_sha256=sha(P/'roofline.py'))
 (P/'evidence/class-inventory.json').write_text(json.dumps(receipt,indent=2)+'\n');print('complete actual draft inventory:',len(labels),'classes PASS')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
