"""Fail-closed admission for the nonqualifying autoregressive MTP probe."""
def validate(args, *, window=False):
    if not getattr(args, 'mtp_k2_probe', False):
        return
    def need(condition, why):
        if not condition:
            raise RuntimeError('MTP k2 probe: '+why)
    need(getattr(args, 'diagnostic_unsealed', False), '--diagnostic-unsealed required; never qualifying')
    need(args.draft_rank == 1 and args.target_split == 23, 'requires 23/25 draft rank 1')
    need(args.context == 4096 or getattr(args, 'mini', False), 'requires context 4096')
    need(getattr(args, 'draft_fault', 'none') == 'none', 'fault injection not supported')
    if window:
        need(args.window in ('W2m', 'W2mc', 'W2m-exact', 'W2m-speed', 'WS', 'WS64x', 'WS64', 'WS128x', 'WS128'), 'requires an MTP window')
    else:
        need(args.draft == 'mtp', 'requires the official MTP provider')

def mark(row, args):
    if getattr(args, 'mtp_k2_probe', False):
        row.update(mtp_k2_probe=True, diagnostic_unsealed=True, qualifying=False,
                   diagnostic=True, diagnostic_for_speed=True, no_speed_claim=True)
    return row
