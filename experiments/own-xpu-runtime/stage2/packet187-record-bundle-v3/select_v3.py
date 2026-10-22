#!/usr/bin/env python3
"""Activate the V3 composition: packet186's V3 selection and dual memory plan, byte for byte.

Writes selection.json, memory-plan.json, bundle-selection.json, selections/<view>/ and the private
native screen seal (V3 engines + V3 native snapshot + active selection/plan/dispatch), then checks
bundle_selection.selected() and that selection.json equals packet186's v3 lineage selection.
"""
import hashlib, json, shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
O = ROOT / 'experiments/own-xpu-runtime/ops/packet187-orchestration'
V3 = P.parent / 'packet186-twocard-v3/v5/lineage/v3'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import sys
    sys.path.insert(0, str(P))
    import bundle_selection as b
    for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json'):
        shutil.copyfile(V3 / leaf, P / leaf)
        assert sha(P / leaf) == sha(V3 / leaf)
    values = (b.DENSE[0], b.HC[0], b.EXPERTS[0], b.HOST[0], b.ROUTE[0], b.NORM[0], b.RECURRENCE[0], b.DRAFT_HEAD[0], b.HEAD[0], b.HC_NORM[0],
              b.DOWN[0], b.DRAFT_ATTENTION[0], b.OTHER_FUSION[0], b.TARGET_HEAD[0], b.DRAFT_PREFIX[0], b.ROLLBACK_STATE[0])
    selection = json.loads((P / 'selection.json').read_text())
    assert selection['choices'] == b.choices(*values), 'packet186 V3 selection is not the registered composition'
    assert selection['draft'] == b.draft(values), 'draft selection differs from the bundle-8 draft'
    name = b.name(*values)
    view = P / 'selections' / (name + '--placement-1')
    for old in (P / 'selections').glob('*'):
        if old != view:
            shutil.rmtree(old)
    view.mkdir(parents=True, exist_ok=True)
    for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json'):
        shutil.copyfile(P / leaf, view / leaf)
    native = json.loads((O / 'inputs/packet186-native.json').read_text())
    seal = dict(schema='packet187.private-native-seal.v1', passed=True, device_executed=False,
                artifacts={k: v['sha256'] for k, v in native['binaries'].items()},
                sources={**{str((P / k).relative_to(ROOT)): v for k, v in native['sources'].items()},
                         **{str((P / leaf).relative_to(ROOT)): sha(P / leaf) for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json')}})
    text = json.dumps(seal, indent=2) + '\n'
    (view / 'screen-seal.json').write_text(text)
    (P / 'screen-seal.json').write_text(text)
    row = dict(zip(b.KEYS, values))
    row.update(name=name, placement='1', draft='draft-hc', miss='banks-batch', draft_rank=1, target_split=0, layer_boundary=24,
               selection_sha256=sha(P / 'selection.json'), screen_seal_sha256=sha(view / 'screen-seal.json'), snapshot_host='static',
               v3=dict(rank0_layers='0-25', boundary='rank0', rank1_first_layer=26, target_layers=[26, 24],
                       origin='packet186 V3 arm (v5/lineage/v3), measured on lane B 2026-10-22'))
    (P / 'bundle-selection.json').write_text(json.dumps(row, indent=2) + '\n')
    chosen = b.selected()
    assert chosen['selection_sha256'] == sha(V3 / 'selection.json')
    print('active V3 composition', name, chosen['selection_sha256'][:16])


if __name__ == '__main__':
    main()
