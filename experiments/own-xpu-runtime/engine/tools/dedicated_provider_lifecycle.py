"""Guarded lifecycle for target owners plus one genuine dedicated provider.

Uses the pipeline Guard's existing passive policy and cooperative stop pipes.
Never retries, kills children, or changes host/device settings.
"""
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import sys
import time

import pipeline_driver as base
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'planning'))
from rolling_provider import dedicated_transport as bridge


def execute(plan, admission, unit):
    base.require(admission.get('schema') == 'ownrt.pipeline-admission.v1'
                 and admission.get('owner_authorized') is True, 'explicit admission required')
    base.require(datetime.fromisoformat(admission['expires_utc']) > datetime.now(timezone.utc),
                 'admission expired')
    base.require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    identity = base.validate_unit(unit)
    targets, provider_spec = plan['stages'], plan['provider']
    base.require(len(targets) in (2, 3) and provider_spec['id'] == 'provider',
                 'separate provider role and two/three targets required')
    specs = targets+[provider_spec]
    base.require(len({s['bdf'] for s in specs}) == len(specs), 'exclusive target/provider devices required')
    output = Path(plan['output'])
    output.mkdir(mode=0o700)
    base.save(output/'plan.json', plan)
    base.save(output/'admission.json', admission)
    base.save(output/'unit.json', identity)
    # Guard admission must include the provider device, even though its spec is
    # not part of the target scheduler topology.
    guard_plan = dict(plan, stages=specs)
    guard = base.Guard(guard_plan, admission, None)
    prior = {sig:signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    for sig in prior:
        signal.signal(sig, lambda *_:guard.signal_stop.set())
    stages, provider, result, failure = [], None, {}, None
    start = time.monotonic()
    try:
        guard.thread.start()
        for spec in targets:
            guard.check()
            stage = bridge.Stage(spec, plan, guard)
            stages.append(stage)
            stage.receive(ready=True)
        guard.check()
        # base.Stage registers every Popen immediately in guard.tracked_processes,
        # before identity capture or launch.json can fail. Cleanup uses that list,
        # never only the successfully returned Stage objects.
        owner = base.Stage(provider_spec, plan, guard)
        provider = bridge.Provider(owner)
        provider.receive_ready(target_stages=len(stages), depth=plan.get('speculative_depth', 2),
                               request=bytes.fromhex(plan['request_sha256']), epoch=plan.get('epoch', 0))
        base.require(all(s.stream_bytes == provider.stream_bytes for s in stages),
                     'target/provider source boundary shape mismatch')
        guard.validate_or_stop(guard.obs.observe(), phase='main-after-ready')
        result = bridge.drive(stages, provider, plan, guard, output)
        # Target control protocol has no finish ACK; provider protocol does.
        for stage in stages:
            stage.command(4, position=2147483647)
        provider.control(4)
        guard.validate_or_stop(guard.obs.observe(), phase='main-before-finish')
        for stage in stages:
            stage.command(5)
        provider.control(5)
    except Exception as error:
        failure = repr(error)
        guard.fail(failure)
    finally:
        end = time.monotonic()+plan['grace_seconds']
        while any(p.poll() is None for _,p in guard.tracked_processes) and time.monotonic() < end:
            time.sleep(.2)
        guard.done.set()
        if guard.thread.ident is not None:
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
        alive = [p.pid for _,p in guard.tracked_processes if p.poll() is None]
        codes = {str(i):p.poll() for i,p in guard.tracked_processes}
        if failure is None and (alive or len(codes) != len(specs) or any(code != 0 for code in codes.values())):
            failure = 'native target/provider owners did not exit cleanly'
        for sig,handler in prior.items():
            signal.signal(sig, handler)
        failure_details = {} if failure is None else dict(guard_failure=guard.failed,
            caught_error=caught_failure, guard_first_failure=guard.first_failure,
            guard_failure_evidence_error=guard.failure_evidence_error)
        terminal = dict(schema='ownrt.dedicated-provider-terminal.v1', passed=failure is None,
            error=failure, live_pids=alive, returncodes=codes, requests=1 if result else 0,
            mode=('dedicated-provider-sequential-bulk' if plan.get('dedicated_bulk_prefill',False) else 'dedicated-provider-per-token'),
            diagnostic_only=True, speed_claim=False,
            bulk_reset_qualified=False, bulk_overlap_qualified=False,
            prefix_evidence_policy='actual native OP15/OP28 records and pair traces; no synthetic scalar ROW/ACCEPT events',
            wall_seconds=time.monotonic()-start, **failure_details)
        receipt = dict(result)
        receipt.update(terminal)
        receipt['schema'] = 'ownrt.dedicated-provider-driver-result.v1'
        # Keep actual emitted IDs/commit timestamps from the transport, including
        # partial evidence on cancellation; no expected answer or throughput claim.
        receipt['native_dumps'] = [dict(owner=s['id'], native_output=s['native_output']) for s in specs]
        try:
            base.save(output/'driver-result.json', receipt)
            base.save(output/'terminal.json', terminal)
        except Exception as evidence_error:
            if failure is not None:
                raise ValueError(failure) from evidence_error
            raise
    base.require(failure is None, str(failure))
    return receipt
