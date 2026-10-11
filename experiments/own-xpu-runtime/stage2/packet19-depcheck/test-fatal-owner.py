#!/usr/bin/env python3
"""CPU owner failure regression; temporary compilation stays under packet19/build."""
import hashlib,importlib.util,json,os,subprocess,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
spec=importlib.util.spec_from_file_location("packet19_build",HERE/"build.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=[]
with tempfile.TemporaryDirectory(prefix="fatal-owner-",dir=HERE/"build") as tmp:
 work=Path(tmp);owner=work/"owner.cpp"
 original=HERE.parent/"packet16-decode/owner.cpp"
 owner.write_text(module.cpu_owner_overlay(original.read_text()))
 binary=work/"fatal-owner-test"
 command=["g++","-std=c++20","-O2","-DOWN_RT_HOST_ONLY","-I"+str(HERE),"-I"+str(HERE.parent.parent/"stage1/packet3-prep/src"),str(HERE/"fatal-owner-test.cpp"),str(owner),"-o",str(binary)]
 subprocess.run(command,check=True,timeout=60)
 dynamic=subprocess.check_output(["readelf","-d",str(binary)],text=True)
 assert not any(x in dynamic.lower() for x in ("libsycl","libze_loader","libur_loader","libopencl"))
 for mode,expected in (("poisoned-index","uninitialized INDEX"),("missing-edge","RAW")):
  report=work/(mode+".json");env=dict(os.environ,DEPCHECK_REPORT=str(report))
  start=time.monotonic();run=subprocess.run([str(binary),mode],env=env,capture_output=True,text=True,timeout=5);elapsed=time.monotonic()-start
  assert run.returncode==2,(mode,run.returncode,run.stderr)
  data=json.loads(report.read_text())
  assert data["device_executed"] is False and data["fatal_owner_retention"] is True
  assert data["canceled_submissions"]==1 and data["executed"]==0,data
  assert len(data["canceled_events"])==1 and any(expected in x for x in data["violations"]),data
  rows.append(dict(case=mode,exit_code=run.returncode,elapsed_seconds=elapsed,report=data,stderr=run.stderr))
 receipt=dict(schema="packet19.cpu-fatal-owner-regression.v1",device_executed=False,passed=True,cases=rows,owner_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
 (HERE/"fatal-owner-test-results.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(dict(passed=True,cases=len(rows),device_executed=False)))
