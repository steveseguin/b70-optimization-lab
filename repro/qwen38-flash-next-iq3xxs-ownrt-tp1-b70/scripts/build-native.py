#!/usr/bin/env python3
"""Build packet165 from a pinned source archive, never from inherited .o files.

Only compiler/linker subprocesses run. Output is a new, unqualified binary;
this command never launches it or modifies a sealed experiment directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import tarfile
import time

HERE = Path(__file__).resolve().parents[1]
MANIFEST = HERE / 'manifests/native-build.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def unpack(manifest, archive, source):
    if digest(archive.read_bytes()) != manifest['archive']['sha256']:
        raise ValueError('source archive hash mismatch')
    expected = manifest['source_files']
    seen = set()
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            name = member.name
            rel = Path(name)
            if not member.isfile() or rel.is_absolute() or '..' in rel.parts or name in seen or name not in expected:
                raise ValueError(f'unexpected or unsafe archive member: {name}')
            data = tf.extractfile(member).read()
            if digest(data) != expected[name]['sha256'] or len(data) != expected[name]['bytes']:
                raise ValueError(f'source hash mismatch: {name}')
            target = source / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            # Only originating checkout paths change. Arithmetic, flags and parser guards do not.
            if target.suffix in ('.cpp', '.hpp', '.h', '.inc', '.c', '.tsv'):
                data = data.replace(manifest['original_root'].encode(), str(source).encode())
            target.write_bytes(data)
            seen.add(name)
    if seen != set(expected):
        raise ValueError('archive does not contain every pinned source')
    return {name: digest((source / name).read_bytes()) for name in sorted(seen)}


def command(template, source, build):
    result = [part.replace('@SOURCE@', str(source)).replace('@BUILD@', str(build)) for part in template]
    if any('@SOURCE@' in part or '@BUILD@' in part for part in result):
        raise ValueError('unexpanded build command')
    return result


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cards', type=int, choices=(1, 2), required=True)
    parser.add_argument('--out', type=Path, required=True, help='fresh directory outside the checkout')
    parser.add_argument('--prepare-only', action='store_true', help='verify and unpack sources without invoking compilers')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    lane = 'one-card' if args.cards == 1 else 'two-card'
    plan = manifest['plans'][lane]
    out = args.out.expanduser().resolve()
    repo = HERE.parents[1]
    if out.is_relative_to(repo) or out.exists():
        raise SystemExit('refusing an existing output path or output inside the checkout')
    if not out.parent.is_dir() or shutil.disk_usage(out.parent).free < 2 * 1024**3:
        raise SystemExit('output parent must exist and have at least 2 GiB free')
    out.mkdir()
    shutil.copyfile(MANIFEST, out / 'input-manifest.json')
    shutil.copyfile(Path(__file__), out / 'build-helper.py')
    source = out / 'source'
    source.mkdir()
    relocated = unpack(manifest, MANIFEST.parent / manifest['archive']['path'], source)
    (out / 'objects').mkdir()
    (out / 'logs').mkdir()
    (out / 'tmp').mkdir()
    receipt = {'schema': 'neural.download.ownrt.source-build-result.v1', 'cards': args.cards,
               'manifest_sha256': digest(MANIFEST.read_bytes()), 'builder_sha256': digest(Path(__file__).read_bytes()), 'archive_sha256': manifest['archive']['sha256'],
               'historical_binary_sha256': plan['historical_binary_sha256'], 'device_executed': False,
               'reused_object_files': False, 'arithmetic_qualified': False, 'passed': False,
               'relocated_source_sha256': relocated, 'commands': []}
    commands = [(row['id'], command(row['command'], source, out)) for row in plan['translation_units']]
    commands.append(('link', command(plan['link_command'], source, out)))
    save(out / 'build-plan.json', {'commands': commands, 'device_execution': 'never'})
    if args.prepare_only:
        receipt['status'] = 'source-prepared-only'
        save(out / 'build-receipt.json', receipt)
        print(f'{lane}: {len(relocated)} pinned source files prepared; no compiler or device executed')
        return
    os.nice(max(0, 19 - os.getpriority(os.PRIO_PROCESS, 0)))
    allowed = sorted(os.sched_getaffinity(0))
    preferred = [cpu for cpu in (8, 9) if cpu in allowed]
    cpus = preferred if len(preferred) == 2 else allowed[:2]
    os.sched_setaffinity(0, cpus)
    env = dict(os.environ, TMPDIR=str(out / 'tmp'), OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
    receipt['cpu_affinity'] = cpus
    receipt['nice'] = os.getpriority(os.PRIO_PROCESS, 0)
    receipt['compiler_versions'] = {}
    for exe in sorted({cmd[0] for _, cmd in commands}):
        if exe not in ('/opt/intel/oneapi/compiler/2026.0/bin/icpx', '/usr/bin/g++', 'g++'):
            raise SystemExit(f'unexpected compiler: {exe}')
        receipt['compiler_versions'][exe] = subprocess.check_output([exe, '--version'], env=env, text=True)
    try:
        for name, cmd in commands:
            if shutil.disk_usage(out).free < 1024**3:
                raise RuntimeError('output filesystem below 1 GiB free')
            if name != 'link':
                cmd = [*cmd, '-MMD', '-MF', str(out / 'objects' / (name + '.d'))]
            started = time.monotonic()
            with (out / 'logs' / (name + '.log')).open('w') as log:
                result = subprocess.run(cmd, cwd=source, env=env, stdin=subprocess.DEVNULL, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=900, preexec_fn=limits)
            row = {'name': name, 'argv': cmd, 'returncode': result.returncode, 'seconds': time.monotonic() - started}
            receipt['commands'].append(row)
            save(out / 'build-receipt.json', receipt)
            if result.returncode:
                raise RuntimeError(f'{name}: compiler failed; inspect logs/{name}.log')
            if name != 'link':
                # The compiler, not just an include-text scan, checks the closed source tree.
                deps = (out / 'objects' / (name + '.d')).read_text().replace('\\\n', ' ')
                paths = set(re.findall(r'/[^\s\\]+', deps))
                outside = [p for p in paths if p.startswith(manifest['original_root'] + '/')]
                if outside:
                    raise RuntimeError(f'{name}: compiler escaped to originating checkout: {outside}')
                project = [p for p in paths if str(source) + '/' in p]
                external = [p for p in paths if Path(p).suffix in ('.cpp', '.hpp', '.h', '.inc') and not p.startswith((str(source) + '/', '/usr/', '/opt/intel/'))]
                if external:
                    raise RuntimeError(f'{name}: unbundled non-system dependency: {external}')
                if not project:
                    raise RuntimeError(f'{name}: no source dependencies reported')
                missing = [p for p in project if str(Path(p).resolve().relative_to(source)) not in relocated]
                if missing:
                    raise RuntimeError(f'{name}: dependency absent from source manifest: {missing}')
                row['dependency_sha256'] = {p: digest(Path(p).read_bytes()) for p in sorted(project)}
            print(f'{lane}: {name} compiled ({row["seconds"]:.1f}s)', flush=True)
        binary = out / 'own-rt-iq3'
        receipt.update(passed=True, status='compiled-not-device-qualified', binary_sha256=digest(binary.read_bytes()),
                       binary_bytes=binary.stat().st_size,
                       historical_binary_hash_matches=digest(binary.read_bytes()) == plan['historical_binary_sha256'])
    except Exception as exc:
        receipt['status'] = 'build-failed'
        receipt['error'] = str(exc)
        raise
    finally:
        receipt['peak_child_rss_bytes'] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
        save(out / 'build-receipt.json', receipt)
    print(f'Built {binary}; GPU execution and arithmetic qualification remain pending.')


if __name__ == '__main__':
    main()
