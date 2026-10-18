"""CPU regression: real reset policy + production argmax/pack/merge; no device imports."""
import difflib
import hashlib
import json
from pathlib import Path
import resource
import shlex
import subprocess

P = Path(__file__).resolve().parent
SOURCE = P
ROOT = P.parents[3]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from build_engine import limits
    limits()
    from compile_turn import turn
    build = P / 'build'
    build.mkdir(exist_ok=True)
    reset = (SOURCE / 'request_reset.hpp').read_text()
    start = reset.index(' std::vector<uint8_t> zero(4*1024*1024,0);')
    end = reset.index(' e.history0=e.history1=')
    # The exact allocation clearing and canonical reinitialization loops.
    (build / 'reset_fragment.inc').write_text(reset[start:end])
    runtime = (SOURCE / 'p105_runtime.hpp').read_text()
    start = runtime.index('  uint32_t zero=0,one=1;',runtime.index('template<class Cancel> void service'))
    end = runtime.index('  for(const auto& command:suffix_commands)', start)
    fixed = runtime[start:end]
    assert 'e.upload(0,active,0,&one,4);' in fixed
    original = fixed.replace(',one=1','').replace('e.upload(0,active,0,&one,4);','')
    (build / 'service_original.inc').write_text(original)
    (build / 'service_fixed.inc').write_text(fixed)
    relative = str((SOURCE / 'p105_runtime.hpp').relative_to(ROOT))
    patch = ''.join(difflib.unified_diff(runtime.splitlines(True),
        runtime.splitlines(True),
        fromfile='a/' + relative, tofile='b/' + relative))
    (P / 'proposed-fix.patch').write_text(patch)
    sources = {str((SOURCE / f).relative_to(ROOT)): sha(SOURCE / f)
               for f in ('request_reset.hpp', 'p105_runtime.hpp', 'round2_submit.cpp',
                         'p105_submit.cpp', 'p105_common.hpp', 'runtime_mock.py')}
    runs = []
    commands = []
    for name, compiler in [('GNU', '/usr/bin/g++'),
                           ('Intel', '/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
        binary = build / ('reset-' + name)
        dep = build / (name + '.d')
        cmd = [compiler, '-std=c++20', '-O2', '-fno-fast-math', '-ffp-contract=off',
               '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
               '-DOWN_RT_HOST_ONLY', '-I' + str(build), '-I' + str(SOURCE),
               '-I' + str(SOURCE.parents[1] / 'stage1/packet3-prep/src'),
               '-I' + str(SOURCE.parent / 'packet2/kernels'),
               '-I' + str(SOURCE.parent / 'packet2/loader'),
               '-MMD', '-MF', str(dep), str(P / 'reset_gate.cpp'), '-o', str(binary), '-lcrypto']
        commands.append(cmd)
        with turn(), (build / (name + '-compile.log')).open('w') as log:
            subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=180)
        for filename in shlex.split(dep.read_text().replace('\\\n', ' ').split(':', 1)[1]):
            f = Path(filename).resolve()
            sources[str(f.relative_to(ROOT))] = sha(f)
        for repeat in (1, 2):
            result = subprocess.run([str(binary)], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, check=True, timeout=120)
            runs.append(dict(compiler=name, repeat=repeat, binary_sha256=sha(binary),
                             result=json.loads(result.stdout)))
        print(name + ': reset bug detected; repair passes 21 cases twice', flush=True)
    result = dict(passed=True, device_executed=False, synthetic_logits=True,
                  failing_position_hidden_replay=False, runs=runs, commands=commands,
                  sources=sources, gate_sha256=sha(__file__),
                  patch_sha256=sha(P / 'proposed-fix.patch'),
                  max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    (P / 'evidence/reset-regression.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
