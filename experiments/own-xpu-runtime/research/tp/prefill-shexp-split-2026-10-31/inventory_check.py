"""Shared by the rank drivers' compare (research/tp/prefill-speed-2026-10-29): the reset-time allocation inventory
(request-state-inventory.json, every standalone non-weight allocation hashed) and the OWNRT_PREFILL_MOE_NATIVE ones
invariant. inventory(a, b): allocations present on both sides must hash equal, except the exchange control words
('*:tp-exchange-control'), which hold wait/poll statistics (timing) next to the epochs.
ones(dir) (exact form since research/tp/prefill-draft-batch-2026-10-30): the '*:prefill:moe-ones' allocation (capacity C =
prefill rows floats) is filled with 1.0 at allocation; a request reset zeroes it; every batched chunk of M rows rewrites
floats [0, M) before its sites, and its native moe_combine reads exactly those (Spec.tokens = M, one weight per row).
So at the reset that ends a request the buffer must be: the first request of the process, all C ones; a request after a
reset, k = min(C, rows per chunk, its prompt rows) ones then zeros when it was read batched, all zeros token by token.
The earlier form required all C ones at every reset, which a request after a reset whose chunks are all shorter than C
cannot meet (research/hc-kernels-2026-10-30 x1: 64-row second request, k = 64; the floats past 64 are never read). Build
r6 (no rewrite) leaves k = 0 after a batched second request and still fails."""
import hashlib, json, struct
from pathlib import Path
TIMING = (':tp-exchange-control',)
def inventories(run):
    return sorted(Path(run).glob('rank*/request-state-inventory.json'))
def expected_ones(run, sub, capacity):
    """Leading 1.0 floats the ones buffer must hold at the reset that ends request `sub` (rankN = first request, rankN-b =
    the second request, after a reset), from the driver's summary.json."""
    if not sub.endswith('-b'):
        return capacity
    s = json.loads((Path(run) / 'summary.json').read_text())
    batched = s.get('batched') if 'batched' in s else not s.get('token_prompt')
    rows, prompt = s.get('rows') or capacity, s.get('second_prompt') or 0
    return min(capacity, rows, prompt) if batched else 0
def ones(run):
    out = []
    for f in inventories(run):
        inv = json.loads(f.read_text())['standalone_target_mutable']
        for label, v in inv.items():
            if label.endswith(':prefill:moe-ones'):
                n = v['bytes'] // 4
                k = expected_ones(run, f.parent.name, n)
                want = hashlib.sha256(struct.pack(f'<{n}f', *([1.0] * k + [0.0] * (n - k)))).hexdigest()
                out.append(dict(file=f.parent.name, label=label, expected_leading_ones=k, ok=v['sha256'] == want))
    return out
def inventory(a, b, sub):
    fa, fb = Path(a) / sub / 'request-state-inventory.json', Path(b) / sub / 'request-state-inventory.json'
    if not fa.exists() or not fb.exists():
        return dict(compared=0, missing=[str(x) for x in (fa, fb) if not x.exists()])
    ia, ib = (json.loads(x.read_text())['standalone_target_mutable'] for x in (fa, fb))
    common = sorted(set(ia) & set(ib))
    timing = [k for k in common if k.endswith(TIMING)]
    differ = [k for k in common if k not in timing and ia[k]['sha256'] != ib[k]['sha256']]
    return dict(compared=len(common) - len(timing), timing_excluded=timing, differ=differ[:20], differ_count=len(differ),
                only_a=sorted(set(ia) - set(ib)), only_b=sorted(set(ib) - set(ia)))
