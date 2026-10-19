"""One-card report rehearsal on temporary synthetic native receipts.

This exercises the actual one-card summarize_bracket, oracle and metrics,
including final-token corruption refusal. entry_gate.py independently runs
the shared ops --report checker on both exact proposals.
"""
import json,resource,tempfile
from pathlib import Path
import test_bracket as T
from build_engine import P,sha,save

def main():
    T.SummaryTests.setUpClass();fixture=T.SummaryTests();rows=[]
    for candidate,tag in [('smoke','smoke'),('resident','v5')]:
        with tempfile.TemporaryDirectory(prefix='p58ag-report-') as d:
            out=Path(d);fixture.fixture(out,candidate)
            summary=T.D.summarize_bracket(out,candidate,fixture.manifest)
            assert summary['passed'] and summary['request_count']==(12 if tag=='smoke' else 60)
            assert not summary['submission_eligible'] and not summary['realistic_final_gate']['passed']
            last=T.V.bracket(candidate)[-1][0];file=out/'run'/last/fixture.manifest['prompts'][-1]['prompt_id']/'result.json'
            bad=T.D.read(file);bad['tokens'][-1]+=1;T.D.save(file,bad)
            try:T.D.summarize_bracket(out,candidate,fixture.manifest)
            except ValueError as e:assert 'token identity' in str(e)
            else:raise AssertionError('final-token corruption accepted')
        proposal=P/'proposals'/('proposed-p58aj-'+tag+'-A.txt')
        rows.append(dict(proposal=str(proposal.relative_to(P)),proposal_sha256=sha(proposal),candidate=candidate,
            requests=summary['request_count'],cap=summary['requested_max_new'],passed=True,final_token_corruption_refused=True))
    save(P/'evidence/report-gate.json',dict(passed=True,device_executed=False,synthetic_only=True,real_report_function='suite_driver.summarize_bracket',records=rows,shared_ops_report_supported=True))
    print('Both one-card real report paths PASS; shared --report is verified separately by entry_gate.py')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
