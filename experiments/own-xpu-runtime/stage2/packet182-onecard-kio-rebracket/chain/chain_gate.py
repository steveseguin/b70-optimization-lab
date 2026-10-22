#!/usr/bin/env python3
"""Packet182 win-path chain rule (read-only). Prints CHAIN ... or NOCHAIN ...; exit 0 either way, 2 if unreadable.

A record chain is derived and launched only if the packet182 v5 bracket summary shows
- passed, device_executed, candidate_beats_all_controls, control drift <= 3%;
- 5 views x 12 requests, every request passed and exact against the oracle;
- minimum gain of both B views over the best warm A control >= +2.0% (brief rule 8);
- the slower B view >= 1.02 x the live one-card record threshold
  (scripts/packet58_onecard_record_threshold.json, last record; 34.573038 tok/s on 2026-10-22).
The v5 gate itself (+0.5%) is unchanged; this is only the chain rule on top of it.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MIN_GAIN = 0.02
RECORD_MARGIN = 1.02


def decide(summary_path):
    s = json.loads(Path(summary_path).read_text())
    ledger = json.loads((ROOT / 'scripts/packet58_onecard_record_threshold.json').read_text())
    record = ledger['records'][-1]['threshold_tok_s']
    views = s.get('views') or []
    requests = [r for v in views for r in v.get('requests', [])]
    rates = s.get('rates') or []
    reasons = []
    if not (s.get('passed') is True and s.get('device_executed') is True):
        reasons.append('bracket summary did not pass')
    if s.get('candidate_beats_all_controls') is not True:
        reasons.append('v5 gate failed (candidate_beats_all_controls false)')
    if not (s.get('control_drift_passed') is True and (s.get('control_drift_fraction') or 1) <= 0.03):
        reasons.append('control drift')
    if not (len(views) == 5 and len(requests) == 60 and all(r.get('passed') is True and r.get('exact_oracle') is True for r in requests)):
        reasons.append('not 60/60 exact')
    gain = s.get('minimum_gain_vs_best_control')
    if not (type(gain) in (int, float) and gain >= MIN_GAIN):
        reasons.append(f'minimum gain {gain} below +2%')
    b = [rates[1], rates[3]] if len(rates) == 5 else []
    if not (b and min(b) >= RECORD_MARGIN * record):
        reasons.append(f'slower B {min(b) if b else None} below 1.02 x record {record}')
    word = 'CHAIN' if not reasons else 'NOCHAIN'
    return f'{word} rates={rates} min_gain={gain} record={record} ' + ('; '.join(reasons) if reasons else 'all chain rules pass')


if __name__ == '__main__':
    try:
        print(decide(sys.argv[1]))
    except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
        print('NOCHAIN unreadable: ' + str(e))
        raise SystemExit(2)
