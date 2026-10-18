"""Read-only source/import/parent checks, then write this packet's CPU receipt."""
import ast,hashlib,json,resource,shutil
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def main():
    limits()
    from exec_limits import snapshot
    before=snapshot()
    import readiness,entry,screen,queue_runner,suite_driver
    assert snapshot()==before
    files=list(P.glob('*.py'))
    for f in files:ast.parse(f.read_text(),str(f))
    import analyze
    assert json.loads((P/'readiness-policy.json').read_text())==analyze.RULES
    manifest=json.loads((P/'lineage/vendor58ae-manifest.json').read_text())
    parent=ROOT/manifest['parent']
    for name,digest in manifest['files_sha256'].items():assert sha(parent/name)==digest,name
    gates=['build-measure','partition-cpu','reset-gate','fullshape-submit-cpu','postload-allocation-cpu','native-parser','argument-gate','entry-report','cpu-tests']
    for name in gates:assert json.loads((P/'evidence'/(name+'.json')).read_text())['passed'],name
    save(P/'evidence/final-cpu-checks.json',dict(passed=True,device_executed=False,
        python_sources_parsed=len(files),parent_files_unchanged=len(manifest['files_sha256']),
        resource_limits_unchanged_on_import=True,root_free_bytes=shutil.disk_usage('/').free,
        build_bytes=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())))

if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
