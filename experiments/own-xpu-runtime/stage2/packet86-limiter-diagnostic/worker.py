#!/usr/bin/env python3
"""Internal screen worker: one rank pair, one load, 64-token gate then 12x128."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time

P = Path(__file__).resolve().parent
WRAPPER = P.parent / 'screen/v4-lanes'
sys.path.insert(0, str(WRAPPER))

from common import D, P56, ROOT, SUPPORT, compare_tokens, label, read, require, save, sha, summary

sys.path.append(str(P))
from policy import guard, labels, classify
from conditions import LANES, Teardown, lane_gate
from devices import DeviceMonitor, masked_environment

def request_schedule(entries, paired):
    if paired:
        return [('incident64', entries[0], 64, 'control')] + [
            (arm + '/' + e['prompt_id'], e, 128, arm)
            for arm in ('control', 'attribution') for e in entries]
    return [('incident64', entries[0], 64, None)] + [(e['prompt_id'], e, 128, None) for e in entries]


def reset_observation(suite, transport, destination, arm):
    # RESET token is unused in the parent. This instrumentation ABI interprets
    # 1 as event recording off and 0 as on. All numerical state reset is unchanged.
    if arm is None:
        return suite.reset(transport, destination)
    call = transport.call
    def reset_call(rank, op, *args, **kwargs):
        require(op == suite.RESET, 'unexpected command during request reset')
        return call(rank, op, token=int(arm == 'control'))
    transport.call = reset_call
    try:
        suite.reset(transport, destination)
    finally:
        transport.call = call

def drain(transport, output, success, reason=None):
    """A stop arriving during FINISH must drain inside the same spacing permit."""
    failure = None
    def refused(error):
        transport.teardown_refused = True
        # Transport.stop writes ! to our inherited stop pipe. Transport.close
        # waits at most 65 seconds and never signals or kills a process.
        # Disable only the remembered Python cancellation during this wait;
        # the outer supervisor continues passive fault/memory monitoring.
        transport.check = lambda: None
        try:
            transport.stop(error)
        finally:
            transport.close(False)
        return dict(cooperative_stop_requested=True, own_ranks_exited=True,
                    drain_bound_seconds=65)
    with Teardown(output, on_refusal=refused):
        try:
            if not success:
                transport.stop(reason)
                # Stop is already delivered through the native stop descriptor.
                # Keep draining despite the remembered Python cancellation;
                # the outer passive supervisor still checks memory and faults.
                transport.check = lambda: None
            transport.close(success)
        except Exception as error:
            failure = error
            transport.stop(error)
            transport.check = lambda: None
            transport.close(False)
    if failure is not None:
        raise failure


def run(identity, output, seconds, pair_dir=None):
    from placement import verify_identity
    placement, memory_gate = verify_identity(identity)
    # Use this lineage's admission for both prelaunch and live census checks.
    sys.modules['memory_gate'] = memory_gate
    # Reuse the sealed dispatch/control protocol, with private Python module state.
    # Only paths used for new writes are redirected. No sealed files are modified.
    sys.path.insert(0, str(P56))
    import pipeline
    import suite
    import storage
    view=Path(identity['lineage']).name
    guard(view, timing=identity['timing'])
    require(identity['lane'] in ('A','B'), 'packet86 lane')
    require(read(identity['seal']).get('diagnostic_nonexact') is True, 'diagnostic seal required')
    suite.EOS=()  # fixed 128-token diagnostic work; never a natural completion benchmark
    manifest = D.oracle_inputs()
    entries = manifest['prompts']
    adapter = output / 'adapter'
    (adapter / 'build').mkdir(parents=True)
    for name in ('selection.json', 'memory-plan.json'):
        (adapter / name).write_bytes((Path(identity['lineage']) / name).read_bytes())
    pipeline.P = adapter
    storage.P, storage.B = adapter, adapter / 'build'
    # Screen has its own admitted peak; do not reserve an eleven-window chain.
    storage.admit = lambda extra, **unused: SUPPORT.storage(output, extra)
    args = pipeline.parser().parse_args(['--output', str(output), '--device',
        '--binary', identity['binary'], '--dispatch', identity['dispatch'],
        '--controller', 'native', '--draft', 'mtp', '--draft-rank', str(placement['draft_rank']),
        '--target-split', str(placement['target_split']), '--context', '4096', '--tokens', '128',
        '--retain-steps', 'none', '--timing', 'token', '--native-nice', '0',
        '--card', '0',
        '--seconds', str(seconds), '--wait-seconds', str(seconds)])
    # Packet56's parser predates the attribution string. The controller ABI is
    # unchanged; sealed() already checks the candidate's supported timing modes.
    args.timing = identity['timing']
    args.selection_sha256 = identity['selection_sha256']
    checker = suite.checker_module(P56.parent / 'packet49-integrate/oracle/suite_check.py')
    snapshots = suite.admit_inputs(entries, output, checker)
    args.input = snapshots[entries[0]['prompt_id']][0]
    ranks = output / 'ranks'
    ranks.mkdir()
    stopped, rows, incident = [], [], {}
    arm_rows = {'control': [], 'attribution': []}
    monitor = DeviceMonitor(identity['lane'], output)
    environment = masked_environment(identity['lane'], dict(os.environ), inherited=True)
    monitoring = True
    def check():
        require(not stopped, 'coordinator stop requested')
        if monitoring:
            monitor.poll()
    handlers = {s: signal.signal(s, lambda n, f: stopped.append(n))
                for s in (signal.SIGTERM, signal.SIGINT)}
    transport = pipeline.Transport.__new__(pipeline.Transport)
    try:
        pipeline.Transport.__init__(transport, args, ranks, environment, check, launch_hook=monitor.register)
        monitor.poll(ready=True)
        requests = request_schedule(entries, True)
        for name, entry, count, arm in requests:
            check()
            dest = output / name
            reset_observation(suite, transport, dest, arm)
            prompt = snapshots[entry['prompt_id']][1]
            result = suite.run_request(transport, args, prompt, count)
            expected = D.CHECK.token_record(D.ORACLE / 'results' / entry['prompt_id'])
            comparison=classify(view,result['tokens'],expected,count)
            result.update(prompt_id=entry['prompt_id'], prompt_class=D.METRICS.PROMPT_CLASSES[entry['prompt_id']],
                          repeat=1, prompt_token_sha256=D.token_hash(prompt))
            result.update(attribution_arm=arm, binary_sha256=identity['binary_sha256'],
                          selection_sha256=identity['selection_sha256'], target_split=placement['target_layers'],
                          **comparison, **labels(view))
            save(dest / 'receipt.json', label(result))
            if count == 64:
                incident = dict(passed=True, tokens_compared=64, mode='separate-reset-request',
                                receipt_sha256=sha(dest / 'receipt.json'))
                save(output / 'incident64.json', incident)
            else:
                arm_rows[arm].append(result)
        monitor.poll(ready=True)
        suite.reset(transport, output / 'after-suite')
        if pair_dir is not None:
            # Keep either teardown out of the other lane's measurement span.
            save(pair_dir / (identity['lane'] + '-measured.json'), dict(passed=True, requests=12))
            deadline = time.monotonic() + seconds
            while not all((pair_dir / (lane + '-measured.json')).exists() for lane in ('A', 'B')):
                check()
                require(not (pair_dir / 'STOP').exists(), 'pair stopped before teardown')
                require(time.monotonic() < deadline, 'paired measurement barrier timeout')
                time.sleep(.1)
        monitor.poll(ready=True)
        # Stage raw exactness receipts BEFORE drain; aggregation runs only in the
        # parent after postflight and release. No CPU report runs after our drain.
        rows = arm_rows['attribution']
        save(output / 'paired-inputs.json', dict(passed=True, arms=arm_rows, incident64=incident, **labels(view)))
        save(output / 'report-inputs.json', dict(passed=True, requests=rows, incident64=incident,
             placement=placement, lane=identity['lane'], timing=identity['timing'], **labels(view),
             device_isolation=read(output / 'device-isolation.json')))
        monitoring = False  # FINISH legitimately closes rank FDs and PIDs.
        drain(transport, output, True)
        return 0
    except Exception as error:
        save(output / 'failure.json', label(dict(passed=False, error=str(error))))
        if hasattr(transport, 'stop_write') and not getattr(transport, 'closed', False):
            if not getattr(transport, 'teardown_refused', False):
                try:
                    drain(transport, output, False, error)
                except Exception as drain_error:
                    save(output / 'drain-error.json', dict(error=str(drain_error)))
            # Keep the supervising process alive while it still owns live ranks.
            # The outer wrapper returns 75 and leaves the user unit for supervision.
            while any(p.poll() is None for p in transport.children):
                time.sleep(.25)
        return 1
    finally:
        for s, handler in handlers.items():
            signal.signal(s, handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identity', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    parser.add_argument('--pair-dir', type=Path)
    args = parser.parse_args()
    lane_gate(read(args.identity)['lane'])
    # The outer supervisor owns authorization; accidental standalone calls fail.
    require((args.identity.parent / 'window.json').is_file(), 'outer screen admission required')
    raise SystemExit(run(read(args.identity), args.output, args.seconds, args.pair_dir))
