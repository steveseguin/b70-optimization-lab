#!/usr/bin/env python3
"""Activate the k3x composition: packet189's k3x selection and k3 dual memory plan, byte for byte.

Writes selection.json, memory-plan.json, dispatch-speed6.json, bundle-selection.json, selections/<view>/ and
the private native screen seal (k3x engines + k3x native snapshot + active selection/plan/dispatch), then
checks bundle_selection.selected() and that selection.json equals packet189's k3x lineage selection
(sha256 c5443bbf...; 19 keys) and memory-plan.json packet189's k3x ledger (sha256 97a76116...).
"""
import hashlib, json, shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
O = ROOT / 'experiments/own-xpu-runtime/ops/packet190-orchestration'
K3X = P.parent / 'packet189-twocard-k3x/v5/lineage/k3x'
SELECTION = 'c5443bbfbc88b39fd562956a55ce05667de0781f640fd0cd522a1e5800f392bb'
PLAN = '97a7611646cdab0d9780166a3a670375a986dcb150cae491c686203eb0fb7d39'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import sys
    sys.path.insert(0, str(P))
    import bundle_selection as b
    assert sha(K3X / 'selection.json') == SELECTION and sha(K3X / 'memory-plan.json') == PLAN, 'packet189 k3x lineage bytes differ from the README'
    for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json'):
        shutil.copyfile(K3X / leaf, P / leaf)
        assert sha(P / leaf) == sha(K3X / leaf)
    values = (b.DENSE[0], b.HC[0], b.EXPERTS[0], b.HOST[0], b.ROUTE[0], b.NORM[0], b.RECURRENCE[0], b.DRAFT_HEAD[0], b.HEAD[0], b.HC_NORM[0],
              b.DOWN[0], b.DRAFT_ATTENTION[0], b.OTHER_FUSION[0], b.TARGET_HEAD[0], b.DRAFT_PREFIX[0], b.ROLLBACK_STATE[0])
    selection = json.loads((P / 'selection.json').read_text())
    assert selection['choices'] == b.choices(*values), 'packet189 k3x selection is not the registered composition'
    assert len(selection['choices']) == 19 and selection['choices']['boundary_export'] == 'copy'
    assert selection['draft'] == b.draft(values), 'draft selection differs from the bundle-8 draft'
    plan = json.loads((P / 'memory-plan.json').read_text())
    rank0 = plan['placements']['1']['capacities']['4096']['ranks'][0]
    assert rank0['target_layers'] == 27 and rank0['target_modeled_allocations_bytes'] == 32003283826
    name = b.name(*values)
    view = P / 'selections' / (name + '--placement-1')
    for old in (P / 'selections').glob('*'):
        if old != view:
            shutil.rmtree(old)
    view.mkdir(parents=True, exist_ok=True)
    for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json'):
        shutil.copyfile(P / leaf, view / leaf)
    native = json.loads((O / 'inputs/packet189-native.json').read_text())
    seal = dict(schema='packet190.private-native-seal.v1', passed=True, device_executed=False,
                artifacts={k: v['sha256'] for k, v in native['binaries'].items()},
                sources={**{str((P / k).relative_to(ROOT)): v for k, v in native['sources'].items()},
                         **{str((P / leaf).relative_to(ROOT)): sha(P / leaf) for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json')}})
    text = json.dumps(seal, indent=2) + '\n'
    (view / 'screen-seal.json').write_text(text)
    (P / 'screen-seal.json').write_text(text)
    row = dict(zip(b.KEYS, values))
    row.update(name=name, placement='1', draft='draft-hc', miss='banks-batch', draft_rank=1, target_split=0, layer_boundary=24,
               selection_sha256=sha(P / 'selection.json'), screen_seal_sha256=sha(view / 'screen-seal.json'), snapshot_host='static',
               v3=dict(rank0_layers='0-26', boundary='rank0-k3', rank1_first_layer=27, target_layers=[27, 24],
                       kernel_io='kernel', rank0_prepare='async', boundary_export='copy',
                       origin='packet189 k3x arm (v5/lineage/k3x), measured on lane B 2026-10-22 (lanequeue-B36)'),
               k3x=dict(moved_layers='24-26', boundary='rank0-k3', kernel_io='kernel', rank0_prepare='async', boundary_export='copy',
                        memory_plan_sha256=sha(P / 'memory-plan.json'), rank0_census_bytes=31374119922, rank1_census_bytes=31581735626))
    (P / 'bundle-selection.json').write_text(json.dumps(row, indent=2) + '\n')
    chosen = b.selected()
    assert chosen['selection_sha256'] == SELECTION
    print('active k3x composition', name, chosen['selection_sha256'][:16])


if __name__ == '__main__':
    main()
