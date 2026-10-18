"""CPU-only reselection and restoration; retain each selected plan receipt."""
import json, subprocess, sys, time
from build_engine import P, B, sha, save, limits
from bundle_selection import KEYS

def main():
    limits()
    base = json.loads((P/'baseline-pins.json').read_text())['selection']
    proof_hash = sha(P/'evidence/dry-run.json')
    binaries = {mode: sha(B/mode/'own-rt-iq3') for mode in ('device', 'gnu-host')}
    cases = [
        ('baseline', {}),
        ('q4', dict(experts='gate-input-packed', recurrence='rec-gates', draft_head='q4-g32')),
        ('prefix990', dict(experts='down-input-packed', recurrence='rec-parallel', draft_head='prefix990')),
        ('prefix985', dict(experts='input-packed', recurrence='rec-gates', draft_head='prefix985')),
        ('rank1-split23', dict(placement='1-split23')),
        ('rank0', dict(placement='0')),
        ('rank0-split23', dict(placement='0-split23')),
        ('restored', {}),
    ]
    rows = []
    for label, delta in cases:
        selected = dict(base, **delta)
        start = time.monotonic()
        args = [sys.executable, '-B', str(P/'fast_reseal.py')]
        for key in (*KEYS, 'placement'):
            args += ['--'+key, selected[key]]
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, check=True, timeout=120)
        reseal_seconds = time.monotonic()-start
        (P/'evidence'/('rehearsal-'+label+'-reseal.log')).write_text(result.stdout+result.stderr)
        subprocess.run([sys.executable, '-B', str(P/'dry_run.py')],
                       stdin=subprocess.DEVNULL, check=True, timeout=300)
        report = json.loads((P/'evidence/selection-dry-run.json').read_text())
        assert report['cached_proof_sha256'] == proof_hash == sha(P/'evidence/dry-run.json')
        assert all(sha(B/mode/'own-rt-iq3') == value for mode, value in binaries.items())
        logs = {}
        for check in report['checks']:
            source = P/'evidence'/('selected-'+check['name']+'.log')
            assert sha(source) == check['sha256']
            target = P/'evidence'/('rehearsal-'+label+'-'+check['name']+'.log')
            target.write_bytes(source.read_bytes()); logs[target.name] = sha(target)
        save(P/'evidence'/('rehearsal-'+label+'.json'), report)
        rows.append(dict(label=label, selection=selected, reseal_seconds=reseal_seconds,
                         rehearsal_seconds=report['seconds'], logs=logs,
                         receipt_sha256=sha(P/'evidence'/('rehearsal-'+label+'.json'))))
        print(label, 'reseal and all window plans PASS', flush=True)
    save(P/'evidence/reselection.json', dict(passed=True, device_executed=False,
         cached_proof_sha256=proof_hash, binaries=binaries, runs=rows,
         baseline_restored=True))

if __name__ == '__main__': main()
