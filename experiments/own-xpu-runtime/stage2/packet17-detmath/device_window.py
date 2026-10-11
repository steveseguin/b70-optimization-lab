#!/usr/bin/env python3
"""Prepared W-A/W-B; --check reads files and ldd only, never device APIs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from summarize_census import summarize as summarize_census

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = HERE / 'build'
LATCH = BUILD / 'device-fault-latch.json'
# Exact packet2 fault signatures; no broad 'hang' match.
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|devcoredump|device coredump|GPU.*coredump|GuC.*(?:hang|lockup)|timed.out.*(?:job|fence)', re.I)
PREFIX = ['nice', '-n', '19', 'ionice', '-c', '3', 'env', 'OMP_NUM_THREADS=2']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def journal(cursor=None):
    args = ['journalctl', '-k', '--no-pager', '--show-cursor']
    args += ['--after-cursor', cursor] if cursor else ['-n', '200']
    p = subprocess.run(PREFIX + args, capture_output=True, text=True, timeout=3)
    if p.returncode or p.stderr.strip():
        raise RuntimeError('kernel journal unavailable: ' + p.stderr)
    lines = p.stdout.splitlines()
    cursors = [s[len('-- cursor: '):] for s in lines if s.startswith('-- cursor: ')]
    if not cursors and not cursor:
        raise RuntimeError('missing journal boundary')
    return '\n'.join(s for s in lines if not s.startswith('-- cursor: ')) + '\n', cursors[-1] if cursors else cursor


def check(mode, output, card):
    if not 0 <= card < 4:
        raise ValueError('card must be 0..3')
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        raise ValueError('nice19 and OMP_NUM_THREADS=2 required')
    out = output.resolve()
    if BUILD.is_symlink() or BUILD not in out.parents or out.exists():
        raise ValueError('fresh output under packet17/build required')
    if LATCH.exists():
        raise ValueError('fault/exactness latch requires coordinator review')
    prepared = BUILD / 'window-prepared.json'
    m = json.loads(prepared.read_text())
    if m.get('device_executed') is not False or not m.get('compiled'):
        raise ValueError('invalid prepared state')
    for name, digest in m['hashes'].items():
        path = (ROOT / name).resolve()
        if ROOT not in path.parents or sha(path) != digest:
            raise ValueError('identity changed: ' + name)
    if m['chunk'] > 262144 or m['chunk'] % 64 or m['native_bits'] < 28:
        raise ValueError('coverage or submission bound changed')
    if mode == 'W-B' and not m.get('host_hashes_complete'):
        raise ValueError('all 2^32 host hashes must finish before W-B')
    if mode == 'W-B' and not m.get('cpu_three_way_passed'):
        raise ValueError('GNU/IntelLLVM core/parallel gate must pass before W-B')
    if mode == 'W-A' and not m.get('fixture_trace_complete'):
        raise ValueError('actual 72-fixture input trace required before W-A')
    # This precedes mkdir, latch writes and any device_executed claim. ldd does
    # not invoke main or Level Zero discovery. The coordinator sources setvars.
    for name in ('census_binary', 'fixture_binary') if mode == 'W-B' else ('census_binary',):
        p = subprocess.run(PREFIX + ['ldd', str(ROOT / m[name])], capture_output=True, text=True, timeout=15)
        if p.returncode or 'not found' in p.stdout or 'not found' in p.stderr:
            raise ValueError('loader preflight failed before device window: ' + p.stdout + p.stderr)
    return m, out


def watch(command, out, seconds, on_started=None):
    pre, cursor = journal()
    out.mkdir()
    (out / 'preflight-kernel.txt').write_text(pre)
    result = dict(returncode=None, stop_reason=None, fault_lines=[], child_alive=False,
                  external_idle_health_still_required=True)
    requested = []
    old = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in old:
        signal.signal(sig, lambda s, f: requested.append('watcher signal ' + str(s)))
    child = None
    try:
        with (out / 'stdout.txt').open('w') as log, (out / 'kernel-window.txt').open('w') as kernel:
            child = subprocess.Popen(PREFIX + command, stdout=log, stderr=subprocess.STDOUT)
            result['pid'] = child.pid
            if on_started is not None:
                on_started(child.pid)
            started = time.monotonic()
            sent_at = None
            while True:
                try:
                    fresh, cursor = journal(cursor)
                    kernel.write(fresh)
                    kernel.flush()
                    matches = [line for line in fresh.splitlines() if FAULT.search(line)]
                    if matches:
                        result['fault_lines'] += matches
                        requested.append('new GPU fault')
                except Exception as e:
                    requested.append('journal lost: ' + str(e))
                now = time.monotonic()
                if now - started > seconds:
                    requested.append('deadline')
                if requested and sent_at is None:
                    result['stop_reason'] = requested[0]
                    save(LATCH, dict(result, output=str(out)))
                    if child.poll() is None:
                        child.send_signal(signal.SIGTERM)
                    sent_at = now
                if child.poll() is not None:
                    break
                if sent_at is not None and now - sent_at > 20:
                    result['child_alive'] = True
                    result['coordinator_action'] = 'owner retained; inspect recorded pid; no retry, no forced kill'
                    break
                time.sleep(.25)
            result['returncode'] = child.poll()
            if not result['child_alive']:
                for _ in range(20):
                    time.sleep(.25)
                    try:
                        fresh, cursor = journal(cursor)
                        kernel.write(fresh)
                        matches = [line for line in fresh.splitlines() if FAULT.search(line)]
                        if matches:
                            result['fault_lines'] += matches
                            requested.append('post-exit GPU fault')
                    except Exception as e:
                        requested.append('postflight journal lost: ' + str(e))
            result['elapsed_seconds'] = time.monotonic() - started
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
    if requested:
        result['stop_reason'] = requested[0]
    if result['returncode'] != 0 or requested or result['child_alive']:
        save(LATCH, dict(result, output=str(out)))
    save(out / 'watch.json', result)
    if result['returncode'] != 0 or requested or result['child_alive']:
        raise RuntimeError('child failed or stopped; no retry; see ' + str(out))
    return result


def final_jsonl(path):
    last = None
    with path.open() as f:
        for line in f:
            last = json.loads(line)
    if not last or last.get('complete') is not True:
        raise ValueError('incomplete census')
    return last


def fixture_gate(path, cases, authority):
    d = json.loads((path / 'device.json').read_text())
    t = d.get('teardown', {})
    if (d.get('error') or d.get('checks') != 2 * len(cases)
            or d.get('packet4_device_checks') != len(cases)
            or d.get('packet4_device_host_matches') != len(cases)
            or d.get('authority') != authority
            or t.get('safe_to_exit') is not True or t.get('idle_marker_complete') is not True
            or t.get('live_bytes') != 0 or t.get('in_flight') != 0 or t.get('exit_code') != 0
            or t.get('status') != 'complete' or t.get('error')
            or 'context-released' not in t.get('sequence', [])):
        raise ValueError('parallel-v2/device-core/host-core/teardown gate failed')
    return {name: sha(path / (name + '.core')) for name in cases}


def execute(mode, output, card, seconds):
    m, out = check(mode, output, card)
    # Journal preflight also occurs before claiming a device launch.
    journal()
    out.mkdir()
    result = dict(schema='own-runtime.packet17.window.v2', mode=mode, card=card,
                  passed=False, device_executed=False, prepared_sha256=sha(BUILD / 'window-prepared.json'), owners=[])
    def started(pid):
        result['device_executed'] = True
        result['last_launched_pid'] = pid
        save(out / 'window.json', result)
    try:
        for owner in range(1 if mode == 'W-A' else 2):
            base = out / ('owner' + str(owner))
            base.mkdir()
            census_out = base / 'census'
            cmd = [str(ROOT / m['census_binary']), 'native' if mode == 'W-A' else 'verify',
                   str(m['native_bits'] if mode == 'W-A' else 32), str(m['chunk']),
                   str(census_out / 'census.jsonl'), str(ROOT / m['fixture_trace' if mode == 'W-A' else 'host_hashes']), str(card)]
            owner_result = {'census_watch': watch(cmd, census_out, seconds, on_started=started)}
            owner_result['census_complete'] = final_jsonl(census_out / 'census.jsonl')
            owner_result['census_sha256'] = sha(census_out / 'census.jsonl')
            if mode == 'W-A':
                owner_result['census_summary'] = summarize_census(census_out / 'census.jsonl')
                save(census_out / 'summary.json', owner_result['census_summary'])
                owner_result['summary_sha256'] = sha(census_out / 'summary.json')
            if mode == 'W-B':
                path = base / 'fixtures'
                command = [str(ROOT / m['fixture_binary']), '--authorized-device-window', str(card), str(ROOT / m['fixtures']), str(path), 'exactness']
                owner_result['fixture_watch'] = watch(command, path, min(seconds, 1800), on_started=started)
                owner_result['fixture_hashes'] = fixture_gate(path, m['cases'], m['authority'])
            result['owners'].append(owner_result)
        if mode == 'W-B' and result['owners'][0]['fixture_hashes'] != result['owners'][1]['fixture_hashes']:
            raise ValueError('two fresh owners differ')
        result['passed'] = True
    except Exception as e:
        result['error'] = str(e)
        save(LATCH, dict(reason=str(e), output=str(out)))
    finally:
        save(out / 'window.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authorized-device-window', action='store_true')
    p.add_argument('--check', action='store_true')
    p.add_argument('--mode', choices=('W-A', 'W-B'), required=True)
    p.add_argument('--card', type=int, default=3)
    p.add_argument('--seconds', type=int, default=7200)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not 1 <= a.seconds <= 14400:
        raise SystemExit('deadline must be 1..14400 seconds per census owner')
    if a.check:
        check(a.mode, a.output, a.card)
        print('Hash/loader checks passed; no device queried.')
        return
    if not a.authorized_device_window:
        raise SystemExit('coordinator device admission required')
    raise SystemExit(0 if execute(a.mode, a.output, a.card, a.seconds)['passed'] else 1)


if __name__ == '__main__':
    main()
