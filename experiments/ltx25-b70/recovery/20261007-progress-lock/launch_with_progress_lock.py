#!/usr/bin/env python3
"""Explicit process-local refresh overlay for the exact sealed packet 98 launcher.

No restart, signal, model access or device call here. The delegated launcher does
its normal admission and server work. This overlay is a distinct runtime identity;
its receipt is not a server health, output parity or campaign completion claim.
"""
import argparse
import datetime
import hashlib
import inspect
import json
import os
from pathlib import Path
import runpy
import stat
import sys

HERE = Path(__file__).resolve().parent
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-size-98')
MANIFEST_SHA = '918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f'
LAUNCHER_SHA = 'c31bf7a95f10ba8b7f15181ae49ef84701fbc3d7255503adf0475b1997c0215e'
SOURCE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/tqdm/std.py')
SOURCE_SHA = 'dd76d965de52c590819dec376644220cb35dc4831e40efb4c30944884fc57d86'
CANDIDATE_SHA = '1dc1fb8c669aed183eb45ac67a579838e45389c3d5d77cb59ff44b4c7c8ffd56'
ORIGINAL_SHA = '331cd792515f2f7f1b1b283a725f278c2e37c647011d1c5afc724d58f016f03d'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    path = Path(path)
    require(path.is_absolute(), 'Path must be absolute')
    for parent in [path, *path.parents]:
        require(not parent.is_symlink(), 'Symlink refused: ' + str(parent))
    require(stat.S_ISREG(path.stat().st_mode), 'Not a regular file: ' + str(path))
    return path.read_bytes()


def bound(path, expected):
    data = regular(path)
    require(digest(data) == expected, 'Hash mismatch: ' + str(path))
    return data


def code_identity(fn):
    c = fn.__code__
    constants = tuple(inspect.cleandoc(v) if i == 0 and isinstance(v, str) else v
                      for i, v in enumerate(c.co_consts))
    return (c.co_code, constants, c.co_names, c.co_varnames, c.co_freevars,
            c.co_cellvars, c.co_argcount, c.co_posonlyargcount, c.co_kwonlyargcount,
            c.co_flags, c.co_stacksize, c.co_exceptiontable,
            fn.__defaults__, fn.__kwdefaults__)


def install():
    bound(SOURCE, SOURCE_SHA)
    import tqdm
    import tqdm.std
    require(tqdm.__version__ == '4.70.1', 'Wrong tqdm version')
    require(Path(tqdm.std.__file__) == SOURCE, 'Unexpected tqdm source location')
    bound(SOURCE, SOURCE_SHA)
    original = bound(HERE / 'refresh.original.py', ORIGINAL_SHA)
    candidate = bound(HERE / 'refresh.candidate.py', CANDIDATE_SHA)
    original_ns, candidate_ns = {}, {}
    exec(compile(original, str(HERE / 'refresh.original.py'), 'exec'), original_ns)
    exec(compile(candidate, str(HERE / 'refresh.candidate.py'), 'exec'), candidate_ns)
    require(code_identity(tqdm.std.tqdm.refresh) == code_identity(original_ns['refresh']),
            'Loaded refresh differs from original; refuse repeated or foreign overlay')
    require(tqdm.tqdm is tqdm.std.tqdm, 'Unexpected tqdm class alias')
    tqdm.std.tqdm.refresh = candidate_ns['refresh']
    return {'distribution': 'tqdm', 'version': tqdm.__version__, 'source_path': str(SOURCE),
            'source_sha256': SOURCE_SHA, 'original_refresh_sha256': ORIGINAL_SHA,
            'candidate_refresh_sha256': CANDIDATE_SHA,
            'loaded_refresh_filename': inspect.getfile(tqdm.std.tqdm.refresh)}


def validate_launcher(launcher, args):
    require(launcher == PACKET / 'launch/serve-encoder.py', 'Only sealed packet 98 launcher is admitted')
    bound(PACKET / 'manifest.json', MANIFEST_SHA)
    bound(launcher, LAUNCHER_SHA)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--health-receipt', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parsed = parser.parse_args(args)
    require(parsed.packet == PACKET and parsed.manifest_sha256 == MANIFEST_SHA,
            'Launcher arguments differ from pinned packet')
    return parsed


def write_receipt(path, value):
    require(path.is_absolute(), 'Receipt must be absolute')
    require(not path.exists() and not path.is_symlink(), 'Receipt already exists')
    require(path.parent.is_dir(), 'Receipt parent must already exist')
    for parent in path.parents:
        require(not parent.is_symlink(), 'Receipt ancestor is a symlink')
    require(not path.is_relative_to(PACKET), 'Receipt must be outside sealed packet')
    data = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return digest(data)


def delegate(launcher, args):
    # Same argv tokens remain in /proc/cmdline for the sealed campaign PID gate.
    sys.path.insert(0, str(launcher.parent))
    sys.argv = [str(launcher), *args]
    runpy.run_path(str(launcher), run_name='__main__')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('launcher', type=Path)
    parser.add_argument('launcher_args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    require(sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python', 'Baseline interpreter required')
    parsed = validate_launcher(args.launcher, args.launcher_args)
    overlay = install()
    receipt = {'schema': 'ltx.progress-lock-process-overlay.v1',
               'status': 'overlay-installed-before-launch; server outcome not established',
               'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'pid': os.getpid(), 'proc_start_ticks': Path('/proc/self/stat').read_text().split(') ')[1].split()[19],
               'run_name': parsed.run_name, 'packet': str(PACKET), 'packet_manifest_sha256': MANIFEST_SHA,
               'launcher': str(args.launcher), 'launcher_sha256': LAUNCHER_SHA,
               'wrapper': str(Path(__file__).resolve()), 'wrapper_sha256': digest(regular(Path(__file__).resolve())),
               'overlay': overlay, 'installed_files_changed': False, 'sealed_packet_changed': False,
               'limits': 'refresh display-lock exception safety only; no disk admission, GPU or output-parity qualification'}
    receipt_sha = write_receipt(args.receipt, receipt)
    os.environ['LTX_PROGRESS_LOCK_RECEIPT'] = str(args.receipt)
    os.environ['LTX_PROGRESS_LOCK_RECEIPT_SHA256'] = receipt_sha
    delegate(args.launcher, args.launcher_args)


if __name__ == '__main__':
    main()
