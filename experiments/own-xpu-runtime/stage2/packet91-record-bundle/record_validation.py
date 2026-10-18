# Retained ancestor implementation; not an entrypoint for packet91.
if __name__ == '__main__':
    raise SystemExit('Retired inherited entrypoint. Use build_engine.py, cpu_gate.py, composed_cpu.py, full_shape.py, prepare_chain.py, prepare_packet.py, then fast_reseal.py; see README.md.')
#!/usr/bin/env python3
"""Bind completed CPU gates, memory accounting and both screen wrappers."""
import gzip
import hashlib
import json
import os
from pathlib import Path
from storage import digest
P = Path(__file__).resolve().parent
ROOT = P.parents[3]

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    paths = [P/'record_validation.py', P/'flat_fixture.cpp']
    for leaf in ('controller.json','native_mailbox_fault_test.json','host_wait_test.json','flat-fixture.json','memory-admission.json','cpu-gates.json'):
        path=P/'evidence'/leaf;row=json.loads(path.read_text())
        assert row['passed'] and row['device_executed'] is False, leaf
        paths.append(path)
    memory=json.loads((P/'evidence/memory-admission.json').read_text())
    from memory_gate import configuration, arena_bytes, ARENA_LIMIT_BYTES
    ledger=json.loads((P/'memory-plan.json').read_text())
    for row in memory['placements']:
        archive=P/row['census_archive'];paths.append(archive)
        assert digest(archive)==row['census_archive_sha256']
        raw=gzip.decompress(archive.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==row['census_sha256']
        census=json.loads(raw)
        snapshot=next(r for r in census['allocations'] if 'speculative-private-image' in r['label'])
        bound=(len(census['allocations'])+snapshot['bytes']//134217728+1)*32
        assert bound==row['descriptor_bytes_bound']<65536
        config=configuration(ledger,4096,1,row['target_split'])
        for rank in config['ranks']:
            extra=65536 if rank['rank']==0 else 0
            assert extra<rank['allocation_reserve_bytes']
            assert arena_bytes(rank)+extra<ARENA_LIMIT_BYTES
    paths += [P/'evidence/final-tests.log',P/'evidence/flat-build-commands.json']
    assert '113 passed, 7 subtests passed' in (P/'evidence/final-tests.log').read_text()
    plans=[]
    for placement in ('1','1-split23'):
        for draft in ('production','draft-hc'):
            for miss in ('control','batch'):
                for lane in ('A','B'):
                    for prefix in ('plan-','plan-lanes-'):
                        path=P/'selections'/f'{placement}-{draft}-{miss}'/(prefix+lane+'.json')
                        row=json.loads(path.read_text())
                        assert row['supported'] and row['device_executed'] is False
                        assert row['identity']['lane']==lane
                        plans.append(path)
    paths+=plans
    for wrapper in ('v3-packet64','v3-packet64-lanes'):
        root=P.parent/'screen'/wrapper
        for leaf in ('wrapper-seal.json','build-receipt.json','byte-fixture.json'):
            path=root/'placement-validation'/leaf;paths.append(path)
            row=json.loads(path.read_text())
            paths += [ROOT/key for key in row.get('sources',{})]
        paths.append(root/'placement-validation/cpu-tests.log')
    # Count owned regular-file inodes once. Read-only parent symlinks are excluded.
    unique={}
    for root in (P/'build',P/'selections'):
        for path in root.rglob('*'):
            if path.is_file() and not path.is_symlink():
                stat=path.stat();unique[(stat.st_dev,stat.st_ino)]=stat.st_size
    size=sum(unique.values());assert size<400_000_000,size
    row=dict(passed=True,device_executed=False,screen_plans=32,selection_combinations=8,
        memory_placements=2,build_owned_unique_bytes=size,build_limit_bytes=400_000_000,
        chain_tests=113,subtests=7,files={str(path.relative_to(ROOT)):digest(path) for path in sorted(set(paths))},
        scope='CPU preparation only. Parent device census is memory accounting evidence, not packet64 speed or quality.')
    (P/'cpu-validation.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({key:value for key,value in row.items() if key!='files'}))

if __name__=='__main__':main()
