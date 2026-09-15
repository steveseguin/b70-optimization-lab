"""Negative tests: the packet13 checker must reject tampering, including a
manifest regenerated to match the tampered tree."""
import hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PK = ROOT / 'prepared-encoder-host-residency-13'
PYEXE = '/home/steve/.venvs/ltx25-baseline/bin/python'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check(pk):
    r = subprocess.run([PYEXE, '-B', str(pk / 'launch/serve-encoder.py'), '--packet', str(pk),
                        '--manifest-sha256', sha(pk / 'manifest.json'),
                        '--run-name', 'encoder-server-negative-probe', '--check-only'],
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stderr.strip().splitlines() or [''])[-1]

def regen_manifest(pk):
    m = json.loads((pk / 'manifest.json').read_text())
    files = {}
    for p in sorted(pk.rglob('*')):
        if p.is_file():
            rel = str(p.relative_to(pk))
            if rel in ('manifest.json', 'STATUS.txt'): continue
            files[rel] = sha(p)
    m['files'] = files
    m['startup_tools'] = {'encoder_runtime_common.py': files['launch/encoder_runtime_common.py'],
                          'serve-encoder.py': files['launch/serve-encoder.py']}
    m['extension_sha256s'] = {k: files['source/scripts/' + k] for k in m['extension_sha256s']}
    with (pk / 'manifest.json').open('w') as h:
        json.dump(m, h, indent=2, sort_keys=True); h.write('\n')

cases = []
import contextlib
@contextlib.contextmanager
def _scratch():
    d = ROOT
    made = []
    try:
        yield d, made
    finally:
        for p in made: shutil.rmtree(p, ignore_errors=True)
with _scratch() as (tmp, MADE):
    tmp = Path(tmp)
    MADE.extend([tmp/'prepared-encoder-negative-one', tmp/'prepared-encoder-negative-two', tmp/'prepared-encoder-negative-three', tmp/'prepared-encoder-negative-four'])
    # Case 1: numerical source tampered, manifest NOT regenerated
    pk1 = tmp / 'prepared-encoder-negative-one'
    shutil.copytree(PK, pk1)
    t = pk1 / 'source/comfy/ldm/lightricks/av_model.py'
    t.write_text(t.read_text().replace('run_vx = transformer_options.get("run_vx", True)',
                                       'run_vx = transformer_options.get("run_vx", True)  # tampered', 1))
    cases.append(('numerical source edited, manifest stale', *check(pk1)))
    # Case 2: same tamper, manifest REGENERATED to match (the blind-gate test)
    regen_manifest(pk1)
    cases.append(('numerical source edited, manifest regenerated', *check(pk1)))
    # Case 3: launcher changed beyond the reserved-VRAM literal, manifest regenerated
    pk2 = tmp / 'prepared-encoder-negative-two'
    shutil.copytree(PK, pk2)
    L = pk2 / 'launch/serve-encoder.py'
    L.write_text(L.read_text().replace("'--deterministic',", "", 1))
    regen_manifest(pk2)
    cases.append(('launcher dropped --deterministic', *check(pk2)))
    # Case 4: reserved VRAM set to a value the contract does not declare
    pk3 = tmp / 'prepared-encoder-negative-three'
    shutil.copytree(PK, pk3)
    L = pk3 / 'launch/serve-encoder.py'
    L.write_text(L.read_text().replace("'--reserve-vram', '2'", "'--reserve-vram', '0'", 1))
    regen_manifest(pk3)
    cases.append(('reserved VRAM changed to 0', *check(pk3)))
    # Case 5: an extra uninventoried file
    pk4 = tmp / 'prepared-encoder-negative-four'
    shutil.copytree(PK, pk4)
    (pk4 / 'source/scripts/sneaky.py').write_text('x = 1\n')
    regen_manifest(pk4)
    cases.append(('extra file added to source/scripts', *check(pk4)))

ok = all(rc != 0 for _, rc, _ in cases)
for name, rc, err in cases:
    print(f'{"REJECTED" if rc else "ACCEPTED!!":10s} rc={rc}  {name}\n           -> {err[:150]}')
print('\nALL NEGATIVE CASES REJECTED:', ok)
sys.exit(0 if ok else 1)
