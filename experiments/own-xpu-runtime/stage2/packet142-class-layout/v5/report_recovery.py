"""Offline report repair; original device window and failure remain immutable."""
import gzip,json,time
from pathlib import Path
from common import HERE,ROOT,D,read,require,sha,save

def recover(args):
 output=args.output.resolve()
 require(output==HERE/'evidence/device-attention-order600-smoke-B' and args.kind=='smoke' and args.variant=='attention-order600' and args.lane=='B','only the retained attention smoke may be recovered')
 require(not (output/'report-regeneration.json').exists(),'report already regenerated')
 window=read(output/'window.json');identity=read(output/'identity.json');coord=read(output/'lane-coordination.json')
 require(window['identity']==identity and window.get('device_complete') and window.get('device_executed') and window.get('lease_released') and not window.get('child_still_running') and not window.get('child_retained') and not window.get('stop_reasons') and window.get('returncode')==0,'device completion unproven')
 require(window.get('report_failed') and read(output/'report-failure.json').get('device_failure') is False,'not a report-only failure')
 require(coord['passed'] and coord['released_before_report'] and read(output/'run/teardown.json')['drained'],'drain/release unproven')
 require(sha(identity['binary'])==identity['binary_sha256'] and sha(identity['dispatch'])==identity['dispatch_sha256'],'native identity changed')
 require(sha(D.ORACLE/'results/completion.json')==window['oracle_completion_sha256'] and read(output/'suite-manifest.snapshot.json')==D.oracle_inputs(),'oracle changed')
 archive=HERE.parent/'lineage-inputs/pre-142c.json.gz';old=json.loads(gzip.decompress(archive.read_bytes()))
 import hashlib
 oldseal=old['v5/placement-validation/wrapper-seal.json'].encode()
 require(hashlib.sha256(oldseal).hexdigest()==window['wrapper_seal_sha256'],'original wrapper not retained')
 # All native sources and configurations from the execution seal must still match.
 for name,digest in json.loads(oldseal)['sources'].items():
  if Path(name).suffix in ('.cpp','.hpp','.bf16','.tsv') or '/native-' in name or '/build/' in name:
   require(sha(ROOT/name)==digest,'native input changed: '+name)
 before={str(f.relative_to(output)):sha(f) for f in output.rglob('*') if f.is_file()}
 originals={n:(output/n).read_bytes() for n in ('summary.json','run/summary.json')}
 from screen import report_completed
 result=report_completed(output,window,identity,coord)
 for name,raw in originals.items():(output/name).write_bytes(raw)
 require(all(sha(output/n)==digest for n,digest in before.items()),'original evidence changed')
 receipt=dict(schema='packet142.offline-report-regeneration.v1',passed=True,device_executed=False,model_payload_read=False,regenerated_utc_ns=time.time_ns(),original_files=before,original_wrapper_archive=str(archive.relative_to(ROOT)),original_wrapper_archive_sha256=sha(archive),original_wrapper_seal_sha256=window['wrapper_seal_sha256'],report_sha256=sha(output/'bracket-summary.json'),report_sources={str(f.relative_to(ROOT)):sha(f) for f in (HERE/'bracket_job.py',HERE/'screen.py',HERE/'report_recovery.py',HERE/'p142_v5_compare.py')},original_failure_preserved=True,original_window_preserved=True)
 save(output/'report-regeneration.json',receipt)
 print('Offline attention smoke report PASS; original device evidence preserved')
 return 0

def recovered_window(output,window):
 receipt=read(output/'report-regeneration.json')
 require(receipt['passed'] and receipt['device_executed'] is False,'invalid offline recovery')
 for name,digest in receipt['original_files'].items():require(sha(output/name)==digest,'original evidence changed: '+name)
 for name,digest in receipt['report_sources'].items():require(sha(ROOT/name)==digest,'report code changed: '+name)
 require(sha(ROOT/receipt['original_wrapper_archive'])==receipt['original_wrapper_archive_sha256'] and receipt['original_wrapper_seal_sha256']==window['wrapper_seal_sha256'],'original wrapper changed')
 require(sha(output/'bracket-summary.json')==receipt['report_sha256'],'recovered report changed')
 return dict(window,passed=True,files={**receipt['original_files'],'bracket-summary.json':receipt['report_sha256']})
