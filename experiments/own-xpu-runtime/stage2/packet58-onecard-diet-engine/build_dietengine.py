#!/usr/bin/env python3
"""Packet58-onecard-diet-engine build: relink the parent objects unchanged, recompile only the TUs the diet touches.

CPU only. Every compiler invocation takes the shared ops compile turn (one host compiler at a time) and runs under a
4 GiB address-space cap, nice 19, on the CPU-only core set. Before each compile batch the user units are polled
(nothing but the owner's qwen38-* endpoints and an endpoint-restore window `window-*-driver` may be active) and the
host compiler count is read from `ps -eo comm` (exact names, never pgrep -f): it must be 0.

  1. restore_build.py: 77 pinned objects (75 packet58aj kernel/host objects, packet182's single_device.o, the K1 core)
     copied by digest into build/ (the two p58ag_submit.o objects are NOT restored: replaced-objects.json).
  2. native/generated -> build/native (the sealed entry source snapshot, incl. the pinned diet header).
  3. p58ag_submit (gnu-host g++, device icpx -fsycl): the record gate/up TU (host dispatch change only) and the NEW diet TU
     p58ag_diet_submit (issue_diet<> + p58ag_diet::GateUp), both with packet58ag's recorded flags.
  4. gnu-host: entry-main (g++) + own-rt-iq3 link        -> the real-parser CPU gate binary
  5. device:   entry-main (icpx -fsycl) + own-rt-iq3 link -> the device engine
  6. preparation probe (packet176 recipe), wait tests (gnu + intel), K1 exec wrapper (g++; execs this packet's restored core)
  Not built: intel-host own-rt-iq3 (no gate reads it).
Writes evidence/build.json: commands, wall seconds, artifact digests, 0-warning check, unit/compiler polls.
"""
import json, os, re, resource, shutil, subprocess, sys, time
from pathlib import Path
from build_engine import P, ROOT, B, compiler_turn, sha, save, limits

OLD = str(P.parent / 'packet58ag-onecard-ports')
ORIGINAL = json.loads((P / 'lineage/58ag-build-commands.json').read_text())
WORK = B / 'preparation'
DIET_HEADER_SHA = '35005ee3b3f3561902b727f9658ea0b08513e58a3a5651aff540fd1fabd66089'


def units():
    cp = subprocess.run(['systemctl', '--user', 'list-units', 'window-*', 'lanequeue-*', 'packet*', '--state=active,activating,deactivating', '--no-legend', '--plain'],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True)
    rows = [l.split()[0] for l in cp.stdout.splitlines() if l.strip()]
    tolerated = [u for u in rows if re.fullmatch(r'window-.*-driver\.service', u)]  # the owner's endpoint-restore window
    others = [u for u in rows if not u.startswith('qwen38-') and u not in tolerated]
    assert not others, 'device/queue units active: ' + str(others)
    ps = subprocess.run(['ps', '-eo', 'comm'], stdin=subprocess.DEVNULL, capture_output=True, text=True).stdout.split()
    compilers = sum(1 for c in ps if c in ('icpx', 'clang++', 'icx', 'ocloc'))
    assert compilers == 0, f'{compilers} host compiler process(es) active'
    return dict(active=rows, tolerated_restore_windows=tolerated, host_compilers_by_comm=compilers, checked_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


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
    assert sha(P / 'native/generated/p58ag_diet.hpp') == sha(P / 'native/p58ag_diet.hpp') == DIET_HEADER_SHA, 'pinned diet header changed'
    polls = [units()]
    cp = subprocess.run([sys.executable, '-B', str(P / 'restore_build.py')], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr[-2000:]
    restored = json.loads((P / 'restore-inputs.json').read_text())['records']
    assert len(restored) == 77 and not any(r['destination'].endswith('p58ag_submit.o') for r in restored)
    for row in restored:
        assert sha(P / row['destination']) == row['digest'], row['destination']
    replaced = json.loads((P / 'replaced-objects.json').read_text())['records']
    for row in replaced:
        assert sha(row['original']) == row['digest'], 'pinned parent object changed: ' + row['original']
        if (P / row['destination']).exists():
            (P / row['destination']).unlink()
    shutil.copytree(P / 'native/generated', B / 'native', dirs_exist_ok=True)
    rows = []
    # the one TU the diet kernel touches: p58ag_submit (gnu-host + device), packet58ag's recorded flags
    (B / 'gnu-host').mkdir(parents=True, exist_ok=True); (B / 'device').mkdir(parents=True, exist_ok=True)
    rows.append(run(command('gnu-host-p58ag_submit'), 'gnu-host-p58ag_submit'))
    rows.append(run(command('device-p58ag_submit'), 'device-p58ag_submit'))
    # the diet dispatch TU (its own object, so the record TU's device code is exactly the parent's kernel set)
    for mode in ('gnu-host', 'device'):
        c = command(mode + '-p58ag_submit')
        c[c.index('-o') + 1] = str(B / mode / 'p58ag_diet_submit.o'); c[c.index('-MF') + 1] = str(B / mode / 'p58ag_diet_submit.d')
        assert c[-1].endswith('/build/native/p58ag_submit.cpp'); c[-1] = str(B / 'native/p58ag_diet_submit.cpp')
        rows.append(run(c, mode + '-p58ag_diet_submit'))
    polls.append(units())
    # gnu-host
    rows.append(run(command('gnu-host-entry-main'), 'gnu-host-entry-main'))
    link = command('gnu-host-own-rt-iq3'); assert str(B / 'gnu-host/p58ag_submit.o') in link
    link.insert(link.index(str(B / 'gnu-host/p58ag_submit.o')) + 1, str(B / 'gnu-host/p58ag_diet_submit.o'))
    rows.append(run(link, 'gnu-host-own-rt-iq3'))
    polls.append(units())
    # device: entry-main recompiled; single_device.o restored (backend TU untouched)
    rows.append(run(command('device-entry-main'), 'device-entry-main'))
    link = command('device-own-rt-iq3')
    assert str(B / 'device/single_device.o') in link and str(B / 'device/entry-main.o') in link and str(B / 'device/p58ag_submit.o') in link
    link.insert(link.index(str(B / 'device/p58ag_submit.o')) + 1, str(B / 'device/p58ag_diet_submit.o'))
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
    assert src.read_text().count(str(core)) == 1 and not any(x in src.read_text() for x in ('packet182', 'packet176', 'cache23'))
    rows.append(run(['/usr/bin/g++', '-O2', src, '-o', B / 'device/p58-cache-fixtures'], 'k1-help'))
    wrapper = (B / 'device/p58-cache-fixtures').read_bytes()
    assert wrapper.count(str(core).encode()) == 1 and not any(x in wrapper for x in (b'packet182', b'packet176', b'cache23'))
    helped = subprocess.run([str(B / 'device/p58-cache-fixtures'), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=dict(PATH='/usr/bin:/bin'))
    assert helped.returncode == 0 and '--output' in helped.stdout.split()
    helped2 = subprocess.run([str(B / 'device/own-rt-iq3'), '--help'], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, env=dict(PATH='/usr/bin:/bin'))
    assert helped2.returncode == 0 and '--cache-cap 18GB|max|max23 (default:max)' in helped2.stdout and '--expert-gateup production|diet (default:production)' in helped2.stdout and '--foreground-io copy|kernel' in helped2.stdout
    assert sum(r['warnings'] for r in rows) == 0, 'compiler warnings'
    size = sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
    artifacts = {str(f.relative_to(P)): sha(f) for f in (B / 'device/own-rt-iq3', B / 'gnu-host/own-rt-iq3', B / 'device/p58-cache-fixtures', B / 'device/p58-cache-fixtures-core', WORK / 'prepare-probe',
                                                       B / 'device/p58ag_submit.o', B / 'gnu-host/p58ag_submit.o', B / 'device/p58ag_diet_submit.o', B / 'gnu-host/p58ag_diet_submit.o')}
    row = dict(schema='packet58dietengine.build.v1', passed=True, device_executed=False, commands=rows, artifacts=artifacts,
               restored_objects=len(restored), replaced_objects=replaced,
               restored_from=sorted({Path(r['original']).parts[-5] if 'frozen-inputs' in r['original'] else Path(r['original']).parents[1].name for r in restored}),
               recompiled_translation_units=['build/native/p58ag_submit.cpp (gnu-host, device): the record gate/up TU, host dispatch gains the expert_gateup argument (packet58ag recorded flags)',
                                             'build/native/p58ag_diet_submit.cpp (gnu-host, device): NEW TU, the diet dispatch issue_diet<> + p58ag_diet::GateUp (same recorded flags)',
                                             'build/native/entry-main.cpp (gnu-host, device): the expert_gateup key', 'native/preparation_probe.cpp (+ probe-main.cpp)', 'native/wait_test.cpp (gnu, intel)', 'native/k1_help.cpp'],
               relinked_unchanged=['36 frozen packet58j device kernel objects', '28 frozen gnu-host objects', 'owner/owner_retire/p60_submit (device + gnu-host)', 'single_device.o (packet182 bytes)', 'K1 fixture core (packet182 bytes)'],
               not_built=['intel-host own-rt-iq3 (no gate reads it)'],
               diet_header=dict(path='native/generated/p58ag_diet.hpp', sha256=DIET_HEADER_SHA, pinned_from='packet58-onecard-diet-micro/p58ag_diet.hpp (byte for byte, never re-derived)'),
               warnings=0, compile_turns=len([r for r in rows if r['name'] not in ('gnu-wait-test', 'intel-wait-test')]), unit_polls=polls,
               engine_help=helped2.stdout.strip(), k1_wrapper_help=helped.stdout.strip(),
               peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024, build_tree_bytes=size,
               root_free_before=free0, root_free_after=shutil.disk_usage('/').free, native_source_sha256=sha(P / 'native/generated/main.cpp'),
               p58ag_submit_source_sha256=sha(P / 'native/generated/p58ag_submit.cpp'), p58ag_diet_submit_source_sha256=sha(P / 'native/generated/p58ag_diet_submit.cpp'))
    assert size < 2_000_000_000
    save(P / 'evidence/build.json', row)
    print(json.dumps(dict(passed=True, engine=artifacts['build/device/own-rt-iq3'], build_tree_bytes=size, seconds=sum(r['seconds'] for r in rows))))


if __name__ == '__main__':
    main()
