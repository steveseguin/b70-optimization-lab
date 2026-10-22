"""Packet184 row report: every gate of the two-card checkpoint rows, judged after the lane release.

Reads only the worker's staged receipts (run/lifecycle-inputs.json) and the checkpoint manifests on
disk (run/checkpoints/<id>/manifest.json, or the copy the worker kept before the delete tool ran).
Pure CPU. A failed gate makes the summary passed=false with the first failing gate named; it is a
FAILURE of the row, never retried. Reported (never gated): save/restore seconds and bytes, cold
prefill vs restore, append prefill per token, decode rates, the cross-engine (packet180 one-card)
agreement of the saved history.
"""
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
LABEL, CONTRACT = 'experimental-two-card', 'v1.2+p184'


def read(path):
    return json.loads(Path(path).read_text())


def manifest(run, cid):
    for path in (run / 'checkpoints' / cid / 'manifest.json', run / (cid + '-manifest-copy') / 'manifest.json'):
        if path.exists():
            return read(path), hashlib.sha256(path.read_bytes()).hexdigest()
    raise FileNotFoundError('manifest of ' + cid)


def blob_map(m):
    return {(rs['rank'], b['name']): (b['sha256'], b['bytes']) for rs in m['ranks'] for b in rs['blobs']}


def same_state(a, b):
    ba, bb = blob_map(a), blob_map(b)
    diff = sorted(f'rank{k[0]}/{k[1]}' for k in set(ba) | set(bb) if ba.get(k) != bb.get(k))
    ts = all(a['token_state'][k] == b['token_state'][k] for k in ('position', 'next_token', 'tokens_sha256', 'token_history'))
    return dict(passed=not diff and ts and a['draft']['position'] == b['draft']['position'], blobs=len(ba), differing=diff[:16], token_state_equal=ts)


def analyze(run):
    run = Path(run)
    x = read(run / 'lifecycle-inputs.json')
    legs = {leg['leg']: leg for leg in x['legs']}
    gates, reported = {}, {}

    def gate(name, ok, **detail):
        gates[name] = dict(passed=bool(ok), **detail)

    oracle = x.get('oracle')
    K, M = x['K'], x['M']
    P = x['prompt_tokens']
    tools = x['tools']
    for name, row in tools.items():
        if name.startswith(('metadata:', 'full:')):
            gate('tool ' + name, row['exit'] == 0 and row['ok'], error=row.get('error'))
    for leg in legs:
        t = run / 'legs' / leg / 'teardown.json'
        gate('leg drained ' + leg, t.exists() and read(t).get('drained') is True)
    if x['kind'] == 'smoke':
        ref = legs['leg1']['requests']['reference']
        a = legs['leg1']['requests']['save_request']
        b = legs['leg2']['requests']['resume']
        rec = legs['leg2']['restores']['s1']
        s1 = legs['leg1']['saves']['s1']
        gate('reference complete (K+M, no early stop)', len(ref['tokens']) == K + M, tokens=len(ref['tokens']))
        gate('reference oracle-128', oracle is None or ref['tokens'][:128] == oracle[:128], applicable=oracle is not None,
             first_mismatch=None if oracle is None else next((i for i, (p, q) in enumerate(zip(ref['tokens'], oracle)) if p != q), None))
        gate('save request == reference[0:K]', a['tokens'] == ref['tokens'][:K])
        merged = a['tokens'] + b['tokens']
        gate('merged K+M == uninterrupted reference', merged == ref['tokens'],
             first_divergence=next((i for i, (p, q) in enumerate(zip(merged, ref['tokens'])) if p != q), None), merged=len(merged))
        gate('merged draft guesses == reference', a['guesses'] + b['guesses'] == ref['guesses'], rows=[a['draft_rows'], b['draft_rows'], ref['draft_rows']])
        gate('restore record', rec['operation'] == 'same-generation-resume' and rec['position'] == P + K - 1 and rec['pending_token'] == a['tokens'][-1]
             and not rec['pending_is_stop'], record={k: rec[k] for k in ('operation', 'position', 'pending_token', 'pending_is_stop')})
        m1, sha1 = manifest(run, 's1')
        gate('checkpoint identity s1', m1['label'] == LABEL and m1['contract'] == CONTRACT and m1['lineage']['operation'] == 'save'
             and sha1 == s1['manifest_sha256'] and len(m1['ranks']) == 2 and m1['token_state']['position'] == P + K - 1)
        reported.update(
            save=dict(bytes=s1['bytes'], seconds=s1['seconds'], stage=s1['stage'], commit_seconds=s1['commit_seconds']),
            restore={k: rec[k] for k in ('restore_seconds', 'precheck_seconds', 'restored_bytes', 'ranks')},
            cold_prefix_ttft_ms=ref.get('ttft_ms'), resume_first_token_ttft_ms=b.get('ttft_ms'),
            reference_decode_tok_s=ref.get('decode_tok_s'), resume_decode_tok_s=b.get('decode_tok_s'),
            restore_plus_first_token_ms=rec['restore_seconds'] * 1000 + (b.get('ttft_ms') or 0))
    else:
        R = x['R']
        l1, l2, l3 = legs['leg1'], legs['leg2'], legs['leg3']
        a = l1['requests']['save_request']
        rnew, rref = l1['requests']['new_reference'], l1['requests']['new_oneshot']
        xr, y, x2 = l2['requests']['append'], l3['requests']['resume_s2'], l3['requests']['append_warm']
        rec2, rec3, rec4 = l2['restores']['s1'], l3['restores']['s2'], l3['restores']['s1']
        new_len = l1['new_length']
        gate('save request complete (K)', len(a['tokens']) == K)
        gate('save request oracle-128', oracle is None or a['tokens'][:128] == oracle[:128], applicable=oracle is not None)
        gate('new reference complete (M+R) and one-shot (M)', len(rnew['tokens']) == M + R and len(rref['tokens']) == M)
        gate('one-shot == new reference[0:M]', rref['tokens'] == rnew['tokens'][:M])
        gate('append == one-shot new reference[0:M]', xr['tokens'] == rnew['tokens'][:M],
             first_divergence=next((i for i, (p, q) in enumerate(zip(xr['tokens'], rnew['tokens'])) if p != q), None))
        gate('append + resume(S2) == one-shot new reference', xr['tokens'] + y['tokens'] == rnew['tokens'])
        gate('warm-process repeat append == append', x2['tokens'] == xr['tokens'] and x2['guesses'] == xr['guesses'])
        N1, N2 = rec2['position'], rec3['position']
        g = rnew['guesses']
        gate('append draft guesses == one-shot', xr['guesses'] == g[N1 - 1:N1 - 1 + len(xr['guesses'])], window=[N1 - 1, len(xr['guesses'])])
        gate('resume(S2) draft guesses == one-shot', y['guesses'] == g[N2 - 1:N2 - 1 + len(y['guesses'])], window=[N2 - 1, len(y['guesses'])])
        gate('restore records', rec2['operation'] == 'append' and rec2['appended_length'] == l1['delta_length'] and rec2['position'] == P + K - 1
             and rec3['operation'] == 'same-generation-resume' and N2 == new_len + M - 1 and rec4['operation'] == 'append')
        ms1, sha_s1 = manifest(run, 's1')
        ms2, sha_s2 = manifest(run, 's2')
        msref, _ = manifest(run, 'sref')
        ms2b, _ = manifest(run, 's2b')
        for name, (u, v) in (('state: resumed chain S2 == one-shot SREF (all blobs, both ranks)', (ms2, msref)),
                             ('state: repeat S2b == S2 (all blobs, both ranks)', (ms2b, ms2))):
            row = same_state(u, v)
            gate(name, row.pop('passed'), **row)
        gate('lineage', ms2['lineage'] == dict(operation='restore-then-save', parent=dict(checkpoint_id='s1', manifest_sha256=sha_s1))
             and ms2b['lineage']['parent']['checkpoint_id'] == 's1' and all(m['label'] == LABEL and m['contract'] == CONTRACT for m in (ms1, ms2, msref, ms2b)))
        gate('delete s2b', tools['delete:s2b']['exit'] == 0 and tools['delete:s2b']['deleted'] and tools['after-delete:s2b']['exit'] == 1
             and (tools['after-delete:s2b'].get('error') or {}).get('check') == 'visibility')
        delta = x.get('append_delta') or {}
        reported.update(
            saves={cid: dict(bytes=l['saves'][cid]['bytes'], seconds=l['saves'][cid]['seconds'], stage=l['saves'][cid]['stage'])
                   for l in (l1, l2, l3) for cid in l.get('saves', {})},
            restores={name: {k: r[k] for k in ('operation', 'restore_seconds', 'precheck_seconds', 'restored_bytes', 'appended_length')}
                      for name, r in (('s1-append', rec2), ('s2-resume', rec3), ('s1-append-warm', rec4))},
            cold_new_prompt_ms=rnew.get('prompt_wall_ms'), append_prompt_ms=xr.get('prompt_wall_ms'),
            append_prompt_ms_per_token=(xr.get('prompt_wall_ms') or 0) / max(1, l1['delta_length'] + 1),
            tp1_saved_history_sha256=delta.get('tp1_saved_history_sha256'), tp1_pending_token=delta.get('tp1_pending_token'),
            tp2_saved_tokens_sha256=ms1['token_state']['tokens_sha256'], tp2_pending_token=ms1['token_state']['next_token'],
            tp1_tp2_saved_history_agree=(None if delta.get('tp1_saved_history_sha256') is None else
                                         ms1['token_state']['tokens_sha256'] == delta['tp1_saved_history_sha256'] and ms1['token_state']['next_token'] == delta['tp1_pending_token']))
    failed = [name for name, row in gates.items() if not row['passed']]
    return dict(schema='packet184.lifecycle-report.v1', kind=x['kind'], passed=not failed, first_failed_gate=failed[0] if failed else None,
                gates=gates, reported=reported, device_executed=x.get('device_executed', False), label=LABEL, contract=CONTRACT,
                not_claimed='no speed claim; restore/save timings are observations of this window')
