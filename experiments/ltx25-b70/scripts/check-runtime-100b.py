#!/usr/bin/env python3
"""CPU-only exact packet100 -> packet100b host-ownership transition and launch contract."""
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
PARENT = ROOT / 'prepared-encoder-rebalance-100'
PARENT_SHA = '5f156563da17edda65d8e0042a90344de665c5c93d4b61b603fc8ff0f9037bbc'
PACKET = ROOT / 'prepared-encoder-rebalance-100b'
LAYOUT = 'two-way20-28'
SEGMENTS = (('xpu:0', 0, 20), ('xpu:1', 20, 48))
SOURCE_PATHS = ('source/scripts/host_embedding_resident_node.py',
                'source/custom_nodes/ltx_host_embedding_lab/__init__.py')
COMMON = 'launch/encoder_runtime_common.py'
LAUNCHER = 'launch/serve-encoder.py'
CHANGED = (*SOURCE_PATHS, COMMON, LAUNCHER)
STATUS = b'Packet100b host ownership correction; failed100 preserved; candidate not GPU qualified.\n'


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
require(digest(_parent_raw) == PARENT_SHA, 'Packet100 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
_parent_checker = PARENT / COMMON
require(not _parent_checker.is_symlink() and digest(_parent_checker.read_bytes()) ==
        _parent_manifest['files'][COMMON], 'Packet100 checker changed')
BASE = load(_parent_checker, 'packet100b_immutable_parent')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module


def __getattr__(name):
    # All unchanged runtime, health, progress, dependency and model checks remain
    # the real parent's functions. No global mutation or false old identity.
    return getattr(BASE, name)


def host_source(raw):
    old = """    require(len(shards) == len(segments) - 1 and len(shards) >= 2,
            'Shard owners do not match the multi-segment placement')"""
    new = """    expected = PLACEMENTS[SAMPLER_PLACEMENT]
    require(SAMPLER_PLACEMENT != 'two-way' and segments == [list(seg) for seg in expected],
            'Shard segments differ from the named placement')
    require(len(shards) == len(expected) - 1 and len(shards) >= 1,
            'Shard owners do not match the multi-segment placement')
    require(len({id(s) for s in [model, *shards]}) == len(shards) + 1 and
            len({id(s.model) for s in [model, *shards]}) == len(shards) + 1 and
            [str(s.load_device) for s in shards] == [seg[0] for seg in expected[1:]],
            'Shard owners are aliased or on unexpected devices')"""
    text = BASE.replace_once(raw.decode(), old, new)
    text = BASE.replace_once(text, '    if segments is None:\n',
            "    if segments is None:\n        require(SAMPLER_PLACEMENT == 'two-way', 'Named placement requires segment metadata')\n")
    ast.parse(text)
    return text.encode()


def memory_source(raw):
    text = BASE.replace_once(raw.decode(), "prepared-encoder-rebalance-100'",
                             "prepared-encoder-rebalance-100b'")
    text = BASE.replace_once(text, 'encoder-server-rebalance-100-two-way20-28-',
                             'encoder-server-rebalance-100b-two-way20-28-')
    ast.parse(text)
    return text.encode()


def launcher_source(raw):
    text = BASE.replace_once(raw.decode(), 'encoder-server-rebalance-100-two-way20-28-',
                             'encoder-server-rebalance-100b-two-way20-28-')
    text = BASE.replace_once(text, 'Packet100 admits only the 20/28 batch-one candidate',
                             'Packet100b admits only the corrected20/28 batch-one candidate')
    text = BASE.replace_once(text, "    identity = {'runtime100_transition': manifest['rebalance100'],",
                             "    identity = {'runtime100b_transition': manifest['ownership100b'],\n"
                             "                'runtime100_transition': manifest['rebalance100'],")
    ast.parse(text)
    return text.encode()


def semantic_manifest(parent, files, builder_sha, transition):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.ownership-runtime-packet.v1', files=files,
                  preparer_sha256=builder_sha, ownership100b=transition)
    result['extension_sha256s']['host_embedding_resident_node.py'] = files[SOURCE_PATHS[0]]
    for name in result['startup_tools']:
        result['startup_tools'][name] = files['launch/' + name]
    return result


validate_basis = BASE.validate_basis
control = BASE.control


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET, 'Unexpected packet100b destination')
    raw = regular(packet / 'manifest.json')
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            digest(raw) == expected_manifest_sha256, 'Packet100b manifest changed')
    manifest = BASE.load_json(raw); files = manifest['files']
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    require(regular(packet / 'STATUS.txt') == STATUS, 'Candidate status differs')
    expected_delta = {p: host_source(regular(PARENT / p)) for p in SOURCE_PATHS}
    expected_delta[LAUNCHER] = launcher_source(regular(PARENT / LAUNCHER))
    expected_delta[COMMON] = regular(packet / 'provenance/check-runtime-100b.py')
    for path, expected in parent['files'].items():
        want = digest(expected_delta[path]) if path in expected_delta else expected
        require(files.get(path) == want, 'Changed/missing inherited file beyond exact delta: ' + path)
        require(stat.S_IMODE((packet / path).stat().st_mode) ==
                stat.S_IMODE((PARENT / path).stat().st_mode), 'Inherited file mode changed: ' + path)
    transition = manifest['ownership100b']
    require(set(transition) == {'schema', 'parent_packet', 'parent_manifest_sha256', 'control',
            'source_delta', 'campaign_bindings', 'control_basis', 'storage_admission',
            'qualification', 'model_requests'}, 'Transition fields differ')
    require(transition['schema'] == 'ltx.ownership100b.transition.v1' and
            transition['parent_packet'] == str(PARENT) and transition['parent_manifest_sha256'] == PARENT_SHA and
            transition['control'] == control() and transition['qualification'] is False and
            transition['model_requests'] == 0, 'Transition identity differs')
    require(transition['source_delta'] == {
        p: {'before_sha256': parent['files'][p], 'after_sha256': digest(expected_delta[p])}
        for p in SOURCE_PATHS}, 'Source delta receipt differs')
    require(regular(packet / 'provenance/packet100-manifest.json') == regular(PARENT / 'manifest.json'),
            'Parent provenance differs')
    for path in CHANGED:
        require(regular(packet / 'provenance/packet100' / path) == regular(PARENT / path),
                'Original changed file provenance differs')
    bindings = transition['campaign_bindings']
    require(set(bindings) == {'runner', 'memory_helper'}, 'Campaign helper inventory differs')
    for kind, binding in bindings.items():
        filename = {'runner': 'run-campaign-100b.sh', 'memory_helper': 'worker-headroom-100b.py'}[kind]
        require(set(binding) == {'source', 'sha256', 'packet_path'} and
                binding['packet_path'] == 'campaign/' + filename and Path(binding['source']).name == filename,
                'Campaign helper binding differs')
        require(sha(Path(binding['source'])) == binding['sha256'] == files[binding['packet_path']],
                'Campaign helper changed: ' + kind)
    require(regular(packet / bindings['memory_helper']['packet_path']) ==
            memory_source(regular(PARENT / parent['rebalance100']['campaign_bindings']['memory_helper']['packet_path'])),
            'Headroom derivative differs beyond exact packet/run names')
    basis = transition['control_basis']
    require(basis == parent['rebalance100']['control_basis'], 'Qualified99b control basis must remain unchanged')
    require(set(basis) == {'source', 'sha256', 'packet_path'} and
            basis['packet_path'] == 'provenance/control-basis.json', 'Control basis fields differ')
    require(regular(packet / basis['packet_path']) == regular(Path(basis['source'])), 'Control basis copy differs')
    helper = module(packet / bindings['memory_helper']['packet_path'], 'packet100b_checked_memory')
    validate_basis(helper, Path(basis['source']), basis['sha256'])
    extra = {'provenance/build-runtime-100b.py', 'provenance/check-runtime-100b.py',
             'provenance/packet100-manifest.json', basis['packet_path']}
    extra.update('provenance/packet100/' + p for p in CHANGED)
    extra.update(v['packet_path'] for v in bindings.values())
    require(set(files) == set(parent['files']) | extra, 'Packet100b inventory differs')
    checker = module(PARENT / 'provenance/source99/check-upstream-source-99.py', 'packet100b_inventory')
    require(checker.inventory(packet) == set(files) | {'manifest.json', 'STATUS.txt'}, 'Unbound packet files')
    for path, expected in files.items():
        require(sha(safe_path(packet, path)) == expected, 'Packet100b file changed: ' + path)
    require(manifest == semantic_manifest(parent, files, sha(packet / 'provenance/build-runtime-100b.py'), transition),
            'Packet100b semantic contract changed beyond declared delta')
    return manifest


def self_test():
    parent = copy.deepcopy(_parent_manifest)
    raws = [regular(PARENT / p) for p in SOURCE_PATHS]
    changed = [host_source(raw) for raw in raws]
    require(raws[0] == raws[1] and changed[0] == changed[1], 'Host/custom-node mirrors differ')
    before, after = ast.parse(raws[0]), ast.parse(changed[0])
    strip = lambda tree: [ast.dump(n) for n in tree.body if not
                          (isinstance(n, ast.FunctionDef) and n.name == 'shared_identity')]
    require(strip(before) == strip(after), 'Source changed outside shared_identity')
    for raw in (raws[0] + raws[0], changed[0]):
        try:
            host_source(raw)
        except RuntimeError:
            pass
        else:
            raise RuntimeError('Ambiguous/reapplied ownership transformation admitted')
    launch = launcher_source(regular(PARENT / LAUNCHER))
    defs = lambda raw: {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
    a, b = defs(regular(PARENT / LAUNCHER)), defs(launch)
    require({n for n in a if a[n] != b[n]} == {'prepare_start', 'launch'}, 'Unrelated launcher code changed')
    text = launch.decode()
    steps = [text.index(x) for x in ('    import comfy.quant_ops',
             '    rope_compat = common.install_rope_compat(packet)',
             "    identity['rope_compatibility'] = rope_compat",
             "    write_json(run / 'server-identity.json', identity)",
             "    write_json(run / 'determinism-after-import.json',",
             "    runpy.run_path(str(packet / 'source/main.py')")]
    require(steps == sorted(steps) and text.count("write_json(run / 'server-identity.json', identity)") == 1,
            'RoPE receipt or single final identity order changed')
    for name in ('install_rope_compat', 'check_control_environment', 'check_file_limits', 'activate_dependencies',
                 'install_progress', 'admit_storage', 'verify_runtime', 'verify_model_receipt'):
        require(__getattr__(name) is getattr(BASE, name), 'Inherited runtime guard changed')
    files = dict(parent['files']); files.update(dict(zip(SOURCE_PATHS, map(digest, changed))))
    files[COMMON] = 'a' * 64; files[LAUNCHER] = digest(launch)
    candidate = semantic_manifest(parent, files, 'b' * 64, {})
    for name in set(parent) - {'schema', 'files', 'preparer_sha256', 'startup_tools', 'extension_sha256s'}:
        require(candidate[name] == parent[name], 'Inherited semantic history changed: ' + name)
    ext = dict(parent['extension_sha256s']); ext['host_embedding_resident_node.py'] = digest(changed[0])
    require(candidate['extension_sha256s'] == ext, 'Unrelated extension hash changed')
    originals = {'provenance/packet100/' + p for p in CHANGED} | {'provenance/packet100-manifest.json'}
    require(not originals.intersection(parent['files']), 'Parent provenance would be overwritten')
    memory = regular(PARENT / 'campaign/worker-headroom-100.py')
    revised = memory_source(memory)
    # AST changes are confined to literals for current packet/run validation.
    def neutral(tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = node.value.replace('prepared-encoder-rebalance-100b', 'prepared-encoder-rebalance-100')
                node.value = node.value.replace('encoder-server-rebalance-100b-', 'encoder-server-rebalance-100-')
        return ast.dump(tree)
    require(neutral(ast.parse(memory)) == neutral(ast.parse(revised)), 'Unrelated headroom policy changed')
    return {'status': 'passed', 'model_requests': 0, 'source_materialized': False,
            'controls': ['mirrors-identical', 'only-shared-identity-source-changed', 'ambiguous-or-reapplied-port-refused',
                         'only-launch-identity-functions-changed', 'rope-and-single-identity-order-preserved',
                         'all-runtime-guards-inherited', 'semantic-history-and-only-host-extension-preserved',
                         'original-provenance-disjoint', 'only-headroom-packet-run-literals-changed']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true'); p.add_argument('--manifest-sha256')
    p.add_argument('--packet', type=Path, default=PACKET); args = p.parse_args()
    result = self_test() if args.self_test else {'status': 'ownership-transition-integrity-only-not-qualified',
              'transition': verify_packet(args.packet, args.manifest_sha256)['ownership100b'], 'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
