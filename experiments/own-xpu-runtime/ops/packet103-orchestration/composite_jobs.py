"""CPU-only immutable decisions and composite/leave-one-out queue proposals."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

O = Path(__file__).resolve().parent
ROOT = O.parents[3]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet103-record-bundle'
QUEUE = O.parent / 'lane-queue'
sys.path.insert(0, str(P))
from bundle_selection import KEYS, name
from build_engine import sha, save
from screen_jobs import DEFAULTS, WRAPPER


def identity(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]


def view(selection):
    return P / 'selections' / (name(*(selection[k] for k in KEYS)) + '--placement-1')


def variants(config, leave_one_out=False):
    if not leave_one_out:
        return {'composite': config['candidate']}
    from orchestrate import DIMENSIONS
    result = {}
    for source in config['confirmed_levers']:
        choice = dict(config['candidate'])
        if source in ('90', '95'):
            part = {'90': 'halfcache', '95': 'grid-prefetch'}[source]
            choice['experts'] = '+'.join(x for x in choice['experts'].split('+') if x != part)
        else:
            for key in DIMENSIONS[source]:
                choice[key] = DEFAULTS[key]
        view(choice)  # Must be one of the existing 128 views.
        result['without-' + source] = choice
    return result


def leave_one_out_required(ratios, config):
    # Compare gains, never absolute speeds across lanes or summed micro wins.
    best = max((ratio for source in config['source_ratios'].values()
                for ratio in source.values()), default=1.)
    reasons = []
    if min(ratios.values()) < best:
        reasons.append('composite gain below best single-source gain')
    if min(ratios.values()) < 1.005:
        reasons.append('composite gain below +0.5% over stronger same-lane control')
    return dict(required=bool(reasons), reasons=reasons, best_source_ratio=best,
                composite_ratios=ratios, comparison='minimum lane gain versus best source gain')


def jobs(config, lane, variant='composite', attempt=''):
    assert not attempt or re.fullmatch(r'[a-z][a-z0-9]*', attempt), 'invalid attempt suffix'
    suffix = '-' + attempt if attempt else ''
    assert lane in ('A', 'B')
    choices = variants(config, variant != 'composite')
    assert variant in choices
    return [dict(index=i, lane=lane, mode='grid', choice=label,
                 selection=selection,
                 out=f'p103-{identity(config)}-{variant}-{lane}-{i}-{label}{suffix}')
            for i, (label, selection) in enumerate((('control', config['control']),
                ('candidate', choices[variant]), ('control', config['control'])))]


def check_selection(config):
    from orchestrate import DIMENSIONS, select, apply_pins, composition
    sources = {n: config['qualified_screens'].get(n, config.get('excluded_sources',{}).get(n,dict(status='no-winner'))) for n in DIMENSIONS}
    control, candidate, qualified = select(sources)
    candidate, pins = apply_pins(candidate, [k+'='+v for k,v in config['coordinator_pins'].items()])
    expected = composition(sources, control, candidate, qualified, pins, config['coordinator_closures'])
    assert config['control'] == expected['control'] and config['candidate'] == expected['candidate'], 'candidate differs from qualified sources'
    assert config['confirmed_levers'] == expected['confirmed_levers'], 'selected source list differs'


def validate(config):
    from seal_inputs import verify as verify_startup_inputs
    verify_startup_inputs()
    from chain_seal import check_map
    from bootstrap import install
    install()
    assert config['status'] == 'confirmed-sources' and config['confirmed_levers']
    assert config['control'] == DEFAULTS and config['candidate'] != config['control']
    check_selection(config)
    from read_screens import reject_later_record_lane_losses
    reject_later_record_lane_losses(config)
    from orchestrate import check_winner
    assert set(config['qualified_screens']) == set(config['confirmed_levers']) == set(config['source_ratios'])
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    for source, evidence in config['qualified_screens'].items():
        check_winner(evidence)
        assert evidence['ratios'] == config['source_ratios'][source]
        assert all(row['boot_id'] == boot for rows in evidence['lanes'].values() for row in rows), 'stale source boot'
    from historical_pins import preserved_pins
    check_map(ROOT, preserved_pins(config['evidence_pins']))
    # Verify the sealed selection dependencies without changing any seal.
    from common import sealed
    from types import SimpleNamespace
    for selection in (config['control'], *variants(config).values(), *variants(config, True).values()):
        lineage = view(selection)
        sealed(SimpleNamespace(lineage=lineage, seal=lineage/'screen-seal.json',
               binary=None, dispatch=None, profile='tp2', timing='token', placement='1'))


def generate(config, leave_one_out=False, wrapper='v4', attempt=''):
    assert wrapper == 'v4', 'unknown wrapper'
    validate(config)
    decision = O / 'decisions' / (identity(config) + '.json')
    decision.parent.mkdir(exist_ok=True)
    if decision.exists():
        assert json.loads(decision.read_text()) == config, 'decision collision'
    else:
        save(decision, config)
    digest = sha(decision)
    paths = []
    payloads = {}
    for lane in ('A', 'B'):
        rows = []
        for variant in variants(config, leave_one_out):
            for job in jobs(config, lane, variant, **({'attempt': attempt} if attempt else {})):
                rows.append(dict(name=job['out'], lane=lane, argv=[
                    '/usr/bin/python3', '-B', str((O/'composite_screen.py').relative_to(ROOT)),
                    '--decision', str(decision), '--decision-sha256', digest,
                    '--variant', variant, '--lane', lane, '--index', str(job['index']),
                    '--attempt', attempt,
                    '--fault-review', '{REVIEW}', '--authorized-device-window'],
                    env_extra={}, review=str((WRAPPER/'fault_review.py').relative_to(ROOT))))
        label = 'leave-one-out' if leave_one_out else 'composite'
        proposal = QUEUE / f'proposed-p103{attempt}-{label}-{lane}.txt'
        payloads[lane] = ''.join(json.dumps(row) + '\n' for row in rows).encode()
        paths.append(proposal)
    plans = []
    # The planner reads queue files only in this disposable directory.
    with tempfile.TemporaryDirectory(prefix='p103-queue-') as tmp:
        for lane, proposal in zip(('A', 'B'), paths):
            (Path(tmp)/f'queue-{lane}.txt').write_bytes(payloads[lane])
            cp = subprocess.run([sys.executable, '-B', str(QUEUE/'lanequeue.py'),
                'plan', '--lane', lane, '--directory', tmp], cwd=ROOT,
                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=240)
            log = O / f'{label}{attempt}-plan-{lane}.log'
            log.write_text(cp.stdout + cp.stderr)
            assert cp.returncode == 0, str(log)
            plans.append(dict(proposal=str(proposal.relative_to(ROOT)),
                sha256=hashlib.sha256(payloads[lane]).hexdigest(), jobs=len(payloads[lane].splitlines()),
                plan_log_sha256=sha(log), passed=True))
    if attempt:
        registration = O/'attempts'/(identity(config)+'-'+attempt+'.json')
        registration.parent.mkdir(exist_ok=True)
        record = dict(decision_sha256=digest, attempt=attempt,
                      variants=list(variants(config, leave_one_out)))
        if registration.exists():
            assert json.loads(registration.read_text()) == record
        else:
            save(registration, record)
    # The coordinator watches these names. Expose them only after both plans pass.
    for lane, proposal in zip(('A', 'B'), paths):
        with tempfile.NamedTemporaryFile(dir=QUEUE, prefix='.p103-proposal-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payloads[lane])
        temporary.replace(proposal)
    receipt = dict(passed=True, device_executed=False, live_queue_modified=False,
                   decision=str(decision.relative_to(ROOT)), decision_sha256=digest, plans=plans)
    save(O / f'{label}{attempt}-plans.json', receipt)
    return receipt


def prepare_proposals(config, leave_one_out=False):
    # Re-evaluation after a measured screen must not re-plan its occupied output
    # paths. The original immutable proposal remains the queue authority.
    started = any((WRAPPER/'evidence'/job['out']).exists()
                  for variant in variants(config, leave_one_out)
                  for lane in ('A', 'B') for job in jobs(config, lane, variant))
    if started:
        decision = O/'decisions'/(identity(config)+'.json')
        assert json.loads(decision.read_text()) == config, 'started screen decision differs'
        return dict(already_started=True, decision=str(decision), decision_sha256=sha(decision),
                    live_queue_modified=False, device_executed=False)
    return generate(config, leave_one_out, wrapper='v4')


def attempts(config, variant='composite'):
    result = ['']
    decision = O/'decisions'/(identity(config)+'.json')
    for path in sorted((O/'attempts').glob(identity(config)+'-*.json')):
        row = json.loads(path.read_text())
        assert row['decision_sha256'] == sha(decision), 'attempt decision changed'
        assert path.stem == identity(config)+'-'+row['attempt']
        assert re.fullmatch(r'[a-z][a-z0-9]*', row['attempt'])
        assert set(row['variants']) <= set(variants(config)) | set(variants(config, True))
        if variant in row['variants']:
            result.append(row['attempt'])
    return result


def read_brackets(config, variant='composite'):
    validate(config)
    import compare
    old_view, old_output = compare.view, compare.output
    try:
        choices = {'control': config['control'], 'candidate': variants(config, variant != 'composite')[variant]}
        compare.view = lambda label: view(choices[label])
        compare.output = lambda job: WRAPPER / 'evidence' / job['out']
        return {lane: [compare.load(job) for job in jobs(config, lane, variant)] for lane in ('A', 'B')}
    finally:
        compare.view, compare.output = old_view, old_output


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decision', type=Path, required=True)
    ap.add_argument('--leave-one-out', action='store_true')
    ap.add_argument('--wrapper', choices=('v4',), default='v4')
    ap.add_argument('--attempt', default='')
    args = ap.parse_args()
    print(json.dumps(generate(json.loads(args.decision.read_text()), args.leave_one_out, args.wrapper, args.attempt), indent=2))


if __name__ == '__main__':
    main()
