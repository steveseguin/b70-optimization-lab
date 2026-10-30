#!/usr/bin/env python3
"""The 38 rank-harness comparisons of sections 3 (phases m1-smoke, m2-smoke, g1, g3, g3-smoke, g5, g5-smoke), rerun on
build r7 (b51c9e8d803e). Each new-binary run of the original comparison is replaced by the r7 run with the same flags
(r2/r4/r6 runs of one flag set map to one r7 run); the archived previous-binary (aafd258dd5ea, ctx131072 k2) and one-card
runs stay the references. Prints compare_phase.sh arguments for RUNS=the r7 rerun directory.
r7 runs: S0-off S0-ld S0-4 S0-ko S1-off S1-mx (40 rows, 16-row chunks, 4 halves) and R1-off R1-mx R1-mx-tbt R0-off R0-4
R0-4-tbt R0-4-m R0-ko R0-ko-tbt R0-ko-m (1,100 rows, 256-row chunks, 16 halves)."""
K2 = '/mnt/raid-models/ownrt-experiment-archives/2026-10-29/ctx131072-runs-k2'
P1, P2 = '/mnt/raid-models/ownrt-experiment-archives/2026-10-29/prefill-speed-runs-p1', '/dev/shm/prefill-speed-20261029/runs-p2'  # p1 runs archived before p2
loc = {n: P1 for n in ('S0-off', 'S0-ld', 'S0-4', 'S0-ko', 'S1-off', 'S1-mx', 'R1-off', 'R1-mx', 'R1-mx-tbt')}
loc.update({n: P2 for n in ('R0-off', 'R0-4', 'R0-4-tbt', 'R0-4-m', 'R0-ko', 'R0-ko-tbt', 'R0-ko-m')})
P = lambda n: n if n.startswith('/') else f'{loc[n]}/{n}'
rows = [  # (original phase, rank spec, a, b)
 ('m1-smoke', '0', 'S0-off', 'S0-ld'),
 ('m2-smoke', '1', 'S1-off', 'S1-mx'), ('m2-smoke', '0', 'S0-off', 'S0-4'),
 ('g1', '1', f'{K2}/g-r1-tp131k', 'R1-off'), ('g1', '1', 'R1-off', 'R1-mx'), ('g1', '1', 'R1-mx', 'R1-mx-tbt'),
 ('g1', '1', f'{K2}/g-r1-tp131k-tbt', 'R1-mx-tbt'), ('g1', 'x1', f'{K2}/g-r1-one64k', 'R1-mx'),
 ('g1', '0', f'{K2}/g-r0-tp131k', 'R0-off'), ('g1', '0', 'R0-off', 'R0-4'), ('g1', '0', 'R0-4', 'R0-4-tbt'),
 ('g1', 'x0', f'{K2}/g-r0-one64k', 'R0-4'), ('g1', '0', f'{K2}/g-r0-tp131k-m', 'R0-4-m'), ('g1', 'x0', f'{K2}/g-r0-one64k-m', 'R0-4-m'),
 ('g3', '0', f'{K2}/g-r0-tp131k', 'R0-off'), ('g3', '0', 'R0-off', 'R0-ko'), ('g3', '0', 'R0-4', 'R0-ko'), ('g3', '0', 'R0-4-tbt', 'R0-ko'),
 ('g3', 'x0', f'{K2}/g-r0-one64k', 'R0-ko'), ('g3', '0', f'{K2}/g-r0-tp131k-m', 'R0-ko-m'), ('g3', 'x0', f'{K2}/g-r0-one64k-m', 'R0-ko-m'),
 ('g3', '1', f'{K2}/g-r1-tp131k', 'R1-mx'), ('g3', '1', 'R1-mx-tbt', 'R1-mx'), ('g3', 'x1', f'{K2}/g-r1-one64k', 'R1-mx'),
 ('g3-smoke', '0', 'S0-off', 'S0-ko'),
 ('g5', '0', f'{K2}/g-r0-tp131k', 'R0-off'), ('g5', '0', 'R0-off', 'R0-ko'), ('g5', '0', 'R0-ko', 'R0-ko-tbt'), ('g5', '0', 'R0-4-tbt', 'R0-ko'),
 ('g5', 'x0', f'{K2}/g-r0-one64k', 'R0-ko'), ('g5', '0', f'{K2}/g-r0-tp131k-m', 'R0-ko-m'), ('g5', 'x0', f'{K2}/g-r0-one64k-m', 'R0-ko-m'),
 ('g5', '1', f'{K2}/g-r1-tp131k', 'R1-off'), ('g5', '1', 'R1-off', 'R1-mx'), ('g5', '1', 'R1-mx-tbt', 'R1-mx'), ('g5', '1', f'{K2}/g-r1-tp131k-tbt', 'R1-mx'),
 ('g5', 'x1', f'{K2}/g-r1-one64k', 'R1-mx'),
 ('g5-smoke', '0', 'S0-off', 'S0-ko')]
assert len(rows) == 38
if __name__ == '__main__':
    import sys
    want = sys.argv[1] if len(sys.argv) > 1 else 'all'  # 'p1': only comparisons whose r7 runs are all in runs-p1
    for ph, rk, a, b in rows:
        if want == 'p1' and not all(x.startswith('/') or loc[x] == P1 for x in (a, b)): continue
        print(f'{rk}:{P(a)}:{P(b)}')
