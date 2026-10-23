#!/usr/bin/env python3
"""Prepared CPU-only native p198 lifecycle/protocol checks; never chooses a device binary."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

P = Path(__file__).resolve().parent; ROOT = P.parents[3]
sys.path.insert(0, str(P))
from prepare_overlay import sha
from build_engine import limits


def read(path): return json.loads(Path(path).read_text())


def parent_environment():
    parent = P.parent / 'packet181-session-swap-v3/one-card'
    script = '''import json,sys
from pathlib import Path
parent=Path(sys.argv[1]).resolve();sys.path.insert(0,str(parent))
import native_env,common
assert Path(native_env.__file__).resolve()==parent/'native_env.py'
assert Path(common.__file__).resolve()==parent/'common.py'
print(json.dumps(native_env.environment('A')))
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(parent)], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def client_module():
    path = ROOT / 'experiments/own-xpu-runtime/integration/request_front/client_v2.py'
    spec = importlib.util.spec_from_file_location('p198_client_v2', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def argv(host, run, count):
    return [str(host), '--mini', '--pipeline-mini', '--context', '64', '--retain-steps', 'none',
            '--native-nice', '19', '--seconds', '120', '--request-front', '--request-front-max-requests', str(count),
            '--request-front-idle-seconds', '10', '--request-front-checkpoints', str(run / 'checkpoints'),
            '--request-front-tokenizer-identity', str(run / 'tokenizer.tsv'), '--output', str(run / 'owner')]


def tokenizer(run):
    (run / 'tokenizer.tsv').write_text('format\townrt.tokenizer-identity.v1\ngguf_header_sha256\t' + '1'*64
        + '\ntokenizer_source_sha256\t' + '2'*64 + '\nvocab_bin_sha256\t' + '3'*64 + '\n')


def incident(process):
    if process.poll() is None:
        process.send_signal(__import__('signal').SIGTERM)
    try:
        process.wait(timeout=65)
    except subprocess.TimeoutExpired:
        print('HOST OWNER RETAINED PID ' + str(process.pid), file=sys.stderr)


def state(run, name, binary):
    folder = run / 'checkpoints' / name
    manifest = read(folder / 'manifest.json')
    assert manifest['label'] == 'experimental-postreply-front' and manifest['contract'] == 'v1.2+p198'
    assert manifest['qualified_by']['device_gates'] == [] and manifest['engine']['binary_sha256'] == sha(binary)
    return {leaf: sha(folder / leaf) for leaf in ['tokens.bin', *[b['name'] + '.bin' for b in manifest['blobs']]]}


def lifecycle(host, env, run, client):
    run.mkdir(); tokenizer(run)
    events, controls = [], []
    with (run / 'stderr.log').open('wb') as log:
        process = subprocess.Popen(argv(host, run, 8), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            front = client.NativeFront(process, context=64, vocab=16, max_requests=8, startup_timeout=30, request_timeout=30)
            assert front.ready['model_loads'] == 1 and front.ready['max_control_ops'] == 8
            def request(name, tokens, cap, restore=None):
                response = front.request(name, tokens, cap, restore=restore)
                row = read(run / 'owner/requests' / name / 'result.json')
                assert row['passed'] and row['tokens'] == response['tokens'] and len(row['tokens']) == cap
                assert row['request_front_scope'] == 'experimental-postreply-owner-v2'
                assert row['session_reuse'] is bool(restore)
                assert row['cached_tokens'] == (row['checkpoint']['restore']['saved_prefix_length'] if restore else 0)
                assert front.state == 'awaiting-disposition' and response['completion']['save_pending'] is True
                events.append(dict(id=name, tokens=row['tokens'], completion=response['completion']))
                return row['tokens']
            def save(operation, checkpoint, tokens):
                folder = run / 'checkpoints' / checkpoint
                assert not folder.exists(), 'save ID is chosen only after the completed reply'
                event = front.save(operation, checkpoint, tokens)
                assert event == read(run / 'owner/operations' / operation / 'save.json')
                assert event['manifest_sha256'] == sha(folder / 'manifest.json')
                state(run, checkpoint, host)
                controls.append(event)
            def release(operation): controls.append(front.release(operation))
            a, b = [2,5,3,7,1], [4,6,2,8]
            saved = request('fresh-a', a, 8); save('save-a', 's1', a + saved)
            first_b = request('fresh-b', b, 4); release('release-b')
            resumed = request('resume-a', a, 4, restore='s1'); save('save-resume', 's2', a + saved + resumed)
            appended = a + saved + [4,6,9,2,8,3]
            x = request('append-a', appended, 4, restore='s1'); save('save-append', 's3', appended + x)
            y = request('append-repeat', appended, 4, restore='s1'); save('save-repeat', 's4', appended + y)
            z = request('append-fresh', appended, 4); save('save-fresh', 's5', appended + z)
            reference = request('fresh-a-reference', a, 12); release('release-reference')
            repeated_b = request('fresh-b-repeat', b, 4)
            assert process.poll() is None and front.state == 'awaiting-disposition', 'final request drained before SAVE'
            save('save-final-b', 's6', b + repeated_b)
            assert controls[-1]['final_request'] is True and front.state == 'draining'
            stopped = front.close()
            assert stopped['completed_requests'] == stopped['completed_controls'] == 8
            assert stopped['discarded_pending'] is False and stopped['pending_request_id'] == ''
            assert saved + resumed == reference and x == y == z and first_b == repeated_b
            snapshots = {name: state(run, name, host) for name in ('s1','s2','s3','s4','s5','s6')}
            assert snapshots['s3'] == snapshots['s4'] == snapshots['s5']
            owner = read(run / 'owner/receipt.json')
            assert owner['passed'] and owner['safe_to_exit'] and owner['device_executed'] is False and process.returncode == 0
        except BaseException:
            incident(process); raise
    # Compare unchanged state bytes with the actual p197 immediate-save host proof.
    parent = P.parent / 'packet197-warm-request-front'
    prior = read(parent / 'evidence/host-probe.json')
    assert prior['passed'] and prior['device_executed'] is False and prior['requests'] == 8
    assert [e['tokens'] for e in events] == [e['tokens'] for e in prior['events']]
    previous_run = Path(prior['run_directory'])
    for name in ('s1','s2','s3','s4','s5'):
        folder = previous_run / 'checkpoints' / name
        expected = {leaf: sha(folder / leaf) for leaf in snapshots[name]}
        assert snapshots[name] == expected, 'postreply state differs from p197 immediate save: ' + name
    return dict(passed=True, requests=events, controls=controls, stopped=stopped,
                model_loads=1, save_resume_exact=True, append_repeat_fresh_state_exact=True,
                parent_immediate_save_state_exact=True, states_sha256=snapshots, run_directory=str(run))


def refusal(host, env, run, client, kind):
    run.mkdir(); tokenizer(run)
    expected = {'wrong-history':'postreply full visible tokens differ',
                'next-run-pending':'pending request needs SAVE or RELEASE',
                'stale-request':'stale or missing pending request',
                'existing-checkpoint':'never overwrite',
                'duplicate-operation':'duplicate operation id'}[kind]
    with (run / 'stderr.log').open('wb') as log:
        process = subprocess.Popen(argv(host, run, 2), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            front = client.NativeFront(process, context=64, vocab=16, max_requests=2, startup_timeout=30, request_timeout=30)
            a = [2,5,3,7,1]; result = front.request('a', a, 4); visible = a + result['tokens']
            if kind == 'existing-checkpoint':
                front.save('first-save', 's1', visible)
                result = front.request('b', a, 4); visible = a + result['tokens']
                raw = 'SAVE\tsecond-save\tb\ts1\t' + ' '.join(map(str, visible)) + '\n'
            elif kind == 'duplicate-operation':
                front.release('once'); front.request('b', a, 4)
                raw = 'RELEASE\tonce\tb\n'
            elif kind == 'next-run-pending': raw = 'RUN\tb\t4\t-\t-\t2 5 3 7 1\n'
            elif kind == 'stale-request': raw = 'RELEASE\top\twrong\n'
            else:
                visible[0] = (visible[0] + 1) % 16  # Same extent and pending token; native must compare the whole prefix.
                raw = 'SAVE\twrong-history\ta\ts1\t' + ' '.join(map(str, visible)) + '\n'
            os.write(process.stdin.fileno(), raw.encode())
            try: front._read(time.monotonic() + 30)
            except RuntimeError as error: assert expected in str(error), str(error)
            else: raise AssertionError('native malformed operation was accepted')
            assert process.wait(timeout=65) == 1
            owner = read(run / 'owner/receipt.json')
            assert not owner['passed'] and owner['safe_to_exit'] and owner['device_executed'] is False
            if kind in ('wrong-history','next-run-pending','stale-request'):
                assert not (run / 'owner/requests/b').exists()
            if kind == 'wrong-history': assert not (run / 'checkpoints/s1').exists()
            return dict(case=kind, expected_refusal=expected, returncode=1, safe_to_exit=True, run_directory=str(run))
        except BaseException:
            incident(process); raise


def pending_quit(host, env, run, client):
    run.mkdir(); tokenizer(run)
    with (run / 'stderr.log').open('wb') as log:
        process = subprocess.Popen(argv(host, run, 1), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            front = client.NativeFront(process, context=64, vocab=16, max_requests=1, startup_timeout=30, request_timeout=30)
            front.request('last', [2,5,3,7,1], 4)
            event = front.close()
            assert event['reason'] == 'quit' and event['discarded_pending'] is True and event['pending_request_id'] == 'last'
            assert event['completed_controls'] == 0 and process.returncode == 0
            assert not (run / 'checkpoints').exists()
            return event
        except BaseException:
            incident(process); raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-host-only', action='store_true')
    args = ap.parse_args()
    if not args.run_host_only: ap.error('explicit --run-host-only after authorized compilation required')
    limits(); resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    build = read(P / 'evidence/build-compile-only.json')
    assert build['passed'] and build['device_executed'] is False
    assert build['source_overlay_sha256'] == sha(P / 'evidence/source-overlay.json')
    assert build['parent_pins_sha256'] == sha(P / 'parent-pins.json')
    for path, digest in read(P / 'parent-pins.json')['sources'].items(): assert sha(ROOT / path) == digest, path
    plans = {row['target']: row for row in build['plans']}
    for target in ('protocol','host'): assert sha(Path(plans[target]['binary'])) == plans[target]['binary_sha256']
    assert '-DOWN_RT_HOST_ONLY' in plans['host']['commands'][0] and plans['host']['commands'][0][0] == '/usr/bin/g++'
    host = Path(plans['host']['binary']); assert host == P / 'build/host/own-rt-iq3'
    protocol = subprocess.run([plans['protocol']['binary']], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=15)
    assert protocol.returncode == 0, (protocol.stdout, protocol.stderr)
    env = parent_environment(); client = client_module()
    run = P / 'build' / ('host-probe-' + time.strftime('%Y%m%dT%H%M%S', time.gmtime())); run.mkdir()
    result = lifecycle(host, env, run / 'lifecycle', client)
    refusals = [refusal(host, env, run / case, client, case) for case in
                ('wrong-history','next-run-pending','stale-request','existing-checkpoint','duplicate-operation')]
    quit_event = pending_quit(host, env, run / 'pending-quit', client)
    receipt = dict(passed=True, device_executed=False, host_native_executed=True, protocol_probe_passed=True,
                   lifecycle=result, native_refusals=refusals, pending_quit=quit_event,
                   binary_sha256=sha(host), harness_sha256=sha(Path(__file__)), run_directory=str(run),
                   scope='Tiny synthetic host geometry only; real-model/device arithmetic and serving remain unqualified.')
    target = P / 'evidence/host-probe.json'
    if target.exists(): (P / 'lineage' / ('host-probe-before-' + str(time.time_ns()) + '.json')).write_bytes(target.read_bytes())
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(passed=True, device_executed=False, requests=8, controls=8, native_refusals=5)))


if __name__ == '__main__': main()
