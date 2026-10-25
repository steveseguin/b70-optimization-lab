#!/usr/bin/env python3
"""Bounded native overlap/rollback proof using explicitly scripted proposals.

Plan-only by default. This is a diagnostic controller, not live drafting or a
speed qualification. It reuses the existing passive admission and lifecycle.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import select
import signal
import time

import pipeline_driver as base

SCHEDULE_PATH = base.HERE.parent / 'planning/wavefront.py'
# dataclasses requires the dynamically imported module in sys.modules.
import importlib.util
import sys
_spec = importlib.util.spec_from_file_location('ownrt_wavefront', SCHEDULE_PATH)
schedule = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = schedule
_spec.loader.exec_module(schedule)


def make_plan(config_path):
    plan = base.make_plan(config_path)
    config = json.loads(Path(config_path).read_text())
    require = base.require
    require(config.get('wavefront') is True, 'explicit wavefront config required')
    proposals = config['scripted_proposal_tokens']
    require(isinstance(proposals, list) and len(proposals) >= plan['max_new'] - 1,
            'bounded scripted proposal sequence required')
    require(all(type(t) is int and 0 <= t < plan['vocab'] for t in proposals), 'scripted token bounds')
    misses = config.get('force_miss_positions', [])
    require(isinstance(misses, list) and len(set(misses)) == len(misses)
            and all(type(p) is int and len(plan['prompt_tokens']) <= p
                    < len(plan['prompt_tokens']) + plan['max_new'] - 1 for p in misses),
            'forced miss positions must address admitted generated inputs')
    verify = config.get('verify_restore', True)
    require(type(verify) is bool, 'explicit boolean restore verification')
    receipt = json.loads(Path(config['build_receipt']).read_text())
    require('pipeline/wavefront.hpp' in receipt.get('sources', {}), 'wavefront build required')
    plan.update(schema='ownrt.wavefront-driver-plan.v1', mode='verified-wavefront',
                scripted_proposal_tokens=proposals, force_miss_positions=misses,
                verify_restore=verify, max_inflight=2, diagnostic_only=True,
                speed_claim=False, limits='Scripted proposal overlap/rollback proof; no live-draft throughput claim.')
    for stage in plan['stages']:
        stage['argv'].append('--pipeline-wavefront')
        if verify:
            stage['argv'].append('--pipeline-wavefront-verify-restore')
    for path in (Path(__file__).resolve(), Path(base.__file__).resolve(), SCHEDULE_PATH,
                 base.ROOT / 'experiments/own-xpu-runtime/ops/packet196-window/passive_device_holders.py',
                 base.ROOT / 'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'):
        plan['pins'][str(path)] = base.digest(path)
    return plan


class AsyncStage(base.Stage):
    def start_async(self):
        self.sock.setblocking(False)
        self.transmit = b''
        self.received = bytearray()
        self.command_pending = None

    def issue(self, command):
        self.guard.check()
        base.require(self.command_pending is None and not self.received and not self.transmit,
                     'one command per stage')
        base.require(command.stage == self.spec['id'] and command.sequence == self.sequence + 1,
                     'controller sequence identity')
        row = command.row
        self.sequence = command.sequence
        self.command_pending = command
        self.transmit = base.REQUEST.pack(command.op, row.token, row.position, row.fixture,
                                          command.speculative, self.sequence,
                                          self.spec['id'], int(self.spec['final']))

    def write_ready(self):
        self.guard.check()
        try:
            written = self.sock.send(self.transmit)
        except BlockingIOError:
            return
        base.require(written > 0, 'stage command channel closed')
        self.transmit = self.transmit[written:]

    def read_ready(self):
        try:
            piece = self.sock.recv(base.REPLY.size - len(self.received))
        except BlockingIOError:
            return None
        base.require(piece, 'stage reply channel closed')
        self.received.extend(piece)
        if len(self.received) != base.REPLY.size:
            return None
        reply = base.REPLY.unpack(self.received)
        command = self.command_pending
        base.require(command is not None and not self.transmit, 'reply without fully sent command')
        base.require(reply[0] == 0 and reply[2] == 0 and reply[4] == command.sequence,
                     'native error or wrong reply sequence')
        base.require(reply[5] == (0 if self.spec['first'] else 1)
                     and reply[6:8] == (self.spec['id'], int(self.spec['final'])),
                     'native stage/final identity')
        stream, token = None, None
        if command.op == schedule.ROW:
            if self.spec['final']:
                base.require(reply[3] == 0, 'final stage must not publish a boundary stream')
                token = reply[1] if command.row.fixture else None
            else:
                base.require(reply[3] == self.stream_bytes and reply[1] == -1,
                             'complete nonfinal stream required')
                # Own the entire output before another command can overwrite it.
                stream = bytes(self.shared[:self.stream_bytes])
        else:
            self.resolution_reply(command, reply)
        self.command_pending = None
        self.received.clear()
        return command, reply, token, stream

    def resolution_reply(self, command, reply):
        base.require(reply[3] == 0, 'resolution reply must have no stream payload')


def drive(stages, plan, guard, output):
    prompt = plan['prompt_tokens']
    proposals = {len(prompt) + i: token for i, token in enumerate(plan['scripted_proposal_tokens'])}
    for position in plan['force_miss_positions']:
        proposals[position] = (proposals[position] + 1) % plan['vocab']
    model = schedule.Wavefront(len(stages), prompt, plan['max_new'], plan['vocab'],
                               plan['eos'], lambda p: proposals.get(p))
    for stage in stages:
        stage.start_async()
    sockets = {stage.sock: stage for stage in stages}
    event_index, emitted = 0, 0
    peak_busy, began = 0, time.monotonic()
    with (output / 'schedule.jsonl').open('x') as trace, (output / 'tokens.jsonl').open('x') as tokens:
        while not model.done:
            guard.check()
            for command in model.commands():
                stage, row = stages[command.stage], command.row
                if command.op == schedule.ROW and command.stage:
                    data = row.streams[command.stage - 1]
                    base.require(len(data) == stage.stream_bytes, 'handoff extent')
                    stage.shared[base.SLOT:base.SLOT + stage.stream_bytes] = data
                stage.issue(command)
                trace.write(json.dumps(dict(event='send', stage=command.stage, op=command.op,
                                            sequence=command.sequence, row=row.identity,
                                            position=row.position, token=row.token,
                                            speculative=command.speculative, monotonic_s=time.monotonic())) + '\n')
            active = [s for s in stages if s.command_pending is not None]
            base.require(active, 'scheduler deadlock with no outstanding native command')
            peak_busy = max(peak_busy, len(active))
            readable, writable, _ = select.select([s.sock for s in active if not s.transmit],
                                                   [s.sock for s in active if s.transmit], [], 0.2)
            for sock in writable:
                sockets[sock].write_ready()
            for sock in readable:
                stage = sockets[sock]
                completed = stage.read_ready()
                if completed is None:
                    continue
                command, reply, token, stream = completed
                model.complete(command, output_token=token, stream=stream)
                trace.write(json.dumps(dict(event='reply', stage=command.stage, op=command.op,
                                            sequence=command.sequence, row=command.row.identity,
                                            position=command.row.position, busy_ms=reply[8],
                                            gpu_ms=reply[9], monotonic_s=time.monotonic())) + '\n')
                while event_index < len(model.events):
                    trace.write(json.dumps(model.events[event_index]) + '\n')
                    event_index += 1
                while emitted < len(model.emitted):
                    tokens.write(json.dumps(dict(index=emitted, token=model.emitted[emitted],
                                                 committed_monotonic_s=time.monotonic())) + '\n')
                    tokens.flush()
                    emitted += 1
            trace.flush()
    for stage in stages:
        base.require(stage.command_pending is None and not stage.received and not stage.transmit,
                     'undrained native wire')
        stage.sock.settimeout(0.2)
    miss_positions = {e['position'] for e in model.events if e['event'] == 'proposal-miss'}
    aborted_positions = {e['position'] for e in model.events if e['event'] == 'abort'}
    coverage = {str(p): dict(target_rejected=p in miss_positions, native_abort_completed=p in aborted_positions)
                for p in plan['force_miss_positions']}
    base.require(all(row['target_rejected'] and row['native_abort_completed'] for row in coverage.values()),
                 'requested forced-miss positions did not exercise target rejection and native rollback')
    return dict(output_ids=model.emitted, input_position=model.frontier, forced_miss_coverage=coverage,
                scheduler_wall_seconds=time.monotonic() - began, peak_commands_inflight=peak_busy,
                events=model.events)


def execute(plan, admission, unit, *, stage_type=AsyncStage, driver=drive,
            scripted_proposals=True):
    base.require(admission.get('schema') == 'ownrt.pipeline-admission.v1'
                 and admission.get('owner_authorized') is True, 'explicit admission required')
    base.require(datetime.fromisoformat(admission['expires_utc']) > datetime.now(timezone.utc),
                 'admission expired')
    base.require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    identity = base.validate_unit(unit)
    guard = base.Guard(plan, admission, None)
    output = Path(plan['output'])
    output.mkdir(mode=0o700)
    base.save(output / 'plan.json', plan)
    base.save(output / 'admission.json', admission)
    base.save(output / 'unit.json', identity)
    prior = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in prior:
        signal.signal(sig, lambda *_: guard.signal_stop.set())
    stages, result, failure = [], {}, None
    start = time.monotonic()
    try:
        guard.thread.start()
        for spec in plan['stages']:
            guard.check()
            stage = stage_type(spec, plan, guard)
            stages.append(stage)
            stage.receive(ready=True)
        base.require(len({s.stream_bytes for s in stages}) == 1, 'stage boundary shape mismatch')
        guard.validate_or_stop(guard.obs.observe(), phase='main-after-ready')
        result = driver(stages, plan, guard, output)
        for stage in stages:
            stage.command(4, position=2147483647)
        guard.validate_or_stop(guard.obs.observe(), phase='main-before-finish')
        for stage in stages:
            stage.command(5)
    except Exception as error:
        failure = repr(error)
        guard.fail(failure)
    finally:
        end = time.monotonic() + plan['grace_seconds']
        while any(p.poll() is None for _, p in guard.tracked_processes) and time.monotonic() < end:
            time.sleep(0.2)
        guard.done.set()
        guard.thread.join(timeout=35)
        if guard.thread.is_alive():
            guard.fail('passive observer did not quiesce')
        if failure is None:
            try:
                guard.check()
                guard.validate_or_stop(guard.obs.observe(), phase='main-after-exit')
            except Exception as error:
                guard.fail(error)
        caught_failure = failure
        failure = guard.failed if guard.failed is not None else failure
        alive = [p.pid for _, p in guard.tracked_processes if p.poll() is None]
        codes = {str(i): p.poll() for i, p in guard.tracked_processes}
        if failure is None and (alive or any(code != 0 for code in codes.values())):
            failure = 'native stages did not exit cleanly'
        for sig, handler in prior.items():
            signal.signal(sig, handler)
        failure_details = {}
        if failure is not None:
            failure_details = dict(guard_failure=guard.failed, caught_error=caught_failure,
                guard_first_failure=guard.first_failure,
                guard_failure_evidence_error=guard.failure_evidence_error)
        try:
            base.save(output / 'result.json', dict(result, **failure_details, schema='ownrt.wavefront-driver-result.v1',
                      passed=failure is None, error=failure, live_pids=alive, returncodes=codes,
                      wall_seconds=time.monotonic() - start, mode='verified-wavefront',
                      diagnostic_only=True, speed_claim=False, scripted_proposals=scripted_proposals))
        except Exception as evidence_error:
            if failure is not None:
                raise ValueError(failure) from evidence_error
            raise
    base.require(failure is None, str(failure))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--admission', type=Path)
    parser.add_argument('--unit')
    args = parser.parse_args()
    if not args.run:
        base.require(args.config is not None, 'config required for planning')
        base.save(args.plan, make_plan(args.config))
        print(json.dumps(dict(plan=str(args.plan), sha256=base.digest(args.plan), device_execution_requested=False)))
        return
    base.require(args.admission is not None and args.unit, 'admission and owning unit required')
    plan = json.loads(args.plan.read_text())
    base.require(plan == make_plan(plan['config']), 'plan/source/launch identity changed')
    admission = json.loads(args.admission.read_text())
    base.require(admission['plan_sha256'] == base.digest(args.plan), 'admission plan mismatch')
    execute(plan, admission, args.unit)


if __name__ == '__main__':
    main()
