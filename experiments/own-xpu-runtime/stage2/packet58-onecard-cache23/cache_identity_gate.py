#!/usr/bin/env python3
"""Byte-identity proof for the `max` view inside the larger arena (CPU; host g++ only).

Compiles native/cache23_identity_test.cpp against the vendored native/cache_table.hpp (the exact
cache policy the engine links) and runs it: the same route trace on (arena S, cap C) and
(arena S + growth, cap C) must produce identical fills, offsets, published tables and residency
at every step; cap = S + growth must keep more resident; a cap above the allocation and a switch
during a position must be refused. Writes evidence/cache-identity.json.
"""
import json, resource, subprocess
from pathlib import Path
from build_engine import P, B, compiler_turn, sha, save, limits


def main():
    limits()
    src = P / 'native/cache23_identity_test.cpp'
    out = B / 'cache23-identity-test'
    cmd = ['/usr/bin/g++', '-std=c++20', '-O2', '-I', str(P / 'native'), str(src), '-o', str(out)]
    with compiler_turn(), (B / 'cache23-identity-build.log').open('w') as log:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                       preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3)))
    assert 'warning' not in (B / 'cache23-identity-build.log').read_text()
    cp = subprocess.run([str(out)], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120, env=dict(PATH='/usr/bin:/bin'))
    assert cp.returncode == 0, cp.stderr[-2000:]
    row = json.loads(cp.stdout.strip().splitlines()[-1])
    assert row['passed'] and row['max23_resident_peak'] > row['max_resident_peak']
    save(P / 'evidence/cache-identity.json', dict(row, schema='packet58cache23.cache-identity.v1', command=cmd,
         source_sha256=sha(src), cache_table_sha256=sha(P / 'native/cache_table.hpp'), binary_sha256=sha(out),
         proof='p58::Cache decisions depend only on (base, capacity): the max view inside the 23,049,601,024-byte arena is '
               'byte-for-byte packet182c\'s 21,552,729,600-byte cache; max23 = the whole arena', scaled=True,
         production_literals=dict(max=21552729600, max23=23049601024, growth=1496871424, aligned_256=True)))
    print(json.dumps(dict(passed=True, checks=row['checks'], max_resident_peak=row['max_resident_peak'], max23_resident_peak=row['max23_resident_peak'])))


if __name__ == '__main__':
    main()
