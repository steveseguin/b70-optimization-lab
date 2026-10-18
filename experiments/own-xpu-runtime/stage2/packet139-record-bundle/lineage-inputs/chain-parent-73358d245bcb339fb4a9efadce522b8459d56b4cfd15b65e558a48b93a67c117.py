#!/usr/bin/env python3
"""No-rank Intel suite prerequisite qualification checks using tiny mock files."""
import copy,hashlib,json,os,tempfile
from pathlib import Path
import cpu_campaign,suite_export
P=Path(__file__).resolve().parent

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 checks=[]
 with tempfile.TemporaryDirectory(prefix='suite-compiler-',dir=P/'build') as directory:
  packet=Path(directory);binary=packet/'build/icpx-host/own-rt-iq3';binary.parent.mkdir(parents=True);binary.write_bytes(b'fake host binary; never executable')
  dispatch=packet/'dispatch-p33.json';dispatch.write_bytes((P/'dispatch-p33.json').read_bytes())
  suite_dispatch=packet/'dispatch-p38.json';suite_dispatch.write_bytes((P/'dispatch-p38.json').read_bytes())
  kernel_source=packet/'mock-kernel.cpp';kernel_source.write_text('// mock CPU gate source')
  sources={kernel_source.name:hashlib.sha256(kernel_source.read_bytes()).hexdigest()}
  children={}
  for name in ('p30-attention-cpu.json','p30-small-cpu.json'):
   child=packet/name;child.write_text(json.dumps(dict(passed=True)))
   children[name]=dict(sha256=hashlib.sha256(child.read_bytes()).hexdigest())
  (packet/'p38-kernel-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,schema='packet38.p30-cpu-gates.v1',arithmetic='iq3-p17-detmath-v2',sources_sha256=sources,receipts=children,binaries_sha256={'build/icpx-host/own-rt-iq3':hashlib.sha256(binary.read_bytes()).hexdigest()})))
  (packet/'p38-qsa-capacity-gates.json').write_text(json.dumps(dict(passed=True,device_executed=False,sources_sha256=sources,checks=528,compilers=2,full_arrays_identical=True)))
  binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest();dispatch_hash=hashlib.sha256(dispatch.read_bytes()).hexdigest()
  template=dict(passed=True,device_executed=False,binary_sha256=binary_hash,dispatch_sha256=dispatch_hash,token_matches=8,layer_matches=384,layer_total=384)
  for mode in ('none','ngram','hit','miss','mtp'):(packet/f'real-icpx-host-{mode}.json').write_text(json.dumps(dict(template,mode=mode)))
  plan=cpu_campaign.suite_compiler_preflight(packet)
  assert plan['host_compiler']=='icpx-host' and plan['binary_relative_to_build']=='icpx-host/own-rt-iq3' and len(plan['prerequisite_receipts_sha256'])==5
  assert plan['prerequisite_dispatch_sha256']==dispatch_hash and plan['suite_dispatch_sha256']==hashlib.sha256(suite_dispatch.read_bytes()).hexdigest()
  assert plan['prerequisite_dispatch_sha256']!=plan['suite_dispatch_sha256'] and len(plan['kernel_qualification_receipts_sha256'])==2
  checks.append('five exact current Intel p33 modes plus separate current p38 kernels admitted')
  target=packet/'real-icpx-host-mtp.json';original=target.read_bytes()
  for name,delta in [('failed mode',dict(passed=False)),('device mode',dict(device_executed=True)),('stale binary',dict(binary_sha256='0'*64)),('different dispatch',dict(dispatch_sha256='0'*64)),('wrong mode',dict(mode='none')),('incomplete tokens',dict(token_matches=7)),('incomplete fixtures',dict(layer_matches=383))]:
   target.write_text(json.dumps(dict(template,mode='mtp')|delta))
   try:cpu_campaign.suite_compiler_preflight(packet)
   except AssertionError:pass
   else:raise AssertionError('admitted '+name)
   target.write_bytes(original);checks.append(name+' refused')
  target.unlink()
  try:cpu_campaign.suite_compiler_preflight(packet)
  except FileNotFoundError:pass
  else:raise AssertionError('missing prerequisite admitted')
  checks.append('missing fifth mode refused')
  target.write_bytes(original)
  kernel_source.write_text('// changed source')
  try:cpu_campaign.suite_compiler_preflight(packet)
  except AssertionError:pass
  else:raise AssertionError('stale p38 kernel source admitted')
  checks.append('stale p38 kernel qualification refused')
 record=dict(passed=True,device_executed=False,native_ranks_executed=False,mocked_only=True,checks=checks,actual_intel_suite_pending=True,source_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['cpu_campaign.py','suite_export.py','test_suite_compiler.py']})
 (P/'suite-compiler-gates.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(passed=True,checks=len(checks))))
if __name__=='__main__':main()
