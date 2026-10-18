"""Offline rehearsal of the complete inherited evidence/attestation/payload path.

The parent remains packet136 in every generated identity. Packet142 screens do
not qualify a submission and this helper never posts or reads credentials.
"""
import argparse,gzip,json,resource,tempfile,hashlib,sys,shutil
from pathlib import Path
P=Path(__file__).resolve().parent
sys.path.insert(0,str(P))
import packet56_submission as validator

def main(argv=None):
 from v5.p142_v5_build_engine import limits
 limits()
 ap=argparse.ArgumentParser();ap.add_argument('--evidence-bundle',type=Path,required=True);ap.add_argument('--rehearsal-parent',choices=('packet136-record-bundle',),required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args(argv)
 assert a.evidence_bundle.resolve().is_relative_to(P) and a.output.resolve().is_relative_to(P)
 assert not a.output.exists(),'never overwrite rehearsal evidence'
 raw=a.evidence_bundle.read_bytes();bundle=json.loads(gzip.decompress(raw));assert bundle['schema']=='lab.packet49.evidence-bundle.v1'
 e=validator.Evidence(bundle['members'])
 with tempfile.TemporaryDirectory(prefix='p142-submission-rehearsal-') as d:
  root=Path(d)
  for name,key in ((validator.THRESHOLD_FILE,'record-threshold.json'),(validator.PINS_FILE,'submission-pins.json')):
   path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(e.raw(key))
  out=root/validator.STAGE/a.rehearsal_parent/'submission/rehearsal'
  result=validator.write_prepared(e,a.rehearsal_parent,out,repo=root)
  queue=json.loads((out/'payload-queue.json').read_text());assert len(queue)==1
  assert not validator.scope_problems(queue[0],repo=root)
  assert result['packet']==a.rehearsal_parent and result['realistic_final_gate']['passed'] is False
  # A changed receipt must fail the same real preparation entry before output.
  corrupt=validator.Evidence(dict(e.members));entry=dict(corrupt.members['WS128/run/summary.json']);entry['sha256']='0'*64;corrupt.members['WS128/run/summary.json']=entry
  refused=False
  try:validator.write_prepared(corrupt,a.rehearsal_parent,out.with_name('corrupt'),repo=root)
  except ValueError:refused=True
  assert refused and not out.with_name('corrupt').exists()
  retained=P/'lineage-inputs'/('rehearsal-'+a.output.stem);assert not retained.exists();retained.mkdir()
  for f in out.iterdir():
   if f.is_file():shutil.copy2(f,retained/f.name)
  paths=[P/'prepare_submission.py',P/'packet56_submission.py',a.evidence_bundle.resolve(),*(P/'lineage-inputs/submission-tools').glob('*.py')]
  sources={str(f.relative_to(P.parents[3])):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths}
  row=dict(passed=True,device_executed=False,network_used=False,submitted=False,rehearsal_only=True,parent_packet=a.rehearsal_parent,packet142_performance_qualified=False,source_bundle_sha256=hashlib.sha256(raw).hexdigest(),parent_rate=result['primary_metric']['value_tok_s'],strict512=False,corrupt_receipt_refused=True,sources=sources,artifacts={str(f.relative_to(P.parents[3])):hashlib.sha256(f.read_bytes()).hexdigest() for f in retained.iterdir() if f.is_file()},validators=['derive','write_prepared','scope_problems','replay_result'])
 a.output.parent.mkdir(exist_ok=True,parents=True);a.output.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
