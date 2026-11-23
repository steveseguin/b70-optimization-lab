#!/usr/bin/env python3
# spec-sim.py <log>...: guess-count rules simulated on INK_DRAFT_LOG files (ink_run with INK_ORACLE = the plain run's
# ids): each line = how many of the drafter's 7 guesses lead the plain text, then their probabilities. Keep chance by
# probability tenth from the logs; check costs (ms, steps of 1-4 tokens measured on card 2, 5-8 extrapolated +2.8 ms per
# token); drafting 1.4 + 0.45 ms per guess. Prints tokens per second for limits of 3, 4, 5 and 7 guesses.
import sys
cost = [None, 11.4, 14.9, 17.4, 20.4, 23.2, 26.0, 28.8, 31.6]
def dcost(n): return 0.0 if n == 0 else 1.4 + 0.45 * n
rounds = {}
for p in sys.argv[1:]:
    rows = []
    for l in open(p):
        f = l.split(); rows.append((int(f[0]), [float(x) for x in f[1:]]))
    rounds[p] = rows
nb = [0] * 10; kb = [0] * 10
for rows in rounds.values():
    for m, pr in rows:
        for j, q in enumerate(pr):
            if j > m: break
            b = min(9, int(q * 10)); nb[b] += 1; kb[b] += (j < m)
qk = [kb[b] / nb[b] if nb[b] else 0.1 for b in range(10)]
print('keep by bucket:', ' '.join(f'{b/10:.1f}:{kb[b]}/{nb[b]}' for b in range(10)))
def policy(pr, kmax):
    best, bk, ex, pp = 1.0 / cost[1], 0, 1.0, 1.0
    for j in range(min(kmax, len(pr))):
        pp *= qk[min(9, int(pr[j] * 10))]; ex += pp
        if ex / cost[j + 2] > best: best, bk = ex / cost[j + 2], j + 1
    return bk
for p, rows in rounds.items():
    res = []
    for kmax in (3, 4, 5, 7):
        tok = ms = 0.0
        for m, pr in rows:
            k = policy(pr[:kmax], kmax)
            tok += 1 + min(m, k); ms += cost[k + 1] + dcost(min(kmax, len(pr)))
        res.append(f'max{kmax}: {1000 * tok / ms:6.1f} tok/s')
    print(f'{p} rounds {len(rows):4d} | ' + ' | '.join(res))
