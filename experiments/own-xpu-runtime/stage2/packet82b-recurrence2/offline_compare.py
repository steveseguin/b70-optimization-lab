"""Bind offline barrier counts and retain full-shape receipts; never open a device."""
import gzip
import json
from build_engine import P, ROOT, B, sha, save, limits


def main():
    limits()
    rows = {}
    for name in ('production', 'candidate'):
        report = json.loads((P/f'register-report-{name}.json').read_text())
        assert report['passed'] and not report['device_executed']
        assert len(report['kernels']) == 1
        kernel = report['kernels'][0]
        assert not kernel['scratch_messages'], 'scratch spills introduced'
        assert sha(ROOT/kernel['assembly']) == kernel['sha256']
        text = gzip.decompress((ROOT/kernel['assembly']).read_bytes()).decode()
        instructions = [line.strip() for line in text.splitlines()
                        if line.strip() and not line.lstrip().startswith('//')]
        barriers = [line for line in instructions
                    if 'send.gtwy' in line and 'signal barrier' in line]
        rows[name] = dict(configured_grf=kernel['configured_grf'],
                          static_instructions=kernel['static_instructions'],
                          scratch_messages=0, barrier_lines=barriers,
                          static_barrier_sites=len(barriers),
                          assembly_sha256=kernel['sha256'])
    assert rows['production']['static_barrier_sites'] == 3
    assert rows['candidate']['static_barrier_sites'] == 2
    retained = []
    for view in ('production', 'rec-both', 'rec-both-plus'):
        for rank in (0, 1):
            source = B/'full-shape'/view/str(rank)
            for leaf in ('census.json', 'selected-operations.txt', 'result.json'):
                raw = (source/leaf).read_bytes()
                dest = P/'evidence'/f'full-shape-{view}-rank{rank}-{leaf}.gz'
                dest.write_bytes(gzip.compress(raw, mtime=0))
                assert gzip.decompress(dest.read_bytes()) == raw
                retained.append(dict(path=str(dest.relative_to(ROOT)), sha256=sha(dest),
                                     raw_sha256=sha(source/leaf), raw_bytes=len(raw)))
    save(P/'evidence/offline-comparison.json', dict(
        passed=True, device_executed=False, rows=rows, retained_full_shape=retained,
        scope='Static offline BMG-G31 assembly; no device occupancy or speed measurement',
        sources={str(f.relative_to(ROOT)):sha(f) for f in
                 [P/'offline_compare.py', P/'register-report-production.json',
                  P/'register-report-candidate.json',
                  *[ROOT/r['path'] for r in retained]]}))
    print('offline barrier sites 3 -> 2; no scratch spills; startup receipts retained')


if __name__ == '__main__': main()
