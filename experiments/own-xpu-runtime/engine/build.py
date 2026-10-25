#!/usr/bin/env python3
"""Build canonical sources, optionally with one authenticated deployment header.

Never executes the engine. Preserve the source tree at its build location: the
current native runtime reads its pinned rope.bf16 next to the compiled main.cpp.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import sys

ENGINE = Path(__file__).resolve().parent
SRC = ENGINE / 'src'
sys.path.insert(0, str(ENGINE))
from deployment.prepare import HEADER, require, validate_overlay


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_command(manifest, unit, out, include=None, compiler=None):
    obj = out / unit['object']
    overlays = ['-I', str(include)] if include is not None else []
    return [compiler or manifest['compiler'], *unit['flags'], *overlays, '-I', str(SRC),
            '-MMD', '-MF', str(obj.with_suffix('.d')), '-c', str(SRC/unit['source']), '-o', str(obj)]


def dependencies(path, include=None):
    # Make dependency output escapes spaces; shlex also handles escaped backslashes.
    tokens = shlex.split(path.read_text().replace('\\\n', ' '))
    canonical, generated = set(), set()
    for token in tokens[1:]:
        p = Path(token).absolute()
        if include is not None and p.is_relative_to(include):
            require(p.relative_to(include).as_posix() == HEADER, 'unexpected generated dependency')
            generated.add(p)
        elif p.is_relative_to(SRC):
            canonical.add(p)
    return canonical, generated


def build(args):
    require(args.jobs > 0, 'positive job count')
    require(Path(args.name).name == args.name and args.name not in ('.', '..'), 'binary basename required')
    supplied = (args.generated_include is not None, args.profile_sha256 is not None, args.deployment_sha256 is not None)
    require(all(supplied) or not any(supplied), 'overlay requires --generated-include, --profile-sha256 and --deployment-sha256')
    include = args.generated_include.absolute() if args.generated_include is not None else None
    overlay = validate_overlay(include, args.profile_sha256, args.deployment_sha256) if include else None
    m = json.loads((ENGINE/'build-manifest.json').read_text())
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=True); (out/'tmp').mkdir(exist_ok=True)
    receipt_path = out/'build-receipt.json'
    env = dict(os.environ, TMPDIR=str(out/'tmp'))

    def compile_tu(unit):
        cmd = compile_command(m, unit, out, include, args.compiler)
        start = time.time(); result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        return unit['object'], cmd, result.returncode, round(time.time()-start, 1), result.stderr[-6000:]

    log = {}; failed = False
    with cf.ThreadPoolExecutor(args.jobs) as pool:
        for name, cmd, rc, seconds, error in pool.map(compile_tu, m['translation_units']):
            log[name] = dict(cmd=cmd, rc=rc, seconds=seconds, stderr=error)
            print(name, 'rc', rc, seconds, 's', flush=True)
            if rc:
                print(error); failed = True
    require(not failed, 'compilation failed')
    binary = out/args.name
    link = [args.compiler or m['link']['compiler'],
            *[x for x in m['link']['flags'] if x.startswith('-fsycl') or x.startswith('-Wl,--gc')],
            *[str(out/u['object']) for u in m['translation_units']],
            *[x for x in m['link']['flags'] if not (x.startswith('-fsycl') or x.startswith('-Wl,--gc'))],
            '-o', str(binary)]
    result = subprocess.run(link, env=env, capture_output=True, text=True)
    log['link'] = dict(cmd=link, rc=result.returncode, stderr=result.stderr[-6000:])
    require(result.returncode == 0, 'link failed: '+result.stderr[-6000:])
    deps, generated = set(), set()
    for unit in m['translation_units']:
        own, extra = dependencies((out/unit['object']).with_suffix('.d'), include)
        deps.update(own); generated.update(extra)
    if include:
        require(generated == {include/HEADER} and SRC/HEADER not in deps,
                'generated authority did not replace canonical header')
        require(validate_overlay(include, args.profile_sha256, args.deployment_sha256) == overlay,
                'deployment authority changed during build')
    runtime = SRC/'gsq-rco-iq3s/dense-packed-block/engine/build/source/rope.bf16'
    receipt = dict(schema='ownrt.engine.build.v1', binary=str(binary), binary_sha256=sha(binary),
        objects={u['object']: sha(out/u['object']) for u in m['translation_units']},
        sources={str(p.relative_to(SRC)): sha(p) for p in sorted(deps)}, commands=log,
        runtime_assets={str(runtime): sha(runtime)}, generated_authority=overlay,
        generated_dependencies={str(p): sha(p) for p in sorted(generated)},
        build_script_sha256=sha(__file__), build_manifest_sha256=sha(ENGINE/'build-manifest.json'))
    receipt_path.write_text(json.dumps(receipt, indent=1)+'\n')
    print('binary', receipt['binary_sha256'])
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--name', default='own-engine')
    parser.add_argument('--compiler', help='explicit compiler path; recorded in every build command')
    parser.add_argument('--generated-include', type=Path)
    parser.add_argument('--profile-sha256')
    parser.add_argument('--deployment-sha256')
    build(parser.parse_args())


if __name__ == '__main__':
    main()
