#!/usr/bin/env python3
"""CPU-only exact packet99b -> packet100 placement transition and launch contract."""
import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-upstream-99b'
PARENT_SHA = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
PACKET = ROOT / 'prepared-encoder-rebalance-100'
LAYOUT = 'two-way20-28'
SEGMENTS = (('xpu:0', 0, 20), ('xpu:1', 20, 48))
SHARD = 'source/scripts/ltx_layer_shard.py'
CAPTURE = 'source/scripts/ltx_graph_capture.py'
COMMON = 'launch/encoder_runtime_common.py'
LAUNCHER = 'launch/serve-encoder.py'
CHANGED = (SHARD, CAPTURE, COMMON, LAUNCHER)
STATUS = b'Packet100 20/28 placement candidate; no GPU, parity or speed qualification.\n'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj


# Bootstrap only from the exact immutable parent, never a refreshed parent pin.
_parent_raw = (PARENT / 'manifest.json').read_bytes()
require(digest(_parent_raw) == PARENT_SHA, 'Packet99b parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
_parent_checker = PARENT / COMMON
require(not _parent_checker.is_symlink() and digest(_parent_checker.read_bytes()) ==
        _parent_manifest['files'][COMMON], 'Packet99b checker changed')
BASE = load(_parent_checker, 'packet100_immutable_parent')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module


def __getattr__(name):
    # All unchanged runtime, health, progress, dependency and model checks remain
    # the real parent's functions. No global mutation or false old identity.
    return getattr(BASE, name)


def source_delta(shard, capture):
    anchor = "    'two-way': (('xpu:0', 0, 23), ('xpu:1', 23, 48)),\n"
    added = "    'two-way20-28': (('xpu:0', 0, 20), ('xpu:1', 20, 48)),\n"
    result = BASE.replace_once(shard.decode(), anchor, anchor + added).encode()
    old = 'SHARD_SOURCE_SHA256 = ' + repr(digest(shard))
    changed = BASE.replace_once(capture.decode(), old,
                                'SHARD_SOURCE_SHA256 = ' + repr(digest(result))).encode()
    ast.parse(result); ast.parse(changed)
    return {SHARD: result, CAPTURE: changed}


def launcher_source(raw):
    text = BASE.replace_once(raw.decode(),
        "encoder-server-upstream-99b-two-way-w2-b1-p1-dxpu2-s256x256",
        "encoder-server-rebalance-100-two-way20-28-w2-b1-p1-dxpu2-s256x256")
    text = BASE.replace_once(text, 'Packet99b admits only the frozen batch-one compatibility control',
                            'Packet100 admits only the 20/28 batch-one candidate')
    text = BASE.replace_once(text, "    identity = {'runtime99b_transition': manifest['rope99b'],",
                            "    identity = {'runtime100_transition': manifest['rebalance100'],\n"
                            "                'runtime99b_transition': manifest['rope99b'],")
    ast.parse(text)
    return text.encode()


def check_control_environment():
    expected = {'LTX_OUTPUT_SIZE': '256x256', 'LTX_BUSY_WINDOWS': '0',
                'LTX_SAMPLER_PLACEMENT': LAYOUT, 'LTX_SAMPLER_WORKERS': '2',
                'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
    require(all(os.environ.get(k) == v for k, v in expected.items()),
            'Explicit packet100 candidate environment differs')


def semantic_manifest(parent, files, builder_sha, transition):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.rebalance-runtime-packet.v1', files=files,
                  preparer_sha256=builder_sha, rebalance100=transition)
    result['sampler_placement']['placements'][LAYOUT] = [list(x) for x in SEGMENTS]
    for name in ('ltx_layer_shard.py', 'ltx_graph_capture.py'):
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    for section in ('graph_capture', 'sampler_shared_pool'):
        result[section]['adapter_sha256'] = files[CAPTURE]
    for name in result['startup_tools']:
        result['startup_tools'][name] = files['launch/' + name]
    return result


def control():
    return {'layout': LAYOUT, 'blocks': [20, 28], 'workers': 2, 'batch': 1,
            'shared_pool': 1, 'decode_replica': 'xpu:2', 'size': '256x256', 'references': 'w93c'}


def validate_basis(helper, path, expected_sha):
    require(re.fullmatch('[0-9a-f]{64}', expected_sha or '') and sha(path) == expected_sha,
            'Qualified packet99b control basis changed')
    # This helper owns the one frozen99b qualification/memory receipt schema.
    result = helper.validate_control_basis(path, expected_sha)
    require(result['admitted'] is True and result['control_manifest_sha256'] == PARENT_SHA,
            'Qualified exact99b basis must admit the conservative20/28 projection')
    return result


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET, 'Unexpected packet100 destination')
    raw = regular(packet / 'manifest.json')
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            digest(raw) == expected_manifest_sha256, 'Packet100 manifest changed')
    manifest = BASE.load_json(raw); files = manifest['files']
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    require(regular(packet / 'STATUS.txt') == STATUS, 'Candidate status differs')
    expected_delta = source_delta(regular(PARENT / SHARD), regular(PARENT / CAPTURE))
    expected_delta[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    expected_delta[COMMON] = regular(packet / 'provenance/check-runtime-100.py')
    for path, expected in parent['files'].items():
        want = digest(expected_delta[path]) if path in expected_delta else expected
        require(files.get(path) == want, 'Changed/missing inherited file beyond exact delta: ' + path)
        require(stat.S_IMODE((packet / path).stat().st_mode) ==
                stat.S_IMODE((PARENT / path).stat().st_mode), 'Inherited file mode changed: ' + path)
    transition = manifest['rebalance100']
    require(set(transition) == {'schema', 'parent_packet', 'parent_manifest_sha256', 'control',
            'source_delta', 'campaign_bindings', 'control_basis', 'storage_admission',
            'qualification', 'model_requests'}, 'Transition fields differ')
    require(transition['schema'] == 'ltx.rebalance100.transition.v1' and
            transition['parent_packet'] == str(PARENT) and transition['parent_manifest_sha256'] == PARENT_SHA and
            transition['control'] == control() and transition['qualification'] is False and
            transition['model_requests'] == 0, 'Transition identity differs')
    require(transition['source_delta'] == {
        p: {'before_sha256': parent['files'][p], 'after_sha256': digest(expected_delta[p])}
        for p in (SHARD, CAPTURE)}, 'Source delta receipt differs')
    require(regular(packet / 'provenance/packet99b-manifest.json') == regular(PARENT / 'manifest.json'),
            'Parent provenance differs')
    for path in CHANGED:
        require(regular(packet / 'provenance/packet99b' / path) == regular(PARENT / path),
                'Original changed file provenance differs')
    bindings = transition['campaign_bindings']
    require(set(bindings) == {'runner', 'memory_helper'}, 'Campaign helper inventory differs')
    for kind, binding in bindings.items():
        filename = {'runner': 'run-campaign-100.sh', 'memory_helper': 'worker-headroom-100.py'}[kind]
        require(set(binding) == {'source', 'sha256', 'packet_path'} and
                binding['packet_path'] == 'campaign/' + filename and Path(binding['source']).name == filename,
                'Campaign helper binding differs')
        require(sha(Path(binding['source'])) == binding['sha256'] == files[binding['packet_path']],
                'Campaign helper changed: ' + kind)
    basis = transition['control_basis']
    require(set(basis) == {'source', 'sha256', 'packet_path'} and
            basis['packet_path'] == 'provenance/control-basis.json', 'Control basis fields differ')
    require(regular(packet / basis['packet_path']) == regular(Path(basis['source'])), 'Control basis copy differs')
    helper = module(packet / bindings['memory_helper']['packet_path'], 'packet100_checked_memory')
    validate_basis(helper, Path(basis['source']), basis['sha256'])
    extra = {'provenance/build-runtime-100.py', 'provenance/check-runtime-100.py',
             'provenance/packet99b-manifest.json', basis['packet_path']}
    extra.update('provenance/packet99b/' + p for p in CHANGED)
    extra.update(v['packet_path'] for v in bindings.values())
    require(set(files) == set(parent['files']) | extra, 'Packet100 inventory differs')
    checker = module(PARENT / 'provenance/source99/check-upstream-source-99.py', 'packet100_inventory')
    require(checker.inventory(packet) == set(files) | {'manifest.json', 'STATUS.txt'}, 'Unbound packet files')
    for path, expected in files.items():
        require(sha(safe_path(packet, path)) == expected, 'Packet100 file changed: ' + path)
    require(manifest == semantic_manifest(parent, files, sha(packet / 'provenance/build-runtime-100.py'), transition),
            'Packet100 semantic contract changed beyond declared delta')
    return manifest


def self_test():
    from unittest import mock
    original = regular(PARENT / SHARD); capture = regular(PARENT / CAPTURE)
    delta = source_delta(original, capture)
    tree = ast.parse(delta[SHARD]); oldtree = ast.parse(original)
    # The only AST difference in numerical code is the allowlist constant.
    strip = lambda t: [ast.dump(n) for n in t.body if not (isinstance(n, ast.Assign) and
                       any(isinstance(x, ast.Name) and x.id == 'PLACEMENTS' for x in n.targets))]
    require(strip(tree) == strip(oldtree), 'Numerical source changed')
    selected = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in ('segment_plan', 'memory_plan'):
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id in
             ('PLACEMENTS', 'DECLARED_SPLIT_INDEX', 'PLAN_GIB_PER_BLOCK', 'MEMORY_FLOOR_GIB') for x in node.targets):
            selected.append(node)
    ns = {}; exec(compile(ast.Module(body=selected, type_ignores=[]), '<CPU placement functions>', 'exec'), ns)
    require(ns['DECLARED_SPLIT_INDEX'] == 23 and ns['PLACEMENTS']['two-way'] ==
            (('xpu:0', 0, 23), ('xpu:1', 23, 48)), 'Old layout changed')
    plan = ns['segment_plan'](ns['PLACEMENTS'][LAYOUT])
    require(len(plan) == 48 and sum(p[0] == 'xpu:0' for p in plan) == 20 and
            sum(p[0] == 'xpu:1' for p in plan) == 28 and
            all(p[1] == 'xpu:0' for p in plan) and [i for i, p in enumerate(plan) if p[2]] == [47],
            'Placement coverage/device routing differs')
    for bad in [(('xpu:0', 0, 20), ('xpu:1', 21, 48)),
                (('xpu:0', 0, 21), ('xpu:1', 20, 48)),
                (('xpu:0', 0, 20), ('xpu:0', 20, 48))]:
        try:
            ns['segment_plan'](bad)
        except ValueError:
            pass
        else:
            raise RuntimeError('Invalid placement admitted')
    ns['memory_plan'](SEGMENTS, {'xpu:0': 21.4, 'xpu:1': 29.16})
    try:
        ns['memory_plan'](SEGMENTS, {'xpu:0': 21.4, 'xpu:1': 29.15})
    except RuntimeError:
        pass
    else:
        raise RuntimeError('Below-floor placement admitted')
    for left, right in ((original + b"\n" + original, capture), (delta[SHARD], capture)):
        try:
            source_delta(left, right)
        except RuntimeError:
            pass
        else:
            raise RuntimeError('Ambiguous/repeated source transformation admitted')
    before = ast.parse(regular(PARENT / LAUNCHER)); after = ast.parse(launcher_source(regular(PARENT / LAUNCHER)))
    before_f = {n.name: ast.dump(n) for n in before.body if isinstance(n, ast.FunctionDef)}
    after_f = {n.name: ast.dump(n) for n in after.body if isinstance(n, ast.FunctionDef)}
    require({n for n in before_f if before_f[n] != after_f[n]} == {'prepare_start', 'launch'},
            'Unrelated launcher function changed')
    parent = copy.deepcopy(_parent_manifest)
    files = dict(parent['files']); files.update({p: digest(v) for p, v in delta.items()})
    candidate = semantic_manifest(parent, files, 'a' * 64, {})
    require(candidate['upstream99'] == parent['upstream99'] and candidate['rope99b'] == parent['rope99b'] and
            candidate['runtime'] == parent['runtime'] and
            candidate['sampler_placement']['default'] == 'two-way' and
            candidate['sampler_shared_pool']['adapter_sha256'] == digest(delta[CAPTURE]), 'Semantic identity changed')
    launch_text = launcher_source(regular(PARENT / LAUNCHER)).decode()
    ordering = [launch_text.index(x) for x in ('    import comfy.quant_ops',
                '    rope_compat = common.install_rope_compat(packet)',
                "    identity['rope_compatibility'] = rope_compat",
                "    write_json(run / 'server-identity.json', identity)",
                "    write_json(run / 'determinism-after-import.json',",
                "    runpy.run_path(str(packet / 'source/main.py')")]
    require(ordering == sorted(ordering) and
            launch_text.count("write_json(run / 'server-identity.json', identity)") == 1 and
            __getattr__('install_rope_compat') is BASE.install_rope_compat,
            'Inherited process-local RoPE activation/receipt ordering changed')
    added_provenance = {'provenance/packet99b/' + p for p in CHANGED} | {'provenance/packet99b-manifest.json'}
    require(not added_provenance.intersection(parent['files']), 'Parent provenance would be overwritten')
    # Candidate environment matches the parent's frozen contract except layout.
    expected_env = {'LTX_OUTPUT_SIZE': '256x256', 'LTX_BUSY_WINDOWS': '0',
                    'LTX_SAMPLER_PLACEMENT': LAYOUT, 'LTX_SAMPLER_WORKERS': '2',
                    'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                    'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                    'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
    with mock.patch.dict(os.environ, expected_env, clear=True):
        check_control_environment()
        for name in expected_env:
            with mock.patch.dict(os.environ, {name: 'wrong'}):
                try:
                    check_control_environment()
                except RuntimeError:
                    pass
                else:
                    raise RuntimeError('Wrong control environment admitted: ' + name)
        with mock.patch.dict(os.environ, {'LTX_SAMPLER_PLACEMENT': 'two-way'}):
            BASE.check_control_environment()
    # No filesystem writes/model imports: fake only the bound receipt transport.
    helper = mock.Mock()
    with mock.patch.dict(globals(), {'sha': lambda path: 'b' * 64}):
        for admitted, parent_sha in [(False, PARENT_SHA), (True, 'c' * 64)]:
            helper.validate_control_basis.return_value = {'admitted': admitted,
                                                          'control_manifest_sha256': parent_sha}
            try:
                validate_basis(helper, Path('/unused-control-basis'), 'b' * 64)
            except RuntimeError:
                pass
            else:
                raise RuntimeError('Wrong/unadmitted basis accepted')
        helper.validate_control_basis.return_value = {'admitted': True, 'control_manifest_sha256': PARENT_SHA}
        validate_basis(helper, Path('/unused-control-basis'), 'b' * 64)
    return {'status': 'passed', 'model_requests': 0, 'source_materialized': False,
            'controls': ['only-placement-AST-change', 'original23/25-preserved', '20/28-exact-route-coverage',
                         'gaps-overlaps-repeated-devices-refused', 'memory-floor-boundary',
                         'ambiguous-or-reapplied-port-refused', 'only-launch-identity-functions-change',
                         'inherited-runtime-dependencies-and-adapter-edges-preserved',
                         'every-wrong-environment-field-refused', 'wrong-parent-or-low-memory-basis-refused',
                         'rope-activation-and-one-identity-order-preserved', 'original-provenance-paths-disjoint']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true'); p.add_argument('--manifest-sha256')
    p.add_argument('--packet', type=Path, default=PACKET); args = p.parse_args()
    result = self_test() if args.self_test else {'status': 'exact-transition-integrity-only-not-qualified',
              'manifest': verify_packet(args.packet, args.manifest_sha256)['rebalance100'], 'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
