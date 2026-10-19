"""Run the frozen ops loader/parser/report checker on both actual proposals."""
import json,resource,subprocess,sys
from build_engine import P,ROOT,sha,save

def main():
    records=[]
    for tag in ('smoke','v5'):
        proposal=P.parents[1]/'ops/lane-queue'/('proposed-p58aj-'+tag+'-A.txt')
        cmd=[sys.executable,'-B',str(P.parents[1]/'ops/rehearse_entry.py'),str(proposal),'--report','--json']
        cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True)
        row=json.loads(cp.stdout);save(P/'evidence'/('ops-entry-report-'+tag+'.json'),row)
        assert cp.returncode==0 and row['passed'] and len(row['jobs'])==1,row
        job=row['jobs'][0]
        assert all(b['passed'] for b in job['binaries']) and len(job['binaries'])==2
        assert job['shared_environment_matches'] and not job['packet_library_override']
        assert job['report']['passed']
        records.append(dict(proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
            native_loader_and_parser_passed=True,shared_report_passed=True,returncode=cp.returncode,
            report=str((P/'evidence'/('ops-entry-report-'+tag+'.json')).relative_to(P))))
    save(P/'evidence/entry-gates.json',dict(passed=True,device_executed=False,native_loader_and_parser_passed=True,
        records=records,shared_report_passed=True,all_requested_checks_passed=True,readiness_blocker=False))
    print('Both actual proposals pass shared native loader/parser and one-card report rehearsal')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
