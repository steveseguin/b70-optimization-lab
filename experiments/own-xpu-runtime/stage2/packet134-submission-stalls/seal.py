"""Seal or verify analysis artifacts. This is not a device admission seal."""
import argparse
import json
import os
from pathlib import Path
import shutil

import analyze

P = Path(__file__).resolve().parent
SEAL = P/'evidence/analysis-seal.json'


def files():
    return {str(f.relative_to(P)): analyze.sha(f) for f in sorted(P.rglob('*'))
            if f.is_file() and f != SEAL}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 25_000_000_000
    analyze.verify_inputs()
    validation = analyze.read(P/'evidence/validation.json')
    assert validation['passed'] and validation['tests'] >= 16
    assert validation['report_sha256'] == analyze.sha(P/'evidence/attribution.json')
    for name, expected in validation['source_sha256'].items():
        assert analyze.sha(P/name) == expected
    assert analyze.generate() == analyze.read(P/'evidence/attribution.json')
    assert analyze.markdown(analyze.read(P/'evidence/attribution.json')) == (P/'ATTRIBUTION.md').read_text()
    if args.verify:
        seal = analyze.read(SEAL)
        assert seal['files'] == files(), 'analysis artifact identity changed'
    else:
        assert not SEAL.exists(), 'do not replace a sealed analysis silently'
        seal = dict(schema='packet134.analysis-seal.v1', passed=True,
                    device_admission=False, runtime_changed=False, files=files())
        analyze.save(SEAL, seal)
    print(json.dumps(dict(passed=True, sealed_files=len(seal['files']),
                         device_admission=False, seal_sha256=analyze.sha(SEAL))))


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    main()
