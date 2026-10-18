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
    parent = HERE.parent / 'packet97-record-bundle'
    bundle = module('p98c_bundle', parent / 'bundle_selection.py')
    values = ('production','hc-wide','wide64','ordered','production','production',
              'rec-parallel','production','production','production')
    source = parent / 'selections' / (bundle.name(*values) + '--placement-1')
    control = source / 'selection.json'
    LINEAGE.mkdir(exist_ok=True)
    for src, name in ((control, 'selection.json'),
                      (source / 'memory-plan.json', 'memory-plan.json'),
                      (source / 'dispatch-speed6.json', 'dispatch-speed6.json')):
        (LINEAGE / name).write_bytes(src.read_bytes())
    import copy
    base = read(control)
    for name, changes, draft in (
        ('candidate', {'route':'route-fast','recurrence':'rec-both-plus'}, {}),
        ('route', {'route':'route-fast'}, {}),
        ('attention', {}, {'qsa_attention':'packet59'}),
        ('rec-production', {'recurrence':'rows4-shared'}, {}),
        ('hc-production', {'hc_gate':'production'}, {})):
        row = copy.deepcopy(base);row['choices'].update(changes);row['draft'].update(draft)
        save(LINEAGE / (name + '.json'), row)
    pins = {str(f.relative_to(ROOT)): sha(f) for f in (control, source / 'memory-plan.json', source / 'dispatch-speed6.json')}
    save(HERE / 'selection-provenance.json', dict(sources=pins, decision='f1e5d7f47fc0fe54',
         projection='kernel-only part; experts fixed wide64 in every view; not the full composite',
         control='packet97 baseline', candidate='route-fast + rec-both-plus',
         draft_attention='packet101 qsa_attention=packet59; existing packet97 implementation 12'))
    (HERE / 'configs').mkdir(exist_ok=True)
    for name, candidate, kind, order in (
        ('smoke','route','smoke',['control','candidate','control']),
        ('bracket','candidate','bracket',['control','candidate','control','candidate','control']),
        ('attention','attention','bracket',['control','candidate','control','candidate','control'])):
        views=[]
        for choice in order:
            selection = LINEAGE / ('selection.json' if choice == 'control' else candidate+'.json')
            views.append(dict(choice=choice, selection=str(selection), selection_sha256=sha(selection)))
        save(HERE / 'configs' / (name + '.json'), dict(kind=kind, views=views))

if __name__ == '__main__': prepare()
