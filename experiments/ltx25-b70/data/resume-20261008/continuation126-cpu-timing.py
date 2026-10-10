"""CPU mechanism timing only; no launch, endpoint, device import or live-run write.

Run with nice19, OMP_NUM_THREADS=2 and the baseline Python -B. Writes one new
JSON beside this script; repeated invocation requires a new --output path.
"""
import argparse
import hashlib
import json
import marshal
import os
from pathlib import Path
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
LANE = HERE.parent.parent
SOURCE = LANE / 'recovery/20261010-continuation126-stream'
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
import session
from test_session import Harness, SHA

CHECKS_PER_BATCH = 35
BATCHES = 100


def summary(values):
    ordered = sorted(values)
    return {'n': len(values), 'median_s': statistics.median(values),
            'mean_s': statistics.mean(values), 'min_s': min(values),
            'p10_s': ordered[int(.1 * (len(values) - 1))],
            'p90_s': ordered[int(.9 * (len(values) - 1))], 'max_s': max(values)}


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--output', type=Path, default=HERE / 'continuation126-cpu-timing.json')
    out = args.parse_args().output
    assert not out.exists(), 'Never overwrite existing evidence'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    assert sys.dont_write_bytecode
    h = Harness(frames=145, reuse=1, anchor='frame', decoder_graph=0,
                levers=('cone', 1, 1))
    try:
        optimized = session.StreamAuthority(h.run.parent / 'plan.json', SHA, 'b' * 64,
            h.run, h.state, 1, 145, 'two-way', 'frame', 0, ('cone', 1, 1),
            server_options={'storage_scan_mode': 'background'})
        modes = {'request': h.a, 'background': optimized}
        durations = {name: [] for name in modes}
        for authority in modes.values():
            for _ in range(5):
                authority.healthy()
        for batch in range(BATCHES):
            order = ('request', 'background') if batch % 2 == 0 else ('background', 'request')
            for mode in order:
                start = time.perf_counter()
                for _ in range(CHECKS_PER_BATCH):
                    modes[mode].healthy()
                durations[mode].append(time.perf_counter() - start)
        # These are complete initialized authorities with setup/qualification aliases,
        # not isolated trees. Version 2 avoids version 4's refcount-dependent flags.
        assert marshal.dumps(optimized.plan, 2) == optimized._plan_binary
        values = [None, True, False, 0, 1, -1, 0.0, -0.0, 1.0, '', '0',
                  [], {}, [0], [False], {'0': 0}, (0,), set(), b'0']
        assert len({marshal.dumps({'value': v}, 2) for v in values}) == len(values)
        result = {
            'schema': 'ltx.continuation126.cpu-mechanism-timing.v1',
            'scope': 'CPU healthy() only; not a measured live chunk period or GPU benchmark',
            'method': '100 paired batches, alternating arm order; 35 healthy() calls/batch; '
                      'initialized 145-frame authorities with inactive request and all aliases installed',
            'python': sys.executable, 'python_version': sys.version,
            'nice': os.getpriority(os.PRIO_PROCESS, 0),
            'omp_num_threads': os.environ['OMP_NUM_THREADS'],
            'marshal_version': 2, 'checks_per_batch': CHECKS_PER_BATCH, 'batches': BATCHES,
            'plan_sha256': session.PLAN_SHA256,
            'canonical_plan_bytes': len(session.canonical(optimized.plan)),
            'marshal_plan_bytes': len(optimized._plan_binary),
            'sources_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (SOURCE / 'session.py', SOURCE / 'plan.py',
                                         SOURCE / 'stream_contract.py', Path(__file__))},
            'type_probe_count': len(values),
            'full_healthy_batch': {name: summary(v) for name, v in durations.items()},
            'paired_saved_s': summary([a - b for a, b in
                                     zip(durations['request'], durations['background'])]),
            'raw_batch_seconds': durations,
            'limits': ['CPU scheduling is shared with the coordinator workload.',
                       'No filesystem/accounting savings are included.',
                       'The receipt count of 35 calls per chunk is external evidence; '
                       'this harness measures exactly that many calls.',
                       'A full native qualification and matched live run remain required.'],
        }
        with out.open('x') as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
        print(json.dumps({key: result[key] for key in ('full_healthy_batch', 'paired_saved_s')},
                         indent=2, ensure_ascii=False))
    finally:
        h.close()


if __name__ == '__main__':
    main()
