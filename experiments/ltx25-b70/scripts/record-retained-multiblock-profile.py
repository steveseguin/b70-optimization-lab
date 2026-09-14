#!/usr/bin/env python3
"""Packet08 retained all48 diagnostic: one profiled clip, then one restored clip.

No server control or retry. --check-only verifies sealed sources offline;
--ready-check additionally requires the same-process terminal screen03 and a
healthy idle endpoint, without attaching or submitting. Ordinary execution
uses one bounded nonblocking py-spy attachment and at most two native requests.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PACKET_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
CLIENT_SHA = 'd8054e9866dfb314a5df37415811a5d4a5db79828b0494cca5f3526884ee3114'
HELPER_SHA = 'aa72ba88cbce87ebe6f5c8b298112bcd6a72cea046020cab55fe2256a616d124'
QUALIFICATION = 'multiblock-screen-03'
PYSPY = Path('/home/steve/.local/bin/py-spy')
PYSPY_SHA = '9b4d1f39b2a47ae44f4c6a46f615dcc0287d7755beba5065f32391951e07d594'
CREDENTIAL = Path('/home/steve/SUDOPASSWORD.txt')
REQUEST_TIMEOUT = 1200
ATTACH_TIMEOUT = 5
PROFILE_SECONDS = 15


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp():
    return {'monotonic_ns': time.monotonic_ns(), 'unix_time_ns': time.time_ns()}


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def load_client():
    path = LANE / 'scripts/run-multiblock-screen-v3.py'
    require(sha(path) == CLIENT_SHA and sha(LANE / 'scripts/ltx_multiblock_receipts_v3.py') == HELPER_SHA,
            'Frozen packet08 client/helper changed')
    spec = importlib.util.spec_from_file_location('retained_profile_sealed_client', path)
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    require(client.PACKET_SHA == PACKET_SHA and client.RECEIPTS_SHA == HELPER_SHA,
            'Sealed client pins disagree')
    return client


def schedule(campaign):
    require(isinstance(campaign, str) and 1 <= len(campaign) <= 64 and
            all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in campaign) and
            campaign[0] != '-', 'Unsafe campaign name')
    return [{'run': campaign + '-' + mode + '-boat', 'mode': mode, 'selection': 'all48',
             'fixture': 'boat', 'qualified_before': 2, 'initialization': False,
             'timeout_seconds': REQUEST_TIMEOUT, 'profiled': mode == 'compiled'}
            for mode in ('compiled', 'restored')]


def passed_parity(row):
    return (isinstance(row, dict) and row.get('status') == 'passed' and
            isinstance(row.get('comparisons'), dict) and set(row['comparisons']) ==
            {'images', 'video_latent', 'audio_latent', 'waveform'} and
            all(isinstance(value, dict) and value.get('bitwise_equal') is True
                for value in row['comparisons'].values()))


def graph_bindings(receipts):
    return {index: [{'graph': graph['graph'], 'files': graph['files']}
                    for graph in block['native_operation_graphs']]
            for index, block in receipts['blocks'].items()}


def terminal_binding(client, args, identity):
    """Require completed cold qualification and retained warm/control receipts."""
    directory = client.retention.safe_path(ROOT, QUALIFICATION)
    prereg = json.loads((directory / 'preregistration.json').read_text())
    progress = json.loads((directory / 'progress.json').read_text())
    plans = client.schedule(QUALIFICATION)
    require(prereg.get('campaign') == QUALIFICATION and prereg.get('client_sha256') == CLIENT_SHA and
            prereg.get('receipt_validator_sha256') == HELPER_SHA and
            prereg.get('packet_manifest_sha256') == PACKET_SHA and prereg.get('identity') == identity and
            prereg.get('schedule') == plans, 'Qualification campaign source/process identity differs')
    rows = progress.get('rows')
    require(progress.get('status') == 'passed' and progress.get('completed_requests') == 12 and
            isinstance(rows, list) and len(rows) == len(plans) == 12,
            'Same-process screen03 is not completely passed')
    for planned, row in zip(plans, rows):
        require(row.get('status') == 'passed' and all(row.get(k) == value for k, value in planned.items()),
                'Qualification terminal schedule/status differs')
        parity_path = client.retention.safe_path(directory, row['run'] + '-parity.json')
        require(passed_parity(json.loads(parity_path.read_text())), 'Prior full-output parity is incomplete')
    require([p.name for p in args.server_run.glob('native-multiblock-*')] == ['native-multiblock-all48'],
            'Unexpected retained selection state')
    validators = client.receipt_helpers()
    identity_sha = sha(args.server_run / 'server-identity.json')
    cold = next(r for r in rows if r['mode'] == 'compiled' and r['initialization'])
    warm = next(r for r in reversed(rows) if r['mode'] == 'compiled')
    restored = rows[-1]
    require(restored['mode'] == 'restored', 'Expected completed restored state at screen03 termination')
    bound = {}
    owners = {}
    for label, row in (('cold', cold), ('warm', warm), ('restored', restored)):
        result = validators.validate_compiler_receipts(args.server_run, row['run'], row['mode'],
                                                       'all48', identity_sha, row['qualified_before'])
        require(result == row['compiler'], 'Terminal compiler receipt snapshot differs from current evidence')
        client.validate_owner_continuity(owners, result['request'])
        bound[label] = result
    graphs = graph_bindings(bound['warm'])
    require(graphs == graph_bindings(bound['cold']) and set(graphs) == {str(i) for i in range(48)} and
            all(len(records) == 2 for records in graphs.values()), 'Native graph qualification changed')
    components = client.screen.latest_components(args.server_run, 'control')
    require(components == restored['components'], 'Resident component identity changed since qualification')
    return {'owners': owners, 'components': components, 'graphs': graphs,
            'qualification_preregistration_sha256': sha(directory / 'preregistration.json'),
            'qualification_progress_sha256': sha(directory / 'progress.json'),
            'qualified_runs': {key: value['request']['run_name'] for key, value in bound.items()},
            'native_graph_json_count': 96, 'native_graph_python_source_count': 192,
            'native_graph_total_evidence_files': 288, 'call_json_count_per_compiled_request': 528}


def profiler_command(pid, output):
    require(type(pid) is int and pid > 1, 'Invalid verified target PID')
    return ['sudo', '-S', '-p', '', str(PYSPY), 'record', '--pid', str(pid),
            '--duration', str(PROFILE_SECONDS), '--rate', '100', '--threads', '--idle',
            '--nonblocking', '--full-filenames', '--format', 'speedscope',
            '--output', str(output / 'stacks.json')]


def start_profiler(pid, output):
    require(sha(PYSPY) == PYSPY_SHA, 'Profiler executable changed')
    command = profiler_command(pid, output)
    write(output / 'profiler-command.json', {'argv': command, 'binary_sha256': PYSPY_SHA,
                                            'binary_resolved_path': str(PYSPY.resolve())})
    context = {'target_pid': pid, 'spawn_before': stamp(), 'requested_duration_seconds': PROFILE_SECONDS,
               'threads_included': True, 'idle_threads_included': True, 'rate_hz': 100,
               'blocking_attach': False}
    # The credential is only stdin of this one sudo child; never log its bytes.
    with CREDENTIAL.open('rb') as credential, (output / 'profiler.log').open('xb') as log:
        worker = subprocess.Popen(command, stdin=credential, stdout=log, stderr=subprocess.STDOUT)
    context.update(worker_pid=worker.pid, spawn_after=stamp())
    write(output / 'profiler-worker.json', context)
    return worker, context


def confirm_attachment(worker, context, output):
    deadline = time.monotonic() + ATTACH_TIMEOUT
    while True:
        text = (output / 'profiler.log').read_text(errors='replace')
        if 'Sampling process' in text and worker.poll() is None:
            context['attachment_confirmed'] = stamp()
            write(output / 'profiler-attached.json', context)
            return
        if worker.poll() is not None or time.monotonic() >= deadline:
            write(output / 'profiler-attachment-failure.json', {'time': stamp(), 'worker_pid': worker.pid,
                'exit_code': worker.poll(), 'action': 'no request submitted; no retry; worker has its own15s duration'})
            raise RuntimeError('Profiler did not confirm attachment; halt without submitting')
        time.sleep(.1)


def profile_summary(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 64 * 1024**2,
            'Missing, linked or oversized profile')
    value = json.loads(path.read_text())
    require(value.get('$schema') == 'https://www.speedscope.app/file-format-schema.json', 'Unexpected profile schema')
    frames = value.get('shared', {}).get('frames')
    profiles = value.get('profiles')
    require(isinstance(frames, list) and all(isinstance(f, dict) and isinstance(f.get('name'), str) for f in frames)
            and isinstance(profiles, list) and profiles, 'Invalid profile frames/threads')
    threads = []
    for profile in profiles:
        require(profile.get('type') == 'sampled' and profile.get('unit') == 'seconds' and
                isinstance(profile.get('name'), str), 'Unexpected sampled-thread format')
        start, end = profile.get('startValue'), profile.get('endValue')
        require(all(type(n) in (int, float) and math.isfinite(n) for n in (start, end)) and
                0 <= start < end, 'Invalid thread sampling window')
        samples, weights = profile.get('samples'), profile.get('weights')
        require(isinstance(samples, list) and isinstance(weights, list) and len(samples) == len(weights) > 0 and
                all(type(w) in (int, float) and math.isfinite(w) and w >= 0 for w in weights),
                'Invalid sampled thread weights')
        seen = set()
        for sample in samples:
            require(isinstance(sample, list) and all(type(i) is int and 0 <= i < len(frames) for i in sample),
                    'Invalid profile frame reference')
            seen.update(sample)
        threads.append({'name': profile['name'], 'sample_count': len(samples),
                        'relative_start_seconds': start, 'relative_end_seconds': end,
                        'sampled_weight_seconds_including_idle': sum(weights),
                        'contains_prompt_worker': any(frames[i]['name'] == 'prompt_worker' for i in seen),
                        'contains_route_validation': any(frames[i]['name'] in ('_validate', '_registered_bindings')
                                                        for i in seen),
                        'contains_selected_block_call': any(frames[i]['name'] == '_call_native' and
                            str(frames[i].get('file', '')).endswith('ltx_multiblock_compile.py') for i in seen)})
    require(any(t['contains_prompt_worker'] for t in threads), 'No Comfy prompt-worker samples captured')
    require(any(t['contains_selected_block_call'] for t in threads), 'No selected block execution samples captured')
    return {'profile_sha256': sha(path), 'profile_bytes': path.stat().st_size, 'threads': threads,
            'time_semantics': 'Per-thread sampled stack weights include idle/waiting; never sum threads into CPU percentages',
            'window_semantics': 'Speedscope windows are relative; parent attachment/request timestamps only bracket their relationship'}


def run_one(client, common, args, identity, binding, base, planned, output, profiler=None):
    """Same v3 receipt/graph/placement/oracle gates for one retained request."""
    client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
    run, mode = planned['run'], planned['mode']
    reference, seed = client.screen.REFERENCES['boat']
    source = json.loads((ROOT / 'requests' / reference / 'prompt.json').read_text())
    require(all(source[n]['inputs']['noise_seed'] == seed for n in ('338', '339')), 'Reference seed changed')
    fixture_prompt = source['364']['inputs']['text']
    graph = client.expected_graph(base, mode, 'all48')
    graph['364']['inputs']['text'] = fixture_prompt
    for node in ('338', '339'):
        graph[node]['inputs']['noise_seed'] = seed
    for node in ('421', '422'):
        graph[node]['inputs']['run_name'] = run
    graph_path = output / (run + '-graph.json')
    write(graph_path, graph)
    command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), run, '--graph', str(graph_path),
               '--server-run', str(args.server_run), '--timeout', str(REQUEST_TIMEOUT)]
    current = {**planned, 'status': 'running', 'command': command,
               'before': client.retention.snapshot(identity['pid']), 'request_launch_before': stamp()}
    write(output / (run + '-request-start.json'), current)
    if profiler is not None:
        require(profiler.poll() is None, 'Profiler exited before submission; halt without request')
    client.screen.run_subprocess(command, output / (run + '-client.log'), REQUEST_TIMEOUT + 60)
    current['request_complete_observed'] = stamp()
    if profiler is not None:
        current['profiler_exit_at_request_completion'] = profiler.poll()
    current['after'] = client.retention.snapshot(identity['pid'])
    client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
    request = ROOT / 'requests' / run
    submitted = json.loads((request / 'prompt.json').read_text())
    require(client.normalized(submitted) == client.normalized(graph), 'Submitted graph differs')
    require(submitted['364']['inputs']['text'] == fixture_prompt and
            all(submitted[n]['inputs']['noise_seed'] == seed for n in ('338', '339')) and
            all(submitted[n]['inputs']['run_name'] == run for n in ('421', '422')), 'Fixture or diagnostic names changed')
    request_identity = json.loads((request / 'identity.json').read_text())
    require(all(request_identity[k] == identity[k] for k in client.screen.IDENTITY_FIELDS), 'Request identity changed')
    identity_sha = sha(args.server_run / 'server-identity.json')
    placement = json.loads((args.server_run / ('encoder-placement-' + run + '.json')).read_text())
    client.screen.validate_placement(placement, run, 'control', identity_sha, identity['model_verification_sha256'])
    components = client.screen.latest_components(args.server_run, 'control')
    require(components == binding['components'], 'Retained resident components changed')
    current['components'] = components
    current['compiler'] = client.receipt_helpers().validate_compiler_receipts(
        args.server_run, run, mode, 'all48', identity_sha, 2)
    client.validate_owner_continuity(binding['owners'], current['compiler']['request'])
    if mode == 'compiled':
        require(graph_bindings(current['compiler']) == binding['graphs'], 'Retained graph evidence changed')
    write(output / (run + '-placement.json'), placement)
    parity_path = output / (run + '-parity.json')
    client.screen.run_subprocess([sys.executable, str(LANE / 'scripts/compare-clip.py'), reference, run,
        '--output', str(parity_path)], output / (run + '-compare.log'), 120)
    require(passed_parity(json.loads(parity_path.read_text())), 'Original four-output parity failed')
    current['capture'] = client.retention.validate_capture(ROOT, run)
    current['profile'] = json.loads((request / 'profile.json').read_text())
    current.update(status='passed', parity_path=str(parity_path), reference=reference,
                   timing_scope='Diagnostic run; profiler overhead may affect times; no speed promotion')
    history = json.loads((request / 'history.json').read_text())
    previews = history['outputs']['75']['images']
    require(len(previews) == 1 and previews[0]['type'] == 'output' and previews[0]['subfolder'] == run,
            'Unexpected preview path')
    runs = {row['run'] for row in schedule(args.campaign)}
    current['output_inventory'] = [client.retention.inventory(ROOT, args.campaign, runs, run,
        Path('output/validation') / run / 'tensors.safetensors'),
        client.retention.inventory(ROOT, args.campaign, runs, run, Path('output') / run / previews[0]['filename'])]
    write(output / (run + '-passed.json'), current)
    return current


def run_diagnostic(client, common, args, base):
    identity, _ = client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
    binding = terminal_binding(client, args, identity)
    plans = schedule(args.campaign)
    for row in plans:
        for relative in (Path('requests') / row['run'], Path('output') / row['run'],
                         Path('output/validation') / row['run']):
            require(not client.retention.safe_path(ROOT, relative, exists=False).exists(), 'Diagnostic output already exists')
        require(not (args.server_run / ('compiler-' + row['run'])).exists(), 'Diagnostic request already attempted')
    output = client.retention.safe_path(ROOT, args.campaign, exists=False)
    output.mkdir(exist_ok=False)
    write(output / 'preregistration.json', {'schema': 'ltx.retained-multiblock-stack-profile.v1',
        'schedule': plans, 'max_native_requests': 2, 'max_profiler_attachments': 1,
        'identity': identity, 'qualification_binding': binding, 'source_sha256': sha(Path(__file__)),
        'client_sha256': CLIENT_SHA, 'helper_sha256': HELPER_SHA, 'packet_manifest_sha256': PACKET_SHA,
        'profile_duration_seconds': PROFILE_SECONDS, 'profile_attach_timeout_seconds': ATTACH_TIMEOUT,
        'speed_promotion': False, 'streaming_qualification': False,
        'failure_action': 'halt new requests; preserve evidence and process; no retry or restored request after failure',
        'retention': 'Prune only verified raw archives after both requests and profiler pass; retain both previews'})
    worker, context = None, None
    rows = []
    phase = 'profiler-attachment'
    try:
        worker, context = start_profiler(identity['pid'], output)
        confirm_attachment(worker, context, output)
        client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
        require(worker.poll() is None, 'Profiler exited before request launch')
        phase = 'profiled-compiled-request'
        # Full numerical/receipt validation happens before the restored request.
        rows.append(run_one(client, common, args, identity, binding, base, plans[0], output, profiler=worker))
        phase = 'profiler-completion'
        code = worker.wait(timeout=25)
        context.update(exit_code=code, exit_observed=stamp())
        write(output / 'profiler-result.json', context)
        require(code == 0, 'Profiler failed; do not submit restored request')
        profile = profile_summary(output / 'stacks.json')
        profile['parent_timestamps'] = context
        profile['request_launch_before'] = rows[0]['request_launch_before']
        profile['request_complete_observed'] = rows[0]['request_complete_observed']
        profile['profiler_exit_at_request_completion'] = rows[0]['profiler_exit_at_request_completion']
        profile['sampling_error_count'] = None
        profile['sampling_error_scope'] = 'Not inferred from historical captures; actual profiler.log preserved for analysis'
        profile['profiler_log_sha256'] = sha(output / 'profiler.log')
        write(output / 'profile-context.json', profile)
        client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
        phase = 'restored-request'
        rows.append(run_one(client, common, args, identity, binding, base, plans[1], output))
        phase = 'verified-retention'
        client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run, identity)
        runs = {row['run'] for row in plans}
        for row in rows:
            client.retention.delete_owned(ROOT, args.campaign, runs, row['output_inventory'][0],
                parity_passed=True, receipts=output / 'deletion-receipts.jsonl')
        write(output / 'result.json', {'status': 'passed', 'rows': rows, 'profile_context': profile,
            'native_requests': 2, 'profiler_attachments': 1, 'restored_control_passed': True,
            'speed_promotion': False, 'streaming_qualification': False})
    except BaseException as error:
        write(output / 'failure.json', {'status': 'failed', 'phase': phase, 'error': repr(error),
            'rows': rows, 'profiler_worker_pid': worker.pid if worker else None,
            'profiler_exit_code': worker.poll() if worker else None, 'time': stamp(),
            'action': 'halt new requests; preserve process/evidence; no retry or restoration on failure'})
        raise
    finally:
        if worker is not None and worker.poll() is None:
            try:
                code = worker.wait(timeout=25)
                write(output / 'profiler-late-exit.json', {'exit_code': code, 'observed': stamp(), 'worker_pid': worker.pid})
            except subprocess.TimeoutExpired:
                write(output / 'profiler-wait-expired.json', {'worker_pid': worker.pid, 'observed': stamp(),
                    'action': 'no signals sent; preserve known worker for operator inspection'})


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--server-run', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--ready-check', action='store_true')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    schedule(args.campaign)
    client = load_client()
    args.packet, args.server_run = args.packet.absolute(), args.server_run.absolute()
    require(args.packet.parent == ROOT and args.server_run.parent == ROOT, 'Invalid packet/server location')
    client.retention.safe_path(ROOT, args.packet.name)
    client.retention.safe_path(ROOT, args.server_run.name, exists=not args.check_only)
    common = client.load('retained_profile_runtime_common', args.packet / 'launch/encoder_runtime_common.py')
    base, _ = client.prepared_sources(args, common)
    require(sha(PYSPY) == PYSPY_SHA, 'Profiler executable changed')
    if args.check_only:
        print(json.dumps({'status': 'source-check-passed', 'terminal_qualification_checked': False,
            'native_readiness_qualified': False, 'native_requests': 0, 'profiler_attachments': 0,
            'packet_manifest_sha256': PACKET_SHA, 'source_sha256': sha(Path(__file__))}, indent=2))
        return
    if args.ready_check:
        identity, _ = client.identity_binding(common, args.packet, args.manifest_sha256, args.server_run)
        binding = terminal_binding(client, args, identity)
        print(json.dumps({'status': 'same-process-terminal-ready', 'qualification_binding': binding,
            'native_requests': 0, 'profiler_attachments': 0, 'scope': 'Read-only endpoint/terminal admission; rechecked at execution'}, indent=2))
        return
    with (args.server_run / 'encoder-screen-client.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run_diagnostic(client, common, args, base)


if __name__ == '__main__':
    main()
