"""Link the real host operators and exercise status/prefix/bounds on CPU."""
import json
import resource
import subprocess
from build_engine import P, ROOT, limits, sha, save


def main():
    limits()
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    commands = json.loads((P / 'engine-commands.json').read_text())
    out = P / 'evidence/head-status'
    out.mkdir(exist_ok=True)
    runs = []
    for name, compiler in [('gnu', '/usr/bin/g++'),
                           ('intel', '/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        obj = P / 'build' / ('head-status-' + name + '.o')
        binary = obj.with_suffix('')
        compile_cmd = [compiler, '-std=c++20', '-O2', '-fPIE', '-fno-fast-math',
                       '-ffp-contract=off', '-DOWN_RT_HOST_ONLY', '-I' + str(P),
                       '-I' + str(P.parents[2] / 'stage1/packet3-prep/src'),
                       '-c', str(P / 'head_status_fixture.cpp'), '-o', str(obj)]
        link = list(next(r['command'] for r in commands if r['name'] == 'gnu-host-link'))
        link = [str(obj) if arg == str(P / 'build/gnu-host/entry-main.o') else arg for arg in link]
        link[link.index('-o') + 1] = str(binary)
        head_obj = P / 'build' / ('head-operator-' + name + '.o')
        head_cmd = list(compile_cmd)
        head_cmd[head_cmd.index('-c') + 1] = str(P / 'p69_head.cpp')
        head_cmd[head_cmd.index('-o') + 1] = str(head_obj)
        link = [str(head_obj) if arg == str(P / 'build/gnu-host/p69_head.o') else arg for arg in link]
        if name == 'intel':
            # Intel's host objects need its memory/math libraries. Frozen
            # production objects retain their GNU OpenMP runtime dependency.
            link = [compiler, *[arg for arg in link[1:] if arg != '-fopenmp'], '-lgomp']
        for label, cmd in [('compile', compile_cmd), ('head-compile', head_cmd), ('link', link)]:
            with (out / f'{name}-{label}.log').open('w') as log:
                subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                               stderr=subprocess.STDOUT, check=True, timeout=180)
        for repeat in (1, 2):
            result = out / f'{name}-{repeat}.bin'
            run = subprocess.run([str(binary), str(result)], stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=180)
            (out / f'{name}-{repeat}.log').write_text(run.stdout + run.stderr)
            if run.returncode:
                print(run.stdout + run.stderr, flush=True)
            run.check_returncode()
            runs.append(dict(compiler=name, repeat=repeat, sha256=sha(result),
                             bytes=result.stat().st_size, stdout=run.stdout,
                             compile=compile_cmd, head_compile=head_cmd, link=link))
            print(name, repeat, run.stdout.strip(), flush=True)
    assert len({r['sha256'] for r in runs}) == 1
    # The exact archived pre-fix operation must still fail this fixture. This
    # prevents a weakened test from silently certifying the original defect.
    legacy = P / 'evidence/reseal-r3/previous'
    legacy_obj = P / 'build/head-operator-legacy.o'
    legacy_cmd = list(runs[0]['head_compile'])
    legacy_cmd[legacy_cmd.index('-c') + 1] = str(legacy / 'p69_head.cpp')
    legacy_cmd[legacy_cmd.index('-o') + 1] = str(legacy_obj)
    legacy_link = list(runs[0]['link'])
    legacy_link = [str(legacy_obj) if arg == str(P / 'build/head-operator-gnu.o') else arg
                   for arg in legacy_link]
    legacy_binary = P / 'build/head-status-legacy'
    legacy_link[legacy_link.index('-o') + 1] = str(legacy_binary)
    for label, cmd in [('legacy-compile', legacy_cmd), ('legacy-link', legacy_link)]:
        with (out / (label + '.log')).open('w') as log:
            subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=180)
    regression = subprocess.run([str(legacy_binary), str(out / 'legacy.bin')],
                                stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
    (out / 'legacy.log').write_text(regression.stdout + regression.stderr)
    assert regression.returncode == 1
    assert 'row=1 expected=42cc actual=fff7' in regression.stderr
    assert 'production argmax sticky error=1' in regression.stderr
    sources = {str((P / n).relative_to(ROOT)): sha(P / n) for n in (
        'head_status_gate.py', 'head_status_fixture.cpp', 'p33_linked_fixture.cpp',
        'p69_head.cpp', 'p69_head.hpp', 'p56_prefix.hpp', 'round2_submit.cpp')}
    sources.update({str((legacy / n).relative_to(ROOT)): sha(legacy / n)
                    for n in ('p69_head.cpp', 'p69_head.hpp')})
    save(out / 'receipt.json', dict(passed=True, device_executed=False,
        cpu_model_executed=False, sources=sources, runs=runs,
        legacy_regression=dict(returncode=regression.returncode, stderr=regression.stderr,
            compile=legacy_cmd, link=legacy_link,
            sources={str((legacy / n).relative_to(ROOT)): sha(legacy / n)
                     for n in ('p69_head.cpp', 'p69_head.hpp')}),
        scope='Linked host head and production argmax/status; not device reproduction'))


if __name__ == '__main__':
    main()
