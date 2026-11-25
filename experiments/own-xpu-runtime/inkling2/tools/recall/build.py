# 20 facts ("the vault combination for project <Name> is <5 digits>") spread from 2 % to 97 % of a ~490K-token
# haystack made of the lab repo's notes (markdown files in path order).
import json, os, random, subprocess, sys
ROOT = '/home/steve/b70-optimization-lab'
OUT = '/home/steve/inkling-work/recall'
target_chars = int(sys.argv[1]) if len(sys.argv) > 1 else 1_900_000
files = subprocess.run(['git', '-C', ROOT, 'ls-files', '*.md'], capture_output=True, text=True).stdout.split()
docs, n = [], 0
for f in sorted(files):
    if 'history' in f.lower():  # (long logs that repeat each other)
        continue
    try:
        t = open(os.path.join(ROOT, f), encoding='utf-8', errors='replace').read().strip()
    except OSError:
        continue
    if not t or len(t) > 60000:
        continue
    docs.append(f'--- Document: {f} ---\n\n{t}\n')
    n += len(docs[-1])
    if n >= target_chars:
        break
names = ['Kestrel', 'Juniper', 'Basalt', 'Marigold', 'Tundra', 'Saffron', 'Quartz', 'Heron', 'Cobalt', 'Lantern',
         'Willow', 'Ember', 'Garnet', 'Harbor', 'Indigo', 'Jasper', 'Orchid', 'Pebble', 'Sequoia', 'Thistle']
rng = random.Random(20261125)
codes = rng.sample(range(10000, 100000), len(names))
total = sum(len(d) for d in docs)
needles, cum, k = [], 0, 0
out = []
depths = [0.02 + 0.05 * i for i in range(len(names))]
for d in docs:
    while k < len(names) and cum >= depths[k] * total:
        s = f'Archive note: the vault combination for project {names[k]} is {codes[k]}.\n\n'
        out.append(s); needles.append({'name': names[k], 'code': codes[k], 'depth': round(depths[k], 2), 'char': cum})
        k += 1
    out.append(d); cum += len(d)
hay = ''.join(out)
assert hay.lower().count('vault combination') == len(names), hay.lower().count('vault combination')
open(f'{OUT}/haystack.txt', 'w').write(hay)
json.dump({'needles': needles, 'docs': len(docs), 'chars': len(hay)}, open(f'{OUT}/needles.json', 'w'), indent=1)
print(len(docs), 'documents,', len(hay), 'characters,', len(needles), 'facts')
