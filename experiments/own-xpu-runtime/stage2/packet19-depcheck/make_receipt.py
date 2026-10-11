#!/usr/bin/env python3
"""Assemble retained CPU audit provenance only after every required gate passed."""
import datetime, hashlib, json, os, socket, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get("OMP_NUM_THREADS")=="2"
 names=["unit-gates.json","fatal-owner-test-results.json","integration-gates.json","final-integration-gates.json","mini-shipped-gates.json","real-short-gates.json","real-oracle-gate.json","native-syntax-receipt.json","packet18-adapter-gate.json"]
 gates={n:json.loads((HERE/n).read_text()) for n in names}
 assert all(g["passed"] for g in gates.values())
 assert gates["real-oracle-gate.json"]["layer_matches"]==48
 equiv=json.loads((HERE/"final-source-equivalence.json").read_text())
 assert equiv["all_common_generated_sources_equal"]
 builds={}
 for mode in ("shipped","patched","final-patched"):
  p=HERE/"build"/mode/"build.json";b=json.loads(p.read_text())
  assert sha(Path(b["binary"]))==b["sha256"]
  builds[mode]=dict(manifest_sha256=sha(p),manifest=b)
 (HERE/"build-identities.json").write_text(json.dumps(builds,indent=2)+"\n")
 for path,pins in json.loads((HERE/"fixes/source-pins.json").read_text()).items():
  assert sha(HERE.parent/path)==pins["original_sha256"]
  assert sha(HERE/"patched"/path)==pins["patched_sha256"]
 patches=[HERE/"fixes"/p for p in (HERE/"fixes/series").read_text().splitlines() if p and not p.startswith("#")]
 subprocess.run(["git","apply","--check",*map(str,patches)],cwd=ROOT,check=True)
 artifacts={str(p.relative_to(HERE)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(HERE.rglob("*")) if p.is_file() and not set(p.relative_to(HERE).parts)&{"build","__pycache__"} and p.name!="build-receipt.json"}
 receipt=dict(schema="packet19.cpu-dependency-audit.v1",created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),host=socket.gethostname(),git_head_at_receipt=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),device_executed=False,fault_halt_preserved=True,limits=dict(nice=19,ionice_class=3,OMP_NUM_THREADS=2,max_compile_jobs=2),gates={n:dict(passed=True,sha256=sha(HERE/n)) for n in names},real_oracle=dict(layer_matches=48,tokens=gates["real-oracle-gate.json"]["tokens"]),patch_apply_check=True,source_equivalence_sha256=sha(HERE/"final-source-equivalence.json"),build_identities_sha256=sha(HERE/"build-identities.json"),root_cause_proven=False,native_fence_qualification="syntax-only; device qualification pending after owner reboot/admission",cpu_owner_harness="Real-weight gates use original owner. Final harness changes only retained-owner fatal path; original13-case suite repeated in both modes and four seeds. All36 common generated sources agree after build-path relocation.",artifacts=artifacts)
 (HERE/"build-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
 print(json.dumps(dict(passed=True,device_executed=False,artifacts=len(artifacts),layer_matches=48)))
if __name__=="__main__":main()
