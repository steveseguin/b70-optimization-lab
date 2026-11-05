#!/usr/bin/env python3
"""Prepare or explicitly run isolated Pi 1.2.0 functional smoke; never starts/restarts the model server.

Default is preparation only. --run forwards bounded real inference requests, so use only after coordinator admission.
--compaction exercises Pi's CLIENT compaction at an advertised 8K window, not the server's native keeper policy.
"""
import argparse
import hashlib
import http.client
import http.server
import json
import os
import re
from pathlib import Path
import subprocess
import threading
import time
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NODE_IMAGE = 'node@sha256:8a34c4ab3ea2c5cd194f07e317b2a8f09461d3c8b05c4e34c8ccd56d56024c4d'
MODEL = 'sc117-qwen3.8-flash-next-iq3s-ownrt'
SOURCE = 'export function sum(values) {\n  let total = 0;\n  for (const value of values) total = value;\n  return total;\n}\n'
TEST = '''import test from 'node:test';
import assert from 'node:assert/strict';
import {sum} from './sum.mjs';
test('sum preserves every value', () => {
  assert.equal(sum([2, 7, 11]), 20);
  assert.equal(sum([-4, 3, -2]), -3);
  assert.equal(sum([]), 0);
  const input = [5, 6]; sum(input); assert.deepEqual(input, [5, 6]);
});
'''


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def prepare(out, model, compaction, fixture='sum'):
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ('work', 'home', 'home/.pi', 'home/.pi/agent'):
        (out / name).mkdir(mode=0o700)
    source_hashes = {}
    if fixture == 'notesdelta':
        for name in ('notesdelta.py', 'test_notesdelta.py', 'sync_notesdelta.py'):
            original = (REPO / 'tools/ctxkeeper' / name).read_bytes()
            source_hashes[name] = hashlib.sha256(original).hexdigest()
            if name == 'notesdelta.py':
                needle = b'return int(nums[-1].replace(",", ""))'
                if original.count(needle) != 1:
                    raise ValueError('unique notesdelta mutation site no longer matches')
                original = original.replace(needle, b'return int(nums[0].replace(",", ""))', 1)
            (out / 'work' / name).write_bytes(original)
        prompt = ('Fix the bug in notesdelta.py so python3 -m unittest -v passes. First run the tests and '
                  'inspect the failing behavior, then read the relevant implementation and tests. Edit only '
                  'notesdelta.py, make the smallest fix, and run the tests again. Do not alter test_notesdelta.py '
                  'or sync_notesdelta.py and do not install anything. Keep your final explanation short.')
    else:
        (out / 'work/sum.mjs').write_text(SOURCE)
        (out / 'work/test_sum.mjs').write_text(TEST)
        source_hashes = {'test_sum.mjs': hashlib.sha256(TEST.encode()).hexdigest()}
        prompt = ('Fix sum.mjs so node --test passes. First read the source and test, run the failing test, '
                  'edit only sum.mjs, then run the test again. Do not alter tests or install anything. '
                  'Use the available tools and keep your final explanation short.')
    if compaction:
        for i in range(1, 6):
            rows = [f'PART {i}']
            if i == 1:
                rows.append('Remember deployment checksum 48151623 for your final answer.')
            rows.extend(f'job-{i}-{j:03d} host=worker-{j%17} status=OK duration={j%31+1}s verified=true'
                        for j in range(80))
            (out / f'work/log-part-{i}.txt').write_text('\n'.join(rows) + '\n')
        prompt = ('Before fixing the code, read log-part-1.txt through log-part-5.txt in order, '
                  'one separate read tool call per file. Remember the checksum in part 1 and repeat it in your '
                  'final answer. Do not use a combined command or omit a part. ' + prompt)
    (out / 'prompt.txt').write_text(prompt + '\n')
    save(out / 'home/.pi/agent/settings.json', {
        'defaultProvider': 'sc117-smoke', 'defaultModel': model, 'defaultThinkingLevel': 'medium',
        'compaction': {'enabled': compaction, 'reserveTokens': 2048, 'keepRecentTokens': 2048},
        'httpIdleTimeoutMs': 180000, 'retry': {'enabled': False, 'maxRetries': 0,
                                            'provider': {'timeoutMs': 180000, 'maxRetries': 0}},
        'cacheWarming': 'off', 'enableInstallTelemetry': False, 'enableAnalytics': False})
    save(out / 'manifest.json', {'schema': 'sc117.pi-functional-smoke.v1', 'model': model,
        'pi_version': '1.2.0', 'node_image': NODE_IMAGE, 'compaction': 'pi-client-8192' if compaction else 'off',
        'fixture': fixture, 'fixture_source_sha256': source_hashes,
        'fixture_test_sha256': source_hashes.get('test_sum.mjs', source_hashes.get('test_notesdelta.py')),
        'server_mutations': False,
        'notes': 'No requests until --run. CPU preparation does not qualify inference or compaction.'})


def models(url, model, compaction):
    # Exercise the exact deployed thinking mapping. The older qwen-chat-template compatibility
    # emitted only enable_thinking and accidentally selected the model template's xhigh default.
    provider = json.loads((HERE / 'pi/models.json').read_text())['providers']['sc117']
    provider.update(baseUrl=url + '/v1', apiKey='sc117-smoke-dummy')
    configured = provider['models'][0]
    configured.update(id=model, name='SC117 isolated functional smoke',
                      contextWindow=8192 if compaction else 131072,
                      maxTokens=2048 if compaction else 4096)
    return {'providers': {'sc117-smoke': provider}}


class Recorder:
    def __init__(self, out, upstream, maximum):
        self.out, self.upstream, self.maximum = out, urlsplit(upstream), maximum
        if self.upstream.scheme != 'http' or self.upstream.username or self.upstream.password:
            raise ValueError('plain local HTTP endpoint without embedded credentials required')
        self.lock, self.rows, self.halted = threading.Lock(), [], False

    def handler(self):
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != '/v1/chat/completions':
                    return self.send_error(404)
                with owner.lock:
                    if owner.halted or len(owner.rows) >= owner.maximum:
                        owner.halted = True
                        return self.send_error(503, 'smoke forwarding halted; no retry forwarded')
                    index = len(owner.rows) + 1
                    started_mono = time.monotonic()
                    row = {'request': index, 'started': time.time(), 'reasoning_chunks': 0,
                           'content_chunks': 0, 'tool_chunks': 0, 'error': None, 'usage': None, 'completed': False,
                           'first_delta_seconds': None, 'first_reasoning_seconds': None,
                           'first_content_seconds': None, 'done_seconds': None, 'bytes_received': 0}
                    owner.rows.append(row)
                conn = None
                try:
                    n = int(self.headers.get('Content-Length', '0'))
                    if not 0 < n <= 2 * 1024**2:
                        raise ValueError('request body bound')
                    raw = self.rfile.read(n)
                    body = json.loads(raw)
                    save(owner.out / f'request-{index:02d}.json', body)
                    headers = {'Content-Type': 'application/json'}
                    for key in ('x-session-affinity', 'x-ctx-session'):
                        if self.headers.get(key): headers[key] = self.headers[key]
                    conn = http.client.HTTPConnection(owner.upstream.hostname, owner.upstream.port or 80, timeout=180)
                    base = owner.upstream.path.rstrip('/')
                    if base.endswith('/v1'): base = base[:-3]
                    conn.request('POST', base + self.path, raw, headers)
                    response = conn.getresponse()
                    row['http_status'] = response.status
                    self.send_response(response.status)
                    self.send_header('Content-Type', response.getheader('Content-Type', 'application/json'))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    if response.status >= 400:
                        owner.halted = True
                        row['error'] = f'HTTP {response.status}'
                    with (owner.out / f'response-{index:02d}.sse').open('wb') as capture:
                        while True:
                            line = response.readline()
                            if not line: break
                            row['bytes_received'] += len(line)
                            capture.write(line); capture.flush()
                            try: self.wfile.write(line); self.wfile.flush()
                            except (BrokenPipeError, ConnectionResetError):
                                row['client_disconnected'] = True  # drain the existing response, never retry it
                            if line.startswith(b'data: '):
                                data = line[6:].strip()
                                if data == b'[DONE]':
                                    row['completed'] = True
                                    row['done_seconds'] = round(time.monotonic() - started_mono, 6)
                                    continue
                                event = json.loads(data)
                                if event.get('error'):
                                    row['error'] = event['error']; owner.halted = True
                                if event.get('usage'): row['usage'] = event['usage']
                                if event.get('ownrt'): row['ownrt'] = event['ownrt']
                                for choice in event.get('choices', []):
                                    delta = choice.get('delta', {})
                                    row['reasoning_chunks'] += bool(delta.get('reasoning_content'))
                                    row['content_chunks'] += bool(delta.get('content'))
                                    row['tool_chunks'] += bool(delta.get('tool_calls'))
                                    elapsed = round(time.monotonic() - started_mono, 6)
                                    if any(delta.get(key) for key in ('reasoning_content', 'content', 'tool_calls')):
                                        if row['first_delta_seconds'] is None: row['first_delta_seconds'] = elapsed
                                    if delta.get('reasoning_content') and row['first_reasoning_seconds'] is None:
                                        row['first_reasoning_seconds'] = elapsed
                                    if delta.get('content') and row['first_content_seconds'] is None:
                                        row['first_content_seconds'] = elapsed
                                    if choice.get('finish_reason'): row['finish_reason'] = choice['finish_reason']
                    if body.get('stream') and not row['completed']:
                        owner.halted = True
                        row['error'] = row['error'] or 'SSE ended without DONE'
                except Exception as error:
                    owner.halted = True; row['error'] = repr(error)
                finally:
                    if conn is not None: conn.close()
                    row['wall_seconds'] = round(time.monotonic() - started_mono, 6)
                    with owner.lock: save(owner.out / 'traffic.json', owner.rows)
        return Handler


def event_checks(events, compaction):
    """Grade executed tools and completed compaction, never mere model intent/start notifications."""
    starts, executed, successful, log_reads, bash_log_mentions = {}, [], set(), [], []
    final_answer = ''
    completions = []
    for event in events:
        kind = event.get('type')
        if kind == 'tool_execution_start':
            starts[event.get('toolCallId')] = event
        elif kind == 'tool_execution_end':
            start = starts.get(event.get('toolCallId'), {})
            name = event.get('toolName', start.get('toolName'))
            args = start.get('args') or {}
            executed.append(name)
            if event.get('isError') is not False:
                continue
            successful.add(name)
            if name == 'read':
                base = Path(str(args.get('path', ''))).name
                if re.fullmatch(r'log-part-[1-5]\.txt', base):
                    log_reads.append(base)
            if name == 'bash':
                mentions = re.findall(r'log-part-[1-5]\.txt', str(args.get('command', '')))
                if mentions:
                    # A mention does not prove a read (it could be echo); retain the deviation explicitly.
                    bash_log_mentions.append({'command': args.get('command'), 'files': mentions})
        elif kind == 'message_end' and (event.get('message') or {}).get('role') == 'assistant':
            final_answer = ''.join(block.get('text', '') for block in event['message'].get('content', [])
                                   if isinstance(block, dict) and block.get('type') == 'text')
        elif kind in ('compaction_end', 'auto_compaction_end'):
            result = event.get('result')
            ok = (event.get('aborted') is False and not event.get('errorMessage') and not event.get('error')
                  and isinstance(result, dict) and isinstance(result.get('summary'), str)
                  and bool(result['summary'].strip()))
            completions.append({'successful': ok, 'reason': event.get('reason'),
                                'aborted': event.get('aborted'), 'error': event.get('errorMessage', event.get('error')),
                                'tokens_before': result.get('tokensBefore') if isinstance(result, dict) else None,
                                'estimated_tokens_after': result.get('estimatedTokensAfter') if isinstance(result, dict) else None})
    checks = {f'{name}_tool_executed': name in successful for name in ('read', 'edit', 'bash')}
    if compaction:
        checks.update(client_compaction_succeeded=bool(completions) and all(c['successful'] for c in completions),
                      all_five_logs_read=list(dict.fromkeys(log_reads)) == [f'log-part-{i}.txt' for i in range(1, 6)],
                      checksum_in_final_answer='48151623' in final_answer)
    return checks, {'executed_tools': executed, 'log_reads': log_reads, 'bash_log_mentions': bash_log_mentions,
                    'compaction_results': completions, 'final_answer': final_answer}


def run(args, out):
    runtime = args.runtime.resolve()
    package = runtime / 'node_modules/@earendil-works/pi-coding-agent'
    if json.loads((package / 'package.json').read_text())['version'] != '1.2.0':
        raise ValueError('runtime must contain pinned Pi 1.2.0; no installation is performed')
    recorder = Recorder(out, args.upstream, args.max_requests)
    proxy = http.server.ThreadingHTTPServer(('127.0.0.1', 0), recorder.handler())
    proxy.daemon_threads = True
    save(out / 'home/.pi/agent/models.json', models(f'http://127.0.0.1:{proxy.server_port}', args.model, args.compaction))
    thread = threading.Thread(target=proxy.serve_forever, daemon=True); thread.start()
    name = f'sc117-pi-smoke-{os.getpid()}'
    work_target = '/pi/work' if args.fixture == 'notesdelta' else '/work'
    common = ['docker', 'run', '--rm', '--name', name, '--network', 'host', '--read-only',
        '--cap-drop=ALL', '--security-opt=no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=268435456',
        '-v', f'{runtime}:/opt/agent:ro', '-v', f'{out / "work"}:{work_target}:rw',
        '-v', f'{out / "home"}:/home/pi:rw', '-w', work_target,
        '-e', 'PI_CODING_AGENT_DIR=/home/pi/.pi/agent',
        '-e', 'PI_OFFLINE=1', '-e', 'PI_SKIP_VERSION_CHECK=1', '-e', 'PI_TELEMETRY=0',
        '-e', 'NO_PROXY=127.0.0.1,localhost', '-e', 'no_proxy=127.0.0.1,localhost', args.node_image]
    command = common + ['node', '/opt/agent/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js',
        '--mode', 'json', '--offline', '--no-extensions', '--provider', 'sc117-smoke', '--model', args.model,
        '--', (out / 'prompt.txt').read_text()]
    save(out / 'command.json', command)
    rc = None
    try:
        with (out / 'pi-events.jsonl').open('w') as stdout, (out / 'pi-stderr.txt').open('w') as stderr:
            rc = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                timeout=args.wall_seconds).returncode
    except subprocess.TimeoutExpired:
        recorder.halted = True
        # This is the isolated CPU client container; the GPU server is never signalled.
        subprocess.run(['docker', 'stop', '-t', '10', name], capture_output=True, timeout=20)
    finally:
        proxy.shutdown(); proxy.server_close(); thread.join()
    grade_command = ['python3', '-B', '-m', 'unittest', '-v'] if args.fixture == 'notesdelta' else ['node', '--test']
    grade = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
        '-v', f'{out / "work"}:{work_target}:ro', '-w', work_target, args.node_image, *grade_command],
        capture_output=True, text=True, timeout=30)
    (out / 'grade.txt').write_text(grade.stdout + grade.stderr)
    events = []
    for line in (out / 'pi-events.jsonl').read_text().splitlines():
        try: events.append(json.loads(line))
        except ValueError: pass
    fixture_manifest = json.loads((out / 'manifest.json').read_text())
    source_hashes = fixture_manifest['fixture_source_sha256']
    protected = ['test_notesdelta.py', 'sync_notesdelta.py'] if args.fixture == 'notesdelta' else ['test_sum.mjs']
    unchanged = all((out / 'work' / name).is_file() and
                    hashlib.sha256((out / 'work' / name).read_bytes()).hexdigest() == source_hashes[name]
                    for name in protected)
    cached = [((r.get('usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens', 0) for r in recorder.rows]
    compactions = [e.get('type') for e in events if 'compaction' in str(e.get('type', '')).lower()]
    checks = {'client_exit_zero': rc == 0, 'fixture_tests_pass': grade.returncode == 0,
        'fixture_tests_unchanged': unchanged, 'multiple_turns': len(recorder.rows) >= 3,
        'thinking_on_wire': any(r['reasoning_chunks'] for r in recorder.rows),
        'tool_calls_on_wire': any(r['tool_chunks'] for r in recorder.rows),
        'no_upstream_error': bool(recorder.rows) and not any(r['error'] for r in recorder.rows),
        'reuse_observed': any(n > 0 for n in cached)}
    if args.fixture == 'notesdelta':
        target = out / 'work/notesdelta.py'
        checks['original_source_restored_exactly'] = (target.is_file() and
            hashlib.sha256(target.read_bytes()).hexdigest() == source_hashes['notesdelta.py'])
    tool_checks, event_details = event_checks(events, args.compaction)
    checks.update(tool_checks)
    required = [v for k, v in checks.items() if k != 'reuse_observed' or args.require_reuse]
    result = {'passed': all(required), 'checks': checks, 'requests': len(recorder.rows),
              'cached_tokens': cached, 'compaction_events': compactions, 'client_exit': rc,
              'server_restarts': 0, 'server_signals': 0, 'event_details': event_details}
    save(out / 'result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path, help='fresh private output directory')
    parser.add_argument('--upstream', default='http://127.0.0.1:18160')
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--runtime', type=Path, help='directory containing pinned Pi node_modules, mounted read-only')
    parser.add_argument('--node-image', default=NODE_IMAGE)
    parser.add_argument('--fixture', choices=('sum', 'notesdelta'), default='sum')
    parser.add_argument('--run', action='store_true', help='explicitly send real inference requests')
    parser.add_argument('--compaction', action='store_true', help='separate Pi-client 8K compaction scenario')
    parser.add_argument('--require-reuse', action='store_true')
    parser.add_argument('--max-requests', type=int, default=16)
    parser.add_argument('--wall-seconds', type=int, default=900)
    args = parser.parse_args()
    if args.run and args.runtime is None: parser.error('--run requires --runtime')
    if not 1 <= args.max_requests <= 32 or not 30 <= args.wall_seconds <= 1800:
        parser.error('request count must be1..32 and wall time30..1800 seconds')
    out = args.out.absolute()
    prepare(out, args.model, args.compaction, args.fixture)
    if args.run: return run(args, out)
    save(out / 'home/.pi/agent/models.json', models('http://127.0.0.1:PORT-ASSIGNED-AT-RUN', args.model, args.compaction))
    print(f'Prepared {out}; no inference requests sent. Run again with --run --runtime PATH and a fresh --out.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
