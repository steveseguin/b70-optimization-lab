#!/usr/bin/env python3
"""AOT build of lab build r1 40388fc92c43 for the Arc Pro B70 (research/aot-tp-2026-10-31). CPU only; never runs the engine.

The only treatment is the engine's own `build.py --aot-target intel_gpu_bmg_g31`, which adds -fsycl-targets=intel_gpu_bmg_g31
to every compile command (after the unit flags) and to the link command (after -fsycl -Wl,--gc-sections). Every other
argument is the r1 build receipt's (research/tp/hc-split-2026-10-30/results/build-r1-build-receipt.json): -O2, precise FP
(-fno-fast-math -ffp-contract=off -fdenormal-fp-math=ieee -foffload-fp32-prec-div -foffload-fp32-prec-sqrt on every
compile), the link line exactly as r1 recorded it (-fsycl -Wl,--gc-sections ... -lcrypto -lze_loader and the pinned
2026.0 rpath), the pinned compiler /opt/intel/oneapi/compiler/2026.0/bin/icpx. The manifest supplies no -fsycl-targets.

Steps (each refuses on failure):
 1. preconditions: no fresh-server timing unit of any agent active (sc117-tp-svc-*), MemAvailable >= 64 GB, /dev/shm free.
 2. copy the private r1 tree /dev/shm/hcsplit-2026-10-30/tree (read only) to TREE; the copy must reproduce all 269 compiled
    sources of the r1 build receipt, its runtime asset (rope-65536.bf16), build.py and build-manifest.json byte for byte.
 3. build with the copy's engine/build.py at nice 19 on CPUs 8-15 with --jobs 4 (wall time and peak RSS by /usr/bin/time).
 4. check: every compile/link argv equals r1's after the tree/build-dir path substitution and removing the one target flag;
    the compiled-source set and hashes equal r1's; the binary's offload images are spir64_gen only (no SPIR-V fallback);
    readelf NEEDED/RUNPATH equal r1's binary.
 5. write results/build-aot-<label>.json (times, binary size, sha256, identities).
Usage: build_aot.py LABEL   (TREE=/dev/shm/aot-tp-2026-10-31/tree, OUT=/dev/shm/aot-tp-2026-10-31/build-<LABEL>)"""
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

D = Path(__file__).resolve().parent
R1 = Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/tp/hc-split-2026-10-30/results/build-r1-build-receipt.json')
R1_TREE = Path('/dev/shm/hcsplit-2026-10-30/tree'); R1_OUT = Path('/dev/shm/hcsplit-2026-10-30/build-r1')
BASE = Path('/dev/shm/aot-tp-2026-10-31'); TREE = BASE / 'tree'
ENG_REL = Path('experiments/own-xpu-runtime/engine')
TARGET = 'intel_gpu_bmg_g31'; TFLAG = '-fsycl-targets=' + TARGET
CPUS = '8-15'; JOBS = 4


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def need(ok, msg):
    if not ok:
        sys.exit('REFUSED: ' + msg)


def readelf_dyn(p):
    out = subprocess.run(['readelf', '-d', str(p)], capture_output=True, text=True).stdout
    return sorted(l.split(None, 1)[1].strip() for l in out.splitlines() if '(NEEDED)' in l or '(RUNPATH)' in l or '(RPATH)' in l)


def offload_targets(p):
    s = subprocess.run(['strings', '-n', '5', str(p)], capture_output=True, text=True).stdout.split('\n')
    return dict(bundles=sorted(set(x for x in s if x.startswith('__CLANG_OFFLOAD_BUNDLE__'))),
                spir64=sum(1 for x in s if x == 'spir64'), spir64_gen=sum(1 for x in s if x == 'spir64_gen'))


def main():
    label = sys.argv[1]
    out = BASE / f'build-{label}'
    rec = dict(schema='aot-tp-2026-10-31.build.v1', label=label, base_receipt=str(R1), base_receipt_sha256=sha(R1),
               tree=str(TREE), out=str(out), target=TARGET, cpus=CPUS, jobs=JOBS, nice=19)
    r1 = json.loads(R1.read_text())
    # 1. preconditions
    units = subprocess.run(['systemctl', '--user', 'list-units', '--state=active', '--no-legend', '--plain'], capture_output=True, text=True).stdout
    timing = [l.split()[0] for l in units.splitlines() if 'sc117-tp-svc' in l]
    need(not timing, f'fresh-server timing units active: {timing}')
    avail = int(re.search(r'MemAvailable:\s+(\d+)', open('/proc/meminfo').read()).group(1)) * 1024
    need(avail >= 64e9, f'MemAvailable {avail}')
    need(shutil.disk_usage('/dev/shm').free >= 8e9, '/dev/shm free below 8 GB')
    need(not out.exists(), f'{out} exists (fresh outputs only)')
    rec['preconditions'] = dict(mem_available=avail, shm_free=shutil.disk_usage('/dev/shm').free, root_free=shutil.disk_usage('/').free)
    # 2. tree copy
    if not TREE.exists():
        BASE.mkdir(exist_ok=True)
        subprocess.run(['cp', '-a', str(R1_TREE), str(TREE)], check=True)
        rec['tree_copied'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    src = TREE / ENG_REL / 'src'
    bad = [k for k, v in r1['sources'].items() if not (src / k).exists() or sha(src / k) != v]
    need(not bad, f'tree copy differs from r1 in {len(bad)} compiled sources: {bad[:5]}')
    for a, h in r1['runtime_assets'].items():
        need(sha(str(a).replace(str(R1_TREE), str(TREE))) == h, 'runtime asset ' + a)
    need(sha(TREE / ENG_REL / 'build.py') == r1['build_script_sha256'], 'build.py differs from r1')
    need(sha(TREE / ENG_REL / 'build-manifest.json') == r1['build_manifest_sha256'], 'build-manifest.json differs from r1')
    rec['tree_check'] = dict(compiled_sources=len(r1['sources']), equal=True, runtime_assets=len(r1['runtime_assets']),
                             build_script_sha256=r1['build_script_sha256'], build_manifest_sha256=r1['build_manifest_sha256'])
    rec['identities'] = {p: sha(p) for p in ('/opt/intel/oneapi/compiler/2026.0/bin/icpx', '/usr/bin/ocloc',
                         '/usr/lib/x86_64-linux-gnu/libocloc.so', os.path.realpath('/usr/local/lib/libigc.so.2'),
                         os.path.realpath('/lib/x86_64-linux-gnu/libze_intel_gpu.so.1'))}
    rec['versions'] = dict(icpx=subprocess.run(['/opt/intel/oneapi/compiler/2026.0/bin/icpx', '--version'], capture_output=True, text=True).stdout.splitlines()[0],
                           ocloc=subprocess.run(['ocloc', '--version'], capture_output=True, text=True).stdout.strip())
    # 3. build (clean environment: PATH, HOME only, as icpx is called by absolute path and finds ocloc in /usr/bin)
    env = dict(PATH='/usr/bin:/bin', HOME=os.environ['HOME'], LANG='C.UTF-8')
    cmd = ['/usr/bin/time', '-v', 'taskset', '-c', CPUS, 'nice', '-n', '19', 'python3', '-B', str(TREE / ENG_REL / 'build.py'),
           str(out), '--jobs', str(JOBS), '--name', 'sc117-engine', '--aot-target', TARGET]
    rec['command'] = cmd; rec['status'] = 'building'; rec['started'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (D / 'results' / f'build-aot-{label}.json').write_text(json.dumps(rec, indent=1) + '\n')
    t0 = time.monotonic()
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    rec['wall_s'] = round(time.monotonic() - t0, 1)
    (D / 'logs' / f'build-aot-{label}.stdout').write_text(p.stdout); (D / 'logs' / f'build-aot-{label}.stderr').write_text(p.stderr)
    m = re.search(r'Maximum resident set size \(kbytes\): (\d+)', p.stderr)
    rec['max_rss_kb_single_process'] = int(m.group(1)) if m else None
    rec['rc'] = p.returncode
    if p.returncode:
        rec['status'] = 'failed'; (D / 'results' / f'build-aot-{label}.json').write_text(json.dumps(rec, indent=1) + '\n')
        sys.exit(f'build failed rc={p.returncode}')
    # 4. checks
    b = json.loads((out / 'build-receipt.json').read_text())
    sub = lambda a: a.replace(str(TREE), str(R1_TREE)).replace(str(out), str(R1_OUT))
    argv_diff = []
    for name, c in b['commands'].items():
        got = [sub(x) for x in c['cmd'] if x != TFLAG]
        need(c['cmd'].count(TFLAG) == 1, f'{name}: target flag count')
        if got != r1['commands'][name]['cmd']:
            argv_diff.append(name)
    need(not argv_diff and set(b['commands']) == set(r1['commands']), f'argv differs from r1 beyond the target flag: {argv_diff}')
    need(b['sources'] == r1['sources'], 'compiled-source hashes differ from r1')
    need({sub(k): v for k, v in b['runtime_assets'].items()} == r1['runtime_assets'], 'runtime asset path/hash differs from r1')
    binary = Path(b['binary'])
    rec['binary'] = str(binary); rec['binary_sha256'] = b['binary_sha256']; rec['binary_bytes'] = binary.stat().st_size
    rec['jit_binary_bytes'] = (R1_OUT / 'sc117-engine').stat().st_size
    rec['readelf'] = readelf_dyn(binary); rec['readelf_jit'] = readelf_dyn(R1_OUT / 'sc117-engine')
    need(rec['readelf'] == rec['readelf_jit'], 'NEEDED/RUNPATH differ from r1')
    rec['offload'] = offload_targets(binary); rec['offload_jit'] = offload_targets(R1_OUT / 'sc117-engine')
    need(rec['offload']['spir64'] == 0 and rec['offload']['spir64_gen'] >= 1, 'binary still carries a spir64 (JIT) image')
    rec['argv_equal_to_r1_except_target'] = True; rec['compiled_sources_equal_to_r1'] = len(b['sources'])
    rec['objects_equal_to_r1'] = sum(1 for k, v in b['objects'].items() if r1['objects'].get(k) == v)
    rec['seconds'] = {k: v.get('seconds') for k, v in b['commands'].items()}
    last_obj = max((out / k).stat().st_mtime for k in b['objects'])
    rec['link_s_from_mtimes'] = round(binary.stat().st_mtime - last_obj, 1)  # build.py records no link seconds
    rec['compile_seconds_sum'] = round(sum(v.get('seconds') or 0 for k, v in b['commands'].items() if k != 'link'), 1)
    rec['status'] = 'passed'; rec['finished'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    (D / 'results' / f'build-aot-{label}.json').write_text(json.dumps(rec, indent=1) + '\n')
    shutil.copy(out / 'build-receipt.json', D / 'results' / f'build-aot-{label}-build-receipt.json')
    print(json.dumps({k: rec[k] for k in ('status', 'binary_sha256', 'binary_bytes', 'jit_binary_bytes', 'wall_s', 'compile_seconds_sum')}))


if __name__ == '__main__':
    main()
