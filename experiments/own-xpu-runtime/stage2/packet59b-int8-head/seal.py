#!/usr/bin/env python3
"""Immutable lean screen seal, including all retained CPU fixture bytes."""
import argparse,importlib.util,json,sys
from pathlib import Path
import build
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');a=ap.parse_args();build.guard()
 for mode in ('device','gnu-host'):
  r=json.loads((P/('build-'+mode+'-receipt.json')).read_text())
  assert r['passed'] and not r['device_executed']
  for name,h in r['sources'].items():assert build.sha(ROOT/name)==h,'source changed: '+name
  for name,h in r['artifacts'].items():assert build.sha(P/name)==h,'artifact changed: '+name
  for name,h in r['command_files'].items():assert build.sha(P/name)==h,'commands changed: '+name
  for name,h in r['checked_mirror_sha256'].items():assert build.sha(P/name)==h,'compiler input changed: '+name
 gate=json.loads((P/'fixture/receipt.json').read_text());assert gate['passed'] and not gate['device_executed']
 assert gate['build_receipt_sha256']==build.sha(P/'build-device-receipt.json')
 assert gate['host_build_receipt_sha256']==build.sha(P/'build-gnu-host-receipt.json')
 for name,h in gate['fixture_files_sha256'].items():assert build.sha(P/name)==h,'fixture changed: '+name
 output=P/'screen-seal.json'
 if a.verify:
  seal=json.loads(output.read_text());assert seal['passed'] and not seal['device_executed']
  for name,h in seal['sources'].items():assert build.sha(ROOT/name)==h,name
  for name,h in seal['artifacts'].items():assert build.sha(P/name)==h,name
  for name,h in seal['gates'].items():assert build.sha(P/name)==h,name
  for name,h in seal['fixture_files'].items():assert build.sha(P/name)==h,name
 else:
  sys.path.insert(0,str(P.parent/'screen'))
  spec=importlib.util.spec_from_file_location('screen_sealer',P.parent/'screen/seal.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  m.create(P,'tp2',P/'build-device-receipt.json',P/'fixture/receipt.json',P/'build/device/own-rt-iq3',P/'dispatch-speed6.json',output)
  seal=json.loads(output.read_text());seal['fixture_files'].update(gate['fixture_files_sha256'])
  seal['gates']['build-gnu-host-receipt.json']=build.sha(P/'build-gnu-host-receipt.json')
  seal['packet59b']=dict(parent='packet56-draft-prefix',draft_rank=0,target_split=23,context=4096,draft_head='INT8 row scale',target_unchanged=True,head_rows=91392)
  output.write_text(json.dumps(seal,indent=2)+'\n')
 print(json.dumps(dict(passed=True,device_executed=False,seal=str(output),sha256=build.sha(output))))
if __name__=='__main__':main()
