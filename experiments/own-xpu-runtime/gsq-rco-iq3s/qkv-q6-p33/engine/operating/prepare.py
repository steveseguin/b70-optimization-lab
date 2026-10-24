#!/usr/bin/env python3
"""Materialize narrowly patched frozen Python sources; no process/device calls."""
import difflib,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[2];R=L.parents[2]
PINS={'serving/adapter.py':'68538b214b7bda9c2fa5cd87534bad2243745b8a1af0dc82b43f01da48b06a01','baseline/suite.py':'301347fe701eaaaa1e16e7a3891da2808a956147ae67b9b918dd451b7fe010d4'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(t,a,b):
 assert t.count(a)==1,(a,t.count(a));return t.replace(a,b)
def materialize():
 out=P/'generated';out.mkdir(exist_ok=True);patch=[];outputs={}
 for name,h in PINS.items():
  src=L/name;assert sha(src)==h;original=src.read_text();t=original
  if name.startswith('serving'):
   t=replace(t,'LANE=P.parent\nROOT=P.parents[3]',f'LANE=Path({str(L)!r})\nROOT=Path({str(R)!r})\nCANDIDATE=P.parent.parent\nLEDGER=P.parent/"candidate-ledger.json"')
   t=t.replace("LANE/'memory/engine-accounting.json'",'LEDGER')
   t=replace(t,"receipt=LANE/'integration/evidence'/('full-host-build.json' if mini else 'full-native-build.json')","require(not mini,'candidate adapter is native-only; no synthetic override')\n    receipt=CANDIDATE/'evidence/native-build.json'")
   t=replace(t,"return cmd\n", "cmd.extend(['--attention-q8-p33','--qkv-q6-p33'])\n    return cmd\n")
   t=replace(t,"files=[Path(__file__).resolve(),PARENT", "files=[Path(__file__).resolve(),P.parent/'prepare.py',P.parent/'preparation.json',PARENT")
  else:
   t=replace(t,"P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3]",f"P=Path({str(L/'baseline')!r});L=P.parent;R=P.parents[3]\nOPERATING=Path(__file__).resolve().parent.parent")
   t=replace(t,"p=L/'serving/adapter.py';", "p=OPERATING/'generated/adapter.py';")
   t=replace(t,'A=load_adapter()',"A=load_adapter()\ns=importlib.util.spec_from_file_location('gsq_combined_candidate_checks',OPERATING/'checks.py');C=importlib.util.module_from_spec(s);s.loader.exec_module(C)")
   begin=t.index('def first_native_proof(');end=t.index('\ndef build_plan',begin)
   t=t[:begin]+"def first_native_proof(binary_sha):\n    return C.prerequisites(binary_sha)\n"+t[end:]
   t=replace(t,"L/'integration/evidence/full-native-build.json'","OPERATING.parent/'evidence/native-build.json',OPERATING/'checks.py',OPERATING/'candidate-ledger.json',OPERATING/'preparation.json'")
   t=replace(t,"m=m or manifest();require(","C.bind_references(plan)\n    m=m or manifest();require(")
   t=replace(t,"A.save(destination/'suite-request.json',row);t.check_alive();return row", "A.save(destination/'suite-request.json',row)\n        if measuring:\n            C.check_arm(row)\n            A.save(destination/'baseline-exact.json',dict(passed=True,reference_sha256=C.REFERENCE_SHA,scope='exact corresponding independently audited baseline token/state arm'))\n        t.check_alive();return row")
   t=replace(t,"adapter=base,manifest_sha256=", "adapter=base,baseline_review_sha256=C.REVIEW_SHA,baseline_result_sha256=C.REFERENCE_SHA,manifest_sha256=")
   t=replace(t,"result.update(evidence_label='GSQ preregistered resident suite; same-new-binary target/MTP'", "result.update(evidence_label='GSQ combined attention/Q6 QKV p33 candidate; every measured arm checked against frozen baseline'")
   t=replace(t,"claim_scope='one resident run;12 fixed short prompts;cap128; initialized kernels; no cold-start/general-context/old-model record claim'", "claim_scope='candidate correctness and descriptive timing only; separate-process baseline comparison is not a speed promotion'")
  path=out/Path(name).name;path.write_text(t);outputs[str(path.relative_to(R))]=sha(path)
  patch.extend(difflib.unified_diff(original.splitlines(True),t.splitlines(True),fromfile=str(src.relative_to(R)),tofile=str(path.relative_to(R))))
 (P/'overlay.patch').write_text(''.join(patch))
 receipt=dict(schema='ownrt.gsq.combined-operating-preparation.v1',source_sha256={str((L/n).relative_to(R)):h for n,h in PINS.items()},generated_sha256=outputs,recipe_sha256=sha(__file__),patch_sha256=sha(P/'overlay.patch'),device_executed=False)
 (P/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':materialize()
