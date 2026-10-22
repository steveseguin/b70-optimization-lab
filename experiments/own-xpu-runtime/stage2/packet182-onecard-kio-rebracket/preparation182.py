#!/usr/bin/env python3
"""Packet182 production-shape startup rehearsal: the real WSCREEN argv through the
device-define CPU preparation probe, under Landlock (no /dev/dri, no /mnt). CPU only.

The probe binary is packet176's build/preparation/prepare-probe, copied byte for byte
(its sha256 must equal packet176's committed preparation receipt): the native sources are
unchanged, so no compile. What is new is the argv: packet182's selection, dispatch, oracle
input bundles, bracket table and output paths, i.e. this packet's real startup path at
production shape (5 views, 60 requests, 130 reset sensors, both kernel-I/O B views).

Landlock grants: read+execute /usr, /opt/intel/oneapi, /etc, /proc, /sys and the
repository's experiments/own-xpu-runtime tree; read /dev/null, /dev/zero, /dev/urandom;
read+write the fresh output directory and a private temporary HOME/TMPDIR. Not granted:
/dev/dri, /dev/accel, /mnt (model files), the rest of /home. A device-node or model-file
open therefore fails inside the probe instead of reaching the driver.

  nice -n 19 taskset -c 8-15,24-31 python3 -B preparation182.py < /dev/null
"""
import ctypes, hashlib, json, os, resource, shutil, subprocess, sys, tempfile
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
B = P / 'build'
PARENT_RECEIPT = 'experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/evidence/preparation.json'


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
            grant(path, 1 | 4 | 8)            # execute, read file, read dir
        for path in dev_read:
            grant(path, 2 | 4)                # write (/dev/null), read
        for path in write_roots:
            grant(path, handled)              # full access below the fresh output / private temp
        if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(446, fd, 0) != 0:
            raise RuntimeError('cannot restrict')
    finally:
        os.close(fd)


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    probe = B / 'preparation/prepare-probe'
    parent = json.loads(subprocess.run(['git', '-C', str(ROOT), 'show', 'HEAD:' + PARENT_RECEIPT], stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, check=True).stdout)
    assert sha(probe) == parent['binary_sha256'], 'probe is not packet176 committed preparation binary'
    assert sha(B / 'device/own-rt-iq3') == parent['target_binary_sha256'], 'device binary differs from packet176 target'
    assert sha(P / 'native/generated/main.cpp') == parent['native_source_sha256'], 'native source differs from packet176'
    sys.path.insert(0, str(P / 'screen'))
    import suite_driver as D, views as V
    from types import SimpleNamespace
    manifest = D.oracle_inputs()
    inputroot = B / 'preparation182/inputs'
    if inputroot.exists():
        shutil.rmtree(inputroot)
    inputroot.mkdir(parents=True)
    V.write_table(inputroot / 'bracket-inputs.tsv', 'resident')
    table = inputroot / 'suite-inputs.tsv'; table.write_text('')
    args = SimpleNamespace(view='resident', miss_mode='zerocopy', window='WSCREEN', output=inputroot, cache_maintenance='overlap')
    argv = D.native_command(args, manifest, table)[2:]
    assert Path(argv[0]).resolve() == (B / 'device/own-rt-iq3').resolve()
    output = P / 'evidence/preparation-sequence'
    assert not output.exists()
    output.mkdir(parents=True)
    from launch_env import environment
    work = Path(tempfile.mkdtemp(prefix='p182-prep-', dir='/tmp/claude-1000/-home-steve/1df77db8-272b-4a21-9a32-d0349da3fe39/scratchpad'))
    env = environment()
    env.update(ENTRY_PREPARE_OUTPUT=str(output), HOME=str(work), TMPDIR=str(work))
    command = ['/usr/bin/ionice', '-c3', str(probe), *argv[1:]]
    read_roots = [Path('/usr'), Path('/opt/intel/oneapi'), Path('/etc'), Path('/proc'), Path('/sys'),
                  ROOT / 'experiments/own-xpu-runtime']
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
    views = list(output.glob('*/host-memory.jsonl'))
    assert len(views) == 5
    for f in views:
        assert [json.loads(x)['phase'] for x in f.read_text().splitlines()] == ['before_view_reset', 'after_view_reset']
    assert row['passed'] is True and row['device_executed'] is False and row['model_reads'] is False
    assert row['p176_kernel_tail_stores'] == 24 and row['p176_kernel_head_loads'] == 24
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    assert peak < 4 * 1024**3
    row.update(command=command, real_device_argv=argv, binary_sha256=sha(probe), target_binary_sha256=sha(B / 'device/own-rt-iq3'),
               native_source_sha256=sha(P / 'native/generated/main.cpp'), probe_reused=dict(name='prepare-probe', parent_relpath='experiments/own-xpu-runtime/stage2/packet176-onecard-kernelio/build/preparation/prepare-probe',
               parent_digest=parent['binary_sha256'], reason='native sources unchanged; no compile'),
               parent_receipt=dict(name='preparation.json', parent_relpath=PARENT_RECEIPT, parent_digest=hashlib.sha256(
                   subprocess.run(['git', '-C', str(ROOT), 'show', 'HEAD:' + PARENT_RECEIPT], stdin=subprocess.DEVNULL, capture_output=True, check=True).stdout).hexdigest()),
               sandbox=dict(kind='Landlock', read=[str(p) for p in read_roots], device_read=[str(p) for p in dev_read],
                            write=['evidence/preparation-sequence', 'private temp HOME/TMPDIR (removed)', 'build/preparation182/inputs'],
                            not_granted=['/dev/dri', '/dev/accel', '/mnt', '/home outside experiments/own-xpu-runtime']),
               peak_child_rss_bytes=peak, real_arm_sequence=True, real_reset_sensors=130, view_resets=5, requests=60,
               substitutions=['CPU transport; no SYCL device creation', 'opaque large allocations; actual small controls/staging',
                              'synthetic embedding bytes and 272 PLE rows with production packed widths',
                              'nice19 observation in parser; original nice0 argv retained', 'output redirected through ENTRY_PREPARE_OUTPUT'])
    (P / 'evidence/preparation.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(passed=True, prepared=row.get('prepared'), issued=row.get('issued'), peak_child_rss_bytes=peak)))


if __name__ == '__main__':
    main()
