#!/usr/bin/env python3
"""Production-shape startup at production size for max AND max23: the real WSCREEN argv through this
packet's device-define CPU preparation probe, under Landlock (no /dev/dri, no /mnt). CPU only.

The probe (build/preparation/prepare-probe, compiled by build_cache23.py from THIS packet's main.cpp
with the two CPU substitutions of preparation_gate.py) runs the real bracket: five view resets
max/max23/max/max23/max (cache_capacity() at the drained boundary each time), 60 request resets,
130 reset sensors, kernel foreground I/O in every view (60 tail stores / 60 head loads). The real
allocate() bound (29,828,911,360) and the real plan check run at production size with the
23,049,601,024-byte arena; the probe writes its peak_device_bytes census. The DRM projection is
computed from the 182c lifetime peak + the arena growth and must sit below the 30.5 GB guard.

Landlock grants: read+execute /usr, /opt/intel/oneapi, /etc, /proc, /sys and the repository's
experiments/own-xpu-runtime tree; read /dev/null, /dev/zero, /dev/urandom; read+write the fresh
output directory and a private temporary HOME/TMPDIR. Not granted: /dev/dri, /dev/accel, /mnt.

  nice -n 19 taskset -c 8-15,24-31 python3 -B preparation_cache23.py < /dev/null
"""
import ctypes, hashlib, json, os, resource, shutil, subprocess, sys, tempfile
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
SCRATCH = Path('/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def landlock(read_roots, write_roots, dev_read):
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 1:
        raise RuntimeError('Landlock unavailable')
    handled = (1 << (15 if abi >= 3 else 14 if abi >= 2 else 13)) - 1
    ruleset = ctypes.c_uint64(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise RuntimeError('cannot create ruleset')

    class Rule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('access', ctypes.c_uint64), ('parent', ctypes.c_int32)]

    def grant(path, access):
        parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
        try:
            if libc.syscall(445, fd, 1, ctypes.byref(Rule(access & handled, parent)), 0) != 0:
                raise RuntimeError('cannot grant ' + str(path))
        finally:
            os.close(parent)
    try:
        for path in read_roots:
            grant(path, 1 | 4 | 8)
        for path in dev_read:
            grant(path, 2 | 4)
        for path in write_roots:
            grant(path, handled)
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, fd, 0) != 0:
            raise RuntimeError('cannot restrict')
    finally:
        os.close(fd)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    build = json.loads((P / 'evidence/build.json').read_text())
    probe = B / 'preparation/prepare-probe'
    assert sha(probe) == build['artifacts']['build/preparation/prepare-probe'] and sha(B / 'device/own-rt-iq3') == build['artifacts']['build/device/own-rt-iq3']
    assert sha(P / 'native/generated/main.cpp') == build['native_source_sha256']
    plan = json.loads((P / 'memory-plan.json').read_text())
    sys.path.insert(0, str(P / 'screen'))
    import suite_driver as D, views as V
    from types import SimpleNamespace
    manifest = D.oracle_inputs()
    inputroot = B / 'preparation58c23/inputs'
    if inputroot.exists():
        shutil.rmtree(inputroot)
    inputroot.mkdir(parents=True)
    rows = V.write_table(inputroot / 'bracket-inputs.tsv', 'resident')
    assert [c for _, c in rows] == ['max', 'max23', 'max', 'max23', 'max']
    table = inputroot / 'suite-inputs.tsv'; table.write_text('')
    args = SimpleNamespace(view='resident', miss_mode='zerocopy', window='WSCREEN', output=inputroot, cache_maintenance='overlap')
    argv = D.native_command(args, manifest, table)[2:]
    assert Path(argv[0]).resolve() == (B / 'device/own-rt-iq3').resolve()
    assert argv[argv.index('--cache-bytes') + 1] == str(V.ALLOCATION_BYTES) and argv[argv.index('--cache-cap') + 1] == 'max'
    output = P / 'evidence/preparation-sequence'
    assert not output.exists()
    output.mkdir(parents=True)
    from launch_env import environment
    work = Path(tempfile.mkdtemp(prefix='p58c23-prep-', dir=SCRATCH if SCRATCH.is_dir() else None))
    env = environment()
    env.update(ENTRY_PREPARE_OUTPUT=str(output), HOME=str(work), TMPDIR=str(work))
    command = ['/usr/bin/ionice', '-c3', str(probe), *argv[1:]]
    read_roots = [Path('/usr'), Path('/opt/intel/oneapi'), Path('/etc'), Path('/proc'), Path('/sys'), ROOT / 'experiments/own-xpu-runtime']
    dev_read = [Path('/dev/null'), Path('/dev/zero'), Path('/dev/urandom')]
    write_roots = [output, work, inputroot]
    try:
        cp = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env,
                            preexec_fn=lambda: landlock(read_roots, write_roots, dev_read))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    (P / 'evidence/preparation-sequence.log').write_text(cp.stdout + cp.stderr)
    assert cp.returncode == 0, cp.stderr[-2500:]
    row = json.loads((output / 'preparation.json').read_text())
    sensors = list(output.glob('*/*/host-memory.jsonl'))
    assert len(sensors) == 60
    for f in sensors:
        values = [json.loads(x) for x in f.read_text().splitlines()]
        assert [v['phase'] for v in values] == ['before_reset', 'after_reset'] and all(v['MemAvailable'] > 0 for v in values)
    views = sorted(output.glob('*/host-memory.jsonl'))
    assert [v.parent.name for v in views] == ['A0', 'A1', 'A2', 'B0', 'B1']
    for f in views:
        assert [json.loads(x)['phase'] for x in f.read_text().splitlines()] == ['before_view_reset', 'after_view_reset']
    assert row['passed'] is True and row['device_executed'] is False and row['model_reads'] is False
    assert row['p176_kernel_tail_stores'] == 60 and row['p176_kernel_head_loads'] == 60
    assert row['cache_allocation_bytes'] == V.ALLOCATION_BYTES and row['device_owned_bound_bytes'] == plan['device_owned_bound_bytes']['value']
    assert 0 < row['peak_device_bytes'] <= row['device_owned_bound_bytes']
    growth = plan['expert_cache_arena_bytes']['growth']
    drm = plan['peaks_after_growth']['drm_projection_bytes']
    assert drm < 30_500_000_000
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    assert peak < 4 * 1024**3
    row.update(schema='packet58cache23.preparation.v1', command=command, real_device_argv=argv, binary_sha256=sha(probe), target_binary_sha256=sha(B / 'device/own-rt-iq3'),
               native_source_sha256=sha(P / 'native/generated/main.cpp'), bracket_rows=rows,
               census=dict(probe_peak_device_bytes=row['peak_device_bytes'], device_owned_bound_bytes=row['device_owned_bound_bytes'],
                           bound_margin_bytes=row['device_owned_bound_bytes'] - row['peak_device_bytes'],
                           record_allocate_peak_plus_growth=plan['peaks_after_growth']['allocate_peak_bytes'],
                           drm_projection_bytes=drm, drm_guard_bytes=30_500_000_000, drm_guard_margin_bytes=30_500_000_000 - drm,
                           drm_source=plan['peaks_after_growth']['drm_source'], arena_growth_bytes=growth,
                           note='the probe reserves the real allocation extents (opaque, untouched) through the real allocate() bound check; '
                                'DRM is a device quantity and is projected from the 182c lifetime peak, not measured here'),
               sandbox=dict(kind='Landlock', read=[str(p) for p in read_roots], device_read=[str(p) for p in dev_read],
                            write=['evidence/preparation-sequence', 'private temp HOME/TMPDIR (removed)', 'build/preparation58c23/inputs'],
                            not_granted=['/dev/dri', '/dev/accel', '/mnt', '/home outside experiments/own-xpu-runtime']),
               peak_child_rss_bytes=peak, real_arm_sequence=True, real_reset_sensors=130, view_resets=5, requests=60,
               substitutions=['CPU transport; no SYCL device creation', 'opaque large allocations; actual small controls/staging',
                              'synthetic embedding bytes and 272 PLE rows with production packed widths',
                              'nice19 observation in parser; original nice0 argv retained', 'output redirected through ENTRY_PREPARE_OUTPUT'])
    (P / 'evidence/preparation.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=True, prepared=row.get('prepared'), issued=row.get('issued'), peak_device_bytes=row['peak_device_bytes'],
                          bound_margin=row['census']['bound_margin_bytes'], drm_projection=drm, peak_child_rss_bytes=peak)))


if __name__ == '__main__':
    main()
