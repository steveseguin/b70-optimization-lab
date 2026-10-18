#!/usr/bin/env python3
"""CPU parser, real-shape startup and existing host-oracle paths for every window.

No weights are loaded. The copied GNU executable's priority-probe runs the
production parser and exits before Weights. fullshape-submit separately runs
initialize/prepare_plan/prepare_commands with production extents and a mock
backend. The only parser substitutions are the host executable, removal of
device authorization, nice19 and a scratch output. Options are checked against
the fullshape harness; no miniature model stands in for real startup.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

import suite_driver as D
import views as V

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    parent = D.read(P / 'parent-build-gnu-host-receipt.json')
    binary = P / 'build/gnu-host/own-rt-iq3'
    assert sha(binary) == parent['binaries']['build/gnu-host/own-rt-iq3']
    full = D.read(P / 'evidence/fullshape-submit-cpu.json')
    records = []
    sources = dict(parent['sources_sha256'])
    for f in (Path(__file__), P/'suite_driver.py', P/'views.py', P/'views.json',
              V.selection('down-tile16'), P/'oracle-binding.json'):
        sources[str(f.relative_to(ROOT))] = sha(f)
    sources.update(D.read(P/'oracle-binding.json')['files_sha256'])
    assert all(sha(ROOT/n) == h for n, h in sources.items())
    with tempfile.TemporaryDirectory(prefix='startup-', dir=P/'build') as tmp:
        for window in D.WINDOWS:
            # This IS the chain's host-reference path: a bound, completed CPU
            # oracle, with no independent host model subprocess in this lineage.
            manifest = D.oracle_inputs()
            assert len(manifest['prompts']) == 12
            cap = 8 if window in ('KD', 'W2m') else 128
            retain = '1-8' if window in ('KD', 'W2m', 'WS') else 'none'
            entries = manifest['prompts'][:1] if cap == 8 else manifest['prompts']
            # Execute the exact comparison path against original completed 58g
            # bytes. This checks the host oracle consumer, not tile16-only device parity.
            previous = P.parent/'packet58g-onecard/evidence/card0-58g-a'/window/'run/run'
            compared = [D.compare_request(previous/e['prompt_id'], D.ORACLE/'results'/e['prompt_id'], e, cap, retain)
                        for e in entries]
            for miss in ('zero-copy', 'streamed'):
                out = Path(tmp)/(window+'-'+miss)
                table = Path(tmp)/(window+'-'+miss+'.tsv')
                table.write_text(''.join(f"{e['prompt_id']} {ROOT/e['input_bundle']/'tokens.txt'}\n" for e in entries))
                args = SimpleNamespace(window=window, view='down-tile16', output=out,
                                       miss_mode='zerocopy' if miss == 'zero-copy' else 'streamed')
                native = D.native_command(args, manifest, table)
                def value(flag): return native[native.index(flag)+1]
                assert value('--cards') == '1' and value('--card') == '0'
                assert value('--context') == '4096' and value('--memory') == 'resident'
                assert value('--stage') == 'decode' and value('--max-new') == str(cap)
                assert value('--retain-steps') == retain and value('--miss-path') == miss
                assert value('--selection') == str(V.selection('down-tile16')) and value('--selection-sha256') == V.digest('down-tile16')
                command = [str(binary), *native[3:]]  # remove ionice + device binary
                command.remove('--authorized-device-window')
                command[command.index('--native-nice')+1] = '19'
                command += ['--priority-probe']
                run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                     timeout=60, env={'PATH':'/usr/bin:/bin', 'OMP_NUM_THREADS':'2'})
                assert run.returncode == 0, run.stdout + run.stderr
                parsed = D.read(out/'run/priority.json')
                assert parsed['passed'] and parsed['device_executed'] is False
                startup = next(r for r in full['records'] if r['window'] == window and r['miss_path'] == miss)
                assert startup['passed'] and startup['selection_sha256'] == V.digest('down-tile16')
                records.append(dict(window=window, miss_path=miss, native_command=native, parser_command=command,
                    parser=parsed, fullshape=startup, host_reference=dict(passed=True, oracle='packet49-integrate',
                    arithmetic=D.ARITHMETIC, request_count=len(compared), cap=cap,
                    compared_layer_fixtures=sum(r['compared_layer_fixtures'] for r in compared),
                    method='actual oracle_inputs and compare_request against completed 58g receipts; no host model subprocess',
                    tile16_only_device_equality_claim=False)))
                shutil.rmtree(out)
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
    assert rss < 8*1024**3 and all(sha(ROOT/n) == h for n,h in sources.items())
    D.save(P/'evidence/startup-cpu.json', dict(passed=True, device_executed=False, model_reads=False,
        records=records, checks=len(records), peak_rss_bytes=rss, sources=sources,
        binary_sha256=sha(binary), fullshape_receipt_sha256=sha(P/'evidence/fullshape-submit-cpu.json')))
    print('10 real command parser + full-size startup + host-oracle checks PASS')


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    main()
