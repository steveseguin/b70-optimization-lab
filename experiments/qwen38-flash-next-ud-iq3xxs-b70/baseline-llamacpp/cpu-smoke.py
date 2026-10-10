#!/usr/bin/env python3
"""Only early help/version paths. Never pass model/device options to binaries."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/home/steve/build/flash-next-iq3-baseline-20261010')
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
LIBS = '/opt/intel/oneapi/compiler/2026.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/tbb/2023.0/lib'
ENV = {'PATH': '/usr/bin:/bin', 'LD_LIBRARY_PATH': LIBS, 'OMP_NUM_THREADS': '2',
       'MKL_NUM_THREADS': '2', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rows = []
    for name in ('llama-cli', 'llama-completion'):
        for flag in ('--help', '--version'):
            stem = name + flag
            trace = ROOT / (stem + '.strace')
            cmd = [str(ROOT / 'build/bin' / name), flag]
            p = subprocess.run(['/usr/bin/strace', '-f', '-e', 'trace=%file', '-o', str(trace), *cmd],
                               env=ENV, capture_output=True, timeout=60)
            (ROOT / (stem + '.stdout')).write_bytes(p.stdout)
            (ROOT / (stem + '.stderr')).write_bytes(p.stderr)
            text = trace.read_text()
            assert '/dev/dri' not in text and '/dev/nvidia' not in text
            assert p.returncode == 0, (cmd, p.stderr)
            rows.append({'argv': cmd, 'returncode': p.returncode,
                         'stdout_sha256': hashlib.sha256(p.stdout).hexdigest(),
                         'stderr_sha256': hashlib.sha256(p.stderr).hexdigest(),
                         'file_syscall_trace_sha256': sha(trace), 'device_node_access': False})
    model_root = Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6')
    files = json.loads((REPO / 'experiments/own-xpu-runtime/data/unsloth-flash-next-stage2-files.json').read_text())['files']
    observed = []
    for f in files:
        if f['path'].startswith('UD-IQ3_XXS/'):
            p = model_root / f['path']
            observed.append({'path': str(p), 'expected_bytes': f['bytes'],
                             'observed_bytes': p.stat().st_size if p.exists() else None})
    complete = all(x['expected_bytes'] == x['observed_bytes'] for x in observed)
    gguf = {'status': 'skipped', 'reason': 'Download incomplete; no live GGUF parser invoked.', 'files': observed}
    if complete:
        # Only numpy-based upstream reader, no torch/model runtime; read-only first
        # shard has zero tensors. This pre-existing Python supplies numpy.
        cmd = ['/home/steve/.venvs/ltx25-baseline/bin/python', '-B',
               str(ROOT / 'llama.cpp/gguf-py/gguf/scripts/gguf_dump.py'),
               '--no-tensors', observed[0]['path']]
        p = subprocess.run(cmd, env=ENV, capture_output=True, timeout=120)
        (ROOT / 'gguf-dump.stdout').write_bytes(p.stdout)
        (ROOT / 'gguf-dump.stderr').write_bytes(p.stderr)
        gguf.update(status='passed' if p.returncode == 0 else 'failed', reason='First shard header only, upstream read-only GGUFReader.',
                    argv=cmd, returncode=p.returncode, stdout_sha256=hashlib.sha256(p.stdout).hexdigest())
        assert p.returncode == 0, p.stderr
    result = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'early_exit_smokes': rows,
              'gguf_dump': gguf, 'source_audit': 'tools/cli/cli.cpp and tools/completion/completion.cpp parse help/version before llama_backend_init; common/arg.cpp exits early; common_init only sets logging.',
              'scope': 'CPU only; no model inference, device enumeration, health probe, server or port operation.'}
    (ROOT / 'cpu-smoke.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
