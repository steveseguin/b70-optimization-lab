"""One-time CPU reseal of the direction driver; native artifacts cannot change."""
from build_engine import P,ROOT,sha,save,limits
from bundle_selection import VIEWS
from screen_jobs import verify
from common import read,require,verify_map

CHANGED = ('screen_jobs.py','run_screens.py','compare.py','test_screen.py',
           'final_check.py','queue_plan.py','evidence/python-tests.json')
EXTRA = ('reseal_direction.py','PREREGISTRATION.md','README.md','WINDOW.md')

def main():
    limits()
    report=P/'evidence/direction-reseal.json'
    require(not report.exists(),'direction reseal already recorded')
    allowed={str((P/n).relative_to(ROOT)) for n in CHANGED}
    extra={str((P/n).relative_to(ROOT)):sha(P/n) for n in EXTRA}
    updates=[]
    def refresh(mapping):
        result=dict(mapping)
        for name,old in mapping.items():
            new=sha(ROOT/name)
            if new!=old:
                require(name in allowed,'unexpected changed dependency: '+name)
                updates.append(dict(path=name,before=old,after=new))
                result[name]=new
        result.update(extra)
        return result
    # Validate every unchanged dependency and artifact before writing any seal.
    pending=[]
    for name in VIEWS:
        view=P/'compat/packet64-record-bundle/selections'/name
        build=read(view/'build-receipt.json');fixture=read(view/'byte-fixture.json')
        seal=read(view/'screen-seal.json')
        verify_map(view,build['artifacts'])
        for key in ('artifacts','gates','fixture_files'):verify_map(view,seal[key])
        require(fixture['build_receipt_sha256']==sha(view/'build-receipt.json'),'fixture build changed')
        verify_map(ROOT,fixture['sources'])
        build['sources']=refresh(build['sources']);seal['sources']=refresh(seal['sources'])
        pending.append((view,build,fixture,seal))
    job=read(P/'screen-jobs-seal.json')
    job['sources']=refresh(job['sources'])
    for view,build,fixture,seal in pending:
        save(view/'build-receipt.json',build)
        fixture['build_receipt_sha256']=sha(view/'build-receipt.json')
        save(view/'byte-fixture.json',fixture)
        seal['gates']={name:sha(view/name) for name in seal['gates']}
        save(view/'screen-seal.json',seal)
        for leaf in ('build-receipt.json','byte-fixture.json','screen-seal.json'):
            key=str((view/leaf).relative_to(ROOT))
            job['sources'][key]=sha(view/leaf)
    save(P/'screen-jobs-seal.json',job)
    verify()
    save(report,dict(passed=True,device_executed=False,binaries_rebuilt=False,
                    allowed_changes=list(CHANGED),added_bindings=list(EXTRA),updates=updates,
                    native_artifacts=read(P/'build-device-receipt.json')['artifacts']))
    print('direction driver resealed; native artifacts verified unchanged')

if __name__=='__main__':main()
