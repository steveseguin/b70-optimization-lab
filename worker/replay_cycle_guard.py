#!/usr/bin/env python3
"""Capture or verify exact cycle-guard trace replay; never execute recorded commands."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from run import CheckedEnvironment, FINISH

HERE = Path(__file__).resolve().parent
PACKETS = ('2026-09-14-five-issues', '2026-09-14-profile-screen', '2026-09-14-readable-observations')
FAILED = 'readable-ml-incomplete-depth-flag'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_records(trajectory):
    records = []
    messages = trajectory['messages']
    for index, message in enumerate(messages):
        actions = message.get('extra', {}).get('actions', [])
        if message.get('role') != 'assistant' or not actions:
            continue
        require(len(actions) == 1, 'one action per response required')
        command = actions[0]['command']
        require(isinstance(command, str), 'command must be complete text')
        blocks = re.findall(r'```bash\s*\n(.*?)\n```', message['content'], re.S)
        require(len(blocks) == 1 and blocks[0].strip() == command.strip(), 'action differs from final-answer bash block')
        if command.strip() == FINISH:
            records.append({'command': command, 'finish': True})
            continue
        observations = []
        for following in messages[index + 1:]:
            if following['role'] == 'assistant':
                break
            if following['role'] == 'user':
                observations.append(following['content'])
        require(len(observations) == 1, 'expected one complete tool observation')
        content = observations[0]
        if content.startswith('<tool_response>'):
            match = re.fullmatch(r'<tool_response>\nExit status: (-?\d+)\nOutput:\n(.*)\n</tool_response>', content, re.S)
            require(match is not None, 'invalid readable tool observation')
            observation = {'returncode': int(match[1]), 'output': match[2]}
        else:
            value = json.loads(content)
            observation = {key: value[key] for key in ('returncode', 'output')}
        require(type(observation['returncode']) is int and isinstance(observation['output'], str), 'invalid tool result')
        records.append({'command': command, 'observation': observation})
    return records


def replay(records):
    class RecordedSandbox:
        calls = 0
        current = None
        def execute(self, action):
            require(action['command'] == self.current['command'], 'replay command mismatch')
            self.calls += 1
            return dict(self.current['observation'])
    sandbox = RecordedSandbox()
    environment = CheckedEnvironment(sandbox, 'never executed', Path('/unused'), 3)
    warnings, blocked, finishes = [], None, 0
    for number, record in enumerate(records, 1):
        if record.get('finish'):
            # Acceptance execution is covered by test_run/test_cycle_guard CPU fakes.
            environment.two_command_cycle.reset()
            finishes += 1
            continue
        sandbox.current = record
        before = environment.loop_warnings
        try:
            environment.execute({'command': record['command']})
        except RuntimeError as exc:
            blocked = {'action': number, 'reason': str(exc), 'tool_executed': False}
            break
        if environment.loop_warnings > before:
            warnings.append(number)
    return {'recorded_actions': len(records), 'tool_calls_replayed': sandbox.calls,
            'finish_commands': finishes, 'warning_actions': warnings, 'blocked': blocked,
            'two_command_cycle_warnings': environment.two_command_cycle.warnings}


def packet_traces(packet_root):
    """Read only hash-bound result/trajectory members; no filesystem extraction."""
    bindings, traces = {}, []
    for packet in PACKETS:
        folder = packet_root / packet
        manifest_bytes = (folder / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_bytes)
        archive = folder / 'evidence.tar.gz'
        require(sha(archive.read_bytes()) == manifest['archive_sha256'], 'archive hash mismatch: ' + packet)
        bindings[packet] = {'manifest_sha256': sha(manifest_bytes), 'archive_sha256': manifest['archive_sha256']}
        with tarfile.open(archive, 'r:gz') as tar:
            def read(name):
                member = tar.getmember(name)
                require(member.isfile() and member.size <= 128 * 1024 * 1024, 'unsafe source member')
                data = tar.extractfile(member).read()
                require(len(data) == manifest['members'][name]['bytes'] and sha(data) == manifest['members'][name]['sha256'], 'source member hash mismatch: ' + name)
                return data
            for name in sorted(manifest['members']):
                if not name.endswith('/result.json') or name.count('/') != 1:
                    continue
                result_bytes = read(name)
                result = json.loads(result_bytes)
                directory = name.split('/')[0]
                if not result.get('acceptance_passed') and directory != FAILED:
                    continue
                trajectory_bytes = read(directory + '/trajectory.json')
                traces.append({'packet': packet, 'directory': directory,
                               'automatic_acceptance_passed': result['acceptance_passed'],
                               'recorded_model_calls': result['model_requests'],
                               'source_hashes': {'trajectory.json': sha(trajectory_bytes), 'result.json': sha(result_bytes)},
                               'records': exact_records(json.loads(trajectory_bytes))})
    return bindings, traces


def make_report(bindings, traces):
    rows = []
    for trace in traces:
        result = replay(trace['records'])
        if trace['automatic_acceptance_passed']:
            require(result['blocked'] is None and result['warning_actions'] == [], 'guard affects an acceptance-passing trace')
        else:
            require(trace['directory'] == FAILED and result['warning_actions'] == [14]
                    and result['blocked']['action'] == 15 and result['tool_calls_replayed'] == 14,
                    'failed trace did not reproduce the expected exact cycle')
        rows.append({key: value for key, value in trace.items() if key != 'records'} | {'replay': result})
    return {'schema': 'neural.download.worker-cycle-replay.v1', 'packet_bindings': bindings,
            'automatic_acceptance_passing_traces': sum(row['automatic_acceptance_passed'] for row in rows),
            'failed_traces': sum(not row['automatic_acceptance_passed'] for row in rows), 'traces': rows,
            'limitations': ['Offline replay of recorded observations; no recorded commands or model requests executed.',
                           'Automatic acceptance is separate from independent review; one thinking trace was review-rejected.',
                           'FINISH acceptance execution is tested separately with CPU fakes.',
                           'No model reaction, latency, token savings, quality, or acceptance improvement measured.',
                           'Identical command/output cycles do not prove hidden workspace state made no progress.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root', type=Path, help='Raw campaign parent (capture only); every selected source must match its frozen packet')
    parser.add_argument('--packet-root', type=Path, default=HERE.parent / 'experiments/local-coding-worker/data')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--verify', action='store_true', help='Replay retained compact receipts and compare with frozen archive sources')
    args = parser.parse_args()
    bindings, traces = packet_traces(args.packet_root)
    report = make_report(bindings, traces)
    sources = {'worker/run.py': sha((HERE / 'run.py').read_bytes()), 'worker/replay_cycle_guard.py': sha(Path(__file__).read_bytes())}
    if args.verify:
        require(json.loads((args.out / 'traces.json').read_bytes()) == traces, 'compact traces differ from frozen source records')
        require(json.loads((args.out / 'report.json').read_bytes()) == report, 'stored replay report differs')
        receipt = json.loads((args.out / 'capture.json').read_bytes())
        require(receipt['traces_sha256'] == sha((args.out / 'traces.json').read_bytes()) and receipt['report_sha256'] == sha((args.out / 'report.json').read_bytes()), 'compact receipt hash mismatch')
    else:
        require(args.raw_root is not None, '--raw-root is required for capture')
        for trace in traces:
            candidates = [args.raw_root / trace['directory']]
            candidates += [folder / trace['directory'] for folder in args.raw_root.glob('local-worker*') if folder.is_dir()]
            require(any(all((folder / name).is_file() and sha((folder / name).read_bytes()) == digest
                            for name, digest in trace['source_hashes'].items()) for folder in candidates),
                    'raw result/trajectory do not match frozen packet: ' + trace['directory'])
        args.out.mkdir(parents=True, exist_ok=True)
        for name in ('traces.json', 'report.json', 'capture.json'):
            require(not (args.out / name).exists(), 'refusing to replace existing replay evidence: ' + name)
        trace_bytes, report_bytes = encoded(traces), encoded(report)
        (args.out / 'traces.json').write_bytes(trace_bytes)
        (args.out / 'report.json').write_bytes(report_bytes)
        (args.out / 'capture.json').write_bytes(encoded({'source_hashes': sources, 'traces_sha256': sha(trace_bytes), 'report_sha256': sha(report_bytes)}))
    print(json.dumps({'verified': args.verify, 'automatic_acceptance_passing_traces': report['automatic_acceptance_passing_traces'],
                      'failed_traces': report['failed_traces'], 'current_replay_sources': sources}, sort_keys=True))


if __name__ == '__main__':
    main()
