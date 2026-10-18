"""Five-view proposals with fail-closed admission to the frozen v5 engine.

A proposal is an intent, not a compatibility claim. Unsupported intents remain
visible and fail the real queue planner before any lease, load, or GPU work.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

O = Path(__file__).resolve().parent
ROOT = O.parents[3]
STAGE = ROOT / 'experiments/own-xpu-runtime/stage2'
V5 = STAGE / 'screen/v5-bracket'
QUEUE = O.parent / 'lane-queue'
PLANS = O / 'v5-plans'
ORDER = ('control', 'candidate', 'control', 'candidate', 'control')
PACKETS = {'92': 'packet92-rank1-reply-first', '94': 'packet94-hc-norm-fusion',
           '100': 'packet100-down-locality', '101': 'packet101-draft-geometry'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value, immutable=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if path.exists() and immutable:
        assert path.read_text() == text, 'immutable proposal changed: ' + str(path)
    else:
        path.write_text(text)


def compatibility(control, candidate):
    """Mirror, never weaken, both the native switch and registered lineage gate."""
    reasons = []
    if set(control) != set(candidate) or control.get('schema') != candidate.get('schema'):
        reasons.append('selection schema differs')
    if control.get('draft') != candidate.get('draft'):
        reasons.append('draft selection differs; frozen native v5 requires identical draft')
    left, right = control['choices'], candidate['choices']
    if set(left) != set(right):
        reasons.append('selection keys differ')
    for key in sorted(set(left) | set(right)):
        if left.get(key) == right.get(key) or key in ('route', 'recurrence'):
            continue
        values = str(left.get(key)) + ' ' + str(right.get(key))
        layout = any(x in values for x in ('halfcache', 'weightcache', 'head-transpose', 'tile16'))
        reasons.append(('load-time layout differs: ' if layout else 'unqualified native switch: ') + key)
    if any(str(row.get('miss', '')).startswith('banks') for row in (left, right)):
        reasons.append('third banks are not qualified')
    return reasons


def admission(manifest):
    assert manifest['schema'] == 'packet98b.bracket-intent.v1'
    assert manifest['lane'] in ('A', 'B') and manifest['record_lane'] == 'A'
    assert [v['choice'] for v in manifest['views']] == list(ORDER), 'complete five-view order required'
    for path, digest in manifest['pins'].items():
        assert sha(ROOT/path) == digest, 'changed proposal input: ' + path
    views = manifest['views']
    for view in views:
        assert sha(view['selection']) == view['selection_sha256'], 'view selection changed'
    assert len({v['selection_sha256'] for v in views[::2]}) == 1
    assert len({v['selection_sha256'] for v in views[1::2]}) == 1
    reasons = compatibility(read(views[0]['selection']), read(views[1]['selection']))
    registered = read(V5/'configs/bracket.json')['views']
    if [v['selection_sha256'] for v in views] != [v['selection_sha256'] for v in registered]:
        reasons.append('exact selection bytes are outside the frozen v5 registered lineage; no substitution')
    if manifest.get('decision'):
        import composite_jobs as c
        config = read(ROOT/manifest['decision'])
        assert c.identity(config) == Path(manifest['decision']).stem
        c.validate(config)
        candidate = c.variants(config, manifest['variant'] != 'composite')[manifest['variant']]
        assert Path(views[0]['selection']) == c.view(config['control'])/'selection.json'
        assert Path(views[1]['selection']) == c.view(candidate)/'selection.json'
    return dict(admitted=not reasons, reasons=reasons, requested_wrapper='v5',
                fallback='v4 with separate loads' if reasons else None,
                record_lane='A', device_executed=False)


def manifest(control, candidate, lane, label, decision=None, variant=None):
    paths = {'control': control/'selection.json', 'candidate': candidate/'selection.json'}
    pins = {str(path.relative_to(ROOT)): sha(path) for path in
            (*paths.values(), control/'screen-seal.json', candidate/'screen-seal.json',
             V5/'wrapper-seal.json', V5/'placement-validation/wrapper-seal.json',
             V5/'native/engine_bracket.hpp', V5/'bracket.py', V5/'bracket_config.py',
             V5/'configs/bracket.json')}
    if decision:
        pins[str(decision.relative_to(ROOT))] = sha(decision)
    return dict(schema='packet98b.bracket-intent.v1', lane=lane, record_lane='A',
                label=label, variant=variant, decision=str(decision.relative_to(ROOT)) if decision else None,
                views=[dict(choice=choice, selection=str(paths[choice]),
                            selection_sha256=sha(paths[choice])) for choice in ORDER], pins=pins)


def job(path):
    row = read(path)
    name = 'p98b-' + path.stem.replace('+', '-plus-')
    return dict(name=name, lane=row['lane'], env_extra={},
                argv=['/usr/bin/python3', '-B', str((O/'v5_screen.py').relative_to(ROOT)),
                      '--manifest', str(path), '--manifest-sha256', sha(path),
                      '--lane', row['lane'], '--output', str(V5/'evidence'/name),
                      '--fault-review', '{REVIEW}', '--authorized-device-window'],
                review=str((V5/'fault_review.py').relative_to(ROOT)))


def write_proposal(label, manifests):
    paths, admissions = [], []
    for row in manifests:
        path = PLANS/(row['label']+'-'+row['lane']+'.json')
        save(path, row)
        paths.append(path)
        admissions.append(admission(row))
    proposal = QUEUE/('proposed-'+label+'.txt')
    save_rows = ''.join(json.dumps(job(path))+'\n' for path in paths)
    if proposal.exists():
        assert proposal.read_text() == save_rows, 'proposal changed'
    else:
        proposal.write_text(save_rows)
    # Isolate every job so an early refusal cannot hide a later candidate.
    plans = []
    with tempfile.TemporaryDirectory(prefix='packet98b-queue-') as tmp:
        for i, (path, check) in enumerate(zip(paths, admissions)):
            lane = manifests[i]['lane']
            (Path(tmp)/('queue-'+lane+'.txt')).write_text(json.dumps(job(path))+'\n')
            cp = subprocess.run([sys.executable, '-B', str(QUEUE/'lanequeue.py'),
                                 'plan', '--lane', lane, '--directory', tmp],
                                cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=240)
            log = PLANS/(path.stem+'-plan.log')
            log.write_text(cp.stdout+cp.stderr)
            plans.append(dict(manifest=str(path.relative_to(ROOT)), manifest_sha256=sha(path),
                              admission=check, queue_plan_passed=cp.returncode == 0,
                              plan_returncode=cp.returncode, log=str(log.relative_to(ROOT)),
                              log_sha256=sha(log)))
    return dict(proposal=str(proposal.relative_to(ROOT)), sha256=sha(proposal), plans=plans,
                live_queue_modified=False, device_executed=False)


def generate_composite(config, leave_one_out=False):
    import composite_jobs as c
    c.validate(config)
    decision = O/'decisions'/(c.identity(config)+'.json')
    if decision.exists():
        assert read(decision) == config
    else:
        # Preserve the established decision encoding and identity.
        c.save(decision, config)
    receipts = []
    for lane in ('A', 'B'):
        rows = []
        for variant, selected in c.variants(config, leave_one_out).items():
            label = 'p97-v5-'+c.identity(config)+'-'+variant
            rows.append(manifest(c.view(config['control']), c.view(selected), lane, label, decision, variant))
        label = 'p97-v5-'+('leave-one-out-' if leave_one_out else '')+c.identity(config)[:4]+'-'+lane
        receipts.append(write_proposal(label, rows))
    result = dict(requested_wrapper='v5', proposals=receipts, device_executed=False,
                  live_queue_modified=False,
                  admitted=all(p['admission']['admitted'] for r in receipts for p in r['plans']))
    save(PLANS/('p97-'+c.identity(config)+('-loo' if leave_one_out else '')+'-plans.json'), result)
    return result


def generate_sources():
    receipts = []
    for packet, dirname in PACKETS.items():
        base = STAGE/dirname
        selections = base/('compat/packet64-record-bundle/selections' if packet in ('92', '94') else 'selections')
        control = selections/('control' if packet == '101' else 'production')
        candidates = {'92': ('reply-first',), '94': ('hc-normfuse', 'hc-normfuse+weightcache'),
                      '100': ('down-interleave', 'down-tile16'), '101': ('draft_attention',)}[packet]
        for lane in ('A', 'B'):
            rows = [manifest(control, selections/choice, lane, 'p'+packet+'-v5-'+choice)
                    for choice in candidates]
            receipts.append(write_proposal('p'+packet+'-v5-'+lane, rows))
    result = dict(proposals=receipts, device_executed=False, live_queue_modified=False)
    save(PLANS/'sources-plans.json', result, immutable=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(generate_sources(), indent=2))
