#!/usr/bin/env python3
# kern_isa.py BIN [IMAGE]: kernel ISA bytes by family (demangled-ish name stem) in an own_run_v41 binary's images,
# biggest first (CPU only, read-only; uses zebin_sizes.py's readers).
import collections, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec = importlib.util.spec_from_file_location('zs', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zebin_sizes.py'))
zs = importlib.util.module_from_spec(spec)
argv = sys.argv; sys.argv = [argv[0], argv[1]]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(zs)
sys.argv = argv
imgs = zs.images(argv[1])
want = int(argv[2]) if len(argv) > 2 else None
fam = collections.Counter(); cnt = collections.Counter()
for i, img in enumerate(imgs):
    if want is not None and i != want: continue
    for n, s in zs.sections(img):
        if not n.startswith('.text.'): continue
        k = n[6:]
        m = re.search(r'ops41sycl(\d+)([A-Za-z0-9_]+)', k)
        stem = m.group(2)[:int(m.group(1))] if m else re.sub(r'\d+', '', k)[:40]
        fam[stem] += s[5]; cnt[stem] += 1
tot = sum(fam.values())
print(f"{len(cnt)} families, {sum(cnt.values())} kernels, {tot/2**20:.1f} MiB ISA")
for k, v in fam.most_common(30):
    print(f"{v/2**20:8.2f} MiB {cnt[k]:5d} kernels  {k}")
