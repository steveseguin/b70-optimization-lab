"""Exercise actual entry/parser/report with synthetic v2 census data; no device."""
import copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
import entry,screen,readiness,cpu_seal
from test_analyze import fixture
from build_engine import P,save,sha

def main():
    results=[]
    for case in ('complete','missing-view','drift','bad-repair','bad-oracle','partial-class','isolated-prototype','missing-residual','missing-probe-rank','changed-chronology','bad-setup'):
        with tempfile.TemporaryDirectory(prefix='p168-report-')as tmp:
            out=Path(tmp);doc=fixture();arm=lambda v:next(r for r in doc['observations']if r['view']==v)
            if case=='missing-view':doc['observations'].pop()
            if case=='drift':
                for row in doc['observations']:
                    if row['view']=='C0':row['interval_ms']=18
            if case=='bad-repair':arm('routed_experts')['probes'][2]['repair_exact']=False
            if case=='bad-oracle':doc['observations'][0]['tokens'][0]^=1
            if case=='partial-class':arm('router_shared_expert')['probes'][0]['class_coverage_complete']=False
            if case=='isolated-prototype':doc['measurement_scope']='isolated_B_replay'
            if case=='missing-residual':doc['report_classes'].pop()
            if case=='missing-probe-rank':arm('gdn')['probes']=arm('gdn')['probes'][:3]
            if case=='changed-chronology':doc['observations'][12:14]=reversed(doc['observations'][12:14])
            if case=='bad-setup':arm('dense_hc')['setup_exact']=False
            (out/'run').mkdir()
            (out/'run/census-input.json').write_text(json.dumps(doc))
            def finish(argv):
                args=screen.parser().parse_args(argv)
                r=screen.report_completed(args.output,dict(device_executed=False),
                  dict(lane=args.lane,bracket=dict(kind=args.kind)),dict(scope='synthetic-report-adapter'))
                return 0 if r['passed'] else 1
            with patch.object(readiness,'verify_ready'),patch.object(cpu_seal,'verify'),patch.object(screen,'main',side_effect=finish):
                rc=entry.main(['--lane','B','--kind','census','--output',str(out),'--authorized-device-window'])
            result=json.loads((out/'bracket-summary.json').read_text())
            assert (rc==0)==(case=='complete')
            assert result['passed']==(case=='complete')
            if case!='complete':assert result['ranked']==[]
            results.append(dict(case=case,expected_pass=case=='complete',actual_pass=result['passed'],
              real_entry=True,real_report=True,observations=len(doc['observations'])))
    save(P/'evidence/report-adapter.json',dict(passed=True,device_executed=False,synthetic_only=True,
      scope='entry/parser/analyzer/report route only; native sequence is qualified by native-lifecycle.json and worker-gate.json',results=results,
      source_sha256={str(f.relative_to(P)):sha(f)for f in(P/'entry.py',P/'screen.py',P/'analyze.py',Path(__file__))}))
    print('PASS private census report adapter (eleven cases)')
if __name__=='__main__':main()
