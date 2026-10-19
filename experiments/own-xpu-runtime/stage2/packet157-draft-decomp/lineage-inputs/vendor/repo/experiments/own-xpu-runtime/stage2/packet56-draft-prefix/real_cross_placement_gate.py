#!/usr/bin/env python3
"""Compare retained CPU draft evidence; never launch binaries or restore caches."""
import argparse
import base64
import gzip
import hashlib
import json
import struct
from pathlib import Path

P = Path(__file__).resolve().parent
CONTEXTS = (256, 4096, 32768)
COUNTERS = ('guesses', 'hits', 'misses', 'no_guess')
# These named buffers have capacity-independent geometry in the draft plan.
# Cache arrays, QSA selector/workspace arrays and generic scratch are excluded.
SEMANTIC_BUFFERS = (
    'active', 'error', 'position', 'embedding', 'streams',
    'merge.hidden', 'merge.norm', 'merge.projected',
    'merge.embedding_norm', 'merge.embedding_projected',
    'final.act', 'final.gate', 'final.low', 'final.mix', 'final.norm',
    'logits', 'next_token',
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for part in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(part)
    return digest.hexdigest()


def retained_draft(row):
    """Verify the archive and extract two small retained, hash-bound text files."""
    archive = row['scratch_archive']
    path = (P / archive['path']).resolve()
    assert path.is_relative_to(P / 'evidence'), 'archive outside packet evidence'
    assert sha(path) == archive['sha256'], 'archive hash changed'
    suffixes = {
        f"/rank{row['draft_rank']}/draft-final-state/all-state.json": 'state',
        f"/rank{row['draft_rank']}/draft-rows.jsonl": 'trace',
    }
    files = {}; hashes = {}; current = None; content = bytearray()
    with gzip.open(path, 'rt') as source:
        assert json.loads(next(source)) == {'schema': 'packet38.scratch-stream.v1'}
        for line in source:
            part = json.loads(line)
            if part['kind'] == 'file':
                assert current is None, 'unfinished retained member'
                matches = [name for suffix, name in suffixes.items() if part['path'].endswith(suffix)]
                if matches:
                    name = matches[0]
                    assert name not in files and part['retained'] and part['bytes'] < 1_000_000
                    current = (name, part); content.clear()
            elif part['kind'] == 'chunk' and current:
                content.extend(base64.b64decode(part['base64'], validate=True))
                assert len(content) <= current[1]['bytes'], 'retained member exceeded extent'
            elif part['kind'] == 'end' and current:
                name, header = current
                assert part['path'] == header['path'] and len(content) == header['bytes']
                assert hashlib.sha256(content).hexdigest() == header['sha256']
                files[name] = bytes(content); hashes[name] = header['sha256']; current = None
    assert current is None and set(files) == {'state', 'trace'}, 'missing draft evidence'
    assert hashes['state'] == row['signature']['draft_state']['all-state.json']
    return json.loads(files['state']), [json.loads(line) for line in files['trace'].splitlines()], hashes


def check(data, *, development_mini=False):
    assert data['passed'] is True and data['completed'] is True and data['device_executed'] is False
    assert data['arithmetic'] == 'iq3-p17-detmath-v2'
    if development_mini:
        assert data['cases'] == len(data['rows']) == 79
        rows = [r for r in data['rows'] if r['name'].endswith('-native-none')]
    else:
        assert data['cases'] == len(data['rows']) == 6
        rows = data['rows']
        assert all(r['oracle_subset_tokens'] == 8 and r['oracle_layer_fixtures'] == 384 for r in rows)
    matrix = {(r['context'], r['draft_rank']): r for r in rows}
    assert len(rows) == len(matrix) == 6
    assert set(matrix) == {(c, r) for c in CONTEXTS for r in (0, 1)}
    base = matrix[256, 0]; base_semantic = None; comparisons = []; archives = {}
    for context in CONTEXTS:
        left, right = matrix[context, 0], matrix[context, 1]
        assert left['signature']['draft_state'] == right['signature']['draft_state'], 'same-capacity draft state differs'
        for rank in (0, 1):
            row = matrix[context, rank]
            assert row['passed'] is True and row['controller'] == 'native' and row['draft'] == 'mtp'
            assert row['fault'] == 'none' and row['eos'] == [] and row['cancel_launch'] == -1
            assert (row['prompt_tokens'], row['count']) == (base['prompt_tokens'], 8)
            assert row['signature']['tokens'] == base['signature']['tokens']
            assert row['signature']['fixtures'] == base['signature']['fixtures']
            assert row['guess_sequence'] == base['guess_sequence'], 'draft guesses differ'
            counters = {name: row['stats'][name] for name in COUNTERS}
            assert counters == {name: base['stats'][name] for name in COUNTERS}, 'draft decision counts differ'
            assert len(row['guess_sequence']) == row['count'] - 1
            assert counters['guesses'] + counters['no_guess'] == row['count'] - 1
            assert counters['hits'] + counters['misses'] == counters['guesses']
            state, trace, member_hashes = retained_draft(row)
            # native_controller submits only while `more`; mtp starts cache
            # position zero and increments once per successful completion.
            completed = row['prompt_tokens'] + row['count'] - 2
            assert state['position'] == completed and state['disabled'] is False
            assert [r['draft_position'] for r in trace] == list(range(completed)), 'draft cache progression differs'
            position_sha = hashlib.sha256(struct.pack('<i', completed)).hexdigest()
            assert row['signature']['draft_state']['position.bin'] == position_sha
            values = state['mutable_sha256']
            semantic = {name: values['card0:draft:' + name] for name in SEMANTIC_BUFFERS}
            assert semantic['position'] == position_sha
            assert semantic['error'] == hashlib.sha256(struct.pack('<i', 0)).hexdigest()
            if base_semantic is None:
                base_semantic = semantic
            assert semantic == base_semantic, 'fixed-size draft semantic state differs across capacities'
            archive = row['scratch_archive']; archives[archive['path']] = archive['sha256']
            comparisons.append(dict(context=context, draft_rank=rank, passed=True,
                completed_drafts=completed, last_draft_cache_index=completed-1,
                last_confirmed_target_input_position=completed, next_draft_cache_position=completed,
                retained_member_sha256=member_hashes, semantic_sha256=semantic))
    return dict(passed=True, device_executed=False, cases=6, same_capacity_pairs=3,
        semantic_buffer_count=len(SEMANTIC_BUFFERS), compared_stat_fields=list(COUNTERS),
        guess_sequence=base['guess_sequence'], stats={n: base['stats'][n] for n in COUNTERS},
        archive_sha256=archives, rows=comparisons,
        scope='Same-capacity complete draft-state hashes; cross-capacity fixed-size semantic outputs, '
              'cache-position progression and decisions. No cross-capacity raw cache-prefix comparison; '
              'capacity-sized tails and scratch are excluded. Timing is not compared. No device or speed claim.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development-mini', action='store_true', help='Read mini79; print result without writing a real gate receipt')
    args = parser.parse_args()
    receipt = P / ('cpu-merged-gates.json' if args.development_mini else 'cpu-real-gates.json')
    before = sha(receipt); data = json.loads(receipt.read_text())
    result = check(data, development_mini=args.development_mini)
    assert sha(receipt) == before, 'source receipt changed during check'
    result.update(schema='packet45.real-cross-placement.v1', input_receipt=receipt.name,
        input_receipt_sha256=before, runtime_binary_sha256=data['build']['binary_sha256'],
        sources={name: sha(P/name) for name in ('real_cross_placement_gate.py', 'mtp.hpp', 'native_controller.hpp')})
    if not args.development_mini:
        tests = json.loads((P/'real-cross-placement-tests.json').read_text())
        assert tests['passed'] and tests['checks'] == 11 and tests['errors'] == tests['failures'] == 0
        assert tests['device_executed'] is False
        for name, digest in tests['source_sha256'].items():
            assert sha(P/name) == digest, 'stale post-run checker tests'
        assert sha(P/'cpu-merged-gates.json') == tests['input_receipt_sha256']
        result['tests_receipt_sha256'] = sha(P/'real-cross-placement-tests.json')
        (P/'real-cross-placement-gates.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({name: result[name] for name in ('passed', 'cases', 'same_capacity_pairs', 'semantic_buffer_count')}))


if __name__ == '__main__':
    main()
