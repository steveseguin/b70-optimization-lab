"""Read-only binding to packet49's existing oracle; never starts an oracle job."""
import argparse
import json
from pathlib import Path
from storage import digest

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
AUTHORITY = P.parent / 'packet49-integrate/oracle'
RESULTS = Path('/home/steve/own-xpu-runtime-results/packet49-integrate/oracle/results')

def static_binding():
    row = json.loads((P / 'oracle-binding.json').read_text())
    if not (P / 'oracle').is_symlink() or (P / 'oracle').resolve() != AUTHORITY.resolve():
        raise ValueError('packet49b must use the unchanged packet49 oracle authority')
    if (AUTHORITY / 'results').resolve() != RESULTS:
        raise ValueError('shared oracle output path changed')
    if row['arithmetic'] != 'iq3-p49-split32-v1' or row['unit'] != 'own-iq3-p49-oracle-20261017b.service':
        raise ValueError('shared oracle identity changed')
    for name, expected in row['files_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('shared oracle static input changed: ' + name)
    from oracle.oracle_job import source_bindings
    build = source_bindings()
    if build['binary_sha256'] != row['binary_sha256']:
        raise ValueError('shared oracle binary changed')
    return row

def completed_binding():
    static = static_binding()
    from oracle.oracle_job import status
    if status(True) != 0:
        raise ValueError('packet49 complete full-model oracle required before this window')
    completion = json.loads((RESULTS / 'completion.json').read_text())
    return dict(arithmetic=static['arithmetic'], unit=static['unit'],
                static_binding_sha256=digest(P / 'oracle-binding.json'),
                completion_path=str(RESULTS / 'completion.json'),
                completion_sha256=digest(RESULTS / 'completion.json'),
                manifest_sha256=completion['manifest_sha256'],
                determinism_sha256=completion['determinism_sha256'],
                kd_capture_sha256=completion['kd_capture_sha256'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    static_binding()
    if args.require_complete:
        from oracle.oracle_job import status
        return status(True)
    print(json.dumps(dict(passed=True, device_executed=False, binding=static_binding())))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
