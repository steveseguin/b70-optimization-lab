"""Resolve exact pre-103x CPU policies without rewriting a frozen decision."""
from pathlib import Path
import hashlib
import json
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
# Only these reviewed orchestration edits move; native/selection pins never do.
ARCHIVED = ('read_screens.py', 'composite_jobs.py', 'composite_screen.py',
            'decision_readiness.py', 'historical_pins.py')

def preserved_pins(pins):
    result = dict(pins)
    migrated = {}
    for leaf in ARCHIVED:
        path = O / leaf
        key = str(path.relative_to(ROOT))
        if key in result and hashlib.sha256(path.read_bytes()).hexdigest() != result[key]:
            archive = O / 'frozen103' / leaf
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == result[key], key
            migrated[key] = result[key]
            result[str(archive.relative_to(ROOT))] = result.pop(key)
    if migrated:
        seal = O/'103x-policy-seal.json'
        row = json.loads(seal.read_text())
        assert row['schema'] == 'packet103x.orchestration-reseal.v1'
        assert all(row['originals'].get(key) == digest for key, digest in migrated.items())
        assert set(migrated) <= set(row['current']), 'current policy binding missing'
        assert set(row['current']) == {str(path.relative_to(ROOT)) for path in O.glob('*.py')}, 'policy seal scope differs'
        assert all(key not in result or result[key] == digest for key, digest in row['current'].items()), 'unreviewed original policy changed'
        # check_map verifies both historical evidence and the replacement policy.
        result.update(row['current'])
        result[str(seal.relative_to(ROOT))] = hashlib.sha256(seal.read_bytes()).hexdigest()
    return result
