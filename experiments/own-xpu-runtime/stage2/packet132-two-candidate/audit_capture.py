#!/usr/bin/env python3
"""Read-only code/dependency audit; writes only evidence/source-audit.json.

No model payload, prompt, token, benchmark manifest, or framework import.
Reproduce: nice -n 19 taskset -c 8-15,24-31 python3 -B audit_capture.py --check </dev/null
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess

P = Path(__file__).resolve().parent
REPO = P.parents[3]
ORIGINAL = P.parent / 'packet49-integrate/oracle'
CAPTURE = P / 'build/capture'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def relative(path):
    return str(path.resolve().relative_to(REPO))


def command(args):
    return subprocess.check_output(args, text=True, stdin=subprocess.DEVNULL,
                                   timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))


def audit():
    old = json.loads((ORIGINAL / 'build-receipt.json').read_text())
    new = json.loads((CAPTURE / 'build-receipt.json').read_text())
    arithmetic = json.loads((ORIGINAL / 'arithmetic.json').read_text())
    known = {}
    checked = {}
    counts = {}
    # Select code filenames BEFORE reading bytes. The frozen suite manifest is
    # intentionally excluded; no benchmark data is needed for this audit.
    for label, mapping in (
        ('arithmetic_sources', arithmetic['arithmetic_sources']),
        ('overlay_sources', arithmetic['overlay_sources']),
        ('frozen_sources', old['frozen_sources']),
    ):
        count = 0
        for name, expected in mapping.items():
            if Path(name).suffix not in ('.cpp', '.hpp', '.h', '.cc', '.py'):
                continue
            actual = sha(REPO / name)
            require(actual == expected, f'original source changed: {name}')
            known[name] = expected
            checked[name] = actual
            count += 1
        counts[label] = count

    generated = {}
    src = CAPTURE / 'build/src'
    for name, expected in old['generated_sources'].items():
        raw = (src / name).read_bytes()
        original_raw = raw
        if name == 'oracle.cpp':
            text = raw.decode()
            for before, after, expected_count in (
                ("5'000'000'000ull", "38'000'000'000ull", 2),
                ('a.context=128;', 'a.context=4096;', 1),
                ('if(false)', 'if(capture>0 && (capture<=8 || (capture>=97 && capture<=104)))', 1),
            ):
                require(text.count(before) == expected_count, f'unexpected edit count: {before}')
                text = text.replace(before, after)
            raw = text.encode()
        require(hashlib.sha256(raw).hexdigest() == expected, f'generated arithmetic changed: {name}')
        generated[name] = dict(current_sha256=hashlib.sha256(original_raw).hexdigest(),
                               original_sha256=expected)

    cmd = new['commands'][0]
    require(cmd[0] == 'g++' and '-DOWN_RT_HOST_ONLY' in cmd, 'not host-only compiler command')
    flags = [x for x in cmd[1:] if x.startswith(('-I', '-D', '-std')) or x == '-fopenmp']
    units = [x for x in cmd if x.endswith('.cpp')]
    require(len(units) == 6, 'unexpected target compilation units')
    dependencies = set()
    for unit in units:
        text = command(['g++', '-MM', *flags, unit])
        dependencies.update(text.replace('\\\n', ' ').split(':', 1)[1].split())
    external = {}
    for name in sorted(dependencies):
        path = Path(name).resolve()
        if path.parent == src:
            require(path.name in generated, f'unrecorded generated dependency: {path}')
            continue
        name = relative(path)
        require(name in known, f'unrecorded target dependency: {name}')
        actual = sha(path)
        require(actual == known[name], f'target dependency mismatch: {name}')
        external[name] = actual

    oracle = CAPTURE / 'build/oracle'
    require(sha(oracle) == new['oracle_sha256'], 'oracle binary differs from receipt')
    dynamic = command(['readelf', '-d', str(oracle)])
    needed = sorted(line.split('[', 1)[1].split(']', 1)[0]
                    for line in dynamic.splitlines() if '(NEEDED)' in line)
    require(set(needed) <= {'libcrypto.so.3', 'libstdc++.so.6', 'libm.so.6',
                            'libgomp.so.1', 'libgcc_s.so.1', 'libc.so.6'},
            f'unexpected native dependency: {needed}')

    lane = REPO / 'experiments/qwen38-flash-next-ud-iq3xxs-b70'
    draft_paths = [P.parent / 'packet31-mtp-acceptance' / name
                   for name in ('draft_reference.py', 'qsa_reference.py')]
    draft_paths += [lane / 'packet2-cpu-oracle' / name for name in
                    ('reference_gguf.py', 'oracle.py', 'packed.py', 'tokenizer.py')]
    draft_paths += [lane / 'packet3-runtime-oracle/linear.py']
    draft_paths += [REPO / 'experiments/own-xpu-runtime/stage1/packet1b/loaders' / name
                    for name in ('headers.py', 'dequant.py')]
    draft_hashes = {}
    for path in draft_paths:
        text = path.read_text()
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                require(node.attr not in ('cuda', 'xpu', 'set_default_device', 'set_device'),
                        f'device API in {path}:{node.lineno}')
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == 'device' and not (isinstance(node.func, ast.Name) and node.func.id == 'dict'):
                        require(isinstance(kw.value, ast.Constant) and kw.value.value == 'cpu',
                                f'nonliteral CPU placement in {path}:{node.lineno}')
                if isinstance(node.func, ast.Attribute) and node.func.attr == 'to':
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            require(arg.value == 'cpu', f'non-CPU transfer in {path}:{node.lineno}')
        draft_hashes[relative(path)] = sha(path)
    linear = (lane / 'packet3-runtime-oracle/linear.py').read_text()
    require("x.device.type!='cpu'" in linear, 'CPU linear admission check missing')
    for name, expected in new['matmul_dependency_sha256'].items():
        require(sha(REPO / name) == expected, f'draft native dependency changed: {name}')
    require(sha(CAPTURE / 'build/matmul.so') == new['matmul_sha256'], 'draft native binary changed')

    core = (src / 'core_v2.hpp').read_text()
    plan = (REPO / 'experiments/own-xpu-runtime/stage2/packet3/step/plan.hpp').read_text()
    require('for (int b = 0; b < (pos + 1) / 4; ++b)' in core, 'QSA valid pool bound changed')
    require('int pos = position, n = (pos + 1) / 4;' in core, 'QSA selection bound changed')
    require('g.budget / 4' in core and '{g.budget + 3}' in plan, 'QSA selection capacity changed')
    require('budget = 2048' in (REPO / 'experiments/own-xpu-runtime/stage2/packet3/kernels/api.hpp').read_text(),
            'attention budget changed')
    return dict(schema='lab.packet132.source-audit.v1', passed=True, device_executed=False,
                payloads_read=False, compiler_preprocessing_only=True,
                original_receipt_sha256=sha(ORIGINAL / 'build-receipt.json'),
                arithmetic_manifest_sha256=sha(ORIGINAL / 'arithmetic.json'),
                capture_receipt_sha256=sha(CAPTURE / 'build-receipt.json'),
                source_counts=counts, original_source_sha256=checked,
                external_compiler_dependency_sha256=external, generated_sources=generated,
                oracle_sha256=sha(oracle), native_needed=needed,
                draft_local_import_source_sha256=draft_hashes,
                draft_native_dependency_sha256=new['matmul_dependency_sha256'],
                draft_native_sha256=new['matmul_sha256'],
                draft_scope='Static local-import audit; CPU constructors and dtype casts; native Linear rejects non-CPU input. Third-party framework binaries are not certified by this source scan.',
                context_proof=dict(original_capacity=4096, capture_capacity=128,
                    maximum_consumed_positions=39, unchanged_attention_budget=2048,
                    conclusion='Capacity changes QSA allocation, copy lengths and begin bounds. Valid pool/selection work follows position; RoPE and arithmetic sources are unchanged. 39 < 128.',
                    limitation='Source-derived numerical-equivalence argument; no new two-capacity execution comparison.'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'CPU affinity required')
    resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
    result = audit()
    raw = json.dumps(result, indent=2, sort_keys=True) + '\n'
    out = P / 'evidence/source-audit.json'
    if args.check:
        require(out.read_text() == raw, 'source audit differs from retained result')
    else:
        out.parent.mkdir(exist_ok=True)
        with out.open('x') as stream:
            stream.write(raw)
    print(json.dumps(dict(passed=True, external_dependencies=len(result['external_compiler_dependency_sha256']),
                          draft_sources=len(result['draft_local_import_source_sha256']))))


if __name__ == '__main__':
    main()
