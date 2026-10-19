"""CPU-only, measured-input critical-path replay. No runtime imports or launches.

Models are sensitivities, not device measurements. Components from distinct
experiments never become an invented additive partition of a record interval.
"""
import argparse
import ast
import base64
from collections import defaultdict
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import resource
import statistics as st

from audit import guard

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
S = P.parent
PINS = {}
METHOD = '6627ffa350361a85aed5160f1f5738409cb23bab4f9ca1f34fea7317a0b63ad4'
ARCHIVE = 'e768ee3dc3d5100312d3226c273b3e02a569f99aedf9e9894f5eec80d93e7122'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(path, sha=None):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(sha is None or digest == sha, f'input hash: {path.name}')
    PINS[str(path.relative_to(ROOT))] = dict(sha256=digest, bytes=len(raw))
    return raw


def load(path):
    return json.loads(read(path))


def method():
    raw = read(S/'packet126-early-draft/method/p85_model.py', METHOD)
    nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef)
             and n.name in ('duration', 'intervals')]
    require(len(nodes) == 2, 'two pure replay functions')
    scope = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'p85-pure-functions', 'exec'), scope)
    return scope['intervals']


def validate_request(r):
    require(r['passed'] and r['cached_tokens'] == 0 and r['device_executed'], 'quality/cold/device evidence')
    require(r['arithmetic'] == 'iq3-p49-split32-v1', 'arithmetic identity')
    stamps = r['generated_token_completion_timestamps']
    require(len(stamps) >= 64 and all(math.isfinite(t) for t in stamps)
            and all(b > a for a, b in zip(stamps, stamps[1:])), 'monotone finite events')
    keys = [(t['rank'], t['op'], t['position'], t['speculative'])
            for t in r['rank_trace'] if t['op'] in (1, 3, 9)]
    require(len(set(keys)) == len(keys), 'duplicate command identity')
    for t in r['rank_trace']:
        require(all(math.isfinite(t[k]) for k in ('rank_received', 'rank_completed'))
                and t['rank_completed'] >= t['rank_received'], 'invalid command clock')


def record():
    intervals = method()
    parent = S/'packet136-record-bundle/submission/prepared-a'
    members = json.loads(gzip.decompress(read(parent/'evidence.json.gz', ARCHIVE)))['members']
    requests, originals = [], {}
    for name, member in sorted(members.items()):
        if not (name.startswith('WS128/run/repeat-1/') and name.endswith('/receipt.json')):
            continue
        raw = base64.b64decode(member['raw_base64'], validate=True)
        require(hashlib.sha256(raw).hexdigest() == member['sha256'], 'record member hash')
        r = json.loads(raw)
        validate_request(r)
        require(r['oracle_check']['passed'], 'record oracle')
        rr = intervals(r)
        for row in rr:
            row.update(prompt_id=r['prompt_id'], prompt_class=r['prompt_class'])
            row['ready_ms'] = max(row['D'], row['R']+row['C'])
            row['race_ms'] = max(row['B'], row['A']+row['spec_start_offset_ms'])
            row['ready_critical'] = 'draft' if row['D'] >= row['R']+row['C'] else 'restore+correction'
            row['race_critical'] = 'B_including_suffix' if row['B'] >= row['A']+row['spec_start_offset_ms'] else 'next_A'
        requests.append((r['prompt_class'], rr))
        originals[r['prompt_id']] = r
    require(len(requests) == 12 and len(originals) == 12, 'twelve unique prompts')
    rows = [r for _, rr in requests for r in rr]
    require(len(rows) == 1188 and sum(r['hit'] for r in rows) == 932, 'record window census')
    require(max(abs(model(r)-r['elapsed_ms']) for r in rows) < 1e-7, 'interval reconstruction')
    result = load(parent/'result.json')
    require(abs(aggregate(requests, model)-result['primary_metric']['value_tok_s']) < 1e-8, 'record metric')
    return requests, originals


def model(r, d=0., b=0., a=0., c=0., restore=0.):
    return (max(max(0., r['D']-d), max(0., r['R']-restore)+max(0., r['C']-c))
            + max(max(0., r['B']-b), max(0., r['A']-a)+r['spec_start_offset_ms'])
            + r['unresolved_control_gaps_ms'])


def aggregate(requests, fn):
    groups = defaultdict(list)
    for cls, rr in requests:
        total = sum(fn(r) for r in rr)
        require(total > 0 and math.isfinite(total), 'positive finite modeled duration')
        groups[cls].append(len(rr)*1000/total)
    require(len(groups) == 6, 'six varied classes')
    return st.median(st.median(v) for v in groups.values())


def scenario(requests, fn):
    base = aggregate(requests, model)
    rate = aggregate(requests, fn)
    rows = [r for _, rr in requests for r in rr]
    return dict(projected_tok_s=rate, gain_percent=100*(rate/base-1),
                pooled_saved_ms=st.mean(model(r)-fn(r) for r in rows),
                reciprocal_saved_ms=1000/base-1000/rate, device_measurement=False)


def threshold(requests, key, gain=3.):
    lo, hi = 0., 20.
    fn = lambda x: scenario(requests, lambda r: model(r, **{key: x}))['gain_percent']
    if fn(hi) < gain:
        return None
    for _ in range(60):
        mid = (lo+hi)/2
        if fn(mid) < gain:
            lo = mid
        else:
            hi = mid
    return hi


def stats(rows):
    fields = ('D', 'R', 'C', 'A', 'B', 'spec_start_offset_ms', 'ready_ms', 'race_ms',
              'unresolved_control_gaps_ms', 'elapsed_ms')
    return dict(count=len(rows), means_ms={k: st.mean(r[k] for r in rows) for k in fields},
                draft_critical=sum(r['ready_critical']=='draft' for r in rows),
                B_critical=sum(r['race_critical']=='B_including_suffix' for r in rows))


def inputs149():
    pin = load(P/'evidence/packet149-retention.json')
    raw = gzip.decompress(read(P/'evidence'/pin['retained'],pin['retained_sha256']))
    require(len(raw)==pin['original_bytes'] and hashlib.sha256(raw).hexdigest()==pin['original_sha256'], '149 retained bytes')
    d = json.loads(raw)
    require(d['passed'] and d['all_13_exact'] and d['draft_proposals_identical'], '149 equality')
    views = d['scheduling_costs']['views']
    require([v['choice'] for v in views] == ['control','candidate','control','candidate','control'], '149 views')
    control = st.mean(v['corrected_half']['mean_ms'] for v in views if v['choice']=='control')
    costs = []
    for v in views:
        require(not v['missing_native_trace'] and v['miss_count'] == 331, '149 complete corrections')
        if v['choice'] != 'candidate':
            continue
        audit = v['exchange_audit']
        require(audit['covered_misses'] == 331 and audit['counts'] == [96]
                and audit['send_bytes_per_miss'] == [849792]
                and audit['receive_bytes_per_miss'] == [1362048], '149 transfer census')
        cost = v['corrected_half']['mean_ms']-control
        require(abs(cost-v['exchange_cost_per_miss_ms']) < 1e-9, '149 corrected-half delta')
        costs.append(cost)
    return dict(control_corrected_half_ms=control, candidate_extra_ms=costs,
                effective_per_exchange_ms=[x/96 for x in costs],
                one_exchange_per_layer_24_layer_proxy_ms=[x/4 for x in costs],
                two_exchanges_per_layer_proxy_ms=[x/2 for x in costs],
                bytes_out_per_miss=849792, bytes_back_per_miss=1362048,
                warning='Dividing by count is amortized pricing, NOT measured small-message latency or a universal transport bound.')


def sensitivity(requests, roofline, transfer):
    groups = {r['group']: r['measured_ms'] for r in roofline['ranked']}
    head = groups['head_gemv']
    both = head+groups['argmax_publication']
    whole = sum(groups.values())
    cuts = dict(half_head=head/2, all_head_and_argmax=both,
                half_routed_plus_half_head=(groups['routed_experts']+head)/2,
                impossible_half_all_draft_kernels=whole/2,
                impossible_all_draft_kernels=whole)
    result = {name: dict(raw_draft_cut_ms=cut, **scenario(requests, lambda r: model(r, d=cut))) for name, cut in cuts.items()}
    result['remove_all_D'] = scenario(requests, lambda r: model(r, d=r['D']))
    result['remove_all_B_but_keep_A'] = scenario(requests, lambda r: model(r, b=r['B']))
    result['remove_all_R'] = scenario(requests, lambda r: model(r, restore=r['R']))
    # A provisional start can advance next-A, but cannot advance B before the
    # unchanged draft/controller rendezvous unless that dependency is ALSO changed.
    result['advance_only_A_by_all_D'] = scenario(requests, lambda r: model(r, a=r['D']))
    result['ideal_equal_cost_B_to_A_balance'] = scenario(requests, lambda r:
        max(r['D'],r['R']+r['C'])+(r['B']+r['A']+r['spec_start_offset_ms'])/2+r['unresolved_control_gaps_ms'])
    e = st.mean(transfer['effective_per_exchange_ms'])
    result['half_all_draft_minus_one_amortized_exchange'] = dict(
        transfer_is_proxy=True, **scenario(requests, lambda r:model(r,d=whole/2-e)))
    result['half_all_draft_minus_eight_amortized_exchanges'] = dict(
        transfer_is_proxy=True, **scenario(requests, lambda r:model(r,d=whole/2-8*e)))
    result['B_expert_parallel_sensitivity'] = []
    for gross in (.3, 1., 1.9):
        for exchanges in (0, 24, 48):
            # Charge the peer the moved work, and donate its extra transport
            # service as free; charge all proxy transport only to B.
            result['B_expert_parallel_sensitivity'].append(dict(
                moved_compute_ms=gross, round_trips=exchanges, exchange_proxy_ms=exchanges*e,
                **scenario(requests,lambda r:model(r,b=gross-exchanges*e,a=-gross))))
    # Deliberately generous: B tracks the saved lead completely. A wrong guess
    # is drained, then a full R+C is paid; no sibling computation is hidden.
    result['provisional_sensitivity'] = []
    recovery = st.mean(x['R']+x['C'] for _, rr in requests for x in rr if not x['hit'])
    for lead in (both, .8, 1.0, 1.2, 1.5):
        for accuracy in (1., .99, .97, .95, .9):
            def fn(r):
                if not r['hit']:
                    return model(r)  # no opportunity while correction owns rank0
                # Sensitivity uses average observed miss recovery, not an invented
                # measured cost for a new transaction. Exposure is an upper bound.
                return model(r)-accuracy*min(lead,r['D'])+(1-accuracy)*recovery
            result['provisional_sensitivity'].append(dict(lead_ms=lead, assumed_agreement=accuracy,
                **scenario(requests, fn)))
    return result


def cross_study():
    p150 = load(S/'packet150-rank0-split/v5/evidence/device-split-v5-B/bracket-summary.json')
    p154 = load(S/'packet154-rank1-split/v5/evidence/device-p154c-split-v5-B/bracket-summary.json')
    require(all(d['passed'] and d['all_13_exact'] and d['draft_proposals_identical'] for d in (p150,p154)), 'scope quality')
    return dict(packet150_rank0=p150['rank0_split']['decisions'],
                packet154_rank1=p154['rank1_split']['scope_summary'],
                packet154_waits=[{k:v[k] for k in ('index','choice','overlap_ms_per_cycle','remote_reply_wait_ms_per_cycle')}
                    for v in p154['rank1_split']['views']],
                warning='Separate measured diagnostic runs. Host scopes nest/overlap. Never add medians or substitute these for record per-interval observations.')


def csv_bytes(rows):
    f = io.StringIO(newline='')
    writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return f.getvalue().encode()


def main():
    guard()
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    requests, originals = record()
    rows = [r for _, rr in requests for r in rr]
    roofline = load(S/'packet158-draft-levers/roofline.json')
    transfer = inputs149()
    report = dict(schema='packet160.critical-path.v1', passed=True, diagnostic=True,
        device_work_performed=False, record_tok_s=aggregate(requests, model),
        hits=stats([r for r in rows if r['hit']]), misses=stats([r for r in rows if not r['hit']]),
        thresholds_3_percent={k: threshold(requests,k) for k in ('d','b','a','c','restore')},
        record_intervals=len(rows), reconstruction_max_error_ms=max(abs(model(r)-r['elapsed_ms']) for r in rows),
        transfer149=transfer, sensitivities=sensitivity(requests, roofline, transfer), cross_study=cross_study(),
        draft_groups_historical_ms={r['group']: r['measured_ms'] for r in roofline['ranked']})
    products = {'report.json': (json.dumps(report, indent=2, allow_nan=False)+'\n').encode(),
                'record-intervals.csv': csv_bytes(rows),
                'input-pins.json': (json.dumps(PINS, indent=2, sort_keys=True)+'\n').encode()}
    for name, raw in products.items():
        path = P/'evidence'/name
        if args.check:
            require(path.read_bytes() == raw, f'replay changed: {name}')
        else:
            path.write_bytes(raw)
    print(json.dumps(dict(passed=True, check=args.check, record_tok_s=report['record_tok_s'],
                         thresholds=report['thresholds_3_percent'], peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))


if __name__ == '__main__':
    main()
