"""Packet171b mechanism readout, kept on every outcome (win, neutral or loss).

Per view: token/error readback bimodality, the probability that a slow readback
follows a fill-submission token, and the slow-token wait excess. Definitions are
those of packet171 measure_58as_host.py: decode tokens with generated_index >= 2;
a readback is slow when transfer_wall_ms > 1.0; a fill-submission token is one
whose pre-enqueue host span (wall - prepare - enqueue - wait - transfer) exceeds
1.8 ms. These are device-run measurements; nothing here is a data-proof cutoff.
"""
import json
import statistics as st
from pathlib import Path

SLOW_MS = 1.0
FILL_OTHER_MS = 1.8


def other(r):
    return r['wall_ms'] - r['prepare_ms'] - r['enqueue_loop_ms'] - r['wait_ms'] - r['transfer_wall_ms']


def view(root, prompt_ids):
    rows = []; same = [0, 0]; after = [0, 0]
    for prompt in prompt_ids:
        stream = [json.loads(s) for s in (Path(root) / prompt / 'timings.jsonl').read_text().splitlines()]
        stream = [r for r in stream if r.get('kind') == 'generated_token' and r['generated_index'] >= 2]
        for i, r in enumerate(stream):
            if other(r) > FILL_OTHER_MS:
                same[0] += 1; same[1] += r['transfer_wall_ms'] > SLOW_MS
                if i + 1 < len(stream):
                    after[0] += 1; after[1] += stream[i + 1]['transfer_wall_ms'] > SLOW_MS
        rows += stream
    if not rows:
        raise ValueError('no decode tokens for mechanism readout')
    slow = [r for r in rows if r['transfer_wall_ms'] > SLOW_MS]
    fast = [r for r in rows if r['transfer_wall_ms'] <= SLOW_MS]
    mean = lambda rs, k: round(st.mean(r[k] for r in rs), 4) if rs else None
    return dict(
        tokens=len(rows), wall_ms=mean(rows, 'wall_ms'), wait_ms=mean(rows, 'wait_ms'),
        transfer_wall_ms=mean(rows, 'transfer_wall_ms'),
        median_transfer_wall_ms=round(st.median(r['transfer_wall_ms'] for r in rows), 4),
        slow_readback_fraction=round(len(slow) / len(rows), 4),
        slow_transfer_wall_ms=mean(slow, 'transfer_wall_ms'), fast_transfer_wall_ms=mean(fast, 'transfer_wall_ms'),
        slow_token_wait_excess_ms=round(mean(slow, 'wait_ms') - mean(fast, 'wait_ms'), 4) if slow and fast else None,
        p_slow_readback_after_fill_token=round(after[1] / after[0], 4) if after[0] else None,
        p_slow_readback_on_fill_token=round(same[1] / same[0], 4) if same[0] else None,
        fill_tokens=same[0])


def readout(run_root, labels, prompt_ids, candidate_wins):
    views = {label: view(Path(run_root) / label, prompt_ids) for label in labels}
    controls = [views[l] for l in ('A1', 'A2') if l in views]
    candidates = [views[l] for l in ('B0', 'B1') if l in views]
    collapsed = bool(controls and candidates) and max(c['slow_readback_fraction'] for c in candidates) <= \
        0.5 * min(a['slow_readback_fraction'] for a in controls)
    if candidate_wins and collapsed:
        verdict = 'confirmed: foreground readbacks queued behind fills on the shared copy ordinal'
    elif not candidate_wins and not collapsed:
        verdict = 'close row 1: slow mode persists; attribute the ~2.6 ms readback to fill/PCIe contention'
    else:
        verdict = 'mixed: speed and slow-mode collapse disagree; record and review before any follow-up'
    return dict(schema='packet171b.mechanism.v1', definitions=dict(
        slow_readback_ms=SLOW_MS, fill_token_other_ms=FILL_OTHER_MS, tokens='generated_index >= 2'),
        views=views, slow_mode_collapsed=collapsed, collapse_rule='max B slow fraction <= 0.5 x min warm A slow fraction',
        candidate_wins=bool(candidate_wins), verdict=verdict)
