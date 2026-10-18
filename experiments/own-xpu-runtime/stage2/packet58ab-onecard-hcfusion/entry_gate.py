"""Run the frozen ops loader/parser/report checker on both actual proposals."""
import json,resource,subprocess,sys
from build_engine import P,ROOT,sha,save

def main():
    records=[]
    for tag in ('smoke','v5'):
        proposal=P.parents[1]/'ops/lane-queue'/('proposed-p58ab-'+tag+'-A.txt')
        cmd=[sys.executable,'-B',str(P.parents[1]/'ops/rehearse_entry.py'),str(proposal),'--report','--json']
        cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
        row=json.loads(cp.stdout);save(P/'evidence'/('ops-entry-report-'+tag+'.json'),row)
        assert cp.returncode==1 and len(row['jobs'])==1
        job=row['jobs'][0];assert all(b['passed'] for b in job['binaries']) and len(job['binaries'])==2
        assert job['shared_environment_matches'] and not job['packet_library_override']
        assert not job['report']['passed'] and all(r['error_type']=='ValueError' for r in job['report']['kinds'])
        # Prove the actual unsupported structural condition, not a guessed reason.
        import ast
        tree=ast.parse((P/'queue_runner.py').read_text())
        assert not any(isinstance(n,ast.Call) and ast.unparse(n.func)=='screen.main' for n in ast.walk(tree))
        records.append(dict(proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
            native_loader_and_parser_passed=True,shared_report_passed=False,returncode=cp.returncode,
            reason='Frozen ops report_probe requires screen.main (two-card v5 layout); this is the one-card queue/window/suite driver.',
            report=str((P/'evidence'/('ops-entry-report-'+tag+'.json')).relative_to(P))))
    save(P/'evidence/entry-gates.json',dict(passed=True,device_executed=False,native_loader_and_parser_passed=True,
        records=records,shared_report_passed=False,all_requested_checks_passed=False,
        report_alternative='evidence/report-gate.json',readiness_blocker=True))
    print('Both native entry/loader checks PASS; required shared --report remains unsupported, recorded as a blocker')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
