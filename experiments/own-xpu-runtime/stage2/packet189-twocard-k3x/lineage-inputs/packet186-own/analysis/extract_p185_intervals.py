#!/usr/bin/env python3
"""One-time, read-only extraction of packet185's measured per-interval device receipts.

Reads the five retained packet185 view rows (lane B, 2026-10-22 14:00-14:22 UTC) and writes a
compact, self-contained table (analysis/p185-intervals.json.gz) that price_v3_measured.py
replays. Packet185 is never written. Each source receipt's sha256 is recorded so the table is
checkable against the retained evidence; the table is a provenance copy, not a pin.

Per prompt: the first 99 intervals of the vendored packet85 interval model (D, A, B, R, C,
offset, elapsed, G = unresolved control gaps), and the rank-0 packet150 host scopes summed
inside the same 99-interval window (handoff_export, accept, snapshot, rollback, ...).
"""
import gzip, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P185 = HERE.parents[1] / 'packet185-twocard-unsplit-head'
sys.path.insert(0, str(P185 / 'v5'))
from interval_model import intervals, SOURCE_SHA256  # vendored packet85 model (sha 6627ffa3...)

VIEWS = ['device-view0-production-B-p185', 'device-view1-unsplit-B-p185', 'device-view2-production-B-p185',
         'device-view3-unsplit-B-p185', 'device-view4-production-B-p185']
SCOPES = ('handoff_export', 'accept', 'snapshot', 'rollback', 'token_prep', 'token_history', 'layer_body',
          'half_total', 'draft_wait', 'remote_reply_wait', 'suffix_head', 'head_service_total', 'head_hidden_wait')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    out = dict(schema='packet186.p185-intervals.v1', source_packet='experiments/own-xpu-runtime/stage2/packet185-twocard-unsplit-head',
               interval_model_sha256=SOURCE_SHA256, views=[])
    for name in VIEWS:
        root = P185 / 'v5/evidence' / name
        summary = json.loads((root / 'bracket-summary.json').read_text())
        row = summary['views'][0]
        dest = root / 'run/views' / ('00-' + row['choice'])
        view = dict(name=name, variant=summary['variant'], choice=row['choice'], rate=row['rate'],
                    bracket_summary_sha256=sha(root / 'bracket-summary.json'), prompts=[])
        for prompt in json.loads((dest / 'summary.json').read_text())['requests']:
            pid = prompt['prompt_id']
            receipt = dest / pid / 'receipt.json'
            r = json.loads(receipt.read_text())
            rows = intervals(r)
            stamps = r['token_timestamps'][:100]
            scopes = {k: 0.0 for k in SCOPES}
            counts = {k: 0 for k in SCOPES}
            for line in (dest / pid / 'rank0/timings.jsonl').read_text().splitlines():
                x = json.loads(line) if line.strip() else {}
                s = x.get('p150_segment')
                if s in scopes and stamps[0] <= x['start'] <= x['end'] <= stamps[-1]:
                    scopes[s] += x['ms']
                    counts[s] += 1
            view['prompts'].append(dict(
                prompt_id=pid, prompt_class=r['prompt_class'], receipt_sha256=sha(receipt),
                rate=99 / (stamps[99] - stamps[0]),
                intervals=[[int(x['hit']), round(x['D'], 6), round(x['A'], 6), round(x['B'], 6), round(x['R'], 6),
                            round(x['C'], 6), round(x['spec_start_offset_ms'], 6), round(x['elapsed_ms'], 6),
                            round(x['unresolved_control_gaps_ms'], 6)] for x in rows],
                scope_ms=scopes, scope_counts=counts))
        out['views'].append(view)
        print(name, view['variant'], round(view['rate'], 4), len(view['prompts']), flush=True)
    out['interval_columns'] = ['hit', 'D', 'A', 'B', 'R', 'C', 'offset', 'elapsed', 'G']
    with gzip.open(HERE / 'p185-intervals.json.gz', 'wt') as f:
        json.dump(out, f, separators=(',', ':'))
    print('wrote', HERE / 'p185-intervals.json.gz')


if __name__ == '__main__':
    main()
