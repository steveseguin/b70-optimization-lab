"""Resolve only byte-exact archived CPU policies; runtime pins never move."""
from pathlib import Path
import hashlib

O = Path(__file__).resolve().parent
ROOT = O.parents[3]


def preserved_pins(pins):
    result = dict(pins)
    for leaf, directory in (('composite_jobs.py', 'frozen98b'),
                            ('orchestrate.py', 'frozen97b'),
                            ('verify_ready.py', 'frozen97b')):
        path = O / leaf
        key = str(path.relative_to(ROOT))
        if key in result and hashlib.sha256(path.read_bytes()).hexdigest() != result[key]:
            archive = O / directory / leaf
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == result[key], \
                'unrecognized historical policy: ' + key
            result[str(archive.relative_to(ROOT))] = result.pop(key)
    return result
