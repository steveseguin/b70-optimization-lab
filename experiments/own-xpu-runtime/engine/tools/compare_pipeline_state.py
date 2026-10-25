#!/usr/bin/env python3
"""Compare sealed target-only pipeline dumps after identical input/output tokens.

Usage: compare_pipeline_state.py --reference SET.json --candidate SET.json
Each ownrt.pipeline-state-set.v1 JSON declares mode="target-only", layer_count,
input_identity (model_sha256, prompt_token_sha256, output_token_sha256,
arithmetic, position), and stages [{id, begin, end, dump, plan, metadata}]. Paths
are relative to the set JSON. Plans need buffer {name, bytes, dtype, shape}
entries; metadata is the engine-emitted pipeline-stage.json sidecar.

All canonical layer buffers compare exactly by absolute layer name. Physical
spares are excluded only with the engine's explicit inactive-bank inventory
and target-only/no-speculation declaration. Legacy service MTP oracle hashes
lack layout/committed-bank identity;
they are not sufficient input for this target-only topology gate.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

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


def load_set(path):
    path = Path(path).resolve()
    raw, receipt = source(path)
    spec = json.loads(raw, object_pairs_hook=BUNDLE.pairs)
    require(spec['schema'] == 'ownrt.pipeline-state-set.v1' and spec['mode'] == 'target-only',
            'only declared target-only pipeline state sets are supported')
    total = spec['layer_count']
    require(type(total) is int and total > 0, 'positive layer_count required')
    identity = spec['input_identity']
    for key in ('model_sha256', 'prompt_token_sha256', 'output_token_sha256'):
        require(BUNDLE.hexhash(identity.get(key)), 'missing/invalid input identity: ' + key)
    require(isinstance(identity.get('arithmetic'), str) and bool(identity['arithmetic']), 'arithmetic identity required')
    require(type(identity.get('position')) is int and identity['position'] >= 0, 'position identity required')
    stages = spec['stages']
    require(isinstance(stages, list) and bool(stages), 'stage list required')
    canonical, excluded, sources = {}, [], [receipt]
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
                                     'reason': 'engine-declared inactive physical spare; target-only execution with speculation disabled',
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
    return {'input_identity': identity, 'layer_count': total, 'canonical': canonical,
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
            'scope': 'sealed target-only state/layout equality for identical declared input/output identities; not performance or CPU model fidelity',
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
