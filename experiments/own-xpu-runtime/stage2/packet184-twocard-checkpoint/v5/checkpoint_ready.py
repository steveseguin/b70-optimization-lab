"""Final marker check: READY-FOR-DEVICE.json is written only after every CPU gate and both plans."""
import json
from p184_build_checkpoint import P, ROOT, sha
from cpu_seal import verify, check_sources

GATES = ('check-queue-rows', 'queue-plan', 'pin-guard', 'final-checks')   # all written before READY


def verify_ready(preplan=False, kind=None, lane=None):
    row = verify()
    if preplan:
        return row
    assert lane in ('A', 'B') and kind in ('smoke', 'lifecycle'), 'registered packet184 rows only'
    marker = json.loads((P.parent / 'READY-FOR-DEVICE.json').read_text())
    assert marker['passed'] and marker['ready_for_device'] and marker['queued'] is False
    for path, digest in marker['proposal_sha256s'].items():
        assert sha(ROOT / path) == digest, 'proposal changed'
    assert marker['cpu_seal_sha256'] == sha(P / 'cpu-seal.json'), 'final composition changed'
    for name in GATES:
        path = P / 'evidence' / (name + '.json')
        proof = json.loads(path.read_text())
        assert proof['passed'] and proof['device_executed'] is False, name
        assert marker['cpu_gate_sha256'][name] == sha(path), 'final gate changed: ' + name
        if proof.get('sources'):
            check_sources(proof['sources'])
    return row
