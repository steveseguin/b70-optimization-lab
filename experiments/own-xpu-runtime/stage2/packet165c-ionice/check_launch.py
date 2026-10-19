"""CPU regression: proposal -> real entry plan -> real worker -> intercepted exec.

Only the native executable is replaced with a tiny ioprio_get process and
synthetic result files. No model, GPU, service or admission path executes.
The separate native reset fixture covers real reset functions and sensors.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OPS = ROOT / 'experiments/own-xpu-runtime/ops'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def check_child(request, output):
    job = read(request)
    packet = (ROOT / job['argv'][2]).parent
    sys.path.insert(0, str(packet))
    import entry, screen, worker, composition, storage, exec_limits, native_env
    import measurement as M
    env = native_env.environment(job['lane'])
    assert all(os.environ.get(k) == v for k, v in env.items())
    assert set(os.environ) <= set(env) | {'HOME', 'LC_CTYPE'}
    items = worker.entries()
    order = [e['prompt_id'] for e in items]
    wanted = ([M.IDS[0], 'prefill512', *M.IDS[1:]] if 'packet165-' in packet.parent.name
              else ['prefill512', *M.IDS])
    assert order == wanted and len({tuple(e['tokens']) for e in items}) == 13
    real_popen = subprocess.Popen
    observed = []
    launch = {}
    drain = dict(passed=True, device_executed=True, teardown=[dict(
        safe_to_exit=True, idle_marker_complete=True, live_bytes=0, in_flight=0, exit_code=0)])
    out = output / 'run'
    worker.save(output / 'window.json', dict(synthetic=True))
    worker.save(output / 'identity.json', dict(lane=job['lane']))

    def command_guard(argv):
        assert argv[:2] == ['/usr/bin/ionice', '-c3'], 'idle I/O wrapper missing'
        assert argv[2] == str(packet / 'build/device/own-rt-iq3')

    class NativeIntercept:
        returncode = 0

        def __init__(self, argv, **kw):
            command_guard(argv)
            assert kw['stdin'] == subprocess.DEVNULL and 'env' not in kw
            declared = job['plan']['entry_rehearsal']['binaries'][0]
            assert sha(argv[2]) == declared['sha256']
            # Execute the real wrapper with inherited worker environment. The
            # replacement executable only asks the kernel about its own class.
            probe = ('import ctypes,json,os,platform;assert platform.machine()=="x86_64";'
                     'v=ctypes.CDLL(None).syscall(252,1,0);assert v>=0;'
                     'print(json.dumps(dict(ioprio=v,io_class=v>>13)))')
            child = real_popen([*argv[:2], '/usr/bin/python3', '-B', '-c', probe],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = child.communicate()
            assert child.returncode == 0 and not stderr
            priority = json.loads(stdout)
            assert priority['io_class'] == 3
            try:
                command_guard(argv[2:])
            except AssertionError:
                pass
            else:
                raise AssertionError('missing wrapper regression accepted')
            help_child = real_popen([argv[2], '--help'], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            help_text, help_error = help_child.communicate()
            assert help_child.returncode == 0 and not help_error
            flags = [v for v in argv[3:] if v.startswith('--')]
            assert all(v in help_text for v in flags)
            launch.update(argv=argv, priority=priority, flags=flags,
                binary_sha256=declared['sha256'], closed_environment=env,
                inherited_driver_home=True, missing_wrapper_refused=True)
            table = Path(argv[argv.index('--suite-inputs') + 1])
            lines = [line.split() for line in table.read_text().splitlines()]
            assert [row[0] for row in lines] == order
            for index, item in enumerate(items):
                assert Path(lines[index][1]).read_bytes() == (packet / 'inputs' / item['prompt_id'] / 'tokens.txt').read_bytes()
                dest = out / 'native' / item['prompt_id']
                dest.mkdir(parents=True)
                worker.save(dest / 'reset.json', dict(passed=True, cached_tokens=0, allocation_ids_preserved=True))
                for leaf in ('timings.jsonl', 'prefill-timings.jsonl'):
                    (dest / leaf).write_text(json.dumps(dict(synthetic=True, request=item['prompt_id'])) + '\n')
                oracle = worker.expected(item)
                tokens = ((oracle or []) + [42] * 512)[:512]
                start = 1000. + 100 * index
                worker.save(dest / 'result.json', dict(passed=True, arithmetic=M.ARITHMETIC,
                    cached_tokens=0, requested_max_new=512, tokens=tokens,
                    timing_rows=[dict(completed_monotonic=start + 1 + i * .1) for i in range(512)],
                    request_start_monotonic=start, request_end_monotonic=start + 53, prefill_ms=999.))
                worker.save(dest / 'lookup-request-complete.json', {})
                observed.append(item['prompt_id'])
            worker.save(out / 'native/receipt.json', drain)
            worker.save(out / 'native/census.json', {})

        def poll(self):
            return 0

        def wait(self):
            return 0

    # Preserve the real exec_limits check: this process inherits unlimited AS,
    # consumes small memory, and is observed by the outer preparation runner.
    with patch.object(worker.subprocess, 'Popen', NativeIntercept), \
         patch.object(composition, 'check_lookups'), patch.object(composition, 'check_census'), \
         patch.object(sys, 'argv', ['worker', '--output', str(out), '--lane', job['lane']]):
        assert worker.main() == 0
    report = read(out / 'report-inputs.json')
    assert observed == order
    assert [r['prompt_id'] for r in report['requests']] == list(M.IDS)
    for item in items:
        dest = out / 'native' / item['prompt_id']
        assert read(dest / 'stream-proof.json')['passed']
        assert read(dest / 'receipt.json')['cached_tokens'] == 0
    if 'packet165-' in packet.parent.name:
        assert report['prefill']['prefill']['warmup']['state_reset_before_prefill']
    # Replay actual retained parent device results, not synthetic speed values.
    rows = []
    for ident in M.IDS:
        raw = read(packet / 'lineage/parent-requests' / (ident + '.json'))
        tokens = list(map(int, (packet / 'inputs' / ident / 'tokens.txt').read_text().split()))
        oracle = read(packet / 'lineage/oracle128' / (ident + '.json'))['tokens']
        rows.append(M.request(raw, tokens, ident, oracle))
    key = 'class_balanced_tok_s_1_100_intervals_after_ttft'
    rate = M.aggregate(rows)[key]['median']
    assert math.isclose(rate, read(packet / 'lineage/parent-summary.json')[key]['median'], rel_tol=1e-12)
    save(output / 'result.json', dict(passed=True, device_executed=False, model_reads=False,
        job=job['name'], launch=launch, execution_order=order, stream_checks=26,
        real_worker_main=True, exec_limits_unmodified=True, native_exec_intercepted=True,
        reset_receipts_synthetic=True, parent_device_rate_reproduced=rate,
        scope='CPU launch and Python orchestration regression; no device arithmetic or speed claim'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--child', type=Path)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if args.child:
        return check_child(args.child, args.output)
    from build_engine import limits
    limits()
    results = []
    for number, folder in ((163, 'packet163-full-gate'), (165, 'packet165-warm-prefill')):
        packet = HERE.parent / folder / 'one-card'
        proposal = OPS / 'lane-queue' / f'proposed-p{number}-one-card-A.txt'
        spec = importlib.util.spec_from_file_location('closed_launch', packet / 'launch_env.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for job in [json.loads(s) for s in proposal.read_text().splitlines() if s and not s.startswith('#')]:
            with tempfile.TemporaryDirectory(prefix='packet165c-arm-') as directory:
                scratch = Path(directory)
                request = scratch / 'job.json'
                save(request, job)
                env = module.environment()
                command = [s.replace('{REVIEW}', str(scratch / 'unused-review.json')) for s in job['argv']]
                planned = subprocess.run([*command, '--plan'], env=env, cwd=ROOT,
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
                plan = json.loads(planned.stdout)
                assert plan['passed'] and not plan['device_executed']
                assert plan['command'][2] == str(packet / 'worker.py')
                assert plan['request_count'] == 13 and plan['per_operation_wait_seconds'] >= 300
                env.update(NEOReadDebugKeys='1', FilterBdfPath='0000:23:00.0',
                    ZE_ENABLE_PCI_ID_DEVICE_ORDER='1', ZE_AFFINITY_MASK='0',
                    ONEAPI_DEVICE_SELECTOR='level_zero:0', HOME=str(scratch / 'driver-home'))
                Path(env['HOME']).mkdir()
                subprocess.run(['/usr/bin/python3', '-B', str(Path(__file__).resolve()),
                    '--child', str(request), '--output', str(scratch)], env=env, cwd=ROOT,
                    stdin=subprocess.DEVNULL, check=True)
                result = read(scratch / 'result.json')
                result.update(proposal=str(proposal.relative_to(ROOT)), proposal_sha256=sha(proposal),
                    real_entry_plan=plan, worker_sha256=sha(packet / 'worker.py'))
                results.append(result)
                print(job['name'], 'idle I/O + real worker sequence PASS', flush=True)
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    assert peak < 4_000_000_000
    save(HERE / 'evidence/launch-checks.json', dict(passed=True, device_executed=False,
        peak_children_rss_bytes=peak, results=results))


if __name__ == '__main__':
    main()
