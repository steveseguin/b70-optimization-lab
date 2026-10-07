#!/usr/bin/env python3
"""CPU-only exact packet99 -> packet99b RoPE compatibility transition and launch contract."""
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
PARENT = ROOT / 'prepared-encoder-upstream-99'
PARENT_SHA = 'e7b268d2e54e9010e88e325681a5d7af43052d7affdf803ca9b6c7ee54ed8736'
PACKET = ROOT / 'prepared-encoder-upstream-99b'
COMMON = 'launch/encoder_runtime_common.py'
LAUNCHER = 'launch/serve-encoder.py'
CHANGED = (COMMON, LAUNCHER)
INSTALLER_ROOT = Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261007-rope-compat')
STATUS = b'Packet99b process-local RoPE compatibility candidate; no GPU, parity or speed qualification.\n'


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
require(digest(_parent_raw) == PARENT_SHA, 'Packet99 parent manifest changed')
_parent_manifest = json.loads(_parent_raw)
_parent_checker = PARENT / COMMON
require(not _parent_checker.is_symlink() and digest(_parent_checker.read_bytes()) ==
        _parent_manifest['files'][COMMON], 'Packet99 checker changed')
BASE = load(_parent_checker, 'packet99b_immutable_parent')
regular, sha, safe_path, module = BASE.regular, BASE.sha, BASE.safe_path, BASE.module


def __getattr__(name):
    # All unchanged runtime, health, progress, dependency and model checks remain
    # the real parent's functions. No global mutation or false old identity.
    return getattr(BASE, name)


def launcher_source(raw):
    text = BASE.replace_once(raw.decode(), 'encoder-server-upstream-99-two-way-w2-b1-p1-dxpu2-s256x256',
                            'encoder-server-upstream-99b-two-way-w2-b1-p1-dxpu2-s256x256')
    text = BASE.replace_once(text, 'Packet99 admits only the frozen batch-one control',
                            'Packet99b admits only the frozen batch-one compatibility control')
    text = BASE.replace_once(text, "    identity = {'runtime99_transition': manifest['upstream99'],",
                            "    identity = {'runtime99b_transition': manifest['rope99b'],\n"
                            "                'runtime99_transition': manifest['upstream99'],")
    identity_write = ("    write_json(run / 'server-identity.json', identity)\n"
                      "    os.environ['LTX_ENCODER_IDENTITY_SHA256'] = common.sha(run / 'server-identity.json')\n")
    text = BASE.replace_once(text, identity_write, '')
    hook = ("    import comfy.quant_ops\n"
            "    rope_compat = common.install_rope_compat(packet)\n"
            "    write_json(run / 'rope-compat.json', rope_compat)\n"
            "    identity['rope_compatibility'] = rope_compat\n" + identity_write)
    text = BASE.replace_once(text, '    import comfy.model_management\n',
                            '    import comfy.model_management\n' + hook)
    ast.parse(text)
    return text.encode()


def install_rope_compat(packet):
    helper = module(packet / 'launch/rope-compat/install_rope_compat.py', 'packet99b_rope_install')
    return helper.install()


def semantic_manifest(parent, files, builder_sha, transition):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.rope-compat-runtime-packet.v1', files=files,
                  preparer_sha256=builder_sha, rope99b=transition)
    for name in result['startup_tools']:
        result['startup_tools'][name] = files['launch/' + name]
    return result


def installer_files():
    """Complete bounded authored installer/evidence inventory, without symlinks."""
    require(INSTALLER_ROOT.is_dir() and not INSTALLER_ROOT.is_symlink(), 'Reviewed installer is not ready')
    out = {}
    for path in sorted(INSTALLER_ROOT.rglob('*')):
        require(not path.is_symlink(), 'Installer symlink refused')
        name = str(path.relative_to(INSTALLER_ROOT))
        if path.is_dir():
            require(name == 'source-evidence', 'Unexpected installer subdirectory')
            continue
        require(path.is_file() and path.stat().st_size <= 256 * 1024, 'Unexpected installer special/oversized file')
        require(len(path.relative_to(INSTALLER_ROOT).parts) <= 2 and
                (path.name.endswith(('.py', '.json', '.md', '.txt')) or path.name in ('LICENSE', 'NOTICE') or
                 name == 'cpu-controls.log') and
                path.name != 'sitecustomize.py', 'Unexpected installer file')
        out[name] = sha(path)
    require({'install_rope_compat.py', 'source-evidence/rope-0.2.33.py',
             'source-evidence/rope-0.2.37.py', 'source-evidence/provenance.json'} <= set(out) and
            len(out) <= 16, 'Installer evidence inventory missing/oversized')
    return out


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET, 'Unexpected packet99b destination')
    raw = regular(packet / 'manifest.json')
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            digest(raw) == expected_manifest_sha256, 'Packet99b manifest changed')
    manifest = BASE.load_json(raw); files = manifest['files']
    parent = BASE.verify_packet(PARENT, PARENT_SHA)
    require(regular(packet / 'STATUS.txt') == STATUS, 'Candidate status differs')
    delta = {LAUNCHER: launcher_source(regular(PARENT / LAUNCHER)),
             COMMON: regular(packet / 'provenance/check-runtime-99b.py')}
    for path, expected in parent['files'].items():
        require(files.get(path) == (digest(delta[path]) if path in delta else expected),
                'Inherited99 file differs beyond launcher transition: ' + path)
        require(stat.S_IMODE((packet / path).stat().st_mode) ==
                stat.S_IMODE((PARENT / path).stat().st_mode), 'Inherited file mode changed')
    transition = manifest['rope99b']
    require(set(transition) == {'schema', 'parent_packet', 'parent_manifest_sha256', 'control',
                'installer', 'campaign_bindings', 'storage_admission', 'qualification', 'model_requests'},
            'Unexpected99b transition fields')
    require(transition['schema'] == 'ltx.rope99b.transition.v1' and
            transition['parent_packet'] == str(PARENT) and transition['parent_manifest_sha256'] == PARENT_SHA and
            transition['control'] == parent['upstream99']['control'] and transition['qualification'] is False and
            transition['model_requests'] == 0, 'Transition identity differs')
    require(regular(packet / 'provenance/packet99-manifest.json') == regular(PARENT / 'manifest.json'),
            'Parent provenance differs')
    for path in CHANGED:
        require(regular(packet / 'provenance/packet99' / path) == regular(PARENT / path),
                'Original startup file provenance differs')
    installer = transition['installer']
    require(set(installer) == {'source', 'files', 'activation'} and installer['source'] == str(INSTALLER_ROOT) and
            installer['activation'] == 'after-preflight-and-normal-quant-ops-import-before-identity-and-main' and
            installer['files'] == installer_files(), 'Installer provenance/activation differs')
    for name, expected in installer['files'].items():
        require(files.get('launch/rope-compat/' + name) == expected, 'Installer snapshot differs')
    bindings = transition['campaign_bindings']
    require(set(bindings) == {'runner', 'memory_helper'}, 'Campaign helper inventory differs')
    for kind, binding in bindings.items():
        filename = {'runner': 'run-campaign-99b.sh', 'memory_helper': 'worker-headroom-98.py'}[kind]
        require(set(binding) == {'source', 'sha256', 'packet_path'} and
                binding['packet_path'] == 'campaign/' + filename and Path(binding['source']).name == filename,
                'Campaign helper binding differs')
        require(sha(Path(binding['source'])) == binding['sha256'] == files[binding['packet_path']],
                'Campaign helper identity changed: ' + kind)
    require(bindings['memory_helper'] == parent['upstream99']['campaign_bindings']['memory_helper'],
            'Baseline headroom helper changed')
    extra = {'provenance/build-runtime-99b.py', 'provenance/check-runtime-99b.py', 'provenance/packet99-manifest.json'}
    extra.update('provenance/packet99/' + p for p in CHANGED)
    extra.update('launch/rope-compat/' + n for n in installer['files'])
    extra.update(v['packet_path'] for v in bindings.values())
    require(set(files) == set(parent['files']) | extra, 'Packet99b file closure differs')
    checker = module(PARENT / 'provenance/source99/check-upstream-source-99.py', 'packet99b_inventory')
    require(checker.inventory(packet) == set(files) | {'manifest.json', 'STATUS.txt'}, 'Unbound packet files')
    for path, expected in files.items():
        require(sha(safe_path(packet, path)) == expected, 'Packet99b file changed: ' + path)
    require(manifest == semantic_manifest(parent, files, sha(packet / 'provenance/build-runtime-99b.py'), transition),
            'Packet99b semantic contract differs beyond transition')
    return manifest


def self_test():
    before = regular(PARENT / LAUNCHER); after = launcher_source(before)
    tree = ast.parse(after)
    funcs = lambda raw: {n.name: ast.dump(n) for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)}
    a, b = funcs(before), funcs(after)
    require({n for n in a if a[n] != b[n]} == {'prepare_start', 'launch'}, 'Unrelated launcher function modified')
    text = after.decode()
    positions = [text.index(x) for x in ["torch.xpu.device_count()", '    argv = server_args(packet, run)',
                '    sys.argv = argv', '    comfy.options.enable_args_parsing()',
                '    import comfy.model_management', '    import comfy.quant_ops',
                '    rope_compat = common.install_rope_compat(packet)',
                "    identity['rope_compatibility'] = rope_compat", "    write_json(run / 'server-identity.json', identity)",
                "    os.environ['LTX_ENCODER_IDENTITY_SHA256'] =", "    write_json(run / 'determinism-after-import.json',",
                "    runpy.run_path(str(packet / 'source/main.py')"]]
    require(positions == sorted(positions), 'Compatibility installation/startup ordering differs')
    require(text.count("write_json(run / 'server-identity.json', identity)") == 1 and
            text.count('common.install_rope_compat(packet)') == 1, 'Identity or installer repeated')
    require("'progress_lock': progress_overlay" in text and 'common.install_progress(packet)' in text,
            'Progress overlay lost')
    # New control delegates the exact original99 environment and all limits.
    for name in ('check_control_environment', 'check_file_limits', 'activate_dependencies', 'install_progress',
                 'admit_storage', 'verify_runtime', 'verify_model_receipt'):
        require(__getattr__(name) is getattr(BASE, name), 'Inherited guard differs')
    parent = copy.deepcopy(_parent_manifest)
    files = dict(parent['files']); files[LAUNCHER] = digest(after); files[COMMON] = 'a' * 64
    candidate = semantic_manifest(parent, files, 'b' * 64, {})
    for name in set(parent) - {'schema', 'files', 'preparer_sha256', 'startup_tools'}:
        require(candidate[name] == parent[name], 'Inherited semantic section changed: ' + name)
    for malformed in (before + before, after):
        try:
            launcher_source(malformed)
        except RuntimeError:
            pass
        else:
            raise RuntimeError('Repeated/ambiguous transformation admitted')
    return {'status': 'passed', 'model_requests': 0, 'source_materialized': False,
            'controls': ['only-two-startup-functions-change', 'post-preflight-normal-import-order',
                         'one-installer-one-final-identity', 'progress-overlay-retained',
                         'all-inherited-guards-identical', 'all-source-and-semantic-sections-preserved',
                         'ambiguous-or-reapplied-port-refused']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--self-test', action='store_true'); p.add_argument('--manifest-sha256')
    p.add_argument('--packet', type=Path, default=PACKET); args = p.parse_args()
    result = self_test() if args.self_test else {'status': 'transition-integrity-only-not-GPU-qualified',
              'transition': verify_packet(args.packet, args.manifest_sha256)['rope99b'], 'model_requests': 0}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
