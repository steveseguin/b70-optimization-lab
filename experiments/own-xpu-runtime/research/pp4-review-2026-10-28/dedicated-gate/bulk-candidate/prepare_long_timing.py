#!/usr/bin/env python3
"""Prepare two initial-cold121854/8 plans only; never launches an owner.

Run after source/build freeze; --root must not exist. Device execution remains
coordinator-owned with fresh explicit all-owner admissions and passive preflight.
"""
import argparse
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'engine/tools'))
sys.path.insert(0,str(ROOT/'gsq-rco-iq3s/serving/lan'))
import dedicated_provider_driver as dedicated
import pp4_backend as pp4

def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def digest(path):return sha256(path.read_bytes()).hexdigest()
def prepare(root,receipt):
 root=root.resolve();receipt=receipt.resolve()
 if root.exists():raise ValueError('fresh exclusive plan root required')
 original=Path('/dev/shm/sc117-pp4-262k-lan/control-_uc2cmys')
 request=original/'output/requests/request-000002/request-plan.json'
 old=json.loads(request.read_text());prompt=old['prompt_tokens']
 if len(prompt)!=121854:raise ValueError('preserved actual long prompt extent')
 resultpath=request.with_name('driver-result.json');result=json.loads(resultpath.read_text())
 if len(result['output_ids'])!=8:raise ValueError('preserved eight-output reference')
 root.mkdir(mode=0o700)
 raw=struct.pack(f'<{len(prompt)}i',*prompt);promptpath=root/'prompt.i32';promptpath.write_bytes(raw)
 common=dict(build_receipt=str(receipt),prompt_tokens=prompt,context=262144,max_new=8,admitted_max_new=8,
  seconds=2400,grace_seconds=120,memory_start_bytes=103079215104,check_policy='measured',
  measured_policy_admitted=True,verify_restore=False,verify_recursive_restore=False,
  verify_provider_survival=False,dump_each=False,ring_trace_limit=100000,
  recursive_flat_copy=True,capture_ready_overlap=True)
 dc=json.loads(Path('/dev/shm/sc117-dedicated-3plus1-20261028-r3/config.json').read_text())
 dc.update(common,output=str(root/'dedicated-output'),dedicated_capture_ready=True,
  dedicated_bulk_prefill=True,prefill_rows=256,prefill_pipeline=False,
  dedicated_prefill_prompt=str(promptpath),dedicated_prefill_prompt_sha256=sha256(raw).hexdigest())
 # These PP4-only config keys are not consumed by the dedicated planner.
 # Preserve the current dedicated implementation; do not imply flat copy is on.
 dc.pop('recursive_flat_copy',None);dc.pop('capture_ready_overlap',None)
 pc=json.loads((original/'config.json').read_text());pc.update(common,output=str(root/'pp4-output'),prefill_pipeline=True,prompt_tokens=[1])
 suite=dict(schema='ownrt.persistent-rolling-inputs.v1',model_identity_sha256=old['model_identity_sha256'],
  activation_dtype=old['activation_dtype'],eos_token_ids=old['eos_token_ids'],
  prompts=[dict(id='planning-only',prompt_tokens=[1],max_new=8)])
 sp=root/'pp4-suite.json';save(sp,suite);pc.update(suite=str(sp),suite_sha256=digest(sp),suite_prompt_count=1)
 paths={}
 for name,config,planner in [('dedicated',dc,dedicated.make_plan),('pp4',pc,pp4.make_plan)]:
  cp=root/(name+'-config.json');save(cp,config);plan=planner(cp);pp=root/(name+'-plan.json');save(pp,plan)
  paths[name]=dict(config=str(cp),plan=str(pp),plan_sha256=digest(pp),output=plan['output'],boundaries=plan['boundaries'],bdfs=[s['bdf'] for s in plan['stages']])
 manifest=dict(schema='ownrt.initial-cold-long-timing-plan.v1',device_execution_requested=False,
  conditions='One first inference request per topology, no warmup or cached prompt state. Dedicated uses initial native cold state; existing PP4 service performs its normal validated cold RESET before first HTTP request. Request elapsed excludes load/reset. Reset kernels may warm differently; no identical-runtime-cost assertion.',
  build_receipt=str(receipt),build_receipt_sha256=digest(receipt),prompt_tokens=121854,max_new=8,
  prompt_i32_sha256=sha256(raw).hexdigest(),historical_output_ids=result['output_ids'],
  historical_source=dict(request_plan=str(request),sha256=digest(request),result=str(resultpath),result_sha256=digest(resultpath)),
  plans=paths,comparison='Exact prompt/output IDs, zero cold-state reuse, same binary/model/core flags/policy/rows; topology and sequential dedicated vs pipelined PP4 are explicit treatments. Historical warmed524.273s is not the control. PP4 planner has tiny planning inputs because its existing service separately admits caller prompts and bounded trace omissions; this is explicit existing service behavior, not a fabricated full scalar trace.',
  recursive_snapshot_copy=dict(dedicated='existing per-extent copy; no flat-copy flag',pp4='qualified flat copy enabled',scope='Explicit implementation difference, not a topology-only comparison. Dedicated planner exposure is a separate unqualified lever.'),
  execution='Dedicated: dedicated_provider_driver.execute via its CLI/admission. PP4: existing PP4 HTTP service first request only, use preserved long-body JSON. Its tiny suite is planning-only and MUST NOT execute as inference; actual request body has121854prompt/8cap. Existing cold RESET is allowed, no new reset implementation. Coordinator owns fresh admissions/start/one shutdown and all-owner cleanup.',
  limitations='Requires completed bulk full-state/seam gate on this binary before timing; no dedicated reset/overlap claim; one sample each, no suite/score/independent-reference claim.')
 save(root/'identity.json',manifest);return manifest
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--build-receipt',type=Path,required=True);a=ap.parse_args()
 os.environ['SC117_CONTEXT']='262144'
 print(json.dumps(prepare(a.root,a.build_receipt),indent=2))
