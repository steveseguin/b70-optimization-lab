#!/usr/bin/env python3
"""Resident four-stage depth-three cold-request backend for LAN HTTP.

The checked-in rolling inputs pin native planning/trace bounds only. Every
executed prompt comes from the caller and receives a fresh all-owner RESET.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import threading
import time

P = Path(__file__).resolve().parent
TOOLS = P.parents[2] / 'engine/tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import persistent_rolling_driver as rolling_driver
import persistent_rolling_suite as rolling

base, bridge = rolling.base, rolling.bridge
BDFS = ('0000:23:00.0', '0000:27:00.0', '0000:43:00.0', '0000:47:00.0')
BOUNDARIES = [0, 8, 21, 34, 48]
VOCAB = 248320
EOS = [248044, 248046]
CONTEXT = 262144
PREFILL_ROWS = 256


def mtp_accounting(result):
    """Count proposals accepted by the final stage, including terminal drain.

    Explicit wrong guesses and discarded unverified descendants are distinct.
    Use the complete in-memory coordinator events, not bounded schedule.jsonl.
    """
    issued_rows = [row['row'] for row in result['issued_proposals']]
    rejected_rows = [row['row'] for row in result['rejected_proposals']]
    issued, rejected = set(issued_rows), set(rejected_rows)
    committed = {event['row'] for event in result['events']
                 if event['event'] in ('final-record-held', 'final-record-terminal')}
    accepted = issued & committed
    base.require(len(issued) == len(issued_rows) and len(rejected) == len(rejected_rows)
                 and rejected <= issued and not accepted & rejected,
                 'MTP proposal accounting identity/disjointness')
    discarded = issued - accepted - rejected
    return dict(guesses=len(issued), hits=len(accepted), misses=len(rejected),
                unverified_discarded=len(discarded),
                accounting='issued=accepted+explicit_rejected+unverified_discarded')


def token_sha(tokens):
    return hashlib.sha256(b''.join(struct.pack('<I', token) for token in tokens)).hexdigest()


def trace_commands(plan, prompt_tokens, max_new):
    return (2 * plan.get('speculative_depth', 2) + 2) * (prompt_tokens + max_new - 1)


def make_plan(config_path):
    """Build a native rolling plan; its planning inputs are never HTTP requests."""
    config_path = Path(config_path).resolve()
    config = json.loads(config_path.read_text())
    base.require(config.get('pp4_http_service') is True, 'explicit PP4 HTTP service config required')
    base.require(config.get('bdfs') == list(BDFS) and config.get('boundaries') == BOUNDARIES,
                 'PP4 HTTP requires balanced stages on cards 23/27/43/47')
    base.require(config.get('context') == CONTEXT and config.get('vocab') == VOCAB and
                 config.get('eos_token_ids') == EOS, 'PP4 262K tokenizer/context/EOS identity')
    base.require(config.get('speculative_depth') == 3 and config.get('capture_ready_overlap') is True,
                 'depth-three capture-ready rolling service required')
    base.require(int(os.environ.get('SC117_CONTEXT', '4096')) == CONTEXT,
                 'SC117_CONTEXT=262144 required for the PP4 endpoint')
    prefill_pipeline = config.get('prefill_pipeline', False)
    base.require(type(prefill_pipeline) is bool, 'PP4 prefill_pipeline must be boolean')
    plan = rolling_driver.make_plan(config_path)
    base.require(len(plan['stages']) == 4 and plan.get('speculative_depth') == 3 and
                 plan.get('capture_ready_overlap') is True and plan.get('use_proposals') is True,
                 'four-stage real depth-three MTP plan required')
    for stage in plan['stages']:
        stage['argv'] += ['--prefill-rows', str(PREFILL_ROWS), '--prefill-shared',
                          str(Path(plan['output']) / f"stage{stage['id']}" / 'prefill.bin')]
    plan['prefill_stream_bytes'] = base.PREFILL_STREAM_BYTES
    for path in (Path(__file__).resolve(), P / 'pp4_service.py', P / 'service.py', P / 'chat.py'):
        plan['pins'][str(path)] = base.digest(path)
    plan.update(schema='ownrt.pp4-lan-service-plan.v1', pp4_http_service=True,
                service_mode='cold-serial-http-depth3', cold_reset_every_request=True,
                request_source='caller', continuation=False, sessions=False, prefill_rows=PREFILL_ROWS,
                prefill_pipeline=prefill_pipeline,
                full_trace_required=plan['check_policy'] == 'qualification',
                trace_retention='full' if plan['check_policy'] == 'qualification' else 'bounded-prefix-with-omission-counters',
                limits='Caller prompts only; one cold depth-three request at a time; max_new is bounded by this plan.')
    if plan['check_policy'] == 'measured':
        plan['coordinator_trace_limit'] = 10000
    plan.pop('diagnostic_only', None)
    plan.pop('speed_claim', None)
    return plan


def validate_admission(plan_path, plan, admission):
    base.require(plan.get('schema') == 'ownrt.pp4-lan-service-plan.v1', 'PP4 service plan schema')
    base.require(admission.get('schema') == 'ownrt.pipeline-admission.v1' and
                 admission.get('owner_authorized') is True, 'explicit owner admission required')
    base.require(admission.get('plan_sha256') == base.digest(plan_path), 'admission plan hash mismatch')
    base.require(datetime.fromisoformat(admission['expires_utc']) > datetime.now(timezone.utc),
                 'admission expired')


class TokenPump:
    """Tail only complete committed rows; finish() proves stream/result identity."""
    def __init__(self, path, callback):
        self.path = Path(path)
        self.callback = callback
        self.fd = None
        self.buffer = b''
        self.index = 0
        self.tokens = []

    def poll(self):
        if self.fd is None:
            try:
                self.fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
            except FileNotFoundError:
                return False
        progress = False
        while True:
            try:
                piece = os.read(self.fd, 65536)
            except BlockingIOError:
                break
            if not piece:
                break
            progress = True
            self.buffer += piece
            base.require(len(self.buffer) <= 1024 * 1024, 'unbounded committed token row')
            while b'\n' in self.buffer:
                raw, self.buffer = self.buffer.split(b'\n', 1)
                row = json.loads(raw)
                base.require(row.get('index') == self.index and type(row.get('token')) is int,
                             'committed stream sequence identity')
                token = row['token']
                self.tokens.append(token)
                self.index += 1
                if self.callback is not None:
                    self.callback(token)
        return progress

    def finish(self, outputs):
        self.poll()
        base.require(self.fd is not None and not self.buffer and self.tokens == list(outputs),
                     'committed stream/final result mismatch')
        os.close(self.fd)
        self.fd = None


def drive(stages, plan, guard, output, on_token=None):
    """Run the real rolling drive; tail committed tokens without changing it."""
    if on_token is None:
        return bridge.drive(stages, plan, guard, output, epoch=plan['epoch'])
    pump = TokenPump(output / 'tokens.jsonl', on_token)
    result, errors = [], []
    cancel = threading.Event()

    def work():
        try:
            result.append(bridge.drive(stages, plan, guard, output, epoch=plan['epoch'],
                                       stop_requested=cancel.is_set))
        except BaseException as error:
            errors.append(error)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    callback_error = None
    while worker.is_alive():
        try:
            if not pump.poll():
                time.sleep(0.01)
        except BaseException as error:
            callback_error = error
            pump.callback = None
            cancel.set()
    worker.join()
    if callback_error is not None:
        if pump.fd is not None:
            os.close(pump.fd)
            pump.fd = None
        raise callback_error
    if errors:
        if pump.fd is not None:
            os.close(pump.fd)
            pump.fd = None
        raise errors[0]
    pump.finish(result[0]['output_ids'])
    return result[0]


class Engine:
    """The service.Engine interface, backed by one resident rolling Stage set."""

    def __init__(self, plan, admission, unit_identity):
        self.plan = plan
        self.admission = admission
        self.unit_identity = unit_identity
        self.output = Path(plan['output'])
        self.lock = threading.Lock()
        self.t = None
        self.prefill_rows = plan.get('prefill_rows', 0)
        self.count = 0
        self.log_bytes = 0
        self.stages = []
        self.guard = None
        self.start_time = time.monotonic()
        self.closed = False
        self.cancel_requested = False
        self.epoch = 0
        self.request_sha256 = plan['request_sha256']
        self.inventory = None

    def activations(self):
        return 'F32'

    def request_cancellation(self):
        self.cancel_requested = True
        if self.lock.locked() and self.guard is not None:
            self.guard.signal_stop.set()

    def expected_cancellation(self, error=None):
        if not self.cancel_requested:
            return False
        if self.guard is not None and self.guard.failed is not None:
            return self.guard.failed == 'coordinator signal stop'
        return str(error) == 'coordinator signal stop'

    def start(self):
        self.output.mkdir(mode=0o700)
        (self.output / 'requests').mkdir(mode=0o700)
        base.save(self.output / 'plan.json', self.plan)
        base.save(self.output / 'admission.json', self.admission)
        base.save(self.output / 'unit.json', self.unit_identity)
        self.guard = base.Guard(self.plan, self.admission, None)
        self.t = True
        self.guard.thread.start()
        for spec in self.plan['stages']:
            self.guard.check()
            stage = bridge.Stage(spec, self.plan, self.guard)
            self.stages.append(stage)
            stage.receive(ready=True)
        base.require(len(self.stages) == 4 and len({s.stream_bytes for s in self.stages}) == 1,
                     'four resident stages with one boundary shape required')
        self.guard.validate_or_stop(self.guard.obs.observe(), phase='pp4-service-after-ready')
        self.check_alive()
        return self.plan

    def check_alive(self):
        if self.guard is not None:
            self.guard.check()
        failed = [stage.spec['id'] for stage in self.stages if stage.proc.poll() is not None]
        base.require(not failed, f'resident PP4 stages exited: {failed}')

    def storage_ok(self):
        try:
            free = shutil.disk_usage(self.output.parent).free
        except OSError as error:
            return 'PP4 evidence storage check failed: ' + repr(error)
        if free < self.plan['evidence_floor_bytes']:
            return f"PP4 evidence free {free} is below {self.plan['evidence_floor_bytes']}"
        return None

    def generate(self, prompt, max_new, label, on_token=None, continue_ok=False, **_ignored):
        """RESET all four stages, then run real depth-three verified rolling MTP."""
        base.require(isinstance(prompt, list) and prompt and
                     all(type(token) is int and 0 <= token < self.plan['vocab'] for token in prompt),
                     'caller prompt token bounds')
        base.require(type(max_new) is int and 1 <= max_new <= self.plan['max_new'] and
                     len(prompt) + max_new - 1 <= self.plan['context'],
                     'caller max_new exceeds native plan/context bound')
        if self.plan.get('full_trace_required'):
            base.require(trace_commands(self.plan, len(prompt), max_new) <= self.plan['ring_trace_limit'],
                         'qualification request exceeds full native trace bound')
        self.check_alive()
        number = self.count + 1
        index = number - 1
        request = self.output / 'requests' / f'request-{number:06d}'
        request.mkdir(mode=0o700)
        row = dict(id=f'http-{number:06d}', prompt_tokens=list(prompt), max_new=max_new)
        next_request = rolling.request_identity(self.plan, row, index, number)
        previous_sequences = [stage.sequence for stage in self.stages]
        started = time.monotonic()
        reset_started = time.monotonic()
        receipts = rolling.reset(self.stages, self.plan, self.guard, request,
                                 previous_epoch=self.epoch, previous_request=self.request_sha256,
                                 epoch=number, request=next_request)
        inventory = [r['receipt']['allocation_inventory_after_sha256'] for r in receipts]
        base.require(self.inventory is None or inventory == self.inventory,
                     'allocation inventory changed between HTTP requests')
        self.inventory = inventory
        reset_ms = (time.monotonic() - reset_started) * 1000
        self.count, self.epoch, self.request_sha256 = number, number, next_request
        request_plan = dict(self.plan, epoch=number, request_sha256=next_request,
                            prompt_tokens=list(prompt), max_new=max_new)
        base.save(request / 'request-plan.json', request_plan)
        for stage in self.stages:
            stage.plan = request_plan
        initial_sequences = [stage.sequence for stage in self.stages]
        began = time.monotonic()
        result = drive(self.stages, request_plan, self.guard, request, on_token=on_token)
        finished = time.monotonic()
        rolling.quiescent(self.stages)
        self.guard.validate_or_stop(self.guard.obs.observe(), phase='pp4-service-after-request')
        outputs = list(result['output_ids'])
        base.require(result.get('cancelled') is False and result.get('cancelled_provider_incomplete') is not True and
                     1 <= len(outputs) <= max_new and
                     (len(outputs) == max_new or outputs[-1] in self.plan['eos_token_ids']) and
                     result.get('input_position') == len(prompt) + len(outputs) - 1 and
                     result.get('provider_serial') == result.get('provider_pairs') == len(prompt) + len(outputs) - 2,
                     'PP4 rolling output/provider/drain boundary')
        final_sequences = [stage.sequence for stage in self.stages]
        dump_sequences = []
        if self.plan['dump_each']:
            for stage in self.stages:
                stage.command(4, position=2000000000 + index)
                dump_sequences.append(stage.sequence)
        timing = rolling.evidence.timing_from_tokens(request / 'tokens.jsonl', outputs, began, finished)
        result_path = request / 'driver-result.json'
        base.save(result_path, result)
        compact = {key: value for key, value in result.items()
                   if key not in ('events', 'issued_proposals', 'rejected_proposals')}
        mtp = mtp_accounting(result)
        summary = dict(request=number, label=label, mode='live-mtp-depth3', streamed=on_token is not None,
                       prompt_tokens=len(prompt), output_tokens=len(outputs), max_new=max_new,
                       mtp=mtp,
                       provider_pairs=result['provider_pairs'], reset_ms=reset_ms,
                       continued_from=0, prefill_rows=self.prefill_rows, wall_s=time.monotonic() - started)
        record = dict(schema='ownrt.pp4-lan-rolling-request-result.v1', passed=True,
                      request=number, epoch=number, request_sha256=next_request,
                      check_policy=self.plan['check_policy'], cached_tokens=0,
                      prompt_tokens=len(prompt), prompt_token_sha256=token_sha(prompt),
                      output_ids=outputs, output_token_sha256=token_sha(outputs),
                      reset_receipts=receipts, previous_sequences=previous_sequences,
                      initial_sequences=initial_sequences, final_sequences=final_sequences,
                      post_dump_sequences=[stage.sequence for stage in self.stages], dump_sequences=dump_sequences,
                      process_reused=number > 1, prompt_state_reused=False,
                      timing=timing, driver_result=compact, driver_result_path=str(result_path),
                      driver_result_sha256=base.digest(result_path))
        base.save(request / 'result.json', record)
        line = json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(), **summary)) + '\n'
        if self.log_bytes < 50 * 1024**2:
            with (self.output / 'requests.jsonl').open('a') as out:
                out.write(line)
            self.log_bytes += len(line.encode())
        return outputs, summary

    def close(self, clean, reason=None):
        """FINISH when idle, or drain an expected active-request cooperative stop."""
        if self.closed:
            return None
        self.closed = True
        failure = None
        if self.guard is not None:
            expected_stop = (self.cancel_requested and self.guard.signal_stop.is_set() and
                             self.guard.failed in (None, 'coordinator signal stop'))
            if expected_stop:
                if self.guard.failed is None:
                    self.guard.fail('coordinator signal stop')
            elif clean:
                try:
                    rolling.quiescent(self.stages)
                    for stage in self.stages:
                        stage.command(5)
                except BaseException as error:
                    failure = repr(error)
                    self.guard.fail(failure)
            else:
                self.guard.fail(reason or 'PP4 service stopping after an error')
            deadline = time.monotonic() + self.plan['grace_seconds']
            while any(proc.poll() is None for _, proc in self.guard.tracked_processes) and time.monotonic() < deadline:
                time.sleep(0.2)
            self.guard.done.set()
            self.guard.thread.join(timeout=35)
            if self.guard.thread.is_alive():
                self.guard.fail('PP4 passive observer did not quiesce')
            alive = [proc.pid for _, proc in self.guard.tracked_processes if proc.poll() is None]
            codes = {str(stage_id): proc.poll() for stage_id, proc in self.guard.tracked_processes}
            guard_clean = self.guard.failed is None or (expected_stop and self.guard.failed == 'coordinator signal stop')
            codes_clean = all(code == 0 or (expected_stop and code == 1) for code in codes.values())
            passed = failure is None and guard_clean and not alive and codes_clean
            error = failure or self.guard.failed
            if passed and expected_stop:
                error = None
            result = dict(passed=passed, error=error, cooperative_cancellation=expected_stop,
                          live_pids=alive, returncodes=codes, requests=self.count,
                          wall_s=time.monotonic() - self.start_time)
            base.save(self.output / ('terminal.json' if result['passed'] else 'incident.json'), result)
            return result
        return None
