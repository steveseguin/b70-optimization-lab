#!/usr/bin/env python3
"""CPU-only native entry rehearsal: python3 -B rehearse_entry.py PROPOSAL.

Reads JSONL proposals, reconstructs lanequeue.command (never executes it),
and tests each declared native ELF with ldd and its help/argument parser.
No packet import, --plan, model read, queue mutation, service or device entry.

Default binary inventory comes from the packet's build-receipt.json artifacts
or artifacts_sha256. New proposals may declare plan.entry_rehearsal.binaries:
[{"path": "repo/relative/native", "sha256": "...", "args": ["--version"],
  "returncode": 0, "contains": "version"}]. Omit args for --help (including
an explicit unknown-option parser refusal). An empty inventory always fails.
Script coordinators require a packet-specific rehearsal; they fail here rather
than guessing their inner environment. This is only the loader/entry gate;
the packet's real arm/state-machine CPU rehearsal remains separately required.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import entry_sandbox
import launch_env

OPS = Path(__file__).resolve().parent
ROOT = OPS.parents[2]


def lanequeue():
    directory = OPS / 'lane-queue'
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('_entry_lanequeue', directory / 'lanequeue.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def inventory(job):
    declaration = job.get('plan', {}).get('entry_rehearsal', {})
    if not isinstance(declaration, dict):
        raise ValueError('invalid entry rehearsal declaration')
    explicit = declaration.get('binaries')
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ValueError('empty or invalid native inventory')
        return explicit
    argv = job['argv']
    script = resolve(argv[2] if Path(argv[0]).name.startswith('python') else argv[0])
    packet = next((p for p in (script.parent, *script.parents)
                   if (p / 'build-receipt.json').is_file()), None)
    if packet is None:
        raise ValueError('declare plan.entry_rehearsal.binaries; no build receipt found')
    receipt = json.loads((packet / 'build-receipt.json').read_text())
    if not isinstance(receipt, dict):
        raise ValueError('invalid build receipt')
    artifacts = receipt.get('artifacts', receipt.get('artifacts_sha256', {}))
    if not isinstance(artifacts, dict):
        raise ValueError('invalid build artifact inventory')
    binaries = []
    for name, digest in artifacts.items():
        path = Path(name)
        if not path.is_absolute():
            path = ROOT / path if name.startswith('experiments/') else packet / path
        # No broad tree scans or model/payload reads. Native executables have
        # no extension in the packet build receipts; .o/.a/.bin are not entrypoints.
        if path.suffix or not ('build' in path.parts and any(
                part in path.parts for part in ('device', 'gnu-host', 'host'))):
            continue
        binaries.append(dict(path=str(path), sha256=digest))
    if not binaries:
        raise ValueError('no native binaries in build receipt; declare an explicit inventory')
    return binaries


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unit_environment(job, queue, ldp):
    queue.validate(job, job.get('lane'))
    if 'script' in job:
        raise ValueError('script coordinator needs a packet-specific inner-environment rehearsal')
    command = queue.command(job, '/tmp/entry-review.json', '/tmp/entry-receipt.json', ldp)
    unit = '--unit=screen-' + job['name']
    if unit not in command:
        raise ValueError('lanequeue unit identity changed')
    index = command.index('/usr/bin/env')
    if command[index + 1] != '-i':
        raise ValueError('lanequeue environment is not closed')
    env = {}
    for arg in command[index + 2:]:
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', arg):
            break
        key, value = arg.split('=', 1)
        env[key] = value
    if env != queue.closed_env(ldp):
        raise ValueError('lanequeue environment construction changed')
    return env


def rehearse(job, queue, ldp, runner=entry_sandbox.run):
    name = job.get('name', '?')
    row = dict(job=name, unit='screen-' + name, passed=False, binaries=[],
               service_started=False, arm_sequence_tested=False)
    try:
        env = unit_environment(job, queue, ldp)
        row['shared_environment_matches'] = env == launch_env.environment()
        native_env = dict(env)
        # Some frozen wrappers replace LD_LIBRARY_PATH from this option. Test
        # that narrower environment as well; do not silently repair the packet.
        argv = job['argv']
        for i, arg in enumerate(argv):
            if arg == '--library-path':
                native_env['LD_LIBRARY_PATH'] = argv[i + 1]
            elif arg.startswith('--library-path='):
                native_env['LD_LIBRARY_PATH'] = arg.split('=', 1)[1]
        row['packet_library_override'] = native_env != env
        for spec in inventory(job):
            result = dict(passed=False)
            row['binaries'].append(result)
            try:
                result['phase'] = 'identity'
                path = resolve(spec['path']).resolve(strict=True)
                result['binary'] = str(path)
                if path.suffix or not os.access(path, os.X_OK):
                    raise ValueError('inventory entry is not a native executable')
                with path.open('rb') as stream:
                    if stream.read(4) != b'\x7fELF':
                        raise ValueError('inventory entry is not ELF')
                expected = spec.get('sha256')
                if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
                    raise ValueError('native inventory requires a SHA256')
                if digest(path) != expected:
                    raise ValueError('native binary differs from recorded build')
                result['phase'] = 'ldd'
                result['unit_ldd'] = launch_env.check_binary(path, env, runner)
                result['native_ldd'] = (launch_env.check_binary(path, native_env, runner)
                                        if native_env != env else result['unit_ldd'])
                if not result['unit_ldd']['passed'] or not result['native_ldd']['passed']:
                    continue
                args = spec.get('args', ['--help'])
                if (not isinstance(args, list) or not args or
                        not all(isinstance(a, str) and '\x00' not in a for a in args)):
                    raise ValueError('invalid native entry probe arguments')
                result['phase'] = 'entry'
                cp = runner(launch_env.env_command([str(path), *args], native_env),
                            binary=path, cwd=ROOT)
                output = cp.stdout + cp.stderr
                if 'args' in spec:
                    match = spec.get('contains')
                    if not isinstance(match, str) or not match:
                        raise ValueError('explicit probe requires expected output text')
                    passed = cp.returncode == spec.get('returncode', 0) and match in output
                else:
                    # A named unknown --help option is itself the binary's own
                    # argument-parse path. A generic rc=1 is never a pass.
                    passed = ((cp.returncode == 0 and bool(re.search(r'usage|options|help', output, re.I)))
                              or (cp.returncode in (1, 2) and bool(re.search(
                                  r'(?:unknown|unrecognized|unexpected|invalid) (?:argument|option)[^\n]*--help',
                                  output, re.I))))
                result.update(passed=passed, entry_returncode=cp.returncode,
                              entry_kind='explicit' if 'args' in spec else 'help-or-parser',
                              entry_timed_out=cp.returncode == 124)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                result['error'] = 'native inventory, loader, or bounded entry check failed'
        row['passed'] = bool(row['binaries']) and all(b['passed'] for b in row['binaries'])
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        # Do not echo arbitrary exceptions, argv, environments or binary output:
        # proposal values can include coordinator secrets.
        row['error'] = 'invalid proposal/inventory, stale binary, or unavailable CPU sandbox'
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proposal', type=Path)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    queue = lanequeue()
    # Read only the one non-secret P49_LDP assignment; never source/print file.
    ldp = queue.library_path()
    rows = []
    for line in args.proposal.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            job = json.loads(line)
            if not isinstance(job, dict) or not isinstance(job.get('name'), str) or not re.fullmatch(
                    r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', job['name']):
                raise ValueError('invalid job')
            row = rehearse(job, queue, ldp)
        except (ValueError, TypeError):
            row = dict(job='invalid-job', passed=False, error='invalid JSONL job')
        rows.append(row)
        if not args.json:
            print(f'{"PASS" if row["passed"] else "FAIL"} screen-{row["job"]}: '
                  f'{sum(b["passed"] for b in row.get("binaries", []))}/'
                  f'{len(row.get("binaries", []))} native entries; CPU arm sequence still required')
    if args.json:
        print(json.dumps(dict(passed=bool(rows) and all(r['passed'] for r in rows), jobs=rows), indent=2))
    return 0 if rows and all(r['passed'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
