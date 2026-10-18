"""Read frozen v5 evidence in its own interpreter; never mutate its modules."""
import argparse
import json
from pathlib import Path
import sys

V5 = Path(__file__).resolve().parents[2]/'stage2/screen/v5-bracket'


def load(output, smoke=False):
    sys.path.insert(0, str(V5))
    from common import read, sha, D
    from compare import load as frozen_load
    from conditions import LANES
    from bracket import load_config
    from bracket_config import sealed_identity
    from types import SimpleNamespace
    result = frozen_load(output)
    window, identity = read(output/'window.json'), read(output/'identity.json')
    assert window['finished_utc_ns'] > window['started_utc_ns']
    assert not window.get('child_retained') and not window.get('report_failed')
    assert window['lane'] == identity['lane'] and identity['conditions'] == LANES[identity['lane']]
    assert window['conditions'] == identity['conditions']
    expected = sealed_identity(SimpleNamespace(profile='tp2', placement='1', timing='token',
                                               binary=None, dispatch=None, seal=None))
    assert all(identity.get(k) == v for k, v in expected.items()), 'native identity changed'
    config = Path(identity['bracket_config'])
    assert sha(config) == identity['bracket_config_sha256']
    assert load_config(config) == identity['bracket'], 'registered bracket differs'
    assert all(result[k] == 1 for k in ('model_lifetimes', 'target_loads', 'draft_loads', 'teardown_count'))
    expected_order = ['control', 'control'] if smoke else ['control', 'candidate', 'control', 'candidate', 'control']
    assert result['kind'] == ('smoke' if smoke else 'bracket')
    assert [r['choice'] for r in result['views']] == expected_order
    coordination = read(output/'lane-coordination.json')
    assert coordination['passed'] and coordination['released_before_report']
    assert coordination['reservation']['scope'] == 'lane-'+identity['lane']
    required = ['identity.json', 'bracket-summary.json', 'suite-manifest.snapshot.json',
                'run/teardown.json', 'run/device-isolation.json']
    identities = []
    for i, row in enumerate(result['views']):
        view = identity['bracket']['views'][i]
        dest = output/'run/views'/f'{i:02d}-{row["choice"]}'
        required += [str((dest/leaf).relative_to(output)) for leaf in
                     ('summary.json', 'identity.json', 'incident64/receipt.json',
                      'boundary/boundary-rank0.json', 'boundary/boundary-rank1.json')]
        assert row['all_13_exact'] is True and row['exact_count'] == 13
        assert row['lane'] == identity['lane'] and row['boot_id'] == window['boot_id']
        assert row['started_utc_ns'] < row['finished_utc_ns']
        if i:
            assert result['views'][i-1]['finished_utc_ns'] < row['started_utc_ns']
        incident = read(dest/'incident64/receipt.json')
        assert incident['passed'] is True and incident['exact_oracle'] is True
        assert len(incident['tokens']) == 64 and incident['cached_tokens'] == 0
        descriptors = []
        for rank in (0, 1):
            proof = read(dest/'boundary'/f'boundary-rank{rank}.json')
            assert proof['passed'] and proof['total_reset'] and proof['allocation_ids_preserved']
            assert proof['cached_tokens'] == proof['weight_uploads_after_load'] == 0
            assert proof['selection_sha256'] == view['selection_sha256']
            descriptors.append((proof['arena_descriptors_sha256'], proof['weight_descriptors_sha256']))
        if i == 0:
            baseline_descriptors = descriptors
        assert descriptors == baseline_descriptors
        row['exact'] = True
        identities.append(dict(identity, selection_sha256=view['selection_sha256']))
    for leaf in required:
        assert window['files'].get(leaf) == sha(output/leaf), 'unbound required artifact: '+leaf
    if smoke:
        assert result['timing_equal_within_control_drift'] is True
    return dict(rows=result['views'], identities=identities, wrapper='v5',
                lane=identity['lane'], shared_model_lifetime=True,
                control_drift_percent=result['control_drift_percent'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--smoke', type=Path)
    args = parser.parse_args()
    print(json.dumps(load(args.smoke or args.output, bool(args.smoke))))
