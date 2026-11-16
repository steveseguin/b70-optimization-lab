#!/usr/bin/env python3
# Read-only: list the device images (zebins) embedded in an own_run_v41 binary and their section sizes, and the
# glibc mmap footprint of N copies of each; with two binaries, compare every kernel's ISA (.text.<kernel>) bytes.
#   python3 -I zebin_sizes.py BIN            sizes per image
#   python3 -I zebin_sizes.py OLD NEW        same + per-kernel ISA compare (identical ISA => identical results)
# The image table is the .tgtimg section: 15 (address, size) pairs into __CLANG_OFFLOAD_BUNDLE__sycl-spir64_gen.
import collections, struct, sys


def sections(b):
    shoff, = struct.unpack_from('<Q', b, 0x28)
    ent, num, stx = struct.unpack_from('<HHH', b, 0x3a)
    sh = [struct.unpack_from('<IIQQQQIIQQ', b, shoff + i * ent) for i in range(num)]
    so = sh[stx][4]
    out = []
    for s in sh:
        e = b.index(b'\0', so + s[0])
        out.append((b[so + s[0]:e].decode(), s))
    return out


def images(path):
    b = open(path, 'rb').read()
    secs = {n: s for n, s in sections(b)}
    t = secs['.tgtimg']
    bun = secs['__CLANG_OFFLOAD_BUNDLE__sycl-spir64_gen']
    raw = b[t[4]:t[4] + t[5]]
    pairs = struct.unpack('<%dQ' % (len(raw) // 8), raw)
    res = []
    for i in range(0, len(pairs), 2):
        addr, size = pairs[i], pairs[i + 1]
        off = bun[4] + (addr - bun[3])
        img = b[off:off + size]
        assert img[:4] == b'\x7fELF'
        res.append(img)
    return res


def chunk(n):  # bytes a glibc mmap'd malloc(n) occupies
    nb = (n + 8 + 15) & ~15
    return -(-(nb + 8) // 4096) * 4096


def summary(imgs):
    tot = collections.Counter()
    for k, img in enumerate(imgs):
        c = collections.Counter()
        nk = 0
        for n, s in sections(img):
            if s[1] == 8:
                continue
            key = '.text' if n.startswith('.text.') else '.spv' if n.startswith('.spv') else '.ze_info' if n.startswith('.ze_info') else 'other'
            nk += n.startswith('.text.')
            c[key] += s[5]
        tot.update(c)
        tot['bytes'] += len(img)
        print('image %2d %11d B  kernels %4d  isa %11d  spv %10d  ze_info %9d  | 3 copies %8d kB, +spv %8d kB'
              % (k, len(img), nk, c['.text'], c['.spv'], c['.ze_info'], 3 * chunk(len(img)) // 1024,
                 (3 * chunk(len(img)) + chunk(c['.spv'])) // 1024))
    print('all images %d B (%.1f MiB): isa %.1f MiB, spv %.1f MiB, ze_info %.1f MiB'
          % (tot['bytes'], tot['bytes'] / 2**20, tot['.text'] / 2**20, tot['.spv'] / 2**20, tot['.ze_info'] / 2**20))


def isa(imgs):
    d = {}
    for img in imgs:
        for n, s in sections(img):
            if n.startswith('.text.'):
                d[n[6:]] = img[s[4]:s[4] + s[5]]
    return d


a = images(sys.argv[1])
summary(a)
if len(sys.argv) > 2:
    b = images(sys.argv[2])
    print('--- second binary')
    summary(b)
    ka, kb = isa(a), isa(b)
    same = sum(1 for k in ka if k in kb and ka[k] == kb[k])
    diff = [k for k in ka if k in kb and ka[k] != kb[k]]
    print('kernels: %d in old, %d in new, %d in both with identical ISA, %d differ, %d only old, %d only new'
          % (len(ka), len(kb), same, len(diff), len(set(ka) - set(kb)), len(set(kb) - set(ka))))
    for k in diff[:20]:
        print('  ISA differs:', k[:160])
