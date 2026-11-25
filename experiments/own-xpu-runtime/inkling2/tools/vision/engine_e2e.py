# drives one serving engine: registers a picture (V), feeds the reference's chunk layout with its rows, greedy ids
import subprocess, sys, os, time, hashlib
card, rgb, w, h, chunks, nnew, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), sys.argv[7]
env = dict(os.environ, INK_SERVE='1', INK_VISION='/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/mmproj-BF16.gguf')
O = '/home/steve/b70-optimization-lab/experiments/own-xpu-runtime/inkling2/scripts/on-card.sh'
M = '/mnt/fast-ai/llm-models/Inkling-2-Mini-GGUF/Inkling-2-Mini-UD-IQ4_XS.gguf'
p = subprocess.Popen([O, card, sys.argv[8], M, card, '/dev/null', '0', '8192'], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=open(out + '.err', 'w'), env=env, text=True, bufsize=1)
def line():
    while True:
        l = p.stdout.readline()
        if not l: raise SystemExit('engine ended')
        if l.startswith('@@'): return l.split()
while line()[0] != '@@READY': pass
key = int.from_bytes(hashlib.sha256(open(rgb, 'rb').read() + f'{w}x{h}'.encode()).digest()[:4], 'little') & ((1 << 30) - 1)
t = time.time(); p.stdin.write(f'V v1 {key} {w} {h} {rgb}\n'); p.stdin.flush()
r = line(); print('V reply', r, '%.3f s' % (time.time() - t))
assert r[0] == '@@V'
nrows = int(r[2])
ids = []
for l in open(chunks):
    f = l.split()
    if f[0] == 'text': ids += [int(x) for x in f[1:]]
    else:
        assert int(f[1]) == nrows, (f, nrows)
        ids += [(1 << 30) + ((key + i) % ((1 << 30) - 1)) for i in range(nrows)]
p.stdin.write(f'G g1 {nnew} 1 200006 {len(ids)} ' + ' '.join(map(str, ids)) + '\n'); p.stdin.flush()
gen = []
while True:
    r = line()
    if r[0] == '@@T': gen += [int(x) for x in r[2:]]
    elif r[0] == '@@D': print('D', r[1:]); break
    elif r[0] == '@@E': print('E', r); break
open(out, 'w').write(' '.join(map(str, gen)) + '\n')
p.stdin.write('Q\n'); p.stdin.flush(); p.wait(timeout=120)
print(len(gen), 'tokens')
