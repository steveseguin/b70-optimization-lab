"""Final-location offline CLI rehearsal on explicit synthetic evidence only."""
import contextlib,copy,io,json,resource,socket,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import packet58_submission as S
import test_submission as T
import submission_cli
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def main():
    fixture,seal=T.synthetic()
    with patch.object(S,'SEAL_SHA',seal),patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
        result=S.derive(fixture);notes=S.submission_notes(result)
        assert result['primary_metric']['value_tok_s']>31.966820
        assert not result['realistic_final_gate']['passed'] and not result['fresh_timing_repeat_passed']
        for term in ('128-token','no strict512','Census','RELEASE-AMENDMENT.md','v5 A0/B0/A1/B1/A2','60/60 exact','cmveqsmsl00ebrf014yvrsosx'):
            assert term in notes,term
        assert len(notes)<=2000
        bad=copy.deepcopy(fixture);T.changed(bad,'queue.json',lambda q:q.pop('readiness'))
        try:S.derive(bad)
        except ValueError:pass
        else:raise AssertionError('missing v5 bracket accepted')
        cli=submission_cli.load_submitter();assert cli.REPO_ROOT==ROOT
        (P/'submission').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.cpu-cli-',dir=P/'submission') as tmp:
            out=Path(tmp)/'prepared';S.write_prepared(fixture,out)
            capture=io.StringIO()
            with patch.object(sys,'argv',[str(P/'submission_cli.py'),'--payloads',str(out/'payload-queue.json'),'--dry-run']),contextlib.redirect_stdout(capture):assert cli.main()==0
            assert json.loads(capture.getvalue())==json.loads((out/'payload-queue.json').read_text())
    report=dict(passed=True,device_executed=False,final_location_cli_passed=True,cli_repo_root=str(cli.REPO_ROOT),synthetic_only=True,new_chain_measurement=False,network_used=False,payload_written=False,temporary_synthetic_payload_removed=True,notes_characters=len(notes),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    assert report['peak_rss_bytes']<2_000_000_000
    (P/'evidence/submission-rehearsal.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
