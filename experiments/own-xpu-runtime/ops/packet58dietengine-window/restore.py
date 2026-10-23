#!/usr/bin/env python3
"""Restore the three daily endpoints serially (2026-10-21 restore3).

Same units, launchers, properties and argv as the 2026-10-20 restoration
(restore-start.json / vision-start.json), with fresh state dirs. One launch at a
time; wait for ready; check the kernel journal for GPU faults before the next;
halt on any failure, never restart. Writes receipts under
/home/steve/inference/20261021-restore3/.
"""
import json, re, subprocess, sys, time, urllib.request
from window import faults_clear
from datetime import datetime, timezone
from pathlib import Path

INF = Path('/home/steve/inference')
SUFFIX = sys.argv[1] if len(sys.argv) == 2 else ''
if not re.fullmatch(r'20261023-restore[0-9]+', SUFFIX):
    raise SystemExit('explicit fresh restore suffix required')
OUT = INF / SUFFIX
OUT.mkdir(exist_ok=False)
RESTORATION = INF / '20261020-restoration'
MODEL = '/mnt/usb-models/llm-models/qwen3.8-27b-fp8-official-017b9c7'
PROPS = ['--property=Restart=no', '--property=SendSIGKILL=no', '--property=TimeoutStopSec=infinity',
         '--property=KillMode=process', '--property=ExitType=cgroup']
FAULT = re.compile(r'(GPU HANG|gpu hang|engine reset|GuC .*(timed out|failed)|\[drm\].*(reset|timeout)|xe .*(hang|lockup|timeout|fault))', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def log(msg):
    line = f'{now()} {msg}'
    print(line, flush=True)
    with (OUT / 'driver.log').open('a') as f:
        f.write(line + '\n')


def kernel_since(stamp):
    return subprocess.run(['journalctl', '-k', '--since', stamp, '--no-pager', '-o', 'short'],
                          capture_output=True, text=True, timeout=30).stdout


def wait_http(url, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        faults_clear()
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(5)
    return False


def unit_active(unit):
    return subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True).stdout.strip()


def run_unit(unit, argv, cwd, stdout=None):
    faults_clear()
    cmd = ['systemd-run', '--user', f'--unit={unit}', f'--working-directory={cwd}', *PROPS]
    if stdout:
        cmd += [f'--property=StandardOutput=append:{stdout}', f'--property=StandardError=append:{stdout}']
    cmd += argv
    log(f'launch {unit}: {" ".join(cmd)}')
    cp = subprocess.run(cmd, capture_output=True, text=True)
    log(f'systemd-run rc={cp.returncode} {cp.stdout.strip()} {cp.stderr.strip()}')
    if cp.returncode != 0:
        raise SystemExit(f'{unit}: systemd-run failed')
    return cmd


def fp8(unit, pkg, sha, state_dir, port):
    argv = ['/usr/bin/python3', str(RESTORATION / 'serve-term-only.py'), str(INF / pkg / 'scripts/serve.py'), sha,
            'start', '--model-dir', MODEL, '--state-dir', str(state_dir), '--profile', 'recommended',
            '--gpu', '0', '--port', str(port)]
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cmd = run_unit(unit, argv, str(INF))
    deadline = time.monotonic() + 900
    while True:
        faults_clear()
        if unit_active(unit) != 'active':
            raise SystemExit(f'{unit}: unit left active state before ready; halting (no restart)')
        state = state_dir / 'state.json'
        if state.exists():
            row = json.loads(state.read_text())
            if row.get('status') == 'ready':
                break
            if row.get('status') not in ('starting', 'ready'):
                raise SystemExit(f'{unit}: state {row.get("status")}: {row.get("error")}')
        if time.monotonic() > deadline:
            raise SystemExit(f'{unit}: not ready within 900 s; halting (no restart)')
        time.sleep(5)
    kern = kernel_since(stamp)
    faults = [l for l in kern.splitlines() if FAULT.search(l)]
    (OUT / f'{unit}-ready.json').write_text(json.dumps(dict(at=now(), argv=cmd, state=json.loads(state.read_text()),
                                                            kernel_fault_lines=faults), indent=2))
    if faults:
        raise SystemExit(f'{unit}: kernel fault lines after start: {faults[:3]}; halting')
    faults_clear()
    log(f'{unit} ready on :{port}')


def validate(unit, port, model, kind, vision=False):
    faults_clear()
    cmd = ['/usr/bin/python3', str(Path(__file__).with_name('validate.py')), '--base', f'http://127.0.0.1:{port}',
           '--model', model, '--kind', kind] + (['--vision'] if vision else [])
    cp = subprocess.run(cmd, capture_output=True, text=True, cwd=str(INF))
    (OUT / f'{unit}-validate.log').write_text(cp.stdout + cp.stderr)
    log(f'{unit} validate rc={cp.returncode} tail={cp.stdout.strip().splitlines()[-1:] }')
    faults_clear()
    if cp.returncode != 0:
        raise SystemExit(f'{unit}: validation failed; no further requests or restart')
    return True


def main():
    faults_clear()
    log(f'{SUFFIX} start')
    for u in ('qwen38-27b-fp8', 'qwen38-27b-fp8-tp1-test', 'qwen38-27b-vision'):
        if unit_active(u) == 'active':
            raise SystemExit(f'{u} already active; nothing to do')
    fp8('qwen38-27b-fp8', 'fp8-tp1-card0-pkg', '33c24d9efadf06f24949a0ca16638d194f863e4ad96716669132494b2f3f7151',
        INF / f'qwen38-27b-fp8-card0-{SUFFIX}', 18130)
    fp8('qwen38-27b-fp8-tp1-test', 'fp8-tp1-pkg', '111e6333a9c01899004d8f953c755b66fde0276afd8b1c15ee40e04a279c330e',
        INF / f'qwen38-27b-fp8-card3-{SUFFIX}', 18131)
    vdir = INF / f'qwen38-27b-vision-{SUFFIX}'
    vdir.mkdir(exist_ok=False)
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cmd = run_unit('qwen38-27b-vision', ['/usr/bin/bash', str(RESTORATION / 'vision.sh')], str(vdir), str(vdir / 'server.log'))
    if not wait_http('http://127.0.0.1:18100/v1/models', 900):
        raise SystemExit('vision: not ready within 900 s; halting (no restart)')
    kern = kernel_since(stamp)
    faults = [l for l in kern.splitlines() if FAULT.search(l)]
    (OUT / 'qwen38-27b-vision-ready.json').write_text(json.dumps(dict(at=now(), argv=cmd, kernel_fault_lines=faults), indent=2))
    if faults:
        raise SystemExit(f'vision: kernel fault lines after start: {faults[:3]}; halting')
    log('vision ready on :18100')
    ok = [validate('qwen38-27b-fp8', 18130, 'qwen38-27b-fp8', 'vllm'),
          validate('qwen38-27b-fp8-tp1-test', 18131, 'qwen38-27b-fp8', 'vllm'),
          validate('qwen38-27b-vision', 18100, 'qwen38-27b-vision', 'llamacpp', vision=True)]
    log(f'{SUFFIX} done; validations {ok}')
    (OUT / 'done.json').write_text(json.dumps(dict(at=now(), validations=ok), indent=2))
    return 0 if all(ok) else 2


if __name__ == '__main__':
    raise SystemExit(main())
