"""Read-only identity verification and CPU plan; save only packet77 evidence."""
import json
import subprocess
import sys
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits


def main():
    limits()
    from run_screen import VIEW, WRAPPER, verify_dependencies
    from common import verify_map, read
    from placement import verify_identity
    verify_dependencies()
    build=read(P/'build-device-receipt.json')
    verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
    plan=read(P/'evidence/screen-plan.json')
    placement,gate=verify_identity(plan['identity'])
    assert plan['reservation_scope']=='lane-B' and plan['supported']
    assert placement['name']=='1' and placement['target_layers']==[24,24]
    assert plan['watchdog_seconds']>=4*420
    assert plan['command'][2]==str(P/'worker.py')
    selection=read(VIEW/'selection.json')
    assert selection==read(P.parent/'packet70-record-bundle/selection.json')
    assert selection['choices']['experts']=='wide64'
    assert selection['choices']['miss']=='batch'
    for side in ('a','f','final'):
        assert selection['draft']['fuse_hc_'+side+'_low']=='packet59'
        assert selection['draft']['fuse_hc_'+side+'_mix']=='packet59'
    for name in ('cpu-gates','reset-gate','fullshape','fullshape-admission','report-fixture','queue-plan'):
        assert read(P/'evidence'/f'{name}.json')['passed']
    # Inventory the final numerical delta separately from instrumentation.
    changed=[]
    for name,digest in read(P/'parent-source-manifest.json').items():
        if sha(P/Path(name).name)!=digest:changed.append(Path(name).name)
    assert sorted(changed)==['main.cpp','mtp.hpp','rank.hpp'],changed
    command=[sys.executable,'-B',str(P/'run_screen.py'),'--plan']
    cp=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True,timeout=120,
        env={'PATH':'/usr/bin:/bin','OMP_NUM_THREADS':'2'})
    fresh=json.loads(cp.stdout)
    assert fresh==plan, 'closed-environment plan differs'
    files=[P/'instrumentation.patch',P/'report_fixture_gate.py',P/'final_check.py',
           P.parents[1]/'ops/lane-queue/proposed-p77-B.txt',VIEW/'screen-seal.json']
    files += [f for f in (P/'evidence').iterdir() if f.is_file() and f.name!='final-check.json']
    logical=sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
    assert logical<500_000_000
    save(P/'evidence/final-check.json',dict(passed=True,device_executed=False,
        production_model_executed=False,selection_matches_packet70=True,experts='wide64',
        placement=placement['name'],target_layers=placement['target_layers'],lane='B',
        reservation_scope='lane-B',closed_environment_plan=True,
        expected_work_seconds=420,watchdog_seconds=plan['watchdog_seconds'],
        parent_files_changed=changed,numerical_objects='inherited byte-pinned packet65 objects',
        wrapper=str(WRAPPER.relative_to(ROOT)),wrapper_seal_sha256=sha(WRAPPER/'wrapper-seal.json'),
        screen_seal_sha256=sha(VIEW/'screen-seal.json'),build_logical_bytes=logical,
        evidence={str(f.relative_to(ROOT)):sha(f) for f in files},
        current_device_measurements='pending',live_queue_modified=False))
    print('final closed-env plan, selection consumers, source/byte closure and all CPU evidence PASS')


if __name__=='__main__':main()
