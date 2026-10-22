#!/usr/bin/env python3
"""Price the resume-queue item (b), fill pacing/deferral on the packet176c line. CPU only.

Inputs (all retained; nothing re-measured):
- evidence/analyzer-real-parent.json (this packet): fill split on packet171b's real spin
  streams (the A arm of packet176 is the same spin/copy configuration);
- packet176c-chain/derived-chain.json (tracked): the packet176 v5 bracket rates;
- the packet176 v5 per-view readout values, transcribed from the coordinator's session
  record (tool output 2026-10-19T12:00:13Z, read of
  packet176-onecard-kernelio/screen/evidence/card0-176-v5-a/resident/WSCREEN/summary.json,
  sha256 ad74c8ef... per derived-chain.json); that summary was never committed and was
  removed with the untracked files on 2026-10-19 21:42 EDT.
Writes evidence/fill-lever-price.json. Decision rule (brief rule 8): build only at >= +2%.
"""
import json, subprocess
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
RECORD = 34.57303759192858
# Transcribed packet176 v5 mechanism readout (per view): wall_ms, transfer_wall_ms, slow_readback_fraction.
P176 = {'A0': (29.0907, 1.19, 0.4055), 'B0': (27.6569, 0.0119, 0.0), 'A1': (28.754, 1.1806, 0.4003),
        'B1': (27.6569, 0.0119, 0.0), 'A2': (28.7488, 1.1801, 0.4009)}
P176_SOURCE = ('coordinator session transcript 9743941a-5875-4449-b2f0-62a6e15d94f5, tool result at 2026-10-19T12:00:13.424Z '
               '(mechanism_readout views of card0-176-v5-a WSCREEN summary.json, digest ad74c8efd7b4984bddffadc36e8c88f54357381ae4ffadd3920f7998458ce9e3)')


def main():
    a = json.loads((P / 'evidence/analyzer-real-parent.json').read_text())
    r171 = next(r for r in a['records'] if r['name'] == 'packet171b')['mechanism_readout']
    derived = json.loads(subprocess.run(['git', '-C', str(ROOT), 'show', 'HEAD:experiments/own-xpu-runtime/stage2/packet176c-chain/derived-chain.json'],
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True).stdout)
    rates = derived['bracket']['rates']
    warm_a = [r171['views'][v] for v in ('A1', 'A2')]
    a_split = [v['fill_split'] for v in warm_a]
    a_ceiling = sum(s['fill_attributable_outside_transfer_ms_per_token'] for s in a_split) / 2
    a_filled_excess = sum(s['fill_attributable_outside_transfer_ms_per_filled_token'] for s in a_split) / 2
    a_wall = sum(P176[v][0] for v in ('A1', 'A2')) / 2
    a_transfer = sum(P176[v][1] for v in ('A1', 'A2')) / 2
    b_wall = sum(P176[v][0] for v in ('B0', 'B1')) / 2
    b_transfer = sum(P176[v][1] for v in ('B0', 'B1')) / 2
    removed = a_transfer - b_transfer
    gained = a_wall - b_wall
    unrecovered = removed - gained
    b_ceiling = a_ceiling + max(0.0, unrecovered)
    v = r171['views']['A1']
    premise = (v['wall_ms_per_fill_mb'] - v['readback_ms_per_fill_mb']) * v['fill_mb_per_token']
    row = dict(
        schema='packet182.fill-lever-price.v1', passed=True, device_executed=False,
        item='CURRENT.md 2026-10-19 OWNER PAUSE resume queue (b): fill pacing/deferral on the packet176c line',
        premise=dict(text='p176 readout shows ~1.0 ms/token of wall outside the transfer window (fill cost moved)',
                     arithmetic=f"(wall slope {v['wall_ms_per_fill_mb']} - transfer slope {v['readback_ms_per_fill_mb']}) ms/MB x "
                                f"{v['fill_mb_per_token']} MB/token = {premise:.3f} ms/token",
                     origin='pre-device packet176 README pricing on packet58as/171b/174 spin streams; the device readout printed at 12:00Z '
                            'carried no B-view slope; the resume-queue line was written 5 minutes later from the pre-device number',
                     why_not_a_fill_cost=('the slopes are fitted over FILLED tokens only; unfilled tokens show the same outside-transfer slope '
                                          f"against the NEXT token's fill bytes ({v['fill_split']['control_unfilled_outside_transfer_ms_per_next_fill_mb']} "
                                          f"vs {v['fill_split']['outside_transfer_ms_per_fill_mb_filled_tokens']} ms/MB on packet171b A1): "
                                          'fill bytes track miss intensity (fills are planned from the previous positions\' misses, '
                                          'misses are autocorrelated), and that slope prices the misses themselves, not the fills. '
                                          'packet176\'s moved_rule fires on packet171b too, where nothing moved.')),
        a_line=dict(source='packet171b real spin streams (A1/A2 = packet58as spin/copy configuration)',
                    filled_minus_unfilled_outside_transfer_ms_per_filled_token=round(a_filled_excess, 4),
                    filled_fraction=a_split[0]['filled_fraction'], fill_mb_per_filled_token=a_split[0]['fill_mb_per_filled_token'],
                    ceiling_ms_per_token=round(a_ceiling, 4)),
        packet176_bracket=dict(rates_tok_s=rates, minimum_gain=derived['bracket']['minimum_gain'], exact_requests=derived['bracket']['exact_requests'],
                               views=P176, view_fields=['wall_ms', 'transfer_wall_ms', 'slow_readback_fraction'], source=P176_SOURCE,
                               warm_a_wall_ms=round(a_wall, 4), b_wall_ms=round(b_wall, 4), transfer_removed_ms=round(removed, 4),
                               wall_gained_ms=round(gained, 4), not_recovered_ms=round(unrecovered, 4)),
        b_line=dict(ceiling_ms_per_token=round(b_ceiling, 4), ceiling_fraction_of_wall=round(b_ceiling / b_wall, 5),
                    ceiling_speed_gain=round(b_wall / (b_wall - b_ceiling) - 1, 5),
                    meaning='if fills became completely free on the kernel-I/O line (impossible: ~61 MB per filled token still crosses PCIe)'),
        realistic=dict(range_speed_gain=[0.0, 0.003],
                       why=['pacing/deferral moves the same bytes; packet174: total bytes, not their placement, set the cost (fill kick -0.02%)',
                            'on the B line 94% of the removed transfer wait already became wall gain: fills overlap compute',
                            'the remaining filled-token excess may be publication staleness (more misses on the stale-table position), which pacing cannot touch']),
        do_not_repeat=['packet174: do not pace or re-time fills inside the token while they show zero absorption (total bytes set the cost)',
                       'packet171b: reopen foreground-copy moves only together with a change to fill scheduling or volume',
                       'packet174: tune admission only once fills overlap compute (now true on the B line, but fills ~free => only prefetch helps)'],
        decision=dict(build=False, rule='brief rule 8: a chain only at >= +2% expected gain', ceiling_below_rule=b_ceiling / (b_wall - b_ceiling) < 0.02,
                      next='packet182: re-bracket packet176 kernel I/O (+3.87% measured, never chained correctly; evidence lost) with a repaired win-path chain'),
        record_threshold_tok_s=RECORD, packet176_b_rate_vs_record=round(min(rates[1], rates[3]) / RECORD - 1, 5))
    assert row['decision']['ceiling_below_rule']
    (P / 'evidence/fill-lever-price.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps(dict(premise_ms=round(premise, 3), a_ceiling=row['a_line']['ceiling_ms_per_token'], b_ceiling=row['b_line'],
                          not_recovered=row['packet176_bracket']['not_recovered_ms'], vs_record=row['packet176_b_rate_vs_record'])))


if __name__ == '__main__':
    main()
