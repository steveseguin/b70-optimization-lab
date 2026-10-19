"""Inventory inherited packet literals and refuse them in live chain entry code."""
import hashlib,json,os,re,resource
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
PATTERN=re.compile(r'58[pmnrt]')
LIVE=('queue_runner.py','window.py','suite_driver.py','views.py','memory_plan.py','legacy_memory_plan.py','onecard_admission.py','chain_devices.py','lane_admission.py','drain_gate.py','exec_limits.py','fault_review.py','owner_teardown.py','teardown_on_error.py','verify_ready.py','packet58_submission.py','submission_cli.py','runtime-selection.json','views.json','selection.json')
def sha(f):
    with f.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def main():
    rows=[]
    for f in sorted(P.rglob('*')):
        rel=f.relative_to(P)
        if not f.is_file() or f.is_symlink() or rel.parts[0] in ('build','evidence') or f.name in ('build-receipt.json','submission-pins.json','ready.json'):continue
        try:lines=f.read_text().splitlines()
        except UnicodeError:continue
        for i,line in enumerate(lines,1):
            if PATTERN.search(line):
                assert str(rel) not in LIVE,'stale live-chain literal: '+str(rel)+':'+str(i)
                kind=('frozen lineage provenance' if rel.parts[0] in ('lineage','host-admission') or f.name in ('copy-manifest.json','library-path.json','record-threshold.json','submission-policy.json') else 'CPU negative control / parser switch / historical receipt / documentation')
                rows.append(dict(path=str(rel),line=i,text=line,classification=kind))
    manifest=json.loads((P/'copy-manifest.json').read_text())
    for rel,target in manifest['template_symlinks'].items():assert (P/rel).is_symlink() and os.readlink(P/rel)==target
    row=dict(passed=True,device_executed=False,pattern=PATTERN.pattern,live_files_checked=list(LIVE),remaining_literals=rows,template_symlinks=manifest['template_symlinks'],symlinks_preserved=True,
             sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in (*LIVE,'literal_audit.py')})
    (P/'evidence/literal-audit.json').write_text(json.dumps(row,indent=2)+'\n')
    print(len(LIVE),'live chain files clear;',len(rows),'historical/CPU/documentation literals classified')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
