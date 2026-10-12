"""Verify the complete CPU suite and write its final evidence report atomically."""
from datetime import datetime
import json,subprocess,sys
import suite_run as r
import suite_check as c

def main():
 r.disk_guard()
 manifest=r.read(r.INPUTS/'suite-manifest.json')
 r.check(manifest['complete'] and len(manifest['prompts'])==12,'suite not complete')
 checks=[]
 for e in manifest['prompts']:
  d=r.HERE/e['prompt_id']; bundle=r.ROOT/e['input_bundle']
  n,f=c.check_prompt(d,d,e)
  r.validate(d,bundle)
  prefix=r.suite64_equality(d,e['prompt_id'])
  r.check(prefix['passed'] is True,'64-suite comparison missing or failed')
  stored=r.read(d/'suite64-equality-proof.json')
  r.check(stored['passed'] is True,'stored prefix comparison missing')
  receipt=r.read(d/'receipt.json')
  snapshot=r.HERE/'runner-snapshots'/(receipt['runner_sha256']+'.py')
  r.check(r.sha(snapshot)==receipt['runner_sha256'],'runner snapshot binding')
  r.check(receipt['build_receipt_sha256']==r.sha(r.HERE/'build-receipt.json'),'build receipt binding')
  r.check(receipt['binary_sha256']==r.read(r.HERE/'build-receipt.json')['binary_sha256'],'CPU binary binding')
  r.check(receipt['suite64_equality_sha256']==r.sha(d/'suite64-equality-proof.json'),'prefix receipt binding')
  for name,info in receipt['compressed_logs'].items():
   with r.gzip.open(d/(name+'.gz'),'rb') as stream:
    r.check(r.hashlib.file_digest(stream,'sha256').hexdigest()==info['sha256'],'compressed log hash')
  checks.append(dict(prompt=e['prompt_id'],tokens=n,raw_fixtures=f,prefix_tokens=prefix['tokens'],passed=True))
 r.check(r.equality(r.HERE/'incident-retrospective')['passed'],'sealed incident mismatch')
 testfiles=['test_suite_run.py','test_suite_check.py']
 tests=[]
 for name in testfiles:
  out=subprocess.run(r.PREFIX+[sys.executable,'-B',str(r.HERE/name)],capture_output=True,text=True)
  tests.append(dict(file=name,sha256=r.sha(r.HERE/name),returncode=out.returncode,output=out.stdout+out.stderr))
  r.check(out.returncode==0,'unit tests failed: '+out.stdout+out.stderr)
 r.save(r.HERE/'checker-tests.json',dict(passed=True,checker_sha256=r.sha(r.HERE/'suite_check.py'),tests=tests))
 receipts=[r.read(r.HERE/e['prompt_id']/'receipt.json') for e in manifest['prompts']]
 start=min(datetime.fromisoformat(x['started_utc']) for x in receipts)
 end=max(datetime.fromisoformat(x['completed_utc']) for x in receipts)
 report=dict(passed=True,checked_utc=r.utc(),manifest_sha256=r.sha(r.INPUTS/'suite-manifest.json'),
    prompts=checks,total_generated_tokens=sum(x['tokens'] for x in checks),
    total_raw_fixtures=sum(x['raw_fixtures'] for x in checks),
    first_start_utc=start.isoformat(),last_completed_utc=end.isoformat(),
    campaign_span_seconds=(end-start).total_seconds(),
    summed_numerical_process_wall_seconds=manifest['total_elapsed_seconds'],
    process_cpu_hours=manifest['total_cpu_hours'],
    all_64_prefixes_equal=True,sealed_capacity_gate_passed=True,
    checker_tests_sha256=r.sha(r.HERE/'checker-tests.json'))
 r.save(r.HERE/'final-verification.json',report)
 extra=f"\nFinal verification: all twelve oracle outputs and both fixture ranges passed the exact checker. All twelve available 64-token prefixes and their step 1–8 fixtures matched. The sealed incident capacity gate passed. Actual campaign span: {report['campaign_span_seconds']:.3f} seconds ({report['campaign_span_seconds']/3600:.3f} hours); summed process wall time: {report['summed_numerical_process_wall_seconds']:.3f} seconds; measured CPU time: {report['process_cpu_hours']:.6f} CPU hours. See `final-verification.json` and `checker-tests.json` in the oracle directory.\n"
 for root in (r.HERE,r.INPUTS):
  path=root/'README.md';text=path.read_text()
  if '\nFinal verification:' in text:text=text.split('\nFinal verification:')[0]
  temp=path.with_suffix('.md.tmp');temp.write_text(text+extra)
  r.check(temp.read_text()==text+extra,'README write verification');temp.replace(path)
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
