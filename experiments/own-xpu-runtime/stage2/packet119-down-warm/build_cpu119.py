"""Strict GNU/Intel host-only gates; resource caps apply only in __main__."""
import gzip
import hashlib
import json
import resource
import shlex
import shutil
import subprocess
from pathlib import Path
from build_engine import limits
from compile_turn import turn
from cpu119_mirror import prepare, DEST

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
VIEWS = ('p119',)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    dest = P/'build/cpu'
    evidence = P/'evidence/cpu-bytes'
    dest.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    report = dict(schema='packet119.cpu-byte-identity.v1', passed=False,
                  device_executed=False, views={}, sources={}, generated_sources={}, compilers=[], commands=[])
    receipt = P/'evidence/cpu-byte-identity.json'
    try:
        for compiler, cxx in [('GNU', '/usr/bin/g++'), ('Intel', '/opt/intel/oneapi/compiler/2026.0/bin/icpx')]:
            limits()
            binary = dest/('fixture-'+compiler)
            deps = dest/(compiler+'.d')
            includes = [P/'kernels', P.parent/'packet103-record-bundle',
                        P.parents[1]/'stage1/packet3-prep/src', P.parent/'packet2/kernels', P.parent/'packet2/loader']
            source = DEST/(P/'p119_cpu.cpp').relative_to(ROOT)
            cmd = [cxx, '-std=c++20', '-O1', '-fno-fast-math', '-ffp-contract=off',
                   '-DOWN_RT_HOST_ONLY', *['-I'+str(p) for p in includes], '-MMD', '-MF', str(deps),
                   str(source), '-o', str(binary)]
            log = P/'evidence'/('cpu-'+compiler+'-compile.log')
            report['commands'].append(cmd)
            with turn(), log.open('w') as f:
                prepare(P/'p119_cpu.cpp')
                subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=600)
            report['compilers'].append(dict(name=compiler, compiler=cxx, binary=str(binary.relative_to(ROOT)),
                                            binary_sha256=sha(binary), compile_log=str(log.relative_to(ROOT)),
                                            compile_log_sha256=sha(log)))
            for n in shlex.split(deps.read_text().replace('\\\n', ' ').split(':', 1)[1]):
                path = Path(n).resolve()
                if path.is_relative_to(DEST):
                    original = ROOT/path.relative_to(DEST)
                    report['sources'][str(original.relative_to(ROOT))] = sha(original)
                    report['generated_sources'][str(path.relative_to(ROOT))] = dict(sha256=sha(path), source=str(original.relative_to(ROOT)), source_sha256=sha(original))
                else:
                    report['sources'][str(path.relative_to(ROOT))] = sha(path)
            for name in VIEWS:
                row = report['views'].setdefault(name, dict(runs=[]))
                for repeat in (1, 2):
                    limits()
                    out = dest/name/compiler/str(repeat)
                    out.mkdir(parents=True, exist_ok=True)
                    command = [str(binary), str(out)]
                    r = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
                    log = evidence/(compiler+'-'+name+'-'+str(repeat)+'.log')
                    log.write_text(r.stdout+r.stderr)
                    r.check_returncode()
                    native = json.loads((out/'native.json').read_text())
                    digest = sha(out/'expected.bin')
                    assert digest == sha(out/'candidate.bin'), 'output bytes differ'
                    retained = evidence/(digest+'.bin.gz')
                    if not retained.exists():
                        retained.write_bytes(gzip.compress((out/'expected.bin').read_bytes(), mtime=0))
                    assert hashlib.sha256(gzip.decompress(retained.read_bytes())).hexdigest() == digest
                    cases = evidence/(compiler+'-'+name+'-'+str(repeat)+'-cases.jsonl')
                    cases.write_bytes((out/'cases.jsonl').read_bytes())
                    row['runs'].append(dict(compiler=compiler, repeat=repeat, command=command,
                        expected_sha256=digest, candidate_sha256=sha(out/'candidate.bin'),
                        raw_evidence=str(retained.relative_to(ROOT)), raw_evidence_sha256=sha(retained),
                        cases_path=str(cases.relative_to(ROOT)), cases_sha256=sha(cases),
                        log_path=str(log.relative_to(ROOT)), log_sha256=sha(log), **native))
                    # Only this invocation's exact-byte retained scratch is removed.
                    shutil.rmtree(out)
                    receipt.write_text(json.dumps(report, indent=2)+'\n')
                print(compiler, name, 'two fresh processes PASS', flush=True)
        for row in report['views'].values():
            assert len(row['runs']) == 4
            for compiler in ('GNU','Intel'):
                runs=[r for r in row['runs'] if r['compiler']==compiler]
                assert len(runs)==2 and len({r['candidate_sha256'] for r in runs})==1
            row['passed'] = True
            row['cross_compiler_note']='Each compiler matches its unchanged production bytes exactly; exceptional baseline payload choices may differ across compilers.'
        for source in (P/'build_cpu119.py', P/'compile_turn.py', P/'build_engine.py', P/'cpu119_mirror.py'):
            report['sources'][str(source.relative_to(ROOT))] = sha(source)
        report.update(passed=True, max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
        limits()
    except Exception as exc:
        report['error'] = repr(exc)
        raise
    finally:
        receipt.write_text(json.dumps(report, indent=2)+'\n')

if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3,8*1024**3))
    limits()
    main()
