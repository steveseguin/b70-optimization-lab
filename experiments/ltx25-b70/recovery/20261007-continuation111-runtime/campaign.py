#!/usr/bin/env python3
"""Explicit finite111 campaign; retains application on success and failure. No signals."""
import argparse
import asyncio
import fcntl
import importlib.util
import json
import os
import signal
from pathlib import Path
import time

_spec = importlib.util.spec_from_file_location('continuation111_client', Path(__file__).with_name('request_client.py'))
C = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(C)


def is_idle(state):
    if type(state) is not dict or state.get('fault') is not False:
        return False
    for key in ('queue_running', 'queue_pending', 'preview_pending', 'preview_failures'):
        if type(state.get(key)) is not int or state[key] != 0:
            return False
    pipe = state.get('pipeline')
    if type(pipe) is not dict or type(pipe.get('running')) is not int or pipe['running'] != 0:
        return False
    stages = pipe.get('stages')
    if type(stages) is not dict:
        return False
    for stage in stages.values():
        if type(stage) is not dict or stage.get('queued_indices') != [] or stage.get('jobs') != []:
            return False
    return True


class Campaign:
    def __init__(self, client, transport_factory=C.AioTransport):
        self.client = client
        self.transport_factory = transport_factory
        self.owned = False
        self.lock_fd = None
        self.requests = []
        self.actions = []

    def check_status(self, value, completed, proofs):
        C.require(type(value) is dict and value.get('phase') == 'native_reference' and
                  value.get('halted') is None and value.get('active') is None and
                  value.get('server_identity_sha256') == self.client.contract['server_identity_sha256'] and
                  value.get('runtime_manifest_sha256') == self.client.contract['runtime_manifest_sha256'],
                  'Runtime status identity/phase/halt differs')
        C.require(value.get('completed') == completed, 'Runtime completion order differs')
        C.require(type(value.get('state')) is dict and value['state'].get('fault') is False,
                  'Runtime fault latched; halt without waiting or lifecycle action')
        actual = value.get('proofs')
        C.require(type(actual) in (list, dict) and len(actual) == len(set(actual)) and
                  set(actual) == set(proofs), 'Runtime proof barriers differ')
        return is_idle(value.get('state'))

    async def wait_idle(self, io, completed, proofs):
        deadline = time.monotonic() + 180
        while True:
            self.client.checkpoint()
            left = deadline - time.monotonic()
            C.require(left > 0, 'Idle deadline; retain application, no retry')
            value = await asyncio.wait_for(io.get('/ltx-resolution/status'), min(30, left))
            if self.check_status(value, completed, proofs):
                return value
            await asyncio.sleep(.25)

    async def action(self, io, action):
        self.client.checkpoint()
        result = await asyncio.wait_for(io.action(action), 600)  # One POST only.
        C.require(type(result) is dict and result.get('passed') is True and
                  result.get('action') == action and result.get('phase') == 'native_reference',
                  'Global proof action refused or response differs')
        if 'proof_sha256' in result:
            C.digest(result['proof_sha256'])
        self.client.checkpoint()
        C.write_new(self.client.directory / ('action-' + action.replace(':', '-') + '.json'), result)
        self.actions.append(action)
        return result

    def acquire(self):
        self.client.acquire()
        self.client.release()
        self.client.active_row = self.client.rows[self.client.ordered_names[0]]
        self.client.checkpoint_policy = 'always'
        self.client.policy_counts = dict(checkpoint_count=0, storage_save_count=0, skipped_storage_save_count=0)
        self.lock_fd = os.open(self.client.directory / 'campaign.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            C.require(not (self.client.directory / 'campaign-started.json').exists(),
                      'Campaign already attempted; no retry')
            C.require(self.client.state['attempts'] == [] and self.client.state['completed'] == [] and
                      self.client.state['verified'] == [], 'Campaign requires pristine bounded ledger')
            C.write_new(self.client.directory / 'campaign-started.json',
                        {'schema':'ltx.continuation111-campaign-start.v1',
                         'contract_sha256': self.client.contract_sha, 'plan_sha256': C.PLAN_SHA,
                         'application_lifecycle':'retained; no automatic stop/restart/signals'})
            self.owned = True
        except BaseException:
            os.close(self.lock_fd); self.lock_fd = None
            raise

    def halt(self, error):
        # No device query or process action, including after uncertain submission.
        record = {'type':type(error).__name__, 'message':str(error)[:2048],
                  'requests':self.requests, 'actions':self.actions,
                  'action':'Halt new requests; retain application; no retries or signals'}
        self.client.state['halted'] = record
        self.client.save_state()
        if not (self.client.directory / 'HALT.json').exists():
            C.write_new(self.client.directory / 'HALT.json', record)
        C.write_new(self.client.directory / 'campaign-failure.json', record)

    async def run(self):
        self.acquire()
        try:
            async with self.transport_factory() as io:
                for index, name in enumerate(self.client.ordered_names):
                    previous = self.client.ordered_names[:index]
                    await self.wait_idle(io, previous, previous)
                    await self.client.execute(name, self.transport_factory())
                    self.requests.append(name)
                    await self.wait_idle(io, self.requests, previous)
                    await self.action(io, 'verify:' + name)
                    await self.wait_idle(io, self.requests, self.requests)
                    self.client.acquire()
                    try:
                        C.require(self.client.state['completed'] == self.requests and
                                  self.client.state['verified'] == previous, 'Client proof ledger drift')
                        self.client.state['verified'].append(name)
                        self.client.save_state()
                    finally:
                        self.client.release()
                await self.action(io, 'verify-final')
                final = await self.wait_idle(io, self.requests, self.requests)
                result = {'schema':'ltx.continuation111-client-completed.v1',
                          'plan_sha256':C.PLAN_SHA, 'contract_sha256':self.client.contract_sha,
                          'requests':self.requests, 'actions':self.actions,
                          'status':final, 'application_retained':True,
                          'quality_claim':'Only server proof receipts establish exactness; no perceptual/seam claim'}
                C.write_new(self.client.directory / 'campaign-completed.json', result)
                return result
        except BaseException as error:
            if self.owned:
                self.halt(error)
            raise
        finally:
            if self.lock_fd is not None:
                os.close(self.lock_fd); self.lock_fd = None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--contract-sha256',required=True)
    parser.add_argument('--run',action='store_true',help='Explicitly submit exactly eight requests; no lifecycle action')
    args=parser.parse_args()
    if not args.run:
        print(json.dumps({'plan_sha256':C.PLAN_SHA,'max_attempts':8,'max_captures':6,
                          'planned_write_bytes':C.WRITE_ALLOWANCE,'min_free_bytes':C.MIN_FREE,
                          'application_lifecycle':'retained','execution':False}))
        return
    client=C.Client(args.contract,args.contract_sha256)
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Campaign interrupted; retain server, no retry')
    old = signal.signal(signal.SIGTERM, interrupted)
    try:
        print(json.dumps(asyncio.run(Campaign(client).run()),sort_keys=True))
    finally:
        signal.signal(signal.SIGTERM, old)


if __name__ == '__main__':
    main()
