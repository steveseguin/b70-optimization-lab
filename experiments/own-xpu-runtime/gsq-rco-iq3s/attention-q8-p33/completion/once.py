#!/usr/bin/env python3
"""Explicit missing-five completion; unchanged candidate monitor/owner lifecycle."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;CANDIDATE=P.parent;L=CANDIDATE.parent
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-attention-p33-completion-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-attention-p33-completion-a')
UNIT='gsq-attention-p33-completion-a.service'
PARENT=CANDIDATE/'operating/once.py';PARENT_SHA='2401e2d8f09c07d5838a21b27054b583754a51188db97f3dcf176e11e0bd54aa'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
if sha(PARENT)!=PARENT_SHA:raise RuntimeError('frozen candidate coordinator changed')
O=load(PARENT,'gsq_completion_candidate_coordinator');parent_plan=O.build_plan
S=load(P/'generated/suite.py','gsq_completion_suite');M=O.M
# Preserve exact adapter exception identity through both private coordinators.
O.S=S;O.O.S=S
for module in (O,O.O,M):module.CONTROL=CONTROL;module.EVIDENCE=EVIDENCE;module.UNIT=UNIT

def build_plan():
 S.V.prerequisites(S.V.BINARY_SHA)
 base=parent_plan();base.update(schema='ownrt.gsq.attention-completion-once.v1',requests=12,unit=UNIT,scope='five missing prompt pairs7..11; separate-session correctness; no combined speed claim')
 review=P/'evidence/independent-review.json';v=json.loads(review.read_text());S.require(v['passed'] and v['source_sha256'],'independent completion review')
 for n,h in v['source_sha256'].items():S.require(sha(Path(n) if Path(n).is_absolute() else S.R/n)==h,'reviewed completion source '+n)
 files=[Path(__file__),PARENT,P/'prepare.py',P/'preparation.json',P/'overlay.patch',P/'checks.py',P/'manifest.json',P/'generated/suite.py',P/'test_completion.py',P/'README.md',review,S.V.PRIOR,S.V.STORAGE,L/'storage/evidence/post-archive-host.json']
 base['source_sha256'].update({str(f):sha(f) for f in files})
 base['completion']=dict(prompt_indices=list(range(7,12)),prior_verified_pairs=7,prior_verified_arms=14,prior_review_sha256=S.V.PRIOR_SHA,separate_session=True,combined_timing_claim=False,recovered_bin_records=57045,new_bin_forecast=27469,additional_metadata_allowance=4096,hard_file_record_quota=False)
 base['monitor_configuration'].update(CONTROL=str(CONTROL),EVIDENCE=str(EVIDENCE),UNIT=UNIT,behavior='unchanged frozen Monitor/run; exact candidate adapter and remaining-five suite')
 return base
O.O.build_plan=build_plan

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=ap.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return 0
 return O.O.run(a.run)
if __name__=='__main__':raise SystemExit(main())
