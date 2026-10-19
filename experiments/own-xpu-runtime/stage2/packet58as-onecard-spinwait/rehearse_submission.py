"""Offline synthetic rehearsal through the vendored CLI at its final location."""
import contextlib,io,json,resource,socket,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import packet58_submission as S
import test_submission as T
import submission_cli
P=Path(__file__).resolve().parent

def main():
 resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
 e,h=T.synthetic()
 with patch.object(S,'SEAL_SHA',h),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
  r=S.derive(e);notes=S.submission_notes(r)
  for text in ('128-token','no strict512','anonymous exact resident','31.901/34.577/31.838/34.568/31.807','60/60 exact','+8.58%','0.096%','Bounded spin','~33% vs ~25%','no setting or governor change','arithmetic unchanged','1.108 ms/token','cmveqsmsl00ebrf014yvrsosx'):assert text in notes,text
  assert not r['realistic_final_gate']['passed'] and not r['fresh_timing_repeat_passed']
  cli=submission_cli.load_submitter();assert cli.REPO_ROOT==S.ROOT
  (P/'submission').mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='.cpu-cli-',dir=P/'submission') as tmp:
   out=Path(tmp)/'prepared';S.write_prepared(e,out)
   capture=io.StringIO()
   with patch.object(sys,'argv',[str(P/'submission_cli.py'),'--payloads',str(out/'payload-queue.json'),'--dry-run']),contextlib.redirect_stdout(capture):assert cli.main()==0
   assert json.loads(capture.getvalue())==json.loads((out/'payload-queue.json').read_text())
  # The real threshold, not a weakened fixture threshold, must refuse equality.
  e,h=T.synthetic();actual=S.derive(e)['primary_metric']['value_tok_s']
  ledger=e.read('record-threshold.json');ledger['records'][-1]['threshold_tok_s']=actual
  T.put(e,'record-threshold.json',ledger)
  try:S.derive(e)
  except ValueError as error:assert 'not above matching one-card threshold' in str(error)
  else:raise AssertionError('equal threshold accepted')
 report=dict(passed=True,device_executed=False,synthetic_fixture_only=True,new_chain_measurement=False,network_used=False,final_location_cli_passed=True,cli_repo_root=str(cli.REPO_ROOT),threshold_equality_refused=True,pinned_predecessor=S.POLICY['supersedes'],notes_characters=len(notes),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 assert report['peak_rss_bytes']<2_000_000_000
 (P/'evidence/submission-rehearsal.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
