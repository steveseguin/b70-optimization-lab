#!/usr/bin/env python3
"""Source-only expanded512 screen; root owns any plan and operational launch."""
from pathlib import Path
import argparse,importlib.util,json
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('expanded_quality_private_suite',P/'suite.py');H=importlib.util.module_from_spec(s);s.loader.exec_module(H)
Q=H.Q;S=H.S;A=H.A;O=Q.O;M=Q.M
CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-quality-expanded-a.control')
EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-quality-expanded-a')
UNIT='gsq-quality-expanded-a.service'
# Preserve the original Transport/RetainedOwner class identity and Monitor.
for module in (Q,Q.X,O,M):module.CONTROL=CONTROL;module.EVIDENCE=EVIDENCE;module.UNIT=UNIT
PARENT_BUILD=Q.build_plan

def build_plan():
 H.actual_authority();p=PARENT_BUILD()
 p.update(initial_cumulative_metadata_margin_bytes=H.INITIAL_METADATA_MARGIN,initial_external_required_bytes=8933302060,schema='gsq.quality-expanded.once.v1',max_new=512,startup_max_new=128,measured_request_max_new=512,scope='Original12 unchanged prompts; full512-cap target/MTP equality plus original128 token prefix; full-output task readback pending',no_speed_claim=True)
 p['source_sha256'].update(H.review_sources())
 H.require(p['requests']==26 and p['suite']['total_requests']==26 and p['suite']['adapter']['request_cap']==26,'unchanged26 requests')
 H.require(p['suite']['storage']['retained_state_dumps']==27 and p['suite']['storage']['evidence_forecast_bytes']==6383165228,'unchanged27 captures/128MiB reserve')
 return p
O.build_plan=build_plan

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--run',type=Path);a=p.parse_args()
 if a.plan:print(json.dumps(build_plan(),indent=2));return
 raise SystemExit(O.run(a.run))
if __name__=='__main__':main()
