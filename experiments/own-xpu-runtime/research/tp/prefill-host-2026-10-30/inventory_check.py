"""Shared by the rank drivers' compare (research/tp/prefill-speed-2026-10-29): the reset-time allocation inventory
(request-state-inventory.json, every standalone non-weight allocation hashed) and the OWNRT_PREFILL_MOE_NATIVE ones
invariant. ones(dir): every '*:prefill:moe-ones' allocation must hold only 1.0f at every reset of the run (a reset zeroes
it; build r6 never rewrote it). inventory(a, b): allocations present on both sides must hash equal, except the exchange
control words ('*:tp-exchange-control'), which hold wait/poll statistics (timing) next to the epochs."""
import hashlib, json, struct
from pathlib import Path
TIMING = (':tp-exchange-control',)
def inventories(run):
    return sorted(Path(run).glob('rank*/request-state-inventory.json'))
def ones(run):
    out = []
    for f in inventories(run):
        inv = json.loads(f.read_text())['standalone_target_mutable']
        for label, v in inv.items():
            if label.endswith(':prefill:moe-ones'):
                want = hashlib.sha256(struct.pack(f'<{v["bytes"] // 4}f', *([1.0] * (v['bytes'] // 4)))).hexdigest()
                out.append(dict(file=f.parent.name, label=label, ok=v['sha256'] == want))
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
