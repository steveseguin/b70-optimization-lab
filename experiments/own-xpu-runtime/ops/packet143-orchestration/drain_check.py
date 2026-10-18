"""Fail closed on both complete local drain scans; no boolean-only admission."""
import importlib.util
from pathlib import Path
from source_decision import O,P,ROOT,sha,save

def check():
    path=ROOT/'scripts/check_drain_fix.py'
    spec=importlib.util.spec_from_file_location('packet124_drain_scanner',path)
    scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)
    reports=[scanner.scan(folder) for folder in (P,O)]
    assert all(r['passed'] and r['counts']['UNFIXED']==0 for r in reports),'drain-fix hard gate failed'
    assert sha(P/'drain_gate.py')==sha(O/'drain_gate.py'),'orchestration/chain drain copies differ'
    for report in reports:
        for item in report['files']:
            path=ROOT/Path(item['path'])
            if path.is_relative_to(O):item['path']=str(P/'lineage-inputs/orchestration'/path.name)
    return dict(passed=True,device_executed=False,scanner_sha256=sha(path),reports=reports)
if __name__=='__main__':
    import json
    report=check();save(O/'evidence/drain-fix.json',report);print(json.dumps(report,indent=2))
