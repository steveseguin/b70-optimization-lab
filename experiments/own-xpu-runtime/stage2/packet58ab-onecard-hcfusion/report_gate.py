"""One-card report rehearsal on temporary synthetic native receipts.

The frozen ops --report checker only recognizes two-card screen.main entries.
This exercises the actual one-card summarize_bracket, oracle and metrics without
adapting its evidence schema or manufacturing a shared-tool pass.
"""
import json,resource,tempfile
from pathlib import Path
import test_bracket as T
from build_engine import P,sha,save

def main():
    T.SummaryTests.setUpClass();fixture=T.SummaryTests();rows=[]
    for candidate,tag in [('smoke','smoke'),('p60fusion','v5')]:
        with tempfile.TemporaryDirectory(prefix='p58ab-report-') as d:
            out=Path(d);fixture.fixture(out,candidate)
            summary=T.D.summarize_bracket(out,candidate,fixture.manifest)
            assert summary['passed'] and summary['request_count']==(12 if tag=='smoke' else 60)
            assert not summary['submission_eligible'] and not summary['realistic_final_gate']['passed']
            last=T.V.bracket(candidate)[-1][0];file=out/'run'/last/fixture.manifest['prompts'][-1]['prompt_id']/'result.json'
            bad=T.D.read(file);bad['tokens'][-1]+=1;T.D.save(file,bad)
            try:T.D.summarize_bracket(out,candidate,fixture.manifest)
            except ValueError as e:assert 'token identity' in str(e)
            else:raise AssertionError('final-token corruption accepted')
        proposal=P/'proposals'/('proposed-p58ab-'+tag+'-A.txt')
        rows.append(dict(proposal=str(proposal.relative_to(P)),proposal_sha256=sha(proposal),candidate=candidate,
            requests=summary['request_count'],cap=summary['requested_max_new'],passed=True,final_token_corruption_refused=True))
    save(P/'evidence/report-gate.json',dict(passed=True,device_executed=False,synthetic_only=True,real_report_function='suite_driver.summarize_bracket',records=rows,shared_ops_report_supported=False))
    print('Both one-card real report paths PASS; shared --report incompatibility remains explicit')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
