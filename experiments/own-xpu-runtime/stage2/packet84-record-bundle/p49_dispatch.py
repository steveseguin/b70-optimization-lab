"""Preserve SPEED6 production choices while retaining fresh K2 measurements."""
import hashlib
import json
from pathlib import Path
from merge_dispatch import validate

P = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_coverage(summary, pinned, registry):
    require(summary.get('passed') is True and not summary.get('failures'), 'K2 must pass before production dispatch selection')
    validate(pinned)
    covered = []
    for section in ('classes', 'fusions', 'gemv'):
        for key, choice in pinned[section].items():
            if section == 'classes' and key == 'qsa.attention':
                # This old string is retained in the historical dispatch. The
                # target Engine overrides it; fresh split32 K1a/b are mandatory.
                continue
            matches = [(name, entry) for name, entry in registry.items()
                       if entry.get('dispatch_section') == section and key in entry.get('dispatch_keys', [entry.get('dispatch_key')])]
            if not matches and section == 'gemv' and key in ('hc.gate', 'hc.low'):
                require(choice == 'r5', 'unmeasured generic HC fallback must stay r5')
                # K2 separately covers hc.a/hc.f/final site choices. These two
                # generic constructor defaults have no separate K2 class.
                covered.append(dict(section=section, key=key, implementation=choice,
                                    measured_class=None, arm='unchanged generic fallback; specific sites measured separately'))
                continue
            require(bool(matches), f'unregistered pinned selection {section}/{key}')
            for name, entry in matches:
                row = summary['classes'][name]
                incumbent = choice == row['incumbent']
                comparisons = list(row['comparisons'].values()) if incumbent else [value for candidate, value in row['comparisons'].items() if candidate == choice or entry.get('candidate_implementation') == choice]
                require(bool(comparisons), f'pinned kernel not measured: {name}/{choice}')
                for comparison in comparisons:
                    arm = comparison['variants']['packet18' if incumbent else 'specialised']
                    require(arm.get('repetitions') == 200 and arm['execution_sum']['count'] >= 198, f'incomplete pinned kernel repetitions: {name}/{choice}')
                    if not incumbent:
                        require(comparison.get('bytes_equal') is True and not comparison.get('candidate_failures') and not comparison.get('rotation_errors') and comparison.get('candidate_available') is True,
                                f'pinned kernel failed fresh K2 exactness: {name}/{choice}')
                covered.append(dict(section=section, key=key, implementation=choice, measured_class=name, arm='incumbent' if incumbent else 'candidate'))
    return covered


def pin_production_dispatch(root, summary, *, round3_root):
    root = Path(root)
    from p49d_k2 import measured_coverage
    selection=json.loads((P/'selection.json').read_text())
    # K2 measures inherited operators. New combined choices are qualified by the
    # selected CPU seal, the screens and fresh chain exactness; never claim that
    # legacy K2 directly measured these new kernels.
    inherited={k:v for k,v in selection['choices'].items() if k not in ('miss','experts','packed_dense','hc_gate','host_retire','hc_norm')}
    if inherited.get('route')=='route-fast':inherited['route']='route-exp32-rank4'
    if inherited.get('recurrence') in ('rec-gates','rec-parallel'):inherited['recurrence']='rows4-shared'
    new_coverage=measured_coverage(round3_root,dict(selection,choices=inherited))
    new_coverage['scope']='Inherited K2 operators only; combined candidates require sealed CPU gates and fresh chain oracle checks'

    from bundle_selection import selected
    placement=selected()
    pinned_path = P / 'dispatch-speed6.json'
    proof = json.loads((P / 'dispatch-speed6-provenance.json').read_text())
    require(sha(pinned_path) == proof['sha256'], 'SPEED6 pinned dispatch identity changed')
    pinned = json.loads(pinned_path.read_text())
    registry = json.loads((P / 'k2-class-registry.json').read_text())['classes']
    covered = verify_coverage(summary, pinned, registry)
    measured_summary = root / 'summary-k2-measured.json'
    measured_dispatch = root / 'dispatch-k2-recommendation.json'
    require(not measured_summary.exists() and not measured_dispatch.exists(), 'production selection already recorded')
    measured_summary.write_bytes((root / 'summary.json').read_bytes())
    measured_dispatch.write_bytes((root / 'dispatch-measured.json').read_bytes())
    policy = dict(schema='packet49.pinned-production-dispatch.v1',
                  placement=placement, policy='Keep sealed packet64 topology and inherited dispatch; bind the sealed packet49d init table only after K2 measures all selectable and banked kernels. Selection comes from the two-owner packet54 decision, never this one-owner screen. Target QSA remains split32.',
                  packet49d_selection_sha256=sha(P/'selection.json'),
                  packet49d_measured_selection=new_coverage,
                  speed6_dispatch_sha256=proof['sha256'],
                  fresh_measured_summary_sha256=sha(measured_summary),
                  fresh_recommendation_sha256=sha(measured_dispatch),
                  fresh_exactness_coverage=covered,
                  unchanged_choices_are_not_new_speed_claims=True)
    summary = dict(summary, measured_final_dispatch=summary['final_dispatch'],
                   final_dispatch=pinned, production_dispatch_policy=policy)
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (root / 'dispatch-measured.json').write_bytes(pinned_path.read_bytes())
    return summary, policy
