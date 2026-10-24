#!/usr/bin/env python3
"""One-time consolidation of the SC117 service engine (binary 17c3c5c2) into one canonical source tree.

Input: the build receipts of the 40 linked objects. Output: engine/src/<logical path> with relative includes,
no #line directives, plus engine/build-manifest.json (40 translation units, flags, link order).
Every file is copied from the exact bytes the binary was compiled from; duplicate copies of one logical file
must be identical modulo include paths and #line directives, or the tool refuses.
"""
import hashlib, json, os, re, shutil, sys
from pathlib import Path

R = Path('/home/steve/llm-optimizations')
LANE = R / 'experiments/own-xpu-runtime/gsq-rco-iq3s'
ENGINE = R / 'experiments/own-xpu-runtime/engine'
SRC = ENGINE / 'src'
D = json.loads((LANE / 'service-speed/d-mtp-fp8/build-receipt.json').read_text())
NATIVE = json.loads((LANE / 'recurrent-f32/evidence/native-build.json').read_text())
FULL = json.loads((LANE / 'integration/evidence/full-native-build.json').read_text())
INC = re.compile(r'^(\s*#\s*include\s+)"(/[^"]+)"', re.M)
REL = re.compile(r'^\s*#\s*include\s+"([^/"][^"]*)"', re.M)
LINE = re.compile(r'^#line\b.*\n', re.M)

def sha(b): return hashlib.sha256(b).hexdigest()
def logical(p):
    p = str(p); i = p.rfind('experiments/own-xpu-runtime/')
    if i < 0: sys.exit('not a lab path: ' + p)
    return p[i + len('experiments/own-xpu-runtime/'):]

# 1. compile command per linked object (latest build that produced it)
commands = {}
for receipt in (FULL, NATIVE):
    for c in receipt['commands'][:-1]:
        commands[c[c.index('-o') + 1]] = c
MOVED = ('/dev/shm/dbuild/', '/mnt/usb-models/own-xpu-runtime-builds/sc117-draft-fp8-a/')  # built in RAM, then copied
def moved(x): return x.replace(*MOVED) if x.startswith(MOVED[0]) else x
for c in D['commands'][:-1]:
    c = [moved(x) for x in c]; commands[c[c.index('-o') + 1]] = c
link = [moved(x) for x in D['commands'][-1]]
objects = [x for x in link if x.endswith('.o')]
assert len(objects) == 40 and all(o in commands for o in objects), 'missing compile command'
for o in objects:
    assert sha(Path(o).read_bytes()) == D['objects'][o], 'object changed: ' + o

# 2. transitive include closure (all #include "..." lines, regardless of preprocessor conditions)
roots = [os.path.realpath(commands[o][commands[o].index('-c') + 1]) for o in objects]
seen, stack = {}, list(roots)
while stack:
    f = stack.pop()
    if f in seen: continue
    text = Path(f).read_text()
    seen[f] = text
    for m in INC.finditer(text):
        target = os.path.realpath(m.group(2))
        if not os.path.exists(target): sys.exit(f'dangling include {target} in {f}')
        stack.append(target)
    for m in REL.finditer(text):  # relative includes resolve next to the including file
        target = os.path.realpath(os.path.join(os.path.dirname(f), m.group(1)))
        if os.path.exists(target): stack.append(target)

# 3. group by logical path; copies must agree modulo include paths and #line
def normalized(text):
    return LINE.sub('', INC.sub(lambda m: m.group(1) + '"' + logical(os.path.realpath(m.group(2))) + '"', text))
groups = {}
for f, text in seen.items():
    groups.setdefault(logical(f), {})[f] = normalized(text)
for k, v in groups.items():
    if len(set(v.values())) != 1: sys.exit('conflicting copies of ' + k + ': ' + ', '.join(v))

# 4. write the tree
if SRC.exists(): sys.exit('engine/src exists; refusing to overwrite')
manifest = dict(schema='ownrt.engine.consolidation.v1', base_binary=D['binary'], base_binary_sha256=D['binary_sha256'],
                files={}, translation_units=[], link=None, assets={})
for k, v in sorted(groups.items()):
    out = SRC / k; out.parent.mkdir(parents=True, exist_ok=True)
    text = next(iter(v.values())); out.write_text(text)
    manifest['files'][k] = dict(sha256=sha(text.encode()), copied_from=sorted(str(Path(f).relative_to(R)) if f.startswith(str(R)) else f for f in v),
                               source_sha256=sorted({sha(seen[f].encode()) for f in v}))

# 5. assets main.cpp located via __FILE__ (its #line pinned stage2/packet136-record-bundle/main.cpp)
uses = [k for k, v in groups.items() if '__FILE__' in next(iter(v.values()))]
for k in uses:
    for name in ('rope.bf16', 'mtp-manifest.tsv'):
        src = R / 'experiments/own-xpu-runtime/stage2/packet136-record-bundle' / name
        if src.exists():
            dst = (SRC / k).parent / name; shutil.copyfile(src, dst)
            manifest['assets'][str(dst.relative_to(SRC))] = dict(sha256=sha(dst.read_bytes()), copied_from=str(src.relative_to(R)))

# 6. build manifest: same flags, sources relative to src/
for o in objects:
    c = commands[o]; source = logical(os.path.realpath(c[c.index('-c') + 1]))
    flags = [x for i, x in enumerate(c[1:], 1) if x not in ('-MMD', '-c', '-o', '-MF') and c[i - 1] not in ('-MF', '-c', '-o')]
    manifest['translation_units'].append(dict(object=Path(o).name if not o.endswith('-cand.o') else ('entry.o' if 'entry' in o else '16.o'),
                                               original_object=o, source=source, flags=flags))
manifest['link'] = dict(flags=[x for x in link[1:] if not x.endswith('.o') and x not in ('-o', moved(link[link.index('-o') + 1]))], compiler=link[0])
manifest['compiler'] = commands[objects[0]][0]
manifest['file_uses_of___FILE__'] = uses
(ENGINE / 'build-manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
print('files', len(groups), 'TUs', len(objects), 'assets', list(manifest['assets']), '__FILE__ users', uses)
