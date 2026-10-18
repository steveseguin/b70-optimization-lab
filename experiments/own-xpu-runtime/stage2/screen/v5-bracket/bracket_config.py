"""Fixed one-binary packet84 control and packet91 routing/recurrence choices."""
import json
from pathlib import Path
from common import HERE, ROOT, P56, ARITHMETIC, read, require, sha, save, verify_map, module

LINEAGE = HERE / 'lineage'

def sealed_identity(args):
    require(args.profile == 'tp2' and args.placement == '1' and args.timing == 'token',
            'v5 requires token timing, 24/24 target and rank1 draft')
    seal = LINEAGE / 'screen-seal.json'
    row = read(seal)
    require(row.get('passed') is True and row.get('device_executed') is False, 'v5 CPU seal missing')
    verify_map(ROOT, row['sources'])
    binary = HERE / 'build/device/own-rt-iq3'
    dispatch = LINEAGE / 'dispatch-speed6.json'
    require(args.binary is None or args.binary.resolve() == binary, 'bracket binary differs')
    require(args.dispatch is None or args.dispatch.resolve() == dispatch, 'bracket dispatch differs')
    require(args.seal is None or args.seal.resolve() == seal, 'bracket seal differs')
    require(row['binary_sha256'] == sha(binary), 'bracket binary changed')
    gate = module('bracket_memory_gate', P56 / 'memory_gate.py')
    configuration = gate.configuration(read(LINEAGE / 'memory-plan.json'), 4096, 1, 0)
    placement = dict(name='1', draft_rank=1, target_split=0, layer_boundary=24,
                     target_layers=[24, 24], context=4096, memory_admitted=True, supported=True,
                     reason='v5 full-shape startup and boundary census', configuration=configuration,
                     memory_gate=str(P56 / 'memory_gate.py'), memory_gate_sha256=sha(P56 / 'memory_gate.py'))
    return dict(placement=placement, timing='token', timing_modes=['token'], lineage=str(LINEAGE),
                seal=str(seal), seal_sha256=sha(seal), binary=str(binary), binary_sha256=sha(binary),
                dispatch=str(dispatch), dispatch_sha256=sha(dispatch), profile='tp2',
                selection_sha256=sha(LINEAGE / 'selection.json'),
                memory_plan_sha256=sha(LINEAGE / 'memory-plan.json'))

def prepare():
    parent = HERE.parent.parent / 'packet91-record-bundle'
    prefix = 'production--hc-wide--wide64--ordered--'
    suffix = '--production--placement-1'
    control = parent / 'selections' / (prefix + 'production--production--rec-parallel' + suffix) / 'selection.json'
    candidate = parent / 'selections' / (prefix + 'fast--production--rec-both-plus' + suffix) / 'selection.json'
    LINEAGE.mkdir(exist_ok=True)
    for src, name in ((control, 'selection.json'), (candidate, 'candidate.json'),
                      (parent / 'memory-plan.json', 'memory-plan.json'),
                      (parent / 'dispatch-speed6.json', 'dispatch-speed6.json')):
        (LINEAGE / name).write_bytes(src.read_bytes())
    pins = {str(f.relative_to(ROOT)): sha(f) for f in (control, candidate, parent / 'baseline-pins.json')}
    save(HERE / 'selection-provenance.json', dict(sources=pins, control='packet84 production',
                                                candidate='packet91 route-fast + rec-both-plus'))
    (HERE / 'configs').mkdir(exist_ok=True)
    for kind, order in (('smoke', ['control'] * 2), ('bracket', ['control','candidate','control','candidate','control'])):
        views=[]
        for choice in order:
            selection = LINEAGE / ('selection.json' if choice == 'control' else 'candidate.json')
            views.append(dict(choice=choice, selection=str(selection), selection_sha256=sha(selection)))
        save(HERE / 'configs' / (kind + '.json'), dict(kind=kind, views=views))

if __name__ == '__main__': prepare()
