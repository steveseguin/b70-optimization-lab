"""Join retained real packet154 host scopes to each emission interval.

The narrowest enclosing host scope wins; asynchronous pending residence is
fallback only. These are host occupancy partitions, never GPU busy times.
"""
import argparse
import gzip
import hashlib
import json
import math
import resource
import statistics as st

from analyze import P, S, read, load, require, method, record, validate_request, csv_bytes, PINS
from audit import guard

REQUIRED1 = {'command','b_issue','b_completion','b_import','hidden_export_issue',
    'hidden_export_completion','prefix_pack','prefix_export','wait_rank0_suffix',
    'merge_import','merge_compute','draft_issue','draft_completion_pending',
    'draft_completion_host','draft_publication','reply_publication','wait_rank0_command'}
CONTAINERS = {'command','half_total','half_total_rank1','head_service_total'}


def stream(raw, rank):
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    rows = [r for r in rows if 'p154_segment' in r]
    require(rows, 'empty timing stream')
    require(not rank or REQUIRED1 <= {r['p154_segment'] for r in rows}, 'incomplete rank1 scopes')
    for r in rows:
        require(r['rank'] == rank and type(r['sequence']) is int and type(r['position']) is int
                and type(r['op']) is int, 'scope identity')
        require(all(math.isfinite(r[k]) for k in ('start','end','ms')) and r['start'] <= r['end']
                and abs((r['end']-r['start'])*1000-r['ms']) < .02, 'scope clock')
    require(len({(r['sequence'],r['op'],r['position'],r['p154_segment'],r['start'],r['end']) for r in rows}) == len(rows), 'duplicate scope')
    return rows


def partition(start, end, scopes):
    active = [r for r in scopes if r['p154_segment'] not in CONTAINERS
              and r['start'] < end and r['end'] > start]
    edges = sorted({start,end,*[max(start,r['start']) for r in active],
                    *[min(end,r['end']) for r in active]})
    out = {}
    for a,b in zip(edges,edges[1:]):
        covering = [r for r in active if r['start'] <= a and r['end'] >= b]
        name = 'unassigned'
        if covering:
            r = min(covering, key=lambda r: (r['p154_segment']=='draft_completion_pending', r['end']-r['start']))
            name = r['p154_segment']
        out[name] = out.get(name,0.)+(b-a)*1000
    require(abs(sum(out.values())-(end-start)*1000) < 1e-6, 'exclusive partition conservation')
    return out


def analyze():
    _, originals = record()
    replay = method()
    parent = S/'packet156-draft-slack'
    bound = load(parent/'evidence/bracket-bound.json')
    require(bound['passed'] and bound['complete_original_analyzer_replay'], 'retained source qualification')
    entries = {e['source']: e for e in bound['inputs']}
    require(len(entries) == len(bound['inputs']), 'duplicate retained entry')

    def retained(name):
        e = entries[name]
        packed = read(parent/e['retained'], e['retained_sha256'])
        require(len(packed) == e['retained_bytes'], 'retained size')
        raw = gzip.decompress(packed)
        require(len(raw) == e['bytes'] and hashlib.sha256(raw).hexdigest() == e['sha256'], 'original receipt bytes')
        return raw

    input_name = next(n for n in entries if n.endswith('/run/bracket-inputs.json'))
    data = json.loads(retained(input_name))
    require([v['choice'] for v in data['views']] == ['control','candidate','control','candidate','control'], 'five views required')
    all_rows, per_views = [], []
    for view in data['views']:
        require(view['passed'] and len(view['requests']) == 12
                and len({r['prompt_id'] for r in view['requests']}) == 12, 'complete unique exact requests')
        view_rows = []
        for r in view['requests']:
            validate_request(r)
            old = originals[r['prompt_id']]
            require(r['exact_oracle'] and r['tokens'] == old['tokens'][:64]
                    and r['prompt_token_sha256'] == old['prompt_token_sha256'], 'real parent token equality')
            require(r['guess_sequence'] == old['guess_sequence'][:len(r['guess_sequence'])], 'unchanged proposals')
            source = view['output'][view['output'].index('experiments/'):]
            streams = [stream(retained(f'{source}/{r["prompt_id"]}/rank{rank}/timings.jsonl'),rank) for rank in (0,1)]
            commands = {(x['sequence'],x['op'],x['position']) for x in streams[1] if x['p154_segment']=='command'}
            waits = [x for x in streams[0] if x['p154_segment']=='remote_reply_wait'
                     and r['token_timestamps'][0] <= x['start'] <= x['end'] <= r['token_timestamps'][-1]]
            require(waits and all((x['sequence'],x['op'],x['position']) in commands for x in waits), 'unmatched peer command')
            rr = replay(r,limit=63)
            ts = r['token_timestamps']
            for i,row in enumerate(rr):
                start,end = ts[i:i+2]
                item = dict(view=view['index'],choice=view['choice'],prompt_id=r['prompt_id'],
                    prompt_class=r['prompt_class'],interval=i,position=row['position'],hit=row['hit'],
                    elapsed_ms=row['elapsed_ms'],D=row['D'],R=row['R'],C=row['C'],A=row['A'],B=row['B'],
                    offset_ms=row['spec_start_offset_ms'],G=row['unresolved_control_gaps_ms'])
                for rank in (0,1):
                    for name,ms in partition(start,end,streams[rank]).items():
                        item[f'r{rank}_{name}_exclusive_ms'] = ms
                # How much B can move when next-A becomes ready early, without
                # changing rank1's own queue: only its actual suffix-wait window.
                suffix = [x for x in streams[1] if x['p154_segment']=='wait_rank0_suffix'
                          and x['start'] < end and x['end'] > start]
                item['rank1_suffix_wait_enclosing_ms'] = sum(max(0.,min(end,x['end'])-max(start,x['start']))*1000 for x in suffix)
                view_rows.append(item)
        require(len(view_rows)==756, '756 intervals per view')
        all_rows.extend(view_rows)
        per_views.append(dict(view=view['index'],choice=view['choice'],intervals=len(view_rows),
            hits=sum(r['hit'] for r in view_rows),
            suffix_wait_ms_per_interval=st.mean(r['rank1_suffix_wait_enclosing_ms'] for r in view_rows),
            mean_elapsed_ms=st.mean(r['elapsed_ms'] for r in view_rows)))
    names = sorted(set().union(*(r.keys() for r in all_rows)))
    normalized = [{k:r.get(k,0.) for k in names} for r in all_rows]
    # Missing a bucket within an otherwise validated interval means zero
    # overlap; missing a stream/census/command is always a refusal above.
    report = dict(schema='packet160.real-parent-scopes.v1',passed=True,
        views=per_views,intervals=len(all_rows),tokens_and_proposals_match_record=True,
        no_wall_clock_proof_deadline=True,host_clock_only=True,
        warning='Each rank sums to the measured interval; ranks overlap. Do not add ranks, nested enclosing scopes, or packet122 GPU times.',
        input_pins=dict(sorted(PINS.items())))
    return normalized,report


def main():
    guard()
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    rows,report=analyze()
    products={'scoped-intervals.csv.gz':gzip.compress(csv_bytes(rows),mtime=0),
              'scope-report.json':(json.dumps(report,indent=2,allow_nan=False)+'\n').encode()}
    for name,raw in products.items():
        path=P/'evidence'/name
        if args.check:require(path.read_bytes()==raw,f'scope replay changed {name}')
        else:path.write_bytes(raw)
    print(json.dumps(dict(passed=True,intervals=len(rows),views=report['views'],
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))


if __name__=='__main__':main()
