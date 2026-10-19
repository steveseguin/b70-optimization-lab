"""CPU-only reselection and restoration; retain each selected plan receipt."""
import json, subprocess, sys, time
from build_engine import P, ROOT, B, sha, save, limits, provenance
from bundle_selection import KEYS

def main():
    limits()
    base = json.loads((P/'baseline-pins.json').read_text())['selection']
    proof_hash = sha(P/'evidence/dry-run.json')
    inherited = provenance()['variants']
    cases = [
        ('baseline', {}),
        ('route-fast', dict(route='fast')),
        ('rec-both-plus', dict(recurrence='rec-both-plus')),
        ('combined', dict(route='fast', recurrence='rec-both-plus')),
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
                                text=True, check=True)
        reseal_seconds = time.monotonic()-start
        (P/'evidence'/('rehearsal-'+label+'-reseal.log')).write_text(result.stdout+result.stderr)
        subprocess.run([sys.executable, '-B', str(P/'dry_run.py')],
                       stdin=subprocess.DEVNULL, check=True)
        report = json.loads((P/'evidence/selection-dry-run.json').read_text())
        assert report['cached_proof_sha256'] == proof_hash == sha(P/'evidence/dry-run.json')
        expected=inherited[selected['recurrence']]['binaries']
        assert all(sha(B/mode/'own-rt-iq3')==item['sha256']==sha(ROOT/item['path']) for mode,item in expected.items())
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
         cached_proof_sha256=proof_hash, binaries=inherited, runs=rows,
         baseline_restored=True))

if __name__ == '__main__': main()
