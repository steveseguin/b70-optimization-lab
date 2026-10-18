#!/usr/bin/env python3
"""Final CPU-only seal/source/byte verification; never invokes a native binary."""
import json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P/"screen"))
from common import read,sha,verify_map,sealed,save
from conditions import cpu_gate
from cpu_seal import verify
from types import SimpleNamespace

def main():
 cpu_gate();wrapper=verify();build=read(P/"build-device-receipt.json")
 verify_map(ROOT,build["sources"]);verify_map(P,build["artifacts"])
 rows=[]
 for choice in ("production","wg64","wg128","prefetch64","wide64"):
  view=P/"selections"/choice
  for timing in ("token","attribution"):
   identity=sealed(SimpleNamespace(lineage=view,seal=view/"screen-seal.json",binary=view/"build/device/own-rt-iq3",dispatch=view/"dispatch-speed6.json",profile="tp2",timing=timing,placement="1"))
   assert identity["placement"]["supported"]
  rows.append(dict(choice=choice,seal_sha256=sha(view/"screen-seal.json")))
 receipts=[read(P/"evidence"/name/"receipt.json") for name in ("cpu-byte-fixture","cpu-byte-fixture-intel")]
 outputs=set()
 for receipt in receipts:
  assert receipt["passed"] and not receipt["device_executed"]
  verify_map(ROOT,receipt["sources"])
  assert sha(P/"cpu_fixture.py")==receipt["fixture_driver_sha256"]
  for run in receipt["runs"]:
   assert run["native"]["cases"]==72 and run["native"]["passed"]
   assert run["expected_sha256"]==run["candidate_sha256"]
   outputs.add(run["candidate_sha256"])
 assert len(outputs)==1
 assert sha(P/"selections/production/fixture/expected.bin") in outputs
 assert sha(P/"selections/production/fixture/candidate.bin") in outputs
 gate=read(P/"evidence/engine-integration.json");assert gate["passed"] and gate["attribution_host_identity"]
 verify_map(ROOT,gate["sources"])
 registers=read(P/"register-report.json");assert registers["passed"] and len(registers["kernels"])==10
 for row in registers["kernels"]:
  assert row["configured_grf"]==128 and not row["spill_metadata"] and not row["scratch_messages"]
  assert sha(ROOT/row["assembly"])==row["sha256"]
 with (P/"evidence/analyzer-tests.log").open("w") as log:
  subprocess.run([sys.executable,"-B","-m","unittest","discover","-s",str(P),"-p","test_expert_composition.py","-v"],stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,check=True)
 plans=read(P/"evidence/screen-plans.json");assert plans["passed"] and len(plans["plans"])==20
 for lane in ("A","B"):
  plan=read(P/"evidence"/("campaign-plan-"+lane+".json"));assert not plan["device_executed"] and len(plan["arms"])==4
  assert [arm["candidate"] for arm in plan["arms"]]==["wide64","wg64","wg128","prefetch64"]
  assert all(len(arm["stages"])==6 for arm in plan["arms"])
 save(P/"cpu-validation.json",dict(schema="packet65.cpu-validation.v1",passed=True,device_executed=False,device_performance="unmeasured",integration_gate_passed=False,selections=rows,build_receipt_sha256=sha(P/"build-device-receipt.json"),register_receipt_sha256=sha(P/"register-report.json"),cpu_output_sha256=next(iter(outputs)),host_compilers=2,fresh_runs_per_compiler=2,cases_per_run=72,raw_fp32_chains_per_run=110592,raw_fp32_trees_per_run=3456,screen_plans=20,campaign_plans=2,wrapper_tests=34,analyzer_tests=6,verification_script_sha256=sha(Path(__file__)),evidence={str(f.relative_to(P)):sha(f) for f in (P/"evidence/engine-integration.json",P/"evidence/selection-tests.json",P/"evidence/analyzer-tests.log",P/"evidence/screen-plans.json",P/"screen/placement-validation/wrapper-seal.json")}))
 print("PASS: source/byte/seal checks; 2 compilers, 5 selections, 20 screen plans; GPU unmeasured")
if __name__=="__main__":main()
