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
  dispatch=packet/'dispatch-p38.json';dispatch.write_text('{}')
  binary_hash=hashlib.sha256(binary.read_bytes()).hexdigest();dispatch_hash=hashlib.sha256(dispatch.read_bytes()).hexdigest()
  template=dict(passed=True,device_executed=False,binary_sha256=binary_hash,dispatch_sha256=dispatch_hash,token_matches=8,layer_matches=384,layer_total=384)
  for mode in ('none','ngram','hit','miss','mtp'):(packet/f'real-icpx-host-{mode}.json').write_text(json.dumps(dict(template,mode=mode)))
  plan=cpu_campaign.suite_compiler_preflight(packet)
  assert plan['host_compiler']=='icpx-host' and plan['binary_relative_to_build']=='icpx-host/own-rt-iq3' and len(plan['prerequisite_receipts_sha256'])==5
  checks.append('five exact current Intel modes admitted')
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
 record=dict(passed=True,device_executed=False,native_ranks_executed=False,mocked_only=True,checks=checks,actual_intel_suite_pending=True,source_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in ['cpu_campaign.py','suite_export.py','test_suite_compiler.py']})
 (P/'suite-compiler-gates.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(passed=True,checks=len(checks))))
if __name__=='__main__':main()
