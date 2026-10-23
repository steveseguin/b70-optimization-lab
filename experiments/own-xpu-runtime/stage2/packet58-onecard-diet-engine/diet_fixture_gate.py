#!/usr/bin/env python3
"""Packet58-onecard-diet-engine engine-dispatch exactness gate (CPU only): native/diet_fixture.cpp linked against the packet's
own gnu-host objects (the real p58ag::expert dispatch of the rebuilt p58ag_submit / p58ag_diet_submit TUs), on GNU and Intel
host twins, with packet162b's real layer-0/layer-24 rows (read in place, digest-recorded), a 512-expert synthetic bank with
permuted slot tables and the non-finite-half bank. See the fixture header. Writes evidence/diet-fixture.json."""
import json, os, resource, shutil, subprocess, sys, time
from pathlib import Path
from build_engine import P, ROOT, B, compiler_turn, sha, save, limits
OUT = B / 'diet-fixture'; INTEL = '/opt/intel/oneapi/compiler/2026.0/bin/icpx'
REAL = P.parent / 'packet162-iq2-lookup/build/micro-inputs'
REAL_SHA = {'layer0.bin': 'eeed9d3bab0c8652c344d363174032c1f197944e7314cdf73fe974493ebc6628', 'layer24.bin': '77bdd24006f6f5425b32e78ddfc50e34faa670b5b655070c4c59ed25aa35f52b'}
MODES = (('GNU', '/usr/bin/g++'), ('Intel', INTEL))
OLD = str(P.parent / 'packet58ag-onecard-ports')
ORIGINAL = json.loads((P / 'lineage/58ag-build-commands.json').read_text())
EXPECTED_STRATA = 8 + 8 + 10 + 8   # real-layer0, real-layer24, synthetic (incl. 2 slot permutations), exceptional-halves


def command(name):
    return [s.replace(OLD, str(P)) for s in next(r['command'] for r in ORIGINAL if r['name'] == name)]


def run(cmd, name):
    limits()
    with compiler_turn(), (OUT / (name + '.log')).open('w') as log:
        subprocess.run(list(map(str, cmd)), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
    assert 'warning:' not in (OUT / (name + '.log')).read_text(), name


def main():
    limits(); OUT.mkdir(parents=True, exist_ok=True)
    for leaf, digest in REAL_SHA.items():
        assert sha(REAL / leaf) == digest, 'packet162b real rows changed: ' + leaf
    build = json.loads((P / 'evidence/build.json').read_text())
    for obj in ('build/gnu-host/p58ag_submit.o', 'build/gnu-host/p58ag_diet_submit.o'):
        assert sha(P / obj) == build['artifacts'][obj], 'gnu-host object differs from the build receipt: ' + obj
    compile_args = command('gnu-host-p58ag_submit'); i = compile_args.index('-c'); del compile_args[i:i + 2]
    compile_args = compile_args[1:compile_args.index('-o')]; compile_args = [a for a in compile_args if a not in ('-MMD',)]
    i = compile_args.index('-MF') if '-MF' in compile_args else None
    if i is not None:
        del compile_args[i:i + 2]
    rows = []
    for compiler, cxx in MODES:
        spell = (lambda xs: ['-fiopenmp' if x == '-fopenmp' else x for x in xs]) if compiler == 'Intel' else (lambda xs: xs)
        obj = OUT / (compiler + '.o'); binary = OUT / ('fixture-' + compiler)
        run([cxx, *spell(compile_args), '-c', P / 'native/diet_fixture.cpp', '-o', obj], 'compile-' + compiler)
        link = command('gnu-host-own-rt-iq3')
        link = [str(obj) if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
        link.insert(link.index(str(B / 'gnu-host/p58ag_submit.o')) + 1, str(B / 'gnu-host/p58ag_diet_submit.o'))
        link = spell(link); link[0] = cxx; link[link.index('-o') + 1] = str(binary)
        if compiler == 'Intel':
            link += ['-no-pie', '-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
        run(link, 'link-' + compiler)
        dest = OUT / ('run-' + compiler)
        if dest.exists():
            shutil.rmtree(dest)
        env = dict(PATH='/usr/bin:/bin', OMP_NUM_THREADS='4', LD_LIBRARY_PATH='/opt/intel/oneapi/compiler/2026.0/lib')
        log = P / 'evidence' / f'diet-fixture-{compiler}.log'; t = time.monotonic()
        with log.open('w') as stream:
            r = subprocess.run([str(binary), '--output', str(dest), '--real-rows', str(REAL)], env=env, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=1800,
                               preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
        assert r.returncode == 0, log.read_text()[-3000:]
        result = json.loads((dest / 'result.json').read_text()); cases = [json.loads(l) for l in (dest / 'cases.jsonl').read_text().splitlines() if l.strip()]
        assert result['passed'] and result['strata'] == len(cases) == EXPECTED_STRATA and result['refusals'] == 3 and all(c['record_equals_production'] and c['other_bytes'] == 0 for c in cases), result
        assert all(c['bytes_equal'] for c in cases if not c['nan_stratum']), 'non-NaN stratum differs'
        assert all(c['payload_order_only'] for c in cases if not c['bytes_equal']), 'a NaN stratum differs beyond payload order'
        assert any(c['error_word'] != 0 for c in cases if c['scenario'] == 'invalid-expert'), 'invalid-expert stratum did not raise the error word'
        payload = [dict(bank=c['bank'], scenario=c['scenario'], different_words=c['different_words'], nan_vs_nan_words=c['nan_vs_nan_words']) for c in cases if not c['bytes_equal']]
        rows.append(dict(compiler=compiler, binary_sha256=sha(binary), seconds=round(time.monotonic() - t, 1), result=result, cases=cases, payload_order_rows=payload, cases_sha256=sha(dest / 'cases.jsonl')))
        print('diet fixture', compiler, 'PASS', result['strata'], 'strata', result['byte_equal_strata'], 'byte-equal', result['payload_order_only_strata'], 'payload-order-only', flush=True)
    g = {(c['bank'], c['scenario']): c for c in rows[0]['cases']}; i = {(c['bank'], c['scenario']): c for c in rows[1]['cases']}
    assert set(g) == set(i) and all(g[k]['y_sha256'] == i[k]['y_sha256'] and g[k]['py_sha256'] == i[k]['py_sha256'] for k in g if not g[k]['nan_stratum']), 'GNU and Intel diet outputs differ on a finite stratum'
    assert all(g[k]['status'] == i[k]['status'] and g[k]['error_word'] == i[k]['error_word'] for k in g), 'status/error words differ between twins'
    real = [dict(name='packet162b real gate/up rows (read in place, provenance, never a pin)', parent_relpath=str(f.relative_to(ROOT)), parent_digest=sha(f)) for f in sorted(REAL.glob('*.bin'))]
    save(P / 'evidence/diet-fixture.json', dict(passed=True, device_executed=False, model_read=False, parents=real,
         scope='engine-dispatch exactness of expert_gateup=diet (p58ag_diet::GateUp via p58ag::expert_diet) vs production (the record kernel p58ag_exp::Kernel<IQ2_S,2560,64,false,true,0,Cached=true>) through the real p58ag::expert with cached=true (experts=wide64+halfcache), the halfcache table binding and indirect p58::Pointer slots, on GNU and Intel host twins: packet162b real layer-0/24 rows (normal, invalid expert, inactive, error-preset, partial routes, NaN/Inf/subnormal inputs), a 512-expert synthetic bank (the same plus reverse and shuffled slot tables), the non-finite-half bank (NaN stratum, compared by is-NaN per word); six-argument production == five-argument record dispatch on every stratum; refusals for a non-halfcache layout, a direct binding and an unknown value',
         strata=EXPECTED_STRATA, runs=rows, twins_agree_on_finite_strata=True,
         sources={str(f.relative_to(ROOT)): sha(f) for f in (P / 'diet_fixture_gate.py', P / 'native/diet_fixture.cpp', P / 'native/generated/p58ag_submit.cpp', P / 'native/generated/p58ag_diet_submit.cpp', P / 'native/generated/p58ag_diet.hpp', B / 'gnu-host/p58ag_submit.o', B / 'gnu-host/p58ag_diet_submit.o')}))
    limits()


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)); main()
