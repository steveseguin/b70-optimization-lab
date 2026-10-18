"""CPU-only placement admission; memory fit is distinct from engine support."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from common import HERE, P56, ROOT, module, read, require, sha

PLACEMENTS = {'1-split23': (1, 23, 23), '0-split23': (0, 23, 23),
              '0': (0, 0, 22), '1': (1, 0, 24)}


def admission_gate(root):
    path = root / 'memory_gate.py'
    if not path.is_file():
        # Lean screen directories inherit the fixed packet56 controller ABI.
        path = P56 / 'memory_gate.py'
    require(sha(path) == sha(P56 / 'memory_gate.py'),
            'lineage memory gate differs from wrapper-sealed controller ABI')
    return path, module('screen_placement_memory', path)


def admit(root, seal, receipt, dispatch, name):
    require(name in PLACEMENTS, 'unknown placement')
    rank, split, boundary = PLACEMENTS[name]
    path, gate = admission_gate(root)
    ledger = read(root / 'memory-plan.json')
    entry = ledger['placements'][name]
    require(entry['draft_rank'] == rank and entry['layer_boundary'] == boundary,
            'placement name differs from memory-plan topology')
    configuration = gate.configuration(ledger, 4096, rank, split)
    require([r['rank'] for r in configuration['ranks']] == [0, 1] and
            [r['target_layers'] for r in configuration['ranks']] == [boundary, 48-boundary],
            'memory-plan rank/layer ownership differs')
    policy = read(HERE / 'placements.json')
    registered = str(root.relative_to(ROOT)) == policy['lineage']
    supported, reason = name == '1-split23', 'control placement inherited from screen v3'
    if registered:
        require(sha(receipt) == policy['seal_sha256'], 'placement audit belongs to another lineage seal')
        require(sha(dispatch) == policy['dispatch_sha256'], 'placement dispatch differs from audited K2 policy')
        for relative, digest in policy['evidence'].items():
            require(sha(ROOT / relative) == digest, 'placement audit evidence changed: ' + relative)
        for leaf in ('main.cpp', 'rank.hpp', 'mtp.hpp', 'p56_config.hpp', 'p56_prefix.hpp'):
            relative = str((root / leaf).relative_to(ROOT))
            require(seal['sources'].get(relative) == policy['evidence'][relative],
                    'placement engine evidence is not bound to candidate seal')
        supported, reason = policy['placements'][name]['supported'], policy['placements'][name]['reason']
    elif root.parent.name == 'selections' and root.parent.parent.name in ('packet64-record-bundle', 'candidates'):
        audit_path = root / 'placement-audit.json'
        require(seal['sources'].get(str(audit_path.relative_to(ROOT))) == sha(audit_path), 'unsealed placement audit')
        audit = read(audit_path)
        require(audit['placement'] == name and audit['draft_rank'] == rank and audit['target_split'] == split,
                'placement differs from sealed selection')
        require(audit['dispatch_sha256'] == sha(dispatch), 'placement dispatch changed')
        require(audit['binary_sha256'] == seal['artifacts']['build/device/own-rt-iq3'], 'placement binary changed')
        for relative, digest in audit['engine_sources'].items():
            require(seal['sources'].get(relative) == digest and sha(ROOT / relative) == digest, 'placement source changed')
        require(name in ('1', '1-split23'), 'packet64 rank1-only prefix')
        supported, reason = True, 'Packet64 sealed rank1 resident head; class dispatch independent of layer boundary'
    elif name != '1-split23':
        reason = 'non-control placement has no engine/dispatch/prefix audit for this lineage seal'
    result = dict(name=name, draft_rank=rank, target_split=split, layer_boundary=boundary,
                  target_layers=[boundary, 48-boundary], context=4096,
                  memory_admitted=True, supported=supported, reason=reason,
                  memory_gate=str(path), memory_gate_sha256=sha(path),
                  memory_plan_sha256=sha(root / 'memory-plan.json'),
                  configuration=configuration, dispatch_policy='same sealed class dispatch on both ranks',
                  rank_dispatch_sha256=[sha(dispatch)]*2, policy_sha256=sha(HERE / 'placements.json'))
    result['plan_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def verify_identity(identity):
    """Recompute all bindings before the worker creates adapters or any child."""
    from common import sealed
    args = SimpleNamespace(lineage=Path(identity['lineage']), seal=Path(identity['seal']),
        binary=Path(identity['binary']), dispatch=Path(identity['dispatch']),
        profile=identity['profile'], timing=identity['timing'], placement=identity['placement']['name'])
    expected = sealed(args)
    require(all(identity.get(key) == value for key, value in expected.items()),
            'sealed screen identity/placement changed')
    placement = expected['placement']
    require(placement['supported'], placement['reason'])
    return placement, admission_gate(args.lineage)[1]
