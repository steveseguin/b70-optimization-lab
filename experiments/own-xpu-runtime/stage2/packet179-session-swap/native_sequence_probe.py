"""CPU native reset/sensor sequences; production geometry, synthetic transport.

Run each topology in a fresh constrained Python process. The unchanged native
reset functions and preparation paths execute; this is not model inference.
The full worker sequence is separately exercised by the Python arm gate.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import time

from build_engine import P, ROOT, limits, turn

OLD = P.parent / 'packet163-full-gate'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main(name):
    limits()
    p = P / name
    old = OLD / name
    build = p / 'build/native-sequence165'
    build.mkdir(parents=True, exist_ok=True)
    old_build = old / 'build/preparation163'
    # All included production code is still the frozen packet163 preparation
    # source; no arithmetic, device executable or existing source is changed.
    for filename in ('probe-main.cpp', 'mock_device.hpp', 'preparation_backend.hpp'):
        if not (old_build / filename).is_file():
            continue
        (build / filename).write_bytes((old_build / filename).read_bytes())
    (build / 'native_sequence_helpers.hpp').write_bytes((P / 'native_sequence_helpers.hpp').read_bytes())
    sources = {str(P / 'native_sequence_helpers.hpp'): sha(P / 'native_sequence_helpers.hpp'),
               str(old_build / 'probe-main.cpp'): sha(old_build / 'probe-main.cpp')}
    if name == 'two-card':
        (build / 'fixture.cpp').write_bytes((P / 'native_sequence_two.cpp').read_bytes())
        sources[str(P / 'native_sequence_two.cpp')] = sha(P / 'native_sequence_two.cpp')
        mtp = next((old / 'native-source').rglob('mtp.hpp'))
        text = mtp.read_text()
        start = text.index(' void reset_request(const fs::path& output) {')
        end = text.index(' void dump_all_state(', start)
        (build / 'draft_reset.inc').write_text(text[start:end])
        sources[str(mtp)] = sha(mtp)
    else:
        text = (old_build / 'fixture.cpp').read_text().split('int main(int argc,char**argv) {')[0]
        text = text.replace('public ownrt::ForegroundPrefix {', 'public ownrt::ForegroundPrefix, public p58v::AsyncBackend {')
        text = text.replace('  bool foreground_prefix_complete() override', '''  ownrt::Event fill(void* d,const void* s,size_t n) override {return copy(d,s,n,{});}
  bool fill_complete(ownrt::Event) override {return true;}
  size_t fills_pending() override {return 0;}
  void finish_fills() override {}
  void foreground_sync() override {synchronize();}
  bool foreground_prefix_complete() override''')
        # Preserve real first64-byte mutable samples in large opaque buffers.
        # Large weight/cache extents remain sparse CPU mappings.
        old_copy = 'if(fits(d)&&fits(s))std::memcpy(d,s,n);'
        assert text.count(old_copy) == 1
        text = text.replace(old_copy, '''auto available=[&](const void* p){for(auto [base,extent]:extents){auto off=uintptr_t(p)-uintptr_t(base);if(off<extent){auto bytes=backing.at(base);return off<bytes?bytes-off:size_t(0);}}return n;};
    const auto clipped=std::min(n,std::min(available(d),available(s)));if(clipped)std::memcpy(d,s,clipped);''')
        text += (P / 'native_sequence_one.inc').read_text()
        (build / 'fixture.cpp').write_text(text)
        sources[str(old_build / 'fixture.cpp')] = sha(old_build / 'fixture.cpp')
        sources[str(P / 'native_sequence_one.inc')] = sha(P / 'native_sequence_one.inc')
    commands = json.loads((old / 'evidence/preparation-build.json').read_text())['commands']
    commands = [[arg.replace(str(old_build), str(build)) for arg in command] for command in commands]
    build_receipt = build / 'compiled-inputs.json'
    previous = json.loads(build_receipt.read_text()) if build_receipt.is_file() else {}
    reuse = (previous.get('commands') == commands
        and (build / 'prepare-probe').is_file()
        and previous.get('binary_sha256') == sha(build / 'prepare-probe')
        and all(Path(path).is_file() and sha(path) == digest
                for path, digest in previous.get('sources_sha256', {}).items()))
    if not reuse:
        for number, command in enumerate(commands):
            with turn(), (build / f'build-{number}.log').open('w') as log:
                subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                    preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
    dependency = (build / 'fixture.d').read_text().replace('\\\n', ' ').split(':', 1)[1]
    for filename in shlex.split(dependency):
        file = Path(filename).resolve()
        if file.is_relative_to(ROOT):
            sources[str(file)] = sha(file)
    save(build_receipt, dict(commands=commands, sources_sha256=sources,
                            binary_sha256=sha(build / 'prepare-probe')))
    sys.path.insert(0, str(p))
    import worker
    import native_env
    sys.path.append(str(ROOT / 'experiments/own-xpu-runtime/ops'))
    spec = importlib.util.spec_from_file_location('native_sequence_sandbox', ROOT / 'experiments/own-xpu-runtime/ops/rehearse_entry.py')
    sandbox = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox)
    binary = build / 'prepare-probe'
    sequence = build / 'sequence.txt'
    ids = [entry['prompt_id'] for entry in worker.entries()]
    assert len(ids) == 13 and ids[:2] == ['incident-retrospective', 'prefill512']
    sequence.write_text('\n'.join(ids) + '\n')
    metadata = [file for file in (p / 'inputs').rglob('*') if file.is_file()]
    # Frozen probe-main references frozen small rotary metadata and plan paths.
    metadata += [file for file in (old / 'inputs').rglob('*') if file.is_file()]
    metadata += [p / 'selection.json', p / 'dispatch.json', p / 'memory-plan.json',
                 old / 'selection.json', old / 'dispatch.json', old / 'memory-plan.json', sequence]
    metadata += list((old / 'native-source').rglob('*.bf16'))
    metadata += list((old / 'native-source').rglob('*manifest*.json'))
    probes = json.loads((old / 'evidence/preparation-probe.json').read_text())['probes']
    results = []
    for number, probe in enumerate(probes):
        output = build / ('run-' + str(time.time_ns()) + '-rank' + str(number))
        output.mkdir()
        # Shared preparation Landlock deliberately denies creating directories.
        # Precreate only the exact request/reset dump destinations required by
        # the fixture, as packet163's original preparation harness does.
        for id in ['', *ids, 'after-suite']:
            request = output / id
            request.mkdir(exist_ok=True)
            (request / 'state-2147483647').mkdir(exist_ok=True)
        if name == 'two-card':
            for id in [*ids, 'after-suite']:
                (output / ('draft-' + id)).mkdir()
        env = native_env.environment('A')
        env.update(ENTRY_PREPARE_OUTPUT=str(output), SEQUENCE_INPUTS=str(sequence))
        argv = [str(binary), *probe['real_native_argv'][1:]]
        # Only argv metadata paths move to the new packet. The C++ parser still
        # receives exactly production options, including 4096/512 dimensions.
        argv = [arg.replace(str(old), str(p)) for arg in argv]
        if '--suite-inputs' in argv:
            table = output / 'suite-inputs.tsv'
            table.write_text(''.join(id + ' ' + str(p / 'inputs' / id / 'tokens.txt') + '\n' for id in ids))
            argv[argv.index('--suite-inputs') + 1] = str(table)
        with turn(), (output / 'stdout.log').open('w') as out, (output / 'stderr.log').open('w') as err:
            child = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                preexec_fn=lambda: sandbox.prepare_restrict(binary, metadata, output))
            peak = 0
            while child.poll() is None:
                try:
                    status = Path(f'/proc/{child.pid}/status').read_text()
                    rss = next(int(line.split()[1]) * 1024 for line in status.splitlines() if line.startswith('VmRSS:'))
                    peak = max(peak, rss)
                    if rss > 4 * 1024**3:
                        child.terminate()
                        child.wait()
                        raise ValueError('CPU probe exceeded 4GB physical RAM')
                except (FileNotFoundError, StopIteration):
                    pass
                time.sleep(.05)
        result = dict(rank=number, argv=argv, returncode=child.returncode, peak_rss_bytes=peak,
                      stdout=(output / 'stdout.log').read_text(), stderr=(output / 'stderr.log').read_text(),
                      output=str(output.relative_to(ROOT)))
        results.append(result)
        save(p / 'evidence/native-sequence-progress.json', dict(results=results))
        assert child.returncode == 0, result
        assert 'PASS native sequence' in result['stdout']
        checks = []
        for id in [*ids, 'after-suite']:
            for filename in ('timings.jsonl', 'prefill-timings.jsonl', 'sites.jsonl', 'progress.jsonl'):
                file = output / id / filename
                rows = [json.loads(line) for line in file.read_text().splitlines()]
                sensors = [row for row in rows if row.get('cpu_sequence_sensor')]
                assert len(sensors) == 1 and sensors[0]['request_id'] == id, (id, filename)
                checks.append(dict(request_id=id, stream=filename, rows=len(rows), sha256=sha(file)))
            reset = json.loads((output / id / 'reset.json').read_text())
            assert reset['passed'] and reset['allocation_ids_preserved']
            if name == 'one-card':
                assert reset['cached_tokens'] == 0
            else:
                row = json.loads((output / ('draft-' + id) / 'draft-rows.jsonl').read_text())
                assert row['cpu_sequence_sensor'] and row['request_id'] == id
        result['sensor_checks'] = checks
    receipt = dict(passed=True, device_executed=False, model_reads=False, requests=ids,
        target_resets_per_native_owner=14, sensor_streams_per_reset=4,
        native_argv_production_geometry=True, commands=commands, sources_sha256=sources,
        binary_sha256=sha(binary), script_sha256=sha(__file__),
        landlock='libraries plus exact metadata and this run scratch; no model or /dev/dri access',
        scope='real target reset and device preparation paths, CPU marker transport; first64 mutable bytes sampled; allocation IDs/pointers/categories preserved; synthetic sensors are not model output or timing evidence',
        draft_scope='two-card: exact extracted draft reset method on real Engine and synthetic facade; constructor, draft kernels, model data and arithmetic not exercised',
        synthetic_dump_retention='generated synthetic .bin/.bf16 dumps removed after reset; JSON state inventories and sensor stream hashes retained',
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024,
        results=results)
    assert receipt['peak_child_rss_bytes'] < 4 * 1024**3
    save(p / 'evidence/native-sequence.json', receipt)
    print(name, 'native reset/sensor sequence PASS', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('topology', choices=('one-card', 'two-card'))
    args = parser.parse_args()
    # CPU backend uses sparse full-shape virtual mappings, so bound physical
    # memory via RSS watchdog, as packet163's preparation harness does.
    main(args.topology)
