#!/usr/bin/env python3
"""Production-driven shadow diagnostic: independent corpus then secondary suite."""
import argparse
import os
from pathlib import Path
import signal
import shutil
import sys
import time
import json
from analyze import paired

from bootstrap import install
install()
from exec_limits import install as install_limits
install_limits()
from common import D, P56, ROOT, SUPPORT, compare_tokens, label, read, require, save, sha, summary

from conditions import LANES, lane_gate
from teardown import Teardown
from devices import DeviceMonitor, masked_environment

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
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pipeline
    import suite
    import storage
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
    args.acceptance_shadow = True
    args.selection_sha256 = identity['selection_sha256']
    checker = suite.checker_module(P56.parent / 'packet49-integrate/oracle/suite_check.py')
    snapshots = suite.admit_inputs(entries, output, checker)
    args.input = snapshots[entries[0]['prompt_id']][0]
    ranks = output / 'ranks'
    ranks.mkdir()
    stopped, rows, incident = [], [], {}
    monitor = DeviceMonitor(identity['lane'], output)
    environment = masked_environment(identity['lane'], dict(os.environ), inherited=True)
    monitoring = True
    def check():
        require(not stopped, 'coordinator stop requested')
        require(shutil.disk_usage('/').free>=25_000_000_000,'root free below 25 GB')
        if monitoring:
            monitor.poll()
    handlers = {s: signal.signal(s, lambda n, f: stopped.append(n))
                for s in (signal.SIGTERM, signal.SIGINT)}
    transport = pipeline.Transport.__new__(pipeline.Transport)
    try:
        pipeline.Transport.__init__(transport, args, ranks, environment, check, launch_hook=monitor.register)
        monitor.poll(ready=True)
        calibration = read(Path(__file__).with_name('calibration')/'inputs.json')
        requests = [(e['prompt_id'], e, 128, 'independent') for e in calibration['prompts']]
        requests += [(e['prompt_id'], e, 128, 'secondary') for e in entries]
        require(len(requests)==22, 'complete independent and secondary corpora required')
        for name, entry, count, group in requests:
            check()
            dest = output / name
            suite.reset(transport, dest)
            prompt = entry['tokens'] if group=='independent' else snapshots[entry['prompt_id']][1]
            result = suite.run_request(transport, args, prompt, count)
            result['attribution_request'] = len(rows)+1
            # Native controller trace is overwritten per request: retain each original.
            (dest/'native-result.json').write_bytes((ranks/'native-result.json').read_bytes())
            if group=='secondary':
                expected = D.CHECK.token_record(D.ORACLE / 'results' / entry['prompt_id'])
                compare_tokens(result['tokens'], expected, count, name)
            require(1<=len(result['tokens'])<=128, 'invalid target generation length')
            native=read(dest/'native-result.json')
            shadow=[json.loads(line) for line in (dest/'rank1/shadow-rows.jsonl').read_text().splitlines()]
            counts=paired(native,shadow,len(prompt),len(result['tokens']))
            result.update(prompt_id=entry['prompt_id'], prompt_class=group if group=='independent' else D.METRICS.PROMPT_CLASSES[entry['prompt_id']],
                          repeat=1, group=group, paired=counts, exact_oracle=group=='secondary',
                          target_verified=True, prompt_token_sha256=D.token_hash(prompt))
            save(dest / 'receipt.json', label(result))
            if group=='secondary' and name == entries[0]['prompt_id']:
                incident = dict(passed=True, tokens_compared=64, mode='first-suite-request',
                                receipt_sha256=sha(dest / 'receipt.json'))
                save(output / 'incident64.json', incident)
            rows.append(result)
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
        save(output / 'report-inputs.json', dict(passed=True, requests=rows, incident64=incident,
             placement=placement, lane=identity['lane'], timing=identity['timing'],
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
