"""Exercise this packet's prepare_submission on a private packet136 evidence copy."""
import gzip,json,resource,shutil,socket,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from p184_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
sys.path.insert(0,str(LOCAL))
import packet56_submission as S

def main():
 limits();source=LOCAL.parent/'packet136-record-bundle/submission/prepared-a/evidence.json.gz'
 copied=LOCAL/'lineage-inputs/submission136-evidence.json.gz'
 shutil.copy2(source,copied);assert sha(source)==sha(copied)
 evidence=S.Evidence(json.loads(gzip.decompress(copied.read_bytes()))['members'])
 with tempfile.TemporaryDirectory(prefix='p153-submission-',dir=P/'evidence') as scratch:
  repo=Path(scratch)
  for path,name in ((S.THRESHOLD_FILE,'record-threshold.json'),(S.PINS_FILE,'submission-pins.json')):
   f=repo/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(evidence.raw(name))
  out=repo/S.STAGE/'packet136-record-bundle/submission/rehearsal'
  with patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
   result=S.prepare_submission(evidence,'packet136-record-bundle',out,repo=repo)
   assert result['primary_metric']['value_tok_s']==58.798108759182306
   assert (out/'payload-queue.json').is_file()
   # New packet has no full-chain promotion identity; historical evidence cannot qualify it.
   try:S.prepare_submission(evidence,'packet184-twocard-checkpoint',out.with_name('forbidden'),repo=repo)
   except (ValueError,KeyError) as e:refusal=str(e)
   else:raise AssertionError('historical chain accepted as packet153')
  assert not (out.with_name('forbidden')).exists()
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'submission_rehearsal.py',LOCAL/'packet56_submission.py',LOCAL/'bundle_selection.py',LOCAL/'kd_projection_replay.py',LOCAL/'receipt_replay.py',copied,*list((LOCAL/'lineage-inputs/submission-vendor').glob('*.py')),*list((LOCAL/'lineage-inputs/submission-templates').glob('*'))]}
 save(P/'evidence/submission-rehearsal.json',dict(passed=True,device_executed=False,method='packet153 packet56_submission.prepare_submission',historical_packet='packet136-record-bundle',historical_rate=58.798108759182306,source_evidence_digest=sha(source),copied_evidence_digest=sha(copied),packet153_evidence_refused=refusal,original_evidence_unchanged=True,network_used=False,payload_retained=False,private_repo_uses_historical_pins=True,sources=sources))
 print('Own prepare_submission: historical136 replay PASS;153 refuses historical promotion')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
