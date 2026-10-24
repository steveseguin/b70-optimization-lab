#!/usr/bin/env python3
"""Build the own-runtime engine from engine/src with the recorded flags.

usage: build.py OUT_DIR [--jobs N] [--only OBJ ...]
Compiles each translation unit of build-manifest.json (same flags as the receipts, plus -I engine/src),
links in manifest order, and writes OUT_DIR/build-receipt.json with source/object/binary hashes.
TMPDIR defaults to OUT_DIR/tmp. Run under nice/taskset; never executes the binary.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ENGINE = Path(__file__).resolve().parent
SRC = ENGINE / 'src'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
ap = argparse.ArgumentParser(); ap.add_argument('out', type=Path); ap.add_argument('--jobs', type=int, default=4)
ap.add_argument('--name', default='own-engine'); a = ap.parse_args()
m = json.loads((ENGINE / 'build-manifest.json').read_text())
out = a.out.resolve(); out.mkdir(parents=True, exist_ok=True); (out / 'tmp').mkdir(exist_ok=True)
env = dict(os.environ, TMPDIR=str(out / 'tmp'))
def compile_tu(tu):
    obj = out / tu['object']
    cmd = [m['compiler'], *tu['flags'], '-I', str(SRC), '-MMD', '-MF', str(obj.with_suffix('.d')), '-c', str(SRC / tu['source']), '-o', str(obj)]
    t = time.time(); p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    return tu['object'], cmd, p.returncode, round(time.time() - t, 1), p.stderr[-6000:]
log = {}
with cf.ThreadPoolExecutor(a.jobs) as ex:
    for name, cmd, rc, sec, err in ex.map(compile_tu, m['translation_units']):
        log[name] = dict(cmd=cmd, rc=rc, seconds=sec, stderr=err)
        print(name, 'rc', rc, sec, 's', flush=True)
        if rc: print(err); sys.exit(1)
binary = out / a.name
link = [m['link']['compiler'], *[x for x in m['link']['flags'] if x.startswith('-fsycl') or x.startswith('-Wl,--gc')],
        *[str(out / tu['object']) for tu in m['translation_units']],
        *[x for x in m['link']['flags'] if not (x.startswith('-fsycl') or x.startswith('-Wl,--gc'))], '-o', str(binary)]
p = subprocess.run(link, env=env, capture_output=True, text=True)
log['link'] = dict(cmd=link, rc=p.returncode, stderr=p.stderr[-6000:])
if p.returncode: print(p.stderr); sys.exit(1)
deps = set()
for tu in m['translation_units']:
    for t in (out / tu['object']).with_suffix('.d').read_text().replace('\\\n', ' ').split()[1:]:
        if t.startswith(str(SRC)): deps.add(t)
receipt = dict(schema='ownrt.engine.build.v1', binary=str(binary), binary_sha256=sha(binary),
               objects={tu['object']: sha(out / tu['object']) for tu in m['translation_units']},
               sources={str(Path(d).relative_to(SRC)): sha(d) for d in sorted(deps)}, commands=log)
(out / 'build-receipt.json').write_text(json.dumps(receipt, indent=1) + '\n')
print('binary', receipt['binary_sha256'])
