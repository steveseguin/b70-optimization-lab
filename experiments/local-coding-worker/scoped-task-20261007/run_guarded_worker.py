#!/usr/bin/env python3
"""Trial-only network/action guard around the unchanged shared worker."""
import json
import os
from pathlib import Path
import signal
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SERVER = Path('/home/steve/worker-scoped-task-20261007/server')


def make_health_guard(server):
    server = Path(server)
    identity = []
    def healthy():
        if any((server / name).exists() for name in ('STOP', 'FAULT.json', 'shutdown.json')):
            raise RuntimeError('Server stopped, stopping or faulted; no further action')
        pid = json.loads((server / 'pid.json').read_text())['supervisor_pid']
        os.kill(pid, 0)
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
        launch = json.loads((server / 'launch.json').read_text())
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if launch['boot_id'] != boot:
            raise RuntimeError('Supervisor boot identity changed')
        current = (pid, boot, fields[19])
        if fields[0] == 'Z':
            raise RuntimeError('Supervisor is a zombie')
        if identity and identity[0] != current:
            raise RuntimeError('Supervisor process identity changed')
        if not identity:
            identity.append(current)
    return healthy


def guard_model(model, healthy, minimum_input_exclusive=300):
    original_open = model.opener.open
    def checked_open(*args, **kwargs):
        healthy()
        return original_open(*args, **kwargs)
    model.opener.open = checked_open
    original_request = model.wire.request_one
    def checked_request(base, payload, directory, **kwargs):
        healthy()
        count = json.loads((Path(directory) / 'token-count.json').read_text())['input_tokens']
        if type(count) is not int or not minimum_input_exclusive < count <= model.max_input:
            raise ValueError('Unsupported or over-budget model input')
        if count + payload['max_tokens'] > 33024:
            raise ValueError('Combined input/output exceeds frozen context')
        response = original_request(base, payload, directory, **kwargs)
        # Preserve a complete original reply even when a trial-specific check refuses it.
        model.wire.write_json(Path(directory) / 'guard-response.json', response)
        healthy()
        if response.get('finish_reasons') != ['stop']:
            raise ValueError('Natural stop required; truncated output refused')
        cached = response.get('cached_tokens')
        if type(cached) is not int or cached != 0:
            raise ValueError('Explicit zero cached tokens required')
        tokens = response.get('token_ids')
        if (response.get('prompt_tokens') != count or response.get('token_ids_available') is not True
                or not isinstance(tokens, list) or type(response.get('completion_tokens')) is not int
                or len(tokens) != response['completion_tokens']):
            raise ValueError('Complete matching prompt/output token accounting required')
        return response
    model.wire.request_one = checked_request
    original_query = model.query
    def checked_query(*args, **kwargs):
        healthy()
        return original_query(*args, **kwargs)
    model.query = checked_query
    return model


def stop_request(server):
    if not server.is_dir():
        return
    try:
        with (server / 'STOP').open('x') as stream:
            stream.write('Scoped task ended; one graceful stop, no retry.\n')
            stream.flush(); os.fsync(stream.fileno())
    except FileExistsError:
        pass


def main():
    os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = '/home/steve/worker-scoped-task-20261007/mini-config'
    os.environ['MSWEA_SILENT_STARTUP'] = '1'
    sys.path.insert(0, str(ROOT / 'worker'))
    import run as worker
    healthy = make_health_guard(SERVER)
    original_model = worker.LocalModel
    def guarded_model(*args, **kwargs):
        healthy()
        return guard_model(original_model(*args, **kwargs), healthy)
    worker.LocalModel = guarded_model
    original_execute = worker.DockerSandbox.execute
    def guarded_execute(self, *args, **kwargs):
        healthy()
        return original_execute(self, *args, **kwargs)
    worker.DockerSandbox.execute = guarded_execute
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Scoped worker interrupted')
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        healthy()
        return worker.main()
    finally:
        stop_request(SERVER)
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
