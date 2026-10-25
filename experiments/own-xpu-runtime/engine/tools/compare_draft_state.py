#!/usr/bin/env python3
"""Strict CPU comparison of sealed, quiescent live-MTP draft state.

Each ownrt.draft-state-set.v1 manifest names a dump and input_identity with
model_sha256, draft_model_sha256, pair_sequence_sha256, arithmetic and position.
The pair sequence hash binds ordered [position, confirmed token, head flag,
raw hidden SHA256] rows; engine/build/topology belong in separate provenance.
This gate compares every allocation, including scratch and pinned transport.
It establishes cross-run state parity, not independent model correctness.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

from compare_pipeline_state import BUNDLE, WIDTH, require


def digest(data):
    return hashlib.sha256(data).hexdigest()


def small(path):
    # Reopened metadata is bounded and bound to its independently verified hash.
    # O_NONBLOCK avoids waiting if a metadata path is replaced by a FIFO.
    import os
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= BUNDLE.META, 'bounded regular metadata required')
        data = bytearray()
        while len(data) < before.st_size:
            part = os.read(fd, min(65536, before.st_size - len(data)))
            require(part, 'metadata truncated')
            data.extend(part)
        require(not os.read(fd, 1) and BUNDLE.identity(before) == BUNDLE.identity(os.fstat(fd))
                == BUNDLE.identity(os.stat(path, follow_symlinks=False)), 'metadata changed')
        raw = bytes(data)
        return raw, dict(path=str(path), bytes=len(raw), sha256=digest(raw))
    finally:
        os.close(fd)


def load_set(path):
    path = Path(path).absolute()
    raw, receipt = small(path)
    spec = json.loads(raw, object_pairs_hook=BUNDLE.pairs)
    require(spec['schema'] == 'ownrt.draft-state-set.v1', 'unsupported draft state set schema')
    identity = spec['input_identity']
    require(isinstance(identity, dict), 'draft input identity required')
    for key in ('model_sha256', 'draft_model_sha256', 'pair_sequence_sha256'):
        require(BUNDLE.hexhash(identity.get(key)), 'missing/invalid draft input identity: ' + key)
    require(isinstance(identity.get('arithmetic'), str) and identity['arithmetic'], 'draft arithmetic required')
    require(type(identity.get('position')) is int and 0 <= identity['position'] <= 2**31-1,
            'draft position identity required')
    require(isinstance(spec['dump'], str) and spec['dump'], 'draft dump path required')
    dump = path.parent / spec['dump']
    hashes = BUNDLE.read_state(dump)
    state_raw, state_receipt = small(dump / 'state.json')
    index_raw, index_receipt = small(dump / 'state-index.tsv')
    seal_raw, seal_receipt = small(dump / 'state-seal.txt')
    fields = seal_raw.decode().splitlines()
    require(len(fields) == 5 and fields[0] == 'GSQ_STATE_SEAL_V1'
            and digest(state_raw) == fields[4] == hashes['state.json']
            and digest(index_raw) == fields[3], 'draft metadata changed after sealed read')
    state = json.loads(state_raw, object_pairs_hook=BUNDLE.pairs)
    require(set(state) == {'schema', 'buffers', 'layouts', 'host'}
            and state['schema'] == 'ownrt.draft-state.v1', 'unsupported native draft state schema')
    host = state['host']
    require(isinstance(host, dict) and set(host) == {
        'position', 'context_extent', 'disabled', 'async_pending', 'pending_head',
        'pending_confirmed', 'reverse_hidden_present', 'queued_probe', 'queued_confirmed', 'depth_probe'},
        'draft host inventory differs')
    for key in ('position', 'context_extent', 'pending_confirmed', 'queued_probe', 'queued_confirmed', 'depth_probe'):
        require(type(host[key]) is int and -1 <= host[key] <= 2**31-1, 'draft host integer: ' + key)
    require(host['position'] == identity['position'] and host['context_extent'] >= max(1, host['position']),
            'draft host position/extent differs')
    require(all(host[key] is False for key in ('disabled', 'async_pending', 'pending_head', 'reverse_hidden_present'))
            and host['pending_confirmed'] == 0 and host['queued_probe'] == host['queued_confirmed'] == -1
            and host['depth_probe'] == 0, 'draft must be synchronous and quiescent without depth probing')
    layouts, buffers = state['layouts'], state['buffers']
    require(isinstance(layouts, dict) and set(layouts) == set(buffers), 'draft layout inventory differs')
    lengths = {parts[0]: int(parts[2]) for parts in
               (line.split('\t') for line in index_raw.decode().splitlines()[1:])}
    canonical = {}
    for label, layout in layouts.items():
        require(label.startswith('card0:draft:') and len(label) > 12, 'draft allocation label required')
        name = BUNDLE.logical_name(label)
        require(isinstance(layout, dict) and type(layout.get('bytes')) is int
                and 0 < layout['bytes'] == lengths[name], 'draft layout byte extent differs: ' + label)
        require(type(layout.get('category')) is int and layout['category'] >= 0
                and layout.get('memory') in ('device', 'pinned'), 'draft allocation metadata: ' + label)
        semantic = layout.get('semantic')
        common = {'bytes', 'category', 'memory', 'semantic'}
        if semantic == 'typed-buffer':
            require(set(layout) == common | {'dtype', 'shape'}, 'draft typed layout fields: ' + label)
            dtype, shape = layout['dtype'], layout['shape']
            require(isinstance(dtype, str) and dtype.lower() in WIDTH and dtype == dtype.upper()
                    and isinstance(shape, list) and shape
                    and all(type(n) is int and n > 0 for n in shape)
                    and math.prod(shape) * WIDTH[dtype.lower()] == layout['bytes'],
                    'draft typed dtype/shape extent: ' + label)
        else:
            require(semantic == 'opaque-mutable-scratch' and set(layout) == common,
                    'unregistered draft allocation semantic: ' + label)
        canonical[label] = dict(layout=layout, sha256=hashes[name])
    for label in ('card0:draft:publication', 'card0:draft:half-staging'):
        require(label in layouts and layouts[label]['memory'] == 'pinned', 'missing pinned draft state: ' + label)
    require(layouts['card0:draft:publication']['bytes'] == 8, 'draft publication extent')
    position = canonical.get('card0:draft:position')
    require(position is not None and position['layout'].get('dtype') in ('I32', 'U32')
            and position['layout'].get('shape') == [1]
            and position['sha256'] == digest(struct.pack('<i', host['position'])),
            'draft sealed device position differs from host identity')
    return dict(input_identity=identity, host=host, canonical=canonical,
                sources=[receipt, state_receipt, index_receipt, seal_receipt],
                provenance=spec.get('provenance', {}))


def compare(reference, candidate):
    errors = []
    for field in ('input_identity', 'host'):
        if reference[field] != candidate[field]:
            errors.append(dict(field=field, reference=reference[field], candidate=candidate[field]))
    a, b = reference['canonical'], candidate['canonical']
    for key in sorted(a.keys() | b.keys()):
        if a.get(key) != b.get(key):
            errors.append(dict(source_key=key, reference=a.get(key), candidate=b.get(key)))
    return dict(schema='ownrt.draft-state-comparison.v1', passed=not errors, errors=errors,
                compared_source_keys=sorted(a.keys() & b.keys()),
                compared_bytes=sum(row['layout']['bytes'] for row in a.values()),
                reference=reference, candidate=candidate,
                scope='Every sealed mutable draft allocation, scratch, pinned transport and host state; no omissions. '
                      'Cross-run parity only, not independent model correctness or performance certification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    result = compare(load_set(args.reference), load_set(args.candidate))
    text = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        with args.out.open('x') as stream:
            stream.write(text)
    else:
        print(text, end='')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
