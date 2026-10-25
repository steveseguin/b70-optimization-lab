#!/usr/bin/env python3
"""Compare sealed committed pipeline dumps after identical input/output tokens.

Usage: compare_pipeline_state.py --reference SET.json --candidate SET.json
Each ownrt.pipeline-state-set.v1 JSON declares mode="target-only", layer_count,
input_identity (model_sha256, prompt_token_sha256, output_token_sha256,
arithmetic, position), and stages [{id, begin, end, dump, plan, metadata}]. Paths
are relative to the set JSON. Plans need buffer {name, bytes, dtype, shape}
entries; metadata is the engine-emitted pipeline-stage.json sidecar.
Version v2 declares mode="verified-wavefront", require_byte_verified_restores
(boolean), and a quiescence path on every stage pointing to the dump's sibling
<dump-name>.wavefront-state.json. Native quiescence and exact seal binding are
mandatory; v1 still admits target-only/no-speculation dumps only.
Version v3 explicitly admits mode="verified-ring", ring_request_sha256 and
ring_epoch. A sibling <dump-name>.ring-state.json and hash-bound native
ring-checkpoint-layout.json must attest a fully resolved target-only ring.

All canonical layer buffers compare exactly by absolute layer name. Physical
spares are excluded only with the engine's explicit inactive-bank inventory
and either target-only/no-speculation metadata or a validated sealed wavefront
quiescence attestation. Legacy service MTP oracle hashes lack layout/committed-
bank identity; they are not sufficient input for this topology gate.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct

LANE = Path(__file__).resolve().parents[2]
READER_PATH = LANE / 'gsq-rco-iq3s/state-bundle/reader.py'
SPEC = importlib.util.spec_from_file_location('sealed_state_reader', READER_PATH)
BUNDLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUNDLE)
LAYER = re.compile(r'^(?:alternate-)?blk\.(\d+)\.')
PERSISTENT = re.compile(r'(^alternate-|\.(keys|values|raw|pooled|state)\.bin$|history\.bin$)')
WIDTH = {'bf16': 2, 'f16': 2, 'f32': 4, 'i32': 4, 'u32': 4, 'i64': 8}
GLOBAL_ALL = {'position.bin', 'token.bin', 'active.bin', 'error.bin'}
GLOBAL_FIRST = {'embedding.bin', 'ple_metadata.bin', 'token_history.bin'}
GLOBAL_LAST = {'final.act.bin', 'final.gate.bin', 'final.low.bin', 'final.mix.bin',
               'final.norm.bin', 'logits.bin', 'next_token.bin', 'streams.bin'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source(path):
    data = path.read_bytes()
    return data, {'path': str(path), 'sha256': sha(data), 'bytes': len(data)}


def wavefront_attestation(path, stage, dump, metadata, identity, seal_source, hashes, lengths,
                          require_verified):
    declared = path.parent / stage['quiescence']
    require(not declared.is_symlink(), 'wavefront attestation symlink refused')
    attestation_path = declared.resolve()
    require(attestation_path == dump.with_name(dump.name + '.wavefront-state.json'),
            'wavefront attestation must be the explicit dump sibling')
    require(0 < attestation_path.stat().st_size <= 1024 * 1024, 'wavefront attestation size bound')
    raw, receipt = source(attestation_path)
    att = json.loads(raw, object_pairs_hook=BUNDLE.pairs)
    require(att['schema'] == 'ownrt.wavefront-state.v1' and att['mode'] == 'verified-wavefront',
            'unsupported wavefront attestation schema/mode')
    marker = re.fullmatch(r'state-(0|[1-9][0-9]*)', dump.name)
    require(marker is not None and type(att['dump_marker']) is int
            and att['dump_marker'] == int(marker[1]), 'wavefront dump marker differs')
    require(type(att['stage_id']) is int and att['stage_id'] == stage['id'], 'wavefront stage id differs')
    require(att['state_seal_sha256'] == seal_source['sha256'], 'wavefront state seal SHA256 differs')
    require(att['pending_ticket'] is False and type(att['pending_tickets']) is int
            and att['pending_tickets'] == 0 and att['checkpoint_active'] is False,
            'wavefront state is not quiescent: pending ticket/checkpoint')
    require(type(att['sticky_error']) is int and att['sticky_error'] == 0,
            'wavefront sticky error must be zero')
    for key in ('actual_position', 'committed_position', 'rows', 'tentative_rows', 'commits', 'aborts',
                'snapshot_captures', 'snapshot_commits', 'snapshot_aborts', 'abort_count',
                'byteverified_restore_count', 'abort_byte_checks', 'saved_bytes',
                'full_mutable_checkpoint_bytes', 'bank_parity'):
        require(type(att[key]) is int and 0 <= att[key] <= 2**64-1,
                'wavefront bounded nonnegative integer required: ' + key)
    position = identity['position']
    require(position <= 2**31-1 and att['actual_position'] == att['committed_position'] == position,
            'wavefront committed/actual position differs from set identity')
    # The bundle reader already authenticated every raw buffer; compare the
    # expected exact scalar encoding, without reopening a potentially changed payload.
    require(lengths.get('position.bin') == 4 and hashes.get('position.bin') == sha(struct.pack('<I', position)),
            'wavefront sealed state position differs from attestation/set identity')
    require(lengths.get('error.bin') == 4 and hashes.get('error.bin') == sha(bytes(4)),
            'wavefront sealed sticky error differs from zero')
    require(att['rows'] == att['commits'] + att['aborts'] and att['commits'] == position,
            'wavefront ledger row/commit/abort accounting differs')
    require(att['tentative_rows'] == att['snapshot_captures'] <= att['rows']
            and att['snapshot_captures'] == att['snapshot_commits'] + att['snapshot_aborts']
            and att['snapshot_commits'] <= att['commits']
            and att['snapshot_aborts'] == att['aborts'] == att['abort_count'],
            'wavefront snapshot/ledger accounting differs')
    require(0 < att['full_mutable_checkpoint_bytes'] <= 512 * 1024**2
            and att['saved_bytes'] == att['full_mutable_checkpoint_bytes'] * att['snapshot_captures'],
            'wavefront saved-byte accounting differs')
    require(type(att['restore_verification_enabled']) is bool
            and type(att['all_aborts_byte_verified']) is bool
            and att['byteverified_restore_count'] == att['abort_byte_checks'] <= att['abort_count']
            and att['all_aborts_byte_verified'] is (att['abort_count'] == att['abort_byte_checks']),
            'wavefront restore verification accounting differs')
    if require_verified:
        require(att['restore_verification_enabled'] is True and att['all_aborts_byte_verified'] is True
                and att['abort_count'] == att['byteverified_restore_count'],
                'wavefront proof requires byte-verified restoration of every abort')
    if att['restore_verification_enabled']:
        require(att['abort_count'] == att['abort_byte_checks'], 'enabled wavefront verification missed an abort')
    else:
        require(att['abort_byte_checks'] == 0, 'disabled wavefront verification cannot report byte checks')
    require(att['bank_parity'] == (position % 2 if stage['id'] == 0 else 0),
            'wavefront canonical bank parity differs')
    inactive = metadata['inactive_alternate_banks']
    require(isinstance(att['inactive_alternate_banks'], list)
            and len(att['inactive_alternate_banks']) == len(inactive)
            and set(att['inactive_alternate_banks']) == set(inactive),
            'wavefront inactive-bank inventory differs from initial metadata')
    mapping = att['canonical_bank_mapping']
    require(isinstance(mapping, dict) and set(mapping) == set(inactive), 'wavefront canonical bank mapping coverage')
    allocations = []
    for name, row in mapping.items():
        require(isinstance(row, dict) and set(row) == {'active_allocation', 'inactive_allocation'}
                and all(type(v) is int and 0 < v <= 2**64-1 for v in row.values()),
                'wavefront canonical bank allocation identity: ' + name)
        allocations.extend(row.values())
    require(len(allocations) == len(set(allocations)), 'wavefront canonical/inactive banks alias')
    return att, receipt


def ring_attestation(path, stage, dump, metadata, identity, seal_source, hashes, lengths, spec):
    declared = path.parent / stage['quiescence']
    require(not declared.is_symlink(), 'ring attestation symlink refused')
    att_path = declared.resolve()
    require(att_path == dump.with_name(dump.name + '.ring-state.json'), 'ring attestation must be exact dump sibling')
    require(0 < att_path.stat().st_size <= 1024 * 1024, 'ring attestation size bound')
    raw, receipt = source(att_path)
    att = json.loads(raw, object_pairs_hook=BUNDLE.pairs)
    require(att['schema'] == 'ownrt.ring-state.v1' and att['mode'] == 'verified-ring', 'unsupported ring attestation schema/mode')
    marker = re.fullmatch(r'state-(0|[1-9][0-9]*)', dump.name)
    require(marker is not None and type(att['dump_marker']) is int and att['dump_marker'] == int(marker[1]), 'ring dump marker differs')
    require(type(att['stage_id']) is int and att['stage_id'] == stage['id'], 'ring stage identity differs')
    require(att['state_seal_sha256'] == seal_source['sha256'], 'ring dump seal SHA differs')
    require(att['ring_request_sha256'] == spec['ring_request_sha256']
            and type(att['ring_epoch']) is int and att['ring_epoch'] == spec['ring_epoch'], 'ring request/epoch identity differs')
    for key in ('ring_capacity','depth','actual_position','committed_position','pending_tickets','active_slots','sticky_error',
                'rows','tentative_rows','commits','accepted_tentative_rows','abort_count','discarded_rows',
                'snapshot_captures','snapshot_releases','byteverified_restore_count','saved_bytes',
                'target_mutable_checkpoint_bytes','bank_parity','max_pending','trace_records','trace_omitted'):
        require(type(att[key]) is int and 0 <= att[key] <= 2**64-1, 'ring bounded nonnegative integer required: '+key)
    require(att['ring_capacity'] == att['depth'] == 2, 'ring depth/capacity must be explicit two')
    require(att['pending_tickets'] == att['active_slots'] == att['sticky_error'] == 0, 'ring is not quiescent/error-free')
    position = identity['position']
    require(position <= 2**31-1 and att['actual_position'] == att['committed_position'] == att['commits'] == position,
            'ring physical/committed position differs')
    require(lengths.get('position.bin') == 4 and hashes.get('position.bin') == sha(struct.pack('<I',position))
            and lengths.get('error.bin') == 4 and hashes.get('error.bin') == sha(bytes(4)), 'ring sealed position/error differs')
    require(att['rows'] == att['commits'] + att['discarded_rows']
            and att['snapshot_captures'] == att['tentative_rows'] == att['snapshot_releases']
            == att['accepted_tentative_rows'] + att['discarded_rows']
            and att['accepted_tentative_rows'] <= att['commits'], 'ring capture/release/row conservation differs')
    require((att['abort_count'] == att['discarded_rows'] == 0) or
            (0 < att['abort_count'] <= att['discarded_rows'] <= 2*att['abort_count']), 'ring suffix abort/discard accounting differs')
    require(att['trace_records'] + att['trace_omitted'] == att['rows'] + att['commits'] + att['abort_count']
            and (att['max_pending'] == 0 if att['rows'] == 0 else 1 <= att['max_pending'] <= (1 if metadata['final'] else 2)),
            'ring trace/maximum pending accounting differs')
    require(type(att['restore_verification_enabled']) is bool and type(att['all_aborts_byte_verified']) is bool
            and att['byteverified_restore_count'] <= att['abort_count']
            and att['all_aborts_byte_verified'] is (att['byteverified_restore_count'] == att['abort_count']),
            'ring restore verification accounting differs')
    require(att['byteverified_restore_count'] == (att['abort_count'] if att['restore_verification_enabled'] else 0),
            'ring declared restore policy differs from checks')
    if spec['require_byte_verified_restores']:
        require(att['restore_verification_enabled'] is True and att['all_aborts_byte_verified'] is True,
                'ring proof requires every restore byte-verified')
    if metadata['final']:
        require(att['tentative_rows'] == att['abort_count'] == att['discarded_rows'] == 0,
                'ring final stage must not speculate')
    size = att['target_mutable_checkpoint_bytes']
    require(0 < size <= 256*1024**2 and att['saved_bytes'] == size*att['snapshot_captures'], 'ring snapshot byte accounting differs')
    layout_path = dump.parent/'ring-checkpoint-layout.json'
    require(not layout_path.is_symlink() and 0 < layout_path.stat().st_size <= 4*1024**2, 'ring layout regular bounded file required')
    layout_raw, layout_source = source(layout_path)
    require(layout_source['sha256'] == att['checkpoint_layout_sha256'], 'ring checkpoint layout SHA differs')
    layout = json.loads(layout_raw, object_pairs_hook=BUNDLE.pairs)
    require(layout['schema'] == 'ownrt.ring-checkpoint-layout.v1'
            and layout['complete_target_owned_mutable_allocations'] is True and layout['provider_present'] is False
            and type(layout['ring_capacity']) is int and layout['ring_capacity'] == 2
            and type(layout['slot_bytes']) is int and layout['slot_bytes'] == size, 'ring complete target-only layout required')
    allocations, labels = set(), set()
    for key in ('allocations','excluded_private_runtime_allocations','checkpoint_private_allocations'):
        require(isinstance(layout[key],list), 'ring layout allocation list required')
        for row in layout[key]:
            require(type(row['id']) is int and 0 < row['id'] <= 2**64-1 and row['id'] not in allocations
                    and isinstance(row['label'],str) and bool(row['label']) and row['label'] not in labels
                    and type(row['bytes']) is int and 0 < row['bytes'] <= 256*1024**2,
                    'ring layout overlapping/invalid allocation identity')
            allocations.add(row['id']);labels.add(row['label'])
    require(layout['allocations'] and sum(row['bytes'] for row in layout['allocations']) == size,
            'ring target allocation extent differs')
    legacy = {'card0:speculative-private-image','card0:speculative-copy-table','card0:speculative-static-copy-table'}
    require({r['label'] for r in layout['excluded_private_runtime_allocations']} <= legacy,
            'ring unregistered private-state exclusion')
    private = layout['checkpoint_private_allocations']
    require({r['label'] for r in private} == {f'card0:ring:{i}:{kind}' for i in (0,1) for kind in ('image','capture','restore')}
            and all(r['bytes'] == size for r in private if r['label'].endswith(':image'))
            and sum(r['bytes'] for r in private) <= 512*1024**2, 'ring two-slot private inventory differs')
    require(att['bank_parity'] == (position % 2 if stage['id'] == 0 else 0), 'ring canonical bank parity differs')
    inactive = metadata['inactive_alternate_banks']
    require(isinstance(att['inactive_alternate_banks'],list) and len(att['inactive_alternate_banks']) == len(inactive)
            and set(att['inactive_alternate_banks']) == set(inactive), 'ring inactive-bank inventory differs')
    mapping = att['canonical_bank_mapping']
    require(isinstance(mapping,dict) and set(mapping) == set(inactive), 'ring canonical-bank coverage differs')
    banks = []
    for name,row in mapping.items():
        require(isinstance(row,dict) and set(row) == {'active_allocation','inactive_allocation'}
                and all(type(v) is int and 0 < v <= 2**64-1 for v in row.values()), 'ring bank allocation identity: '+name)
        banks.extend(row.values())
    require(len(banks) == len(set(banks)) and set(banks) <= {r['id'] for r in layout['allocations']},
            'ring canonical/inactive banks alias or are absent from target inventory')
    return att, receipt, layout_source


def load_set(path):
    path = Path(path).resolve()
    raw, receipt = source(path)
    spec = json.loads(raw, object_pairs_hook=BUNDLE.pairs)
    mode = spec['mode']
    wavefront = spec['schema'] == 'ownrt.pipeline-state-set.v2' and mode == 'verified-wavefront'
    ring = spec['schema'] == 'ownrt.pipeline-state-set.v3' and mode == 'verified-ring'
    require((spec['schema'] == 'ownrt.pipeline-state-set.v1' and mode == 'target-only') or wavefront or ring,
            'unsupported pipeline state set schema/mode; v1 target-only, v2 verified-wavefront or v3 verified-ring required')
    if wavefront or ring:
        require(type(spec.get('require_byte_verified_restores')) is bool,
                'speculative proof must explicitly declare require_byte_verified_restores')
    if ring:
        require(BUNDLE.hexhash(spec.get('ring_request_sha256')) and type(spec.get('ring_epoch')) is int
                and 0 <= spec['ring_epoch'] <= 2**64-1, 'ring request/epoch identity required')
    total = spec['layer_count']
    require(type(total) is int and total > 0, 'positive layer_count required')
    identity = spec['input_identity']
    for key in ('model_sha256', 'prompt_token_sha256', 'output_token_sha256'):
        require(BUNDLE.hexhash(identity.get(key)), 'missing/invalid input identity: ' + key)
    require(isinstance(identity.get('arithmetic'), str) and bool(identity['arithmetic']), 'arithmetic identity required')
    require(type(identity.get('position')) is int and identity['position'] >= 0, 'position identity required')
    stages = spec['stages']
    require(isinstance(stages, list) and bool(stages), 'stage list required')
    canonical, excluded, sources, attestations = {}, [], [receipt], []
    cursor = 0
    boundaries = [stage['begin'] for stage in stages] + [stages[-1]['end']]
    first_history = None
    for ordinal, stage in enumerate(stages):
        require(stage['id'] == ordinal and type(stage['id']) is int, 'stage ids must be ordered 0..N-1')
        begin, end = stage['begin'], stage['end']
        require(type(begin) is int and type(end) is int and begin == cursor and begin < end <= total,
                'stage ranges must partition all layers without gaps/overlaps')
        cursor = end
        dump, plan_path = (path.parent / stage['dump']).resolve(), (path.parent / stage['plan']).resolve()
        metadata_path = (path.parent / stage['metadata']).resolve()
        metadata_raw, metadata_source = source(metadata_path)
        metadata = json.loads(metadata_raw, object_pairs_hook=BUNDLE.pairs)
        if ring:
            require(metadata['schema'] == 'ownrt.pipeline-stage.v1' and metadata['mode'] == 'verified-ring'
                    and metadata['speculation_enabled'] is True
                    and type(metadata['ring_capacity']) is int and metadata['ring_capacity'] == 2
                    and type(metadata['depth']) is int and metadata['depth'] == 2
                    and metadata['ring_request_sha256'] == spec['ring_request_sha256']
                    and type(metadata['ring_epoch']) is int and metadata['ring_epoch'] == spec['ring_epoch'],
                    'engine ring/speculation metadata required')
        elif wavefront:
            require(metadata['schema'] == 'ownrt.pipeline-stage.v1' and metadata['mode'] == 'wavefront'
                    and metadata['speculation_enabled'] is True, 'engine wavefront/speculation metadata required')
        else:
            require(metadata['schema'] == 'ownrt.pipeline-stage.v1' and metadata['mode'] == 'target-only'
                    and metadata['speculation_enabled'] is False, 'engine target-only/no-speculation metadata required')
        require(metadata['stage_id'] == ordinal and metadata['stage_count'] == len(stages)
                and metadata['begin'] == begin and metadata['end'] == end
                and metadata['first'] is (ordinal == 0) and metadata['final'] is (ordinal == len(stages) - 1)
                and metadata['boundaries'] == boundaries, 'engine stage metadata differs from declared partition')
        require(metadata.get('activation_dtype') == 'F32' and type(metadata.get('stream_bytes')) is int
                and metadata['stream_bytes'] > 0, 'explicit F32 boundary layout required')
        inactive = metadata['inactive_alternate_banks']
        require(isinstance(inactive, list) and len(set(inactive)) == len(inactive)
                and all(isinstance(name, str) and re.fullmatch(r'blk\.\d+\.(gdn\.(state|history)|ple\.history)', name) for name in inactive),
                'unregistered or duplicate inactive alternate bank')
        sources.append(metadata_source)
        hashes = BUNDLE.read_state(dump)  # validates bytes, seals, exact inventory and stable file identities
        state_raw, state_source = source(dump / 'state.json')
        state = json.loads(state_raw, object_pairs_hook=BUNDLE.pairs)
        index_raw, index_source = source(dump / 'state-index.tsv')
        seal_raw, seal_source = source(dump / 'state-seal.txt')
        seal = seal_raw.decode().splitlines()
        require(sha(state_raw) == seal[4] == hashes['state.json'] and sha(index_raw) == seal[3],
                'metadata changed after sealed read')
        sources += [state_source, index_source, seal_source]
        lengths = {parts[0]: int(parts[2]) for parts in (line.split('\t') for line in index_raw.decode().splitlines()[1:])}
        if wavefront:
            att, att_source = wavefront_attestation(path, stage, dump, metadata, identity, seal_source, hashes,
                                                   lengths, spec['require_byte_verified_restores'])
            attestations.append({'stage': ordinal, 'attestation': att, 'source': att_source})
            sources.append(att_source)
        if ring:
            att, att_source, layout_source = ring_attestation(path,stage,dump,metadata,identity,seal_source,hashes,lengths,spec)
            attestations.append({'stage':ordinal,'attestation':att,'source':att_source,'layout_source':layout_source})
            sources += [att_source,layout_source]
        plan_raw, plan_source = source(plan_path)
        plan = json.loads(plan_raw, object_pairs_hook=BUNDLE.pairs)
        sources.append(plan_source)
        # Mirrors banks(): only conv/gdn's second, read-write output is banked.
        # This includes PLE convolution history, not just GDN history/state.
        for name in inactive:
            producers = [launch for launch in plan.get('launches', [])
                         if launch.get('op') in ('conv', 'gdn') and len(launch.get('outputs', [])) == 2
                         and launch['outputs'][1] == name and name in launch.get('inputs', [])]
            require(len(producers) == 1, 'inactive bank lacks unique registered temporal producer: ' + name)
        layouts = {}
        for buffer in plan['buffers']:
            name = buffer['name'] + '.bin'
            require(name not in layouts, 'duplicate plan buffer: ' + name)
            dtype, shape, size = buffer.get('dtype'), buffer.get('shape'), buffer['bytes']
            dtype = dtype.lower() if isinstance(dtype, str) else dtype
            require(dtype in WIDTH and isinstance(shape, list) and bool(shape)
                    and all(type(n) is int and n > 0 for n in shape), 'missing/invalid dtype or shape for ' + name)
            require(type(size) is int and size == math.prod(shape) * WIDTH[dtype], 'layout byte count differs for ' + name)
            layouts[name] = {'dtype': dtype, 'shape': shape, 'bytes': size}
        base_names = {k for k in hashes if k != 'state.json' and not k.startswith('alternate-')}
        require(base_names == set(layouts), 'plan/state base buffer inventory differs')
        require('streams.bin' in layouts and layouts['streams.bin']['dtype'] == 'f32'
                and layouts['streams.bin']['bytes'] == metadata['stream_bytes'], 'stage boundary metadata/layout mismatch')
        if wavefront or ring:
            require(all(layouts.get(name, {}).get('dtype') in {'i32', 'u32'}
                        and layouts[name]['shape'] == [1] for name in ('position.bin', 'error.bin')),
                    'speculative position/error require scalar integer layouts')
        require({k for k in hashes if k.startswith('alternate-')} == {'alternate-' + name + '.bin' for name in inactive},
                'actual alternate-bank inventory differs from engine declaration')
        seen_layers = set()
        for key, digest in hashes.items():
            if key == 'state.json':
                continue
            base = key.removeprefix('alternate-')
            require(base in layouts, 'alternate bank has no base layout: ' + key)
            require(lengths[key] == layouts[base]['bytes'], 'state/plan byte length differs: ' + key)
            match = LAYER.match(key)
            role = None
            if match:
                layer = int(match.group(1))
                require(begin <= layer < end, 'layer buffer outside declared stage: ' + key)
                seen_layers.add(layer)
                if key.startswith('alternate-'):
                    require(base in base_names, 'inactive bank has no canonical committed buffer')
                    excluded.append({'stage': ordinal, 'source_key': key, 'sha256': digest,
                                     'reason': (f'engine-declared inactive physical spare; sealed quiescent {mode} canonical bank attested'
                                                if wavefront or ring else 'engine-declared inactive physical spare; target-only execution with speculation disabled'),
                                     'metadata_source': str(metadata_path), **layouts[base]})
                    continue
                role = 'persistent-layer' if PERSISTENT.search(key) else 'layer-intermediate'
            elif key in GLOBAL_ALL:
                role = 'replicated-global'
            elif key in GLOBAL_FIRST:
                require(ordinal == 0, 'first-stage state on another stage: ' + key)
                role = 'first-stage-global'
            elif key in GLOBAL_LAST:
                if ordinal == len(stages) - 1:
                    role = 'last-stage-global'
                elif key in {'streams.bin', 'next_token.bin'}:
                    excluded.append({'stage': ordinal, 'source_key': key, 'sha256': digest,
                                     'reason': 'stage-boundary activation, not final stream' if key == 'streams.bin'
                                     else 'nonfinal stage has no output-head writer', **layouts[base]})
                    continue
                else:
                    raise ValueError('output/head state on nonfinal stage: ' + key)
            else:
                raise ValueError('unregistered global buffer; explicit semantics required: ' + key)
            value = {'sha256': digest, **layouts[base]}
            entry = {'stage': ordinal, 'dump': str(dump), 'source_key': key, 'role': role, **value}
            if key in canonical:
                require(role == 'replicated-global', 'target state occurs more than once: ' + key)
                require(value == {k: canonical[key][k] for k in value}, 'replicated global differs within pipeline: ' + key)
                canonical[key]['replicated_sources'].append(entry)
            else:
                canonical[key] = dict(entry, replicated_sources=[])
        require(seen_layers == set(range(begin, end)), 'declared stage has missing layer buffers')
        require(GLOBAL_ALL <= base_names, 'stage lacks required position/token/status buffers')
        if ordinal == 0:
            require('token_history.bin' in base_names, 'first-stage PLE token history required')
            require('history0' in state and 'history1' in state, 'first-stage host PLE history required')
            first_history = {'history0': state['history0'], 'history1': state['history1']}
        if ordinal == len(stages) - 1:
            require({'logits.bin', 'next_token.bin', 'streams.bin'} <= base_names, 'last-stage head/output buffers required')
    require(cursor == total, 'stage ranges do not cover all layers')
    return {'mode': mode, 'input_identity': identity, 'layer_count': total, 'canonical': canonical,
            'require_byte_verified_restores': spec.get('require_byte_verified_restores') if wavefront or ring else None,
            'quiescence_attestations': attestations,
            'first_stage_host_history': first_history, 'excluded': excluded, 'sources': sources}


def compare(reference, candidate):
    errors = []
    for key in ('input_identity', 'layer_count', 'first_stage_host_history'):
        if reference[key] != candidate[key]:
            errors.append({'field': key, 'reference': reference[key], 'candidate': candidate[key]})
    a, b = reference['canonical'], candidate['canonical']
    for key in sorted(a.keys() | b.keys()):
        if key not in a or key not in b:
            errors.append({'source_key': key, 'error': 'missing state', 'reference_present': key in a, 'candidate_present': key in b})
            continue
        mismatch = [field for field in ('sha256', 'bytes', 'dtype', 'shape', 'role') if a[key][field] != b[key][field]]
        if mismatch:
            errors.append({'source_key': key, 'fields': mismatch, 'reference': a[key], 'candidate': b[key]})
    return {'schema': 'ownrt.pipeline-state-comparison.v1', 'passed': not errors,
            'scope': 'sealed committed state/layout equality for identical declared input/output identities; speculative inputs require native quiescence attestations; not performance or CPU model fidelity',
            'compared_source_keys': sorted(a.keys() & b.keys()), 'errors': errors,
            'reference': reference, 'candidate': candidate,
            'comparator_sha256': sha(Path(__file__).read_bytes()), 'sealed_reader_sha256': sha(READER_PATH.read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = compare(load_set(args.reference), load_set(args.candidate))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result = {'schema': 'ownrt.pipeline-state-comparison.v1', 'passed': False, 'input_error': str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
