#!/usr/bin/env python3
"""Bounded packet108 campaign on one already-owned server. Never starts or retries it.

Default prints the CPU schedule. --run requires a pinned client contract and
manifest. Success keeps the application available. Failure attempts one proven-idle
graceful incident stop; faults or unresolved work require the coordinator.
"""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request

import reference_gate as gate
import schedule
import request_client


def emit(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), message, flush=True)


def call(path, payload=None, timeout=20):
    raw = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request('http://127.0.0.1:8188' + path, data=raw,
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return gate.strict_json(response.read())


def is_idle(state, allow_failed_jobs=False):
    if state.get('queue_running') != 0 or state.get('queue_pending') != 0:
        return False
    if type(state.get('preview_pending')) is not int or state['preview_pending'] != 0:
        return False
    if type(state.get('preview_failures')) is not int or (state['preview_failures'] and not allow_failed_jobs):
        return False
    pipe = state['pipeline']
    if pipe['running'] != 0:
        return False
    for stage in pipe['stages'].values():
        if stage['queued_indices']:
            return False
        for job in stage['jobs']:
            if job['done'] is not True or (job['error'] is not None and not allow_failed_jobs):
                return False
    return True


class Campaign:
    def __init__(self, contract, contract_sha, manifest_sha):
        self.client = request_client.Client(contract, contract_sha)
        self.run, self.root = self.client.run, self.client.root
        gate.require(self.client.full_schedule and self.client.contract['runtime_manifest_sha256'] == manifest_sha,
                     'Complete sealed schedule and expected runtime manifest required')
        self.manifest_sha = manifest_sha
        self.requests = []
        self.actions = []
        self.stop_attempted = False
        self.owns_campaign = False
        self.lock_fd = None
        self.started = time.time()

    def check_identity(self):
        # This passive process check is also valid during graceful failure closeout.
        request_client.actual_process(self.client.identity)
        gate.require(gate.sha(gate.read_file(self.run / 'server-identity.json')) ==
                     self.client.contract['server_identity_sha256'], 'Server identity changed')

    def status(self):
        self.check_identity()
        value = call('/ltx-resolution/status')
        gate.require(value['server_identity_sha256'] == self.client.contract['server_identity_sha256'] and
                     value['runtime_manifest_sha256'] == self.manifest_sha, 'Endpoint belongs to another runtime')
        return value

    def wait_idle(self, seconds=600, closing=False):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if (self.root / 'FAULT.json').exists():
                raise RuntimeError('GPU fault latched; preserve server for incident action')
            value = self.status()
            if not closing:
                gate.require(value['halted'] is None and value['state']['fault'] is False,
                             'Resolution runtime halted')
            if value['active'] is None or closing:
                if is_idle(value['state'], allow_failed_jobs=closing):
                    return value
            time.sleep(2)
        raise TimeoutError('Quiescence not established; no forced stop or request retry')

    async def request(self, row):
        # Refresh the trusted phase observation immediately before the primitive
        # reads it. Serial HTTP completion can still overlap asynchronous stage
        # jobs; only setup boundaries require all pipeline workers idle.
        self.status()
        emit('request ' + row['name'])
        await self.client.execute(row['name'])
        self.requests.append(row['name'])
        emit('completed ' + row['name'])

    def action(self, name):
        self.wait_idle()
        self.check_identity()
        emit('phase action ' + name)
        # One POST; a lost response is uncertain and is never resubmitted.
        # Exact diagnostic proof reconstructs native and candidate gates; allow bounded CPU scans.
        timeout = 300 if name.startswith('verify-') else 180
        value = call('/ltx-resolution/action', {'action': name}, timeout=timeout)
        gate.require(value.get('passed') is True and value.get('action') == name, 'Phase action did not pass')
        self.actions.append(name)
    async def execute(self):
        self.lock_fd = os.open(self.run / 'resolution-campaign.lock', os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        gate.require(not (self.run / 'resolution-campaign-started.json').exists(), 'Campaign may run only once')
        request_client.write_new(self.run / 'resolution-campaign-started.json', {
            'schema': 'ltx.resolution-campaign-start.v1', 'started_unix': self.started,
            'client_contract_sha256': self.client.contract_sha, 'manifest_sha256': self.manifest_sha,
            'policy': '29 attempts maximum; one owned application; no restart/retry'})
        self.owns_campaign = True
        self.wait_idle()
        setup = schedule.build_schedule(plan_path=Path(self.client.contract['plan_path']))['schedule']['rows']
        for row in setup[:2]:
            await self.request(row)
            self.wait_idle()
        self.action('before-native')
        for row in [r for r in self.client.plan['requests'] if r['phase'] in ('native-reference', 'native-repeat')]:
            await self.request(row)
            if row['name'] == self.client.plan['requests'][0]['name']:
                self.action('verify-first-native')
        self.action('verify-native')
        self.action('start-optimized')
        for row in setup[2:]:
            if row['kind'] in ('capture0', 'capture1'):
                # Explicit capture admission uses actual post-native residency and
                # the same conservative4GiB sampler transient allowance; no claim
                # that the historical256 graph pool predicts the new pool peak.
                self.action(row['admission_action'])
            elif row['kind'] == 'decode-probe':
                self.action('admit-decode')
            await self.request(row)
            self.wait_idle()
            if row['kind'] in ('capture0', 'capture1'):
                self.action(row['retirement_action'])
        for row in [r for r in self.client.plan['requests'] if r['phase'] == 'candidate-check']:
            await self.request(row)
        self.action('verify-candidate')
        self.action('start-timing')
        for row in [r for r in self.client.plan['requests'] if r['phase'] == 'timed-fast']:
            await self.request(row)
        self.action('verify-fast-timed')
        return {'passed': True, 'requests': self.requests, 'actions': self.actions,
                'fast_timed_receipt': str(self.run / 'same-size-timed-fast.json'),
                'claim': 'Three-fixture49-frame resource pilot; two timing intervals only. No adoption, full-suite quality, speed-gain, endurance or record claim.'}

    def graceful_stop(self):
        gate.require(self.owns_campaign and self.lock_fd is not None,
                     'This invocation does not own the campaign; must not signal server')
        gate.require(not self.stop_attempted, 'Graceful stop is one-shot')
        self.stop_attempted = True
        first = self.wait_idle(closing=True)
        # Two observations across five seconds also cover done-event/running-count
        # ordering in the worker finally block. Never clear failed jobs to fake idle.
        time.sleep(5)
        second = self.wait_idle(seconds=30, closing=True)
        self.check_identity()
        gate.require(not (self.root / 'FAULT.json').exists(), 'Fault appeared before graceful stop')
        evidence = {'schema': 'ltx.resolution-graceful-stop.v1', 'first': first, 'second': second,
                    'identity': self.client.identity, 'signal': 'SIGINT', 'time_unix': time.time()}
        request_client.write_new(self.run / 'resolution-stop-intent.json', evidence)
        pid = self.client.identity['pid']
        os.kill(pid, signal.SIGINT)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if not Path('/proc/%d' % pid).exists():
                request_client.write_new(self.run / 'resolution-stopped.json',
                    {'pid': pid, 'gone_unix': time.time(), 'hard_kill': False})
                return {'stopped': True, 'pid': pid}
            time.sleep(2)
        raise TimeoutError('Application still alive after180s; no escalation or restart')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--contract', type=Path)
    parser.add_argument('--contract-sha256')
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    if not args.run:
        value = schedule.build_schedule()
        print(json.dumps({'status': 'plan-only', 'schedule_sha256': value['schedule_sha256'],
                          'requests': 57, 'model_requests': 0, 'server_actions': 0}))
        return
    campaign = Campaign(args.contract, args.contract_sha256, args.manifest_sha256)
    signal_received = []
    closing = [False]
    def terminate_once(signum, frame):
        if closing[0]:
            signal_received.append(signum)
            return  # Do not interrupt or repeat an already-bounded graceful stop.
        if not signal_received:
            signal_received.append(signum)
            raise KeyboardInterrupt('Campaign received signal%d; bounded graceful closeout' % signum)
    signal.signal(signal.SIGTERM, terminate_once)
    signal.signal(signal.SIGINT, terminate_once)
    result = {'passed': False}
    try:
        result = asyncio.run(campaign.execute())
    except (Exception, KeyboardInterrupt) as error:
        result.update(error=repr(error), requests=campaign.requests, actions=campaign.actions)
        emit('campaign halted: ' + str(error))
    finally:
        closing[0] = True
        if campaign.owns_campaign and result['passed'] is True:
            try:
                state = campaign.wait_idle()
                result['application'] = {'running': True, 'available_for_reuse': True,
                                         'final_status': state}
                result['stop'] = {'stopped': False, 'reason': 'successful application retained'}
            except Exception as error:
                result['passed'] = False
                result['application'] = {'requires_coordinator': True, 'error': repr(error)}
                result['stop'] = {'stopped': False, 'reason': 'final observation refused'}
        elif campaign.owns_campaign:
            try:
                result['stop'] = campaign.graceful_stop()
            except Exception as error:
                result['stop'] = {'stopped': False, 'error': repr(error), 'requires_coordinator': True}
        else:
            result['stop'] = {'stopped': False, 'not_owner': True, 'server_untouched': True}
        result['ended_unix'] = time.time()
        if campaign.owns_campaign:
            request_client.write_new(campaign.run / 'resolution-campaign-result.json', result)
        if campaign.lock_fd is not None:
            os.close(campaign.lock_fd)
    print(json.dumps(result, indent=2))
    if result['passed'] is not True:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
