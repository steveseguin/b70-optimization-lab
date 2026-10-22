#!/usr/bin/env python3
"""Internal screen worker: one rank pair, one load, 64-token gate then 12x128."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time

from common import D, P56, ROOT, SUPPORT, compare_tokens, label, read, require, save, sha, summary


def run(identity, output, seconds):
    # Reuse the sealed dispatch/control protocol, with private Python module state.
    # Only paths used for new writes are redirected. No sealed files are modified.
    sys.path.insert(0, str(P56))
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
        '--controller', 'native', '--draft', 'mtp', '--draft-rank', '1',
        '--target-split', '23', '--context', '4096', '--tokens', '128',
        '--retain-steps', 'none', '--timing', 'token', '--native-nice', '19',
        '--seconds', str(seconds), '--wait-seconds', str(seconds)])
    args.selection_sha256 = identity['selection_sha256']
    checker = suite.checker_module(P56.parent / 'packet49-integrate/oracle/suite_check.py')
    snapshots = suite.admit_inputs(entries, output, checker)
    args.input = snapshots[entries[0]['prompt_id']][0]
    ranks = output / 'ranks'
    ranks.mkdir()
    stopped, rows, incident = [], [], {}
    def check():
        require(not stopped, 'coordinator stop requested')
    handlers = {s: signal.signal(s, lambda n, f: stopped.append(n))
                for s in (signal.SIGTERM, signal.SIGINT)}
    transport = pipeline.Transport.__new__(pipeline.Transport)
    try:
        pipeline.Transport.__init__(transport, args, ranks, dict(os.environ), check)
        requests = [('incident64', entries[0], 64)] + [(e['prompt_id'], e, 128) for e in entries]
        for name, entry, count in requests:
            check()
            dest = output / name
            suite.reset(transport, dest)
            prompt = snapshots[entry['prompt_id']][1]
            result = suite.run_request(transport, args, prompt, count)
            expected = D.CHECK.token_record(D.ORACLE / 'results' / entry['prompt_id'])
            compare_tokens(result['tokens'], expected, count, name)
            result.update(prompt_id=entry['prompt_id'], prompt_class=D.METRICS.PROMPT_CLASSES[entry['prompt_id']],
                          repeat=1, exact_oracle=True, prompt_token_sha256=D.token_hash(prompt))
            save(dest / 'receipt.json', label(result))
            if count == 64:
                incident = dict(passed=True, tokens_compared=64, mode='separate-reset-request',
                                receipt_sha256=sha(dest / 'receipt.json'))
                save(output / 'incident64.json', incident)
            else:
                rows.append(result)
        suite.reset(transport, output / 'after-suite')
        transport.close(True)
        save(output / 'summary.json', summary(rows, incident, 'tp2'))
        return 0
    except Exception as error:
        save(output / 'failure.json', label(dict(passed=False, error=str(error))))
        if hasattr(transport, 'stop_write'):
            transport.stop(error)
            try:
                transport.close(False)
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
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity')
    # The outer supervisor owns authorization; accidental standalone calls fail.
    require((args.identity.parent / 'window.json').is_file(), 'outer screen admission required')
    raise SystemExit(run(read(args.identity), args.output, args.seconds))
