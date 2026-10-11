#!/usr/bin/env python3
import json,os,subprocess,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
rows=[]
for cards in (1,2):
 expected=None
 for seed in (0,1,17,73):
  name=f"mini-shipped-{cards}-{seed}";out=HERE/"build/scratch"/name;san=out.with_suffix(".san.json")
  binary=HERE/"build/shipped/depcheck-runtime"
  dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
  assert not any(s in dynamic.lower() for s in ("libsycl","libze_loader","libur_loader","libopencl"))
  env=dict(os.environ,DEPCHECK_SEED=str(seed),DEPCHECK_REPORT=str(san));env.pop("DEPCHECK_TRACE",None)
  args=[str(binary),"--mini","--card","0","--cards",str(cards),"--memory","resident" if cards==2 else "layer-streaming","--max-new","3","--output",str(out)]
  p=subprocess.run(args,env=env,capture_output=True,text=True,timeout=240)
  receipt=json.loads((out/"receipt.json").read_text());report=json.loads(san.read_text())
  assert receipt["passed"] and p.returncode==2 and report["violations"]
  assert all("uninitialized read" in v and "layer-snapshots" in v for v in report["violations"])
  digest=hashlib.sha256((out/"buffers.json").read_bytes()).hexdigest()
  if expected is None:expected=digest
  assert digest==expected
  rows.append(dict(cards=cards,seed=seed,buffer_sha256=digest,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),tokens=receipt["tokens"],sanitizer=report))
(HERE/"mini-shipped-gates.json").write_text(json.dumps(dict(passed=True,device_executed=False,runs=rows),indent=2)+"\n")
print("8 shipped mini scheduling runs exact; snapshot poison found in every run")
