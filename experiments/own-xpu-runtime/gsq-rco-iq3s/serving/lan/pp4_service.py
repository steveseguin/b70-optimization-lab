#!/usr/bin/env python3
"""Opt-in four-card 262K resident depth-three MTP HTTP service.

CPU planning:
  SC117_PP4_SERVICE=1 SC117_CONTEXT=262144 python3 pp4_service.py --config CONFIG.json --plan PLAN.json
Admitted execution (from its dedicated systemd user unit):
  SC117_PP4_SERVICE=1 SC117_CONTEXT=262144 python3 pp4_service.py --run \
    --config CONFIG.json --plan PLAN.json --admission ADMISSION.json --unit UNIT.service
"""
import argparse
import io
import json
import os
from pathlib import Path
import resource
import signal
import sys
import threading
import time
import traceback

import pp4_backend as B
import service as S

base = B.base


def plan_only(config, output):
    plan = B.make_plan(config)
    base.save(output, plan)
    print(json.dumps(dict(plan=str(output), sha256=base.digest(output), device_execution_requested=False)))
    return 0


def make_handler(state, engine, chat, key):
    """Legacy HTTP/SSE behavior plus pre-engine PP4 request-bound checks."""
    Legacy = S.make_handler(state, engine, chat, key)

    class Handler(Legacy):
        def do_POST(self):
            if self.path.split('?', 1)[0] not in ('/v1/chat/completions', '/chat/completions'):
                return super().do_POST()
            if not self.allowed():
                return
            try:
                n = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return super().do_POST()
            if 0 < n <= 64 * 1024**2:
                raw = self.rfile.read(n)
                self.rfile = io.BytesIO(raw)
                try:
                    body = json.loads(raw)
                    req = S.CHAT.parse(body, chat) if isinstance(body, dict) else None
                except (ValueError, S.CHAT.RequestError):
                    req = None
                if req is not None:
                    if req['max_new'] > engine.plan['max_new']:
                        return self.error(400, f"max_tokens exceeds the PP4 plan limit {engine.plan['max_new']}")
                    needed = B.trace_commands(engine.plan, len(req['prompt_ids']), req['max_new'])
                    if engine.plan.get('full_trace_required') and needed > engine.plan['ring_trace_limit']:
                        return self.error(400, 'prompt/max_tokens exceed the qualification full-trace bound')
            return super().do_POST()

    return Handler


def cooperative_stop(state, engine, sig):
    """Stop intake and cooperatively abort any active native request."""
    if state.phase != 'halted':
        state.phase = 'stopping'
        state.detail = f'signal {sig}: cooperative PP4 cancellation and drain'
    state.stop.set()
    engine.request_cancellation()


def handle_fault(state, engine, faults, error):
    """Expected cancellation is clean; every earlier/different fault stays fatal."""
    if faults:
        return
    if engine.expected_cancellation(error):
        state.phase = 'stopping'
        state.detail = 'cooperative PP4 cancellation and drain'
        state.stop.set()
        return
    faults.append(error)
    state.phase = 'halted'
    state.detail = repr(error)[:500]
    state.stop.set()
    if engine.guard is not None:
        engine.guard.fail(error)


def exit_status(faults, result):
    return 0 if not faults and result.get('passed') is True else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--admission', type=Path)
    ap.add_argument('--unit')
    ap.add_argument('--bind', default='192.168.2.44')
    ap.add_argument('--port', type=int, default=18161)
    ap.add_argument('--lifetime-hours', type=float, default=47.0)
    args = ap.parse_args()
    if not args.run:
        S.require(args.admission is None and args.unit is None, 'planning does not take admission/unit')
        return plan_only(args.config, args.plan)

    S.require(os.environ.get('SC117_PP4_SERVICE') == '1', 'SC117_PP4_SERVICE=1 explicit opt-in required')
    S.require(args.admission is not None and args.unit, 'run requires admission and owning systemd unit')
    S.require(resource.getrlimit(resource.RLIMIT_AS) == (resource.RLIM_INFINITY, resource.RLIM_INFINITY),
              'unlimited address space required')
    S.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and sorted(os.sched_getaffinity(0)) == S.AFFINITY,
              'nice 19 / CPUs 0-3,16-19 required')
    for directory in (S.P, Path('/home/steve'), S.REPO):
        S.require(not (directory / 'igdrcl.config').exists(), f'unadmitted driver config in {directory}')
    S.require(not any(os.path.lexists(marker) for marker in S.MARKERS),
              'a campaign lane marker is present; not starting')

    plan = B.make_plan(args.config)
    saved_plan = json.loads(B.rolling.evidence.read_bounded(args.plan, 8 * 1024**2))
    S.require(saved_plan == plan, 'PP4 plan/input/source identity changed')
    admission = json.loads(B.rolling.evidence.read_bounded(args.admission, 65536))
    B.validate_admission(args.plan, plan, admission)
    S.require(0.1 <= args.lifetime_hours <= plan['seconds'] / 3600 - 0.5,
              'HTTP lifetime must end before the native deadline')
    unit_identity = base.validate_unit(args.unit)
    interface = S.lan_address(args.bind)
    key = S.KEY_FILE.read_text().strip() if S.KEY_FILE.exists() else None
    chat = S.CHAT.Chat()
    engine = B.Engine(plan, admission, unit_identity)
    state = S.State()
    faults = []
    fault_lock = threading.Lock()

    def fault(error):
        with fault_lock:
            handle_fault(state, engine, faults, error)

    state.fault = fault

    def on_signal(sig, _frame):
        cooperative_stop(state, engine, sig)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    handler = make_handler(state, engine, chat, key)
    servers = [S.Server((args.bind, args.port), handler), S.Server(('127.0.0.1', args.port), handler)]
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(json.dumps(dict(listening=[f'http://{args.bind}:{args.port}', f'http://127.0.0.1:{args.port}'],
                          output=str(engine.output), pp4=True, context=B.CONTEXT, speculative_depth=3)), flush=True)

    result = dict(passed=False, requests=0)
    try:
        state.detail = 'loading four resident depth-three native stages on cards 23/27/43/47'
        engine.start()
        status = dict(schema='ownrt.pp4-lan-run.v1', started=S.utc(), pid=os.getpid(),
                      bind=args.bind, interface=interface, port=args.port,
                      output=str(engine.output), api_key_required=bool(key),
                      lifetime_hours=args.lifetime_hours, tokenizer=chat.authority,
                      model=S.CHAT.MODEL_ID, bdfs=list(B.BDFS), boundaries=B.BOUNDARIES,
                      stages=4, context=B.CONTEXT, speculative_depth=3, capture_ready_overlap=True,
                      cold_reset_every_request=True, live_mtp=True, continuation=False,
                      sessions=False, prefill_rows=engine.prefill_rows)
        base.save(engine.output / 'run.json', status)
        if not state.stop.is_set():
            state.phase = 'ready'
            state.detail = ''
        deadline = engine.start_time + args.lifetime_hours * 3600
        print(json.dumps(dict(ready=True, resident_stages=len(engine.stages), cold_requests=True,
                              speculative_depth=3)), flush=True)
        while not state.stop.is_set():
            engine.guard.check()
            if time.monotonic() > deadline:
                state.detail = 'planned HTTP lifetime reached; restart with fresh admission to continue'
                break
            if engine.lock.acquire(blocking=False):
                try:
                    engine.check_alive()
                finally:
                    engine.lock.release()
            state.stop.wait(5)
    except BaseException as error:
        fault(error)
        traceback.print_exc()

    original = faults[0] if faults else None
    with engine.lock:
        result = engine.close(original is None, reason=repr(original) if original is not None else None) or result
    if original is None and not result.get('passed'):
        original = RuntimeError(result.get('error') or 'PP4 stages did not exit cleanly')
    for server in servers:
        server.shutdown()
    print(json.dumps(result), flush=True)
    return exit_status(faults, result)


if __name__ == '__main__':
    sys.exit(main())
