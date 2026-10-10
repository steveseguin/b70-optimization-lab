#!/usr/bin/env python3
"""Frozen CPU-only packet 135 timelines; read evidence, never import runtime."""
import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, mean

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
HERE = Path(__file__).resolve().parent
SOURCES = {}


def read(path, lines=False):
    raw = path.read_bytes()
    SOURCES[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return [json.loads(x) for x in raw.splitlines() if x.strip()] if lines else json.loads(raw)


def dt(times, start, end):
    a, b = times.get(start), times.get(end)
    return None if a is None or b is None else (b-a)/1e9


def overlap(a, b, c, d):
    return max(0, min(b, d)-max(a, c))/1e9


def stats(values):
    values = sorted(x for x in values if x is not None)
    return {'n': len(values), 'median': median(values), 'mean': mean(values),
            'min': min(values), 'max': max(values)} if values else None


def collect(session, first, last):
    client = Path('/home/steve/ltx-stream')/session
    manifest = read(client/'manifest.jsonl', True)
    state = read(client/'client-state.json')
    run = ROOT/state['server_run']
    rs, ds, ps = {}, {}, {}
    for i in range(first-1, last+2):
        for table, kind in ((rs, 'receipt'), (ds, 'decode'), (ps, 'preview')):
            path = run/'receipts'/f'{kind}-stream135-s{i:08}.json'
            table[i] = read(path)
    assert all(x['server_identity_sha256'] == manifest[0]['server_identity_sha256'] for x in rs.values())
    maintenance = {e['sequence']: e for r in rs.values() for e in r.get('maintenance', {}).get('events', [])}
    schedule = {e['sequence']: e for r in rs.values() for e in r.get('maintenance_schedule', {}).get('events', [])}
    rows = []
    for i in range(first, last+1):
        r, n, d, p, prev_d, prev_p = rs[i], rs[i+1], ds[i], ps[i], ds[i-1], ps[i-1]
        t, origin = r['timing_ns'], r['timing_ns']['submit']
        mark = n['turnaround']['marks_ns']
        end = n['timing_ns']['submit']
        assert mark['submit'] == end
        before = {x['label']: x for x in r['snapshots']}
        elapsed = lambda group: {k: None if v is None else (v-origin)/1e9 for k, v in group.items()}
        metrics = {
            'period_to_next_destination': (end-origin)/1e9,
            'period_from_previous_destination': (origin-rs[i-1]['timing_ns']['submit'])/1e9,
            'pre_sampler': dt(t, 'submit', 'sampler_a_start'),
            'text_window': dt(t, 'condition_a_done', 'stream_text_start'),
            'anchor_node_bounds': dt(t, 'anchor_start', 'condition_a_start'),
            'request_snapshot_outer': dt(t, 'request_snapshot_start', 'request_snapshot_done'),
            'request_snapshot_inner': before['request-before']['seconds'],
            'A_before': before['A-before']['seconds'], 'A_after': before['A-after']['seconds'],
            'A_consume': r['timing_s']['submit_split']['stage_a_consume'],
            'A_lookup': dt(t, 'condition_a_start', 'condition_a_lookup_done'),
            'A_tail': dt(t, 'condition_a_lookup_done', 'condition_a_done'),
            'sampler_A': dt(t, 'sampler_a_start', 'stage_a_done'),
            'A_to_B': dt(t, 'stage_a_done', 'sampler_b_start'),
            'sampler_B': dt(t, 'sampler_b_start', 'stage_b_done'),
            'B_done_to_anchor': dt(t, 'stage_b_done', 'anchor_ready'),
            'cone_chain': r['timing_s']['video_decode_in_chain'],
            'anchor_to_receipt': dt(t, 'anchor_ready', 'receipt_staged'),
            'receipt_to_next_submit': dt(mark, 'receipt_staged', 'submit'),
            'commit_written_to_served': dt(mark, 'commit_written', 'first_served'),
            'executor_exit_to_served': dt(mark, 'executor_exit', 'first_served'),
            'own_go_wait': d['schedule']['go_wait_s'],
            'own_decode_fifo': d['timing_s']['queue_wait'],
            'own_A_precompute': dt(d['timing_ns'], 'precompute_a_start', 'precompute_a_done'),
            'own_A_native_encode': d['precompute']['A']['record']['encode_s'],
            'previous_display_end_relative_submit': (prev_d['timing_ns']['display_done']-origin)/1e9,
            'previous_tail_end_relative_submit': (prev_d['timing_ns']['record_staged']-origin)/1e9,
            'previous_preview_end_relative_submit': (prev_p['timing_ns']['preview_written']-origin)/1e9,
            'previous_preview_lead_to_receipt': (t['receipt_staged']-prev_p['timing_ns']['preview_written'])/1e9,
            'previous_display_request_snapshot_overlap': overlap(prev_d['timing_ns']['display_start'], prev_d['timing_ns']['display_done'], t['request_snapshot_start'], t['request_snapshot_done']),
            'previous_tail_request_snapshot_overlap': overlap(prev_d['timing_ns']['display_done'], prev_d['timing_ns']['record_staged'], t['request_snapshot_start'], t['request_snapshot_done']),
            'previous_preview_request_snapshot_overlap': overlap(prev_p['timing_ns']['write_start'], prev_p['timing_ns']['preview_written'], t['request_snapshot_start'], t['request_snapshot_done']),
            'manual_maintenance_overlap_period': sum(overlap(origin, end, e['timing_ns']['gc_start'], e['timing_ns']['cache_done']) for e in maintenance.values()),
            'manual_maintenance_overlap_handoff': sum(overlap(mark['commit_written'], mark['first_served'], e['timing_ns']['gc_start'], e['timing_ns']['cache_done']) for e in maintenance.values()),
        }
        groups = {'prompt': t, 'nodes': r['node_starts_ns'], 'prior_decode': prev_d['timing_ns'],
                  'prior_preview': prev_p['timing_ns'], 'own_decode': d['timing_ns'],
                  'own_preview': p['timing_ns'], 'receipt_to_next': mark}
        rows.append({'source_seq': i, 'next_destination_seq': i+1, 'origin_ns': origin,
                     'prompt_changed': r['prompt_changed'], 'reuse_text': r['reuse_text'],
                     'metrics_s': metrics, 'marks_ns': groups,
                     'marks_relative_submit_s': {k: elapsed(v) for k, v in groups.items()},
                     'snapshots': r['snapshots'], 'timing_s': r['timing_s'],
                     'decode_timing_s': d['timing_s'], 'preview_timing_s': p['timing_s'],
                     'turnaround_to_next': n['turnaround'],
                     'conditioning': {k: {'source': v.get('source'), 'waited_s': v.get('waited_s'),
                                          'precompute_timing_ns': (v.get('precompute') or {}).get('timing_ns')}
                                      for k, v in r['conditioning_sources'].items()},
                     'schedule': d['schedule'],
                     'text': {k: v for k, v in r['text'].items() if k != 'tensors'}})
    def summarize(selected):
        return {key: stats([x['metrics_s'][key] for x in selected]) for key in rows[0]['metrics_s']}
    return {'run': str(run), 'session': session, 'identity': manifest[0]['server_identity_sha256'],
            'client_manifest_rows_at_capture': len(manifest), 'source_range': [first, last],
            'destination_range': [first+1, last+1], 'n': len(rows), 'rows': rows,
            'summary': summarize(rows),
            'source_parity': {str(k): summarize([r for r in rows if r['source_seq']%2 == k]) for k in range(2)},
            'source_modulo4': {str(k): summarize([r for r in rows if r['source_seq']%4 == k]) for k in range(4)},
            'maintenance_events': list(maintenance.values()), 'maintenance_schedule_events': list(schedule.values()),
            'checks': {'every_A_precomputed': all(r['conditioning_sources']['A']['source'] == 'precomputed' for r in rs.values()),
                       'every_cone_equal': all(d['anchor_decode']['equal'] is True for d in ds.values()),
                       'all_six_snapshots': all(len(r['snapshots']) == 6 for r in rs.values())}}


def main():
    runs = {session: collect(session, start, end) for session, start, end in
            [('s135-gc10-live01', 10, 129), ('s135-live01', 10, 119)]}
    checks = {'script_ast': bool(ast.parse(Path(__file__).read_text())),
              'at_least_40_consecutive_gc10': runs['s135-gc10-live01']['n'] >= 40,
              'all_structural_checks': all(all(r['checks'].values()) for r in runs.values()),
              'all_bucket_sums_close': all(abs(sum(row['metrics_s'][x] for x in ('pre_sampler', 'sampler_A', 'A_to_B', 'sampler_B', 'B_done_to_anchor', 'anchor_to_receipt', 'receipt_to_next_submit'))-row['metrics_s']['period_to_next_destination']) < 1e-8 for r in runs.values() for row in r['rows'])}
    assert all(checks.values()), checks
    output = {'schema': 'ltx.continuation137.cpu-timeline.v1', 'captured_utc': datetime.now(timezone.utc).isoformat(),
              'parity': 'period ending at destination s = submit(s)-submit(s-1); own buckets are source s-1',
              'scope': 'CPU read-only evidence; no runtime imports, GPU, endpoint, or benchmark execution',
              'runs': runs, 'sources': SOURCES, 'structural_checks': checks}
    (HERE/'timelines.json').write_text(json.dumps(output, indent=2)+'\n')
    render_markdown(runs['s135-gc10-live01'])
    for name, run in runs.items():
        print(name, run['n'], 'consecutive source chunks', run['source_range'])
        for mod, summary in run['source_modulo4'].items():
            print('mod4', mod, {k: round(summary[k]['median'],6) for k in ('period_to_next_destination','pre_sampler','text_window','commit_written_to_served','own_go_wait')})
    print('Structural checks:', sum(checks.values()), '/', len(checks))


def render_markdown(run):
    rows = [r for r in run['rows'] if 10 <= r['source_seq'] <= 59]
    out = ['# Packet 137: 50 consecutive saved GC10 timelines', '',
           'Source chunks 10–59, destination periods 11–60. Every row is retained, including outliers. '
           'Seconds are rounded to milliseconds in this companion; [timelines.json](timelines.json) '
           'retains every available integer prompt/node/decode/preview/turnaround mark, '
           'all timing buckets and snapshot parts for 120 consecutive GC10 chunks plus 110 GC60 chunks. '
           'The JSON also records each input path, byte count and SHA256. These are saved wall-clock '
           'observations, not new runtime measurements.', '',
           'Intervals below are relative to the source chunk’s submit unless identified as durations. '
           'Predecessor decode/display/tail/preview belongs to source minus one; it overlaps source sampling. '
           'Own decode prepares the successor after publishing the source anchor. The preview encoder '
           'is a separate worker. Period means submit(source+1) minus submit(source).', '']
    def table(title, heads, value):
        out.extend(['## '+title, '', '| Source | '+' | '.join(heads)+' |',
                    '| ---: | '+' | '.join(['---:']*len(heads))+' |'])
        for row in rows:
            vals = value(row)
            out.append('| '+str(row['source_seq'])+' | '+' | '.join(str(x) if isinstance(x, str) else ('—' if x is None else f'{x:.3f}') for x in vals)+' |')
        out.append('')
    table('Chain durations', ['Period → next','Pre-A','Sampler A','A→B','Sampler B','B→anchor','Anchor→receipt','Receipt→submit'],
          lambda r: [r['metrics_s'][x] for x in ('period_to_next_destination','pre_sampler','sampler_A','A_to_B','sampler_B','B_done_to_anchor','anchor_to_receipt','receipt_to_next_submit')])
    table('Pre-A durations', ['Fresh text','Request outer','Request inner','Anchor bounds','A lookup','A-before','Consume','A-after','A tail','Text window'],
          lambda r: [str(r['prompt_changed'])]+[r['metrics_s'][x] for x in ('request_snapshot_outer','request_snapshot_inner','anchor_node_bounds','A_lookup','A_before','A_consume','A_after','A_tail','text_window')])
    table('Other submit split durations', ['Precheck','Validate/queue','Queue→executor','Authority begin','Before checks','Before tail','Executor→node','Node→A','Dispatch→A','Other'],
          lambda r: [r['timing_s']['submit_split'][x] for x in ('precheck','comfy_validate_queue','queue_to_executor','authority_begin','before_request_checks','before_request_tail','executor_to_first_node','first_node_to_condition_a','dispatch_to_sampler_a','other')])
    def interval(r, group, a, b):
        t = r['marks_relative_submit_s'][group]
        return f'{t[a]:.3f}–{t[b]:.3f}'
    table('Prompt and handoff marks', ['Request snapshot','Anchor→A lookup','A tail','Text→A start','Receipt staged','Commit','Written','Executor exit','First served','Next submit'],
          lambda r: [interval(r,'prompt','request_snapshot_start','request_snapshot_done'), interval(r,'prompt','anchor_start','condition_a_start'),
                     interval(r,'prompt','condition_a_lookup_done','condition_a_done'),interval(r,'prompt','stream_text_start','sampler_a_start')]+
                    [r['marks_relative_submit_s']['receipt_to_next'][x] for x in ('receipt_staged','commit','commit_written','executor_exit','first_served','submit')])
    def snap(r, label):
        s = next(s for s in r['snapshots'] if s['label']==label)
        return f"{(s['start_ns']-r['origin_ns'])/1e9:.3f}–{(s['end_ns']-r['origin_ns'])/1e9:.3f}"
    table('Every snapshot interval', ['Request-before','A-before','A-after','B-before','B-after','Request-after'],
          lambda r: [snap(r, x) for x in ('request-before','A-before','A-after','B-before','B-after','request-after')])
    table('Predecessor decode and preview beside this request', ['A prep','Go','B prep','Display','Audio/tail','Preview encode','Preview slack→receipt'],
          lambda r: [interval(r,'prior_decode','precompute_a_start','precompute_a_done'),r['marks_relative_submit_s']['prior_decode']['go'],
                     interval(r,'prior_decode','precompute_b_start','precompute_b_done'),interval(r,'prior_decode','display_start','display_done'),
                     interval(r,'prior_decode','display_done','record_staged'),interval(r,'prior_preview','write_start','preview_written'),r['metrics_s']['previous_preview_lead_to_receipt']])
    table('Source decode and preview preparing the next request', ['Decode start','Cone done','Anchor ready','A prep','Go','B prep','Display','Audio/tail','Preview encode','Go wait duration'],
          lambda r: [r['marks_relative_submit_s']['own_decode'][x] for x in ('decode_start','video_done','anchor_ready')]+
                    [interval(r,'own_decode','precompute_a_start','precompute_a_done'),r['marks_relative_submit_s']['own_decode']['go'],
                     interval(r,'own_decode','precompute_b_start','precompute_b_done'),interval(r,'own_decode','display_start','display_done'),
                     interval(r,'own_decode','display_done','record_staged'),interval(r,'own_preview','write_start','preview_written'),r['metrics_s']['own_go_wait']])
    out.extend(['The A tail contains A-before, consume and A-after; those are nested intervals and must not be added twice. '
                'The first-node→condition-A bucket encloses the anchor node. Independent bucket medians need not sum '
                'to a median period. The script verifies exact per-row chain telescoping before rounding.', ''])
    (HERE/'timelines.md').write_text('\n'.join(out))


if __name__ == '__main__':
    main()
