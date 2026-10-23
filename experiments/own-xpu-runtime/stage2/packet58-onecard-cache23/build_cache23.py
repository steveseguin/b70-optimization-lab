#!/usr/bin/env python3
"""Packet58-onecard-cache23 build: relink the parent objects unchanged, recompile only the touched TUs.

CPU only. Every compiler invocation takes the shared ops compile turn (one host compiler at a
time; waits for any other compiler on the host) and runs under a 4 GiB address-space cap, nice 19,
on the CPU-only core set. Before each compile batch the user units are polled: nothing but the
owner's qwen38-* endpoints may be active.

  1. restore_build.py: 78 pinned objects (77 packet58aj kernel/host objects, packet182's
     single_device.o) copied by digest into build/.
  2. native/generated -> build/native (the sealed entry source snapshot).
  3. gnu-host: entry-main (g++) + own-rt-iq3 link        -> the real-parser CPU gate binary
  4. device:   entry-main (icpx -fsycl) + own-rt-iq3 link -> the device engine
  5. preparation probe: probe-main.cpp (main.cpp with the two device-define CPU substitutions of
     preparation_gate.py) compiled with native/preparation_probe.cpp and linked without the backend
     and the real entry (packet176's recipe)
  6. wait tests (gnu + intel), K1 exec wrapper (g++; execs this packet's restored core)
  Not built: intel-host own-rt-iq3 (no gate here reads it; packet182 carried it by identity).
Writes evidence/build.json: commands, wall seconds, artifact digests, 0-warning check, unit polls.
"""
import json, os, re, resource, shutil, subprocess, sys, time
from pathlib import Path
from build_engine import P, ROOT, B, compiler_turn, sha, save, limits

OLD = str(P.parent / 'packet58ag-onecard-ports')
ORIGINAL = json.loads((P / 'lineage/58ag-build-commands.json').read_text())
WORK = B / 'preparation'


def units():
    cp = subprocess.run(['systemctl', '--user', 'list-units', 'window-*', 'lanequeue-*', 'packet19*', '--state=active,activating,deactivating', '--no-legend', '--plain'],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True)
    rows = [l.split()[0] for l in cp.stdout.splitlines() if l.strip()]
    others = [u for u in rows if not u.startswith('qwen38-')]
    assert not others, 'device/queue units active: ' + str(others)
    return dict(active=rows, checked_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


def command(name):
    return [s.replace(OLD, str(P)) for s in next(r['command'] for r in ORIGINAL if r['name'] == name)]


def run(cmd, name, log_dir=B):
    limits()
    t0 = time.monotonic()
    with compiler_turn(), (log_dir / (name + '.log')).open('w') as log:
        subprocess.run(list(map(str, cmd)), stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
    text = (log_dir / (name + '.log')).read_text()
    warnings = len(re.findall(r'warning:', text))
    print(name, 'PASS', f'{time.monotonic() - t0:.1f}s', 'warnings', warnings, flush=True)
    return dict(name=name, command=list(map(str, cmd)), seconds=round(time.monotonic() - t0, 1), log=str((log_dir / (name + '.log')).relative_to(P)), warnings=warnings)


def main():
    limits()
    free0 = shutil.disk_usage('/').free
    polls = [units()]
    cp = subprocess.run([sys.executable, '-B', str(P / 'restore_build.py')], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr[-2000:]
    restored = json.loads((P / 'restore-inputs.json').read_text())['records']
    for row in restored:
        assert sha(P / row['destination']) == row['digest'], row['destination']
    shutil.copytree(P / 'native/generated', B / 'native', dirs_exist_ok=True)
    rows = []
    # gnu-host
    (B / 'gnu-host').mkdir(parents=True, exist_ok=True)
    rows.append(run(command('gnu-host-entry-main'), 'gnu-host-entry-main'))
    rows.append(run(command('gnu-host-own-rt-iq3'), 'gnu-host-own-rt-iq3'))
    polls.append(units())
    # device: entry-main recompiled; single_device.o restored (backend TU untouched)
    (B / 'device').mkdir(parents=True, exist_ok=True)
    rows.append(run(command('device-entry-main'), 'device-entry-main'))
    link = command('device-own-rt-iq3')
    assert str(B / 'device/single_device.o') in link and str(B / 'device/entry-main.o') in link
    rows.append(run(link, 'device-own-rt-iq3'))
    polls.append(units())
    # preparation probe (packet176 recipe; see preparation_gate.py)
    WORK.mkdir(exist_ok=True)
    text = (P / 'native/generated/main.cpp').read_text()
    for old, new in (('static constexpr bool allocation_probe=false, legacy_pointer_probe=false;', 'bool allocation_probe=false, legacy_pointer_probe=false;'),
                     ('getpriority(PRIO_PROCESS, 0) == a.native_nice', 'getpriority(PRIO_PROCESS, 0) == 19 /* CPU probe: observed priority only */')):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    (WORK / 'probe-main.cpp').write_text(text)
    probe_compile = command('device-entry-main')
    probe_compile[-1] = str(P / 'native/preparation_probe.cpp')
    probe_compile.insert(1, '-I' + str(WORK))
    probe_compile[probe_compile.index('-o') + 1] = str(WORK / 'probe.o')
    probe_compile[probe_compile.index('-MF') + 1] = str(WORK / 'probe.d')
    rows.append(run(probe_compile, 'device-entry-main', WORK))
    probe_link = [s for s in link if not s.endswith('/single_device.o') and not s.endswith('/own-rt-iq3-entry.cpp.o')]
    probe_link = [str(WORK / 'probe.o') if s == str(B / 'device/entry-main.o') else s for s in probe_link]
    probe_link[probe_link.index('-o') + 1] = str(WORK / 'prepare-probe')
    rows.append(run(probe_link, 'device-own-rt-iq3', WORK))
    polls.append(units())
    # wait tests and the K1 wrapper
    for compiler, tag in [('/usr/bin/g++', 'gnu'), ('/opt/intel/oneapi/compiler/2026.0/bin/icpx', 'intel')]:
        rows.append(run([compiler, '-std=c++20', '-O2', P / 'native/wait_test.cpp', '-o', B / (tag + '-wait-test')], tag + '-wait-build'))
        rows.append(run([B / (tag + '-wait-test')], tag + '-wait-test'))
    src = P / 'native/k1_help.cpp'
    core = P / 'build/device/p58-cache-fixtures-core'
    assert src.read_text().count(str(core)) == 1 and 'packet182' not in src.read_text() and 'packet176' not in src.read_text()
    rows.append(run(['/usr/bin/g++', '-O2', src, '-o', B / 'device/p58-cache-fixtures'], 'k1-help'))
    wrapper = (B / 'device/p58-cache-fixtures').read_bytes()
    assert wrapper.count(str(core).encode()) == 1 and b'packet182' not in wrapper and b'packet176' not in wrapper
    helped = subprocess.run([str(B / 'device/p58-cache-fixtures'), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=dict(PATH='/usr/bin:/bin'))
    assert helped.returncode == 0 and '--output' in helped.stdout.split()
    helped2 = subprocess.run([str(B / 'device/own-rt-iq3'), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=dict(PATH='/usr/bin:/bin'))
    assert helped2.returncode == 0 and '--cache-cap 18GB|max|max23 (default:max)' in helped2.stdout and '--foreground-io copy|kernel' in helped2.stdout
    assert sum(r['warnings'] for r in rows) == 0, 'compiler warnings'
    size = sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
    artifacts = {str(f.relative_to(P)): sha(f) for f in (B / 'device/own-rt-iq3', B / 'gnu-host/own-rt-iq3', B / 'device/p58-cache-fixtures', B / 'device/p58-cache-fixtures-core', WORK / 'prepare-probe')}
    row = dict(schema='packet58cache23.build.v1', passed=True, device_executed=False, commands=rows, artifacts=artifacts,
               restored_objects=len(restored), restored_from=sorted({Path(r['original']).parts[-5] if 'frozen-inputs' in r['original'] else Path(r['original']).parents[1].name for r in restored}),
               recompiled_translation_units=['build/native/entry-main.cpp (gnu-host, device)', 'native/preparation_probe.cpp (+ probe-main.cpp)', 'native/wait_test.cpp (gnu, intel)', 'native/k1_help.cpp'],
               relinked_unchanged=['36 frozen packet58j device kernel objects', '28 frozen gnu-host objects', 'owner/owner_retire/p60_submit/p58ag_submit (device + gnu-host)', 'single_device.o (packet182 bytes)'],
               not_built=['intel-host own-rt-iq3 (no gate reads it; packet182 carried the parent binary by identity)'],
               warnings=0, compile_turns=len([r for r in rows if r['name'] not in ('gnu-wait-test', 'intel-wait-test')]), unit_polls=polls,
               engine_help=helped2.stdout.strip(), k1_wrapper_help=helped.stdout.strip(),
               peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024, build_tree_bytes=size,
               root_free_before=free0, root_free_after=shutil.disk_usage('/').free, native_source_sha256=sha(P / 'native/generated/main.cpp'))
    assert size < 3_000_000_000
    save(P / 'evidence/build.json', row)
    print(json.dumps(dict(passed=True, engine=artifacts['build/device/own-rt-iq3'], build_tree_bytes=size, seconds=sum(r['seconds'] for r in rows))))


if __name__ == '__main__':
    main()
