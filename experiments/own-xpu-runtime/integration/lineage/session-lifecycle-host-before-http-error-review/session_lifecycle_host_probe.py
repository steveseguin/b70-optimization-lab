#!/usr/bin/env python3
"""Prepared tiny HOST_ONLY HTTP lifecycle proof; native execution is explicit."""
from __future__ import annotations

import argparse
import contextlib
import copy
import http.client
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import threading
import time

import checkpoint_engine_host_probe as B
from chat_http import make_server
from chat_service import ChatService
from checkpoint_engine import CheckpointEngine
from native_checkpoint_store import NativeCheckpointStore
from request_front.client_v2 import NativeFront
from session_lifecycle import RunAdmission, SessionLifecycle

HERE, ROOT = B.HERE, B.ROOT
OUTPUT = B.PACKET / 'build/engine-integration-lifecycle-a'


class SyntheticCodec:
    """Explicit tiny alphabet fixture, unrelated to the production tokenizer."""
    def __init__(self, identity):
        self.vocab = identity['geometry']['vocab']
        B.require(self.vocab == 16, 'tiny alphabet requires vocab16')
        self.tokenizer_identity = copy.deepcopy(identity['tokenizer_identity'])
        self.terminal_token_ids = {identity['geometry']['eos']}

    def render(self, messages):
        B.require(len(messages) == 1 and messages[0]['role'] == 'user', 'single synthetic user message')
        return messages[0]['content']

    def encode(self, text):
        tokens = [ord(c) - ord('A') for c in text]
        B.require(tokens and all(0 <= t < 16 for t in tokens), 'synthetic alphabet A..P only')
        return tokens

    def decode(self, tokens):
        B.require(all(type(t) is int and 0 <= t < 16 for t in tokens), 'synthetic token range')
        return ''.join(chr(ord('A') + t) for t in tokens)


def plan(output=OUTPUT):
    B.require(output == OUTPUT and not os.path.lexists(output), 'fixed fresh lifecycle scratch required')
    base = B.plan(output)
    identity = base['expected_identity']
    B.require(identity['geometry']['eos'] in range(16), 'tiny native EOS must be in tiny vocabulary')
    sources = dict(base['sources_sha256'])
    for name in ('session_lifecycle_host_probe.py', 'test_session_lifecycle_host_probe.py',
                 'session_lifecycle.py', 'chat_service.py', 'chat_http.py'):
        path = HERE / name
        sources[str(path.relative_to(ROOT))] = B.sha(path)
    return dict(schema='ownrt.session-lifecycle-host-plan.v1', passed=True,
                device_executed=False, native_executed=False, base=base,
                output=str(output), argv=base['argv'], binary_sha256=base['binary_sha256'],
                native_request_limit=8, soft_request_limit=2, native_idle_seconds=30,
                soft_idle_seconds=20, native_seconds=180, soft_seconds=150,
                address_space_limit_bytes=4*1024**3, planned_write_bytes=8*B.SAVE_BOUND,
                disk_floor_bytes=B.FLOOR, save_bound_bytes=B.SAVE_BOUND,
                parking_budget_bytes=2*B.SAVE_BOUND,
                native_stop_token_ids=[identity['geometry']['eos']],
                requests=[dict(session='alpha', content='BCD', tokens=[1, 2, 3], max_tokens=4),
                          dict(session='beta', content='EF', tokens=[4, 5], max_tokens=4)],
                expected_controls=['SAVE', 'SAVE'], expected_stop_reason='quit',
                source_sha256=sources,
                scope='Tiny HOST_ONLY native owner/store plus synthetic codec and real local HTTP/lifecycle; no model/device/production-tokenizer qualification')


def start_owner(spec, environment, stderr, *, popen=subprocess.Popen):
    B.require(spec['argv'] == spec['base']['argv'] and spec['native_request_limit'] == 8,
              'unchanged pinned HOST_ONLY argv required')
    argv = spec['argv']
    B.require('--mini' in argv and '--pipeline-mini' in argv and
              argv[argv.index('--request-front-max-requests') + 1] == '8', 'tiny owner/native limit required')
    return popen(argv, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)


class GuardedStore:
    def __init__(self, store, guard):
        self.store, self.guard = store, guard

    def __getattr__(self, name):
        value = getattr(self.store, name)
        if name not in ('snapshot', 'delete'):
            return value
        def call(*args, **kwargs):
            self.guard()
            result = value(*args, **kwargs)
            self.guard()
            return result
        return call


def execute(spec):
    B.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
              set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'nice19 helper cores required')
    B.require(plan() == spec, 'inputs changed before tiny owner launch')
    B.require(shutil.disk_usage(ROOT).free >= B.FLOOR + spec['planned_write_bytes'], 'root write forecast refused')
    policy_module, parent = B.modules()
    environment = parent.parent_environment()
    tool_environment = {k: environment[k] for k in ('PATH', 'OMP_NUM_THREADS', 'LD_LIBRARY_PATH')}
    resource.setrlimit(resource.RLIMIT_AS, (spec['address_space_limit_bytes'], spec['address_space_limit_bytes']))
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / 'checkpoints').mkdir(mode=0o700)
    (OUTPUT / 'synthetic-identity.tsv').write_bytes(B.SYNTHETIC_IDENTITY)
    (OUTPUT / 'tokenizer.tsv').write_bytes(Path(spec['base']['tokenizer_source']).read_bytes())
    B.save(OUTPUT / 'plan.json', spec)
    result = dict(passed=False, device_executed=False, native_host_executed=False,
                  requests=[], lifecycle={}, incident_sigterm_count=0)
    owner = server = thread = lifecycle = raw_store = None
    primary_error = None
    outcome = {}
    guards = []

    def guard():
        B.require(shutil.disk_usage(ROOT).free >= B.FLOOR, 'tiny fixture root floor')
        guards.append(time.monotonic())

    try:
        with (OUTPUT / 'stderr.log').open('wb') as log:
            launched = time.monotonic()
            owner = start_owner(spec, environment, log)
            result.update(native_host_executed=True, pid=owner.pid, launched_monotonic=launched)
            front = NativeFront(owner, context=64, vocab=16, max_requests=8, startup_timeout=30, request_timeout=30)
            admission = RunAdmission(front, guard=guard, request_limit=2, idle_seconds=20,
                absolute_deadline=launched+150, last_native_activity=launched,
                native_idle_seconds=30, native_absolute_deadline=launched+180)
            identity = spec['base']['expected_identity']
            codec = SyntheticCodec(identity)
            raw_store = NativeCheckpointStore(OUTPUT / 'checkpoints', Path(spec['argv'][0]),
                                              spec['binary_sha256'], tool_environment)
            # Keep its root FD valid until the handler has definitely stopped,
            # including a failed HTTP client while the owner is still running.
            with contextlib.nullcontext(raw_store):
                engine = CheckpointEngine(admission.front, GuardedStore(raw_store, guard), root=raw_store.root,
                    expected_identity=identity, admitted_contract='v1.2+p198', save_size_bound_bytes=B.SAVE_BOUND,
                    storage_available=lambda path: shutil.disk_usage(path).free, floor_bytes=B.FLOOR)
                policy = policy_module.Parking(engine, codec.render, codec.encode,
                    budget_bytes=spec['parking_budget_bytes'],
                    accepted_contracts={('experimental-postreply-front', 'v1.2+p198')})
                service = ChatService(engine, policy, codec, model='synthetic-host-lifecycle',
                                      native_stop_token_ids=set(spec['native_stop_token_ids']))
                lifecycle = SessionLifecycle(service, admission)
                server = make_server(lifecycle.service)
                def serve():
                    try:
                        outcome['receipt'] = lifecycle.serve(server)
                    except BaseException as error:
                        outcome['error'] = error
                thread = threading.Thread(target=serve, name='tiny-host-http-lifecycle', daemon=True)
                thread.start()
                for row in spec['requests']:
                    payload = dict(model=service.model, messages=[dict(role='user', content=row['content'])],
                                   max_tokens=row['max_tokens'])
                    B.require(codec.encode(codec.render(payload['messages'])) == row['tokens'], 'synthetic prompt identity')
                    connection = http.client.HTTPConnection(*server.server_address, timeout=35)
                    try:
                        connection.request('POST', '/v1/chat/completions', json.dumps(payload).encode(),
                            {'Content-Type': 'application/json', 'X-Ownrt-Session': row['session']})
                        response = connection.getresponse()
                        body = json.loads(response.read())
                        result['requests'].append(dict(session=row['session'], payload=payload, status=response.status, response=body))
                        if 'error' in outcome:
                            raise outcome['error']
                        B.require(response.status == 200, 'tiny HTTP completion refused')
                    finally:
                        connection.close()
                thread.join(35)
                B.require(not thread.is_alive(), 'lifecycle retained after bounded join')
                if 'error' in outcome:
                    raise outcome['error']
                receipt = outcome['receipt']
                stopped = receipt['native_stopped']
                B.require(receipt['passed'] and receipt['close_calls'] == 1 and receipt['reason'] == 'request-limit'
                          and stopped['reason'] == 'quit' and stopped['completed_requests'] == 2
                          and stopped['completed_controls'] == 2 and stopped['discarded_pending'] is False
                          and stopped['pending_request_id'] == '' and owner.returncode == 0,
                          'soft two-request QUIT proof failed')
                B.require(front.max_requests == 8 and front.completed == front.completed_controls == 2,
                          'soft limit must stop before native eight-request limit')
                B.require(set(policy.parked) == {'alpha', 'beta'}, 'both policy SAVE states required')
                checkpoints = {}
                for row, reply in zip(spec['requests'], result['requests']):
                    parked = policy.parked[row['session']]
                    snapshot = raw_store.snapshot(parked.checkpoint_id)
                    B.require(snapshot is not None, 'saved state must remain visible after owner shutdown')
                    raw = B.read(OUTPUT / 'owner/requests' / reply['response']['id'][len('chatcmpl-'):] / 'result.json')
                    generated = raw['tokens']
                    display = generated[:-1] if generated[-1] in codec.terminal_token_ids else generated
                    B.require(reply['response']['choices'][0]['message']['content'] == codec.decode(display),
                              'HTTP output must preserve exact synthetic token text')
                    B.require(reply['response']['usage'] == dict(prompt_tokens=len(row['tokens']),
                        completion_tokens=len(generated), total_tokens=len(row['tokens'])+len(generated)), 'HTTP usage identity')
                    checkpoints[row['session']] = dict(id=parked.checkpoint_id, storage_bytes=snapshot.storage_bytes,
                        state_sha256=B.state_hashes(OUTPUT / 'checkpoints' / parked.checkpoint_id))
                native = B.read(OUTPUT / 'owner/receipt.json')
                B.require(native['passed'] and native['safe_to_exit'] and native['device_executed'] is False,
                          'HOST_ONLY teardown proof required')
                result.update(passed=True, lifecycle=receipt, checkpoints=checkpoints,
                    model_loads=front.ready['model_loads'], owner_returncode=owner.returncode,
                    guard_checks=len(guards), policy=policy.status(), native_receipt_sha256=B.sha(OUTPUT / 'owner/receipt.json'))
    except BaseException as error:
        primary_error = error
        result['error'] = str(error)
        if lifecycle is not None:
            lifecycle.request_close()
        if owner is not None and owner.poll() is None:
            result['incident_sigterm_count'] = 1
            try:
                owner.send_signal(signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                owner.wait(timeout=65)
            except subprocess.TimeoutExpired:
                pass
        if thread is not None:
            thread.join(2)
        result.update(owner_retained=owner is not None and owner.poll() is None,
                      handler_retained=thread is not None and thread.is_alive())
        raise
    finally:
        try:
            if thread is None or not thread.is_alive():
                if server is not None:
                    server.server_close()
                if raw_store is not None:
                    raw_store.close()
            result['finished_utc_ns'] = time.time_ns()
            B.save(OUTPUT / 'result.json', result)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note('probe receipt/cleanup failure: ' + str(cleanup_error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--run-host-only', action='store_true')
    args = parser.parse_args()
    spec = plan()
    if args.plan:
        print(json.dumps(spec, indent=2))
    else:
        result = execute(spec)
        print(json.dumps(dict(passed=result['passed'], device_executed=False, requests=2,
                              native_stop=result['lifecycle']['native_stopped']['reason'], output=str(OUTPUT))))


if __name__ == '__main__':
    main()
