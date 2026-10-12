#!/usr/bin/env python3
"""Actual Intel-host 128-token tail-fixture proof for one of twelve prompts.

This is partial CPU correctness evidence only. It is not full-suite qualification
or a device speed result. The frozen 64-token exporter is deliberately unused.
"""
import argparse,fcntl,json,os,time
from pathlib import Path
import pipeline as pp,suite,storage
P=Path(__file__).resolve().parent;B=P/'build'
SOURCES=('suite128_cpu_gate.py','suite.py','suite_metrics.py','pipeline.py','storage.py','main.cpp','rank.hpp','native_controller.hpp','mtp.hpp')
PROMPT='incident-retrospective'
def process_identity(pid):
 try:
  # /proc field22 is starttime; splitting after comm tolerates spaces/parens.
  return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
 except FileNotFoundError:return None
 except (OSError,IndexError,UnicodeError):return 'unreadable'
def run():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--output',type=Path,default=B/'suite128-tail-cpu')
 a=ap.parse_args();root=a.output.resolve()
 pp.require(root.parent==B.resolve() and not root.exists(),'fresh direct child of packet40/build required')
 pp.require(os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2','nice19 OMP_NUM_THREADS=2 required')
 admission=storage.admit(128_000_000)
 source_sha256={name:pp.sha(P/name) for name in SOURCES}
 binary=B/'icpx-host/own-rt-iq3';binary_sha256=pp.sha(binary)
 manifest_path=P.parent/'suite-inputs-20261012-cap128/suite-manifest.json'
 original=json.loads(manifest_path.read_text());entries=[e for e in original['prompts'] if e['prompt_id']==PROMPT]
 pp.require(original['token_cap']==128 and original['complete'] is True and len(original['prompts'])==12 and len(entries)==1,'complete128 parent manifest required')
 entry=entries[0];oracle=suite.ROOT/entry['oracle_directory']
 pp.require(entry['generated_tokens']==128 and not entry['ended_early'],'128 oracle tokens required')
 selector='1-8,97-104';steps=pp.retention_steps(selector,128)
 pp.require(entry['fixture_steps']==steps,'oracle tail fixture steps changed')
 oracle_receipt_sha256=pp.sha(oracle/'receipt.json');oracle_result_sha256=pp.sha(oracle/'result.json')
 pp.require(oracle_receipt_sha256==entry['oracle_receipt_sha256'],'oracle receipt identity')
 checker=oracle.parent/'suite_check.py';checker_sha256=pp.sha(checker)
 subset=dict(original,complete=False,prompts=entries,parent_manifest_sha256=pp.sha(manifest_path),scope='partial CPU correctness only: incident-retrospective, 1 of 12 prompts')
 subset_path=root/'subset-manifest.json'
 args=suite.parser().parse_args(['--binary',str(binary),'--output',str(root/'run'),'--suite-manifest',str(subset_path),'--controller','native','--draft','mtp','--dispatch',str(P/'dispatch-p38.json'),'--repeat','1','--context','256','--max-new','128','--retain-steps',selector,'--seconds','172800','--wait-seconds','7200'])
 pp.require(args.device is False and args.mini is False,'actual host model only')
 row=dict(passed=False,device_executed=False,no_speed_claim=True,real_model_execution=True,partial_suite=True,prompts_executed=1,total_prompts=12,prompt_id=PROMPT,requested_max_new=128,retain_steps=selector,controller='native',draft='mtp',host_compiler='icpx-host',binary_sha256=binary_sha256,binary_relative_to_build='icpx-host/own-rt-iq3',source_sha256=source_sha256,parent_manifest_sha256=pp.sha(manifest_path),subset_manifest_sha256=None,oracle_receipt_sha256=oracle_receipt_sha256,oracle_result_sha256=oracle_result_sha256,checker_sha256=checker_sha256,dispatch_sha256=pp.sha(P/'dispatch-p38.json'),storage_admission=admission,realistic_final_gate=dict(passed=False,reason='partial CPU correctness proof;128 cap;no device or promotion evidence'))
 error=None;started=time.monotonic();owned_root=False;launched={}
 def record_launch(pid):
  launched[pid]=None
  launched[pid]=process_identity(pid)
 try:
  root.mkdir();owned_root=True;pp.save(subset_path,subset);row['subset_manifest_sha256']=pp.sha(subset_path)
  summary=suite.run(args,launch_hook=record_launch)
  pp.require(summary['passed'] and summary['declared_prompt_count']==1 and summary['input_manifest_complete'] is False,'partial suite result')
  request_path=root/'run/repeat-1'/PROMPT/'receipt.json';request=json.loads(request_path.read_text());check=request['oracle_check']
  pp.require(request['passed'] and len(request['tokens'])==128 and not request['ended_early'],'all128 emitted tokens required')
  pp.require(check['passed'] and check['every_emitted_token'] and check['tokens']==128 and check['fixture_files']==768,'every token and all768 early/tail fixtures required')
  pp.require(request['device_executed'] is False and request['binary_sha256']==binary_sha256 and request['diagnostic'],'host diagnostic identity')
  request_root=request_path.parent
  fixtures={str(f.relative_to(request_root)):pp.sha(f) for f in request_root.glob('step*/layer-*.bf16')}
  pp.require(len(fixtures)==768 and all(digest==pp.sha(oracle/name) for name,digest in fixtures.items()),'retained fixture hashes differ from oracle')
  retained=suite.retained_state(request_root)
  inventories={str(rank):retained[f'rank{rank}/request-state-inventory.json']['sha256'] for rank in (0,1)}
  ownership=json.loads((root/'run/ranks/ownership.json').read_text())
  pp.require(not ownership['retained_pids'] and ownership['returncodes']==[0,0],'host rank owners not drained')
  for rank in (0,1):
   launch=json.loads((root/'run/ranks'/f'rank{rank}-launch.json').read_text())
   pp.require(launch['device_executed'] is False and Path(launch['argv'][0]).resolve()==binary.resolve(),'non-host rank launch')
  pp.require(source_sha256=={name:pp.sha(P/name) for name in SOURCES} and pp.sha(binary)==binary_sha256,'source/binary changed during gate')
  pp.require(pp.sha(manifest_path)==row['parent_manifest_sha256'] and pp.sha(oracle/'receipt.json')==oracle_receipt_sha256 and pp.sha(oracle/'result.json')==oracle_result_sha256 and pp.sha(checker)==checker_sha256,'oracle/manifest/checker changed during gate')
  row.update(passed=True,tokens=128,fixture_files=768,fixture_sha256=fixtures,token_ids=request['tokens'],output_token_sha256=request['output_token_sha256'],request_receipt_sha256=pp.sha(request_path),state_inventory_sha256=inventories,warmup_receipt_sha256=pp.sha(root/'run/warmup/receipt.json'),summary=summary)
 except BaseException as exc:
  error=exc;row.update(error=str(exc))
 finally:
  row['wall_seconds_diagnostic']=time.monotonic()-started
  observed={pid:process_identity(pid) for pid in launched}
  retained=[pid for pid,start in launched.items() if observed[pid] is not None and (start in (None,'unreadable') or observed[pid]=='unreadable' or observed[pid]==start)]
  row['retained_pids']=retained
  if retained:
   row.update(passed=False,error='CPU rank still exists after suite drain; retain owned scratch for inspection',scratch_retained=str(root))
   if error is None:error=RuntimeError(row['error'])
  elif owned_root:row['scratch_archive']=storage.discard(root)
  pp.save(P/'suite128-tail-cpu-gates.json',row)
 print(json.dumps(dict(passed=row['passed'],tokens=row.get('tokens'),fixtures=row.get('fixture_files'),partial_suite='1/12',scratch_removed=not root.exists())))
 if error:raise error
def main():
 # Serialize the full draft model with all other CPU MTP gates.
 with (B/'cpu-mtp.lock').open('a+') as lock:
  fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
  run()
if __name__=='__main__':main()
