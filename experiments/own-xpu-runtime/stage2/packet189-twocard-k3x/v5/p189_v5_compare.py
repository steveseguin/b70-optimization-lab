"""V4 request-schema adapter; packet189 rows: k3x smoke and the V3/k3x one-load bracket (packet188 row 1 is the fresh V3 reference)."""
import hashlib, json, math, statistics
from pathlib import Path
from common import D, METRICS, read, require, sha, save, summary, label

def proposal_identity(destination):
    """Compare actual proposals, not only aggregate acceptance or target tokens."""
    traces=list(Path(destination).glob('rank1/draft-rows.jsonl'))
    require(len(traces)==1,'rank1 draft proposal trace missing')
    rows=[json.loads(line) for line in traces[0].read_text().splitlines() if line.strip()]
    keys=('draft_position','confirmed_token','guess','head')
    values=[[r[k] for k in keys] for r in rows]
    require(values and any(r[3] for r in values),'draft proposal sequence empty')
    return dict(rows=len(values),sha256=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest())

def class_copies(output,identity):
    # Packet149 has no copied class bank. Scratch is not model state.
    return []

def checked_requests(summary, oracle, cap=64):
    require(cap in (64,128), 'unsupported diagnostic cap')
    rows = summary['requests']
    require([r['prompt_id'] for r in rows] == list(D.CHECK.PROMPT_IDS), 'complete ordered suite required')
    require(summary.get('cached_tokens') == 0 and summary.get('requested_max_new') == cap
            and summary.get('request_count') == 12, 'twelve cold 64-token diagnostic requests required')
    require(summary.get('passed') is True and summary.get('kv_dtype') == 'BF16', 'summary/precision failed')
    grouped, acceptance, counts = {}, [], []
    for r in rows:
        prompt = r['prompt_id']
        require(r['prompt_class'] == METRICS.PROMPT_CLASSES[prompt], 'prompt class changed')
        require(r.get('cached_tokens') == 0 and r.get('repeat', 1) == 1, 'cached/repeated request')
        require(r.get('passed') is True and r.get('exact_oracle') is True and
                len(r['tokens']) == cap and r['tokens'] == oracle(prompt)[:cap], 'target output mismatch')
        ts = r['token_timestamps']
        require(len(ts) == cap and all(math.isfinite(t) for t in ts)
                and all(b > a for a, b in zip(ts, ts[1:])), 'invalid timestamps')
        rate = (min(cap,100)-1) / (ts[min(cap,100)-1] - ts[0])
        require(rate>0, 'invalid diagnostic rate')
        grouped.setdefault(r['prompt_class'], []).append(rate)
        hits, guesses = r['hits'], r['guesses']
        require(type(hits) is int and type(guesses) is int and 0 <= hits <= guesses and guesses > 0,
                'invalid acceptance counts')
        require(math.isclose(r['acceptance'], hits / guesses, rel_tol=1e-10), 'acceptance differs from counts')
        acceptance.append(hits / guesses)
        counts.append(dict(prompt_id=prompt, hits=hits, guesses=guesses))
    return dict(rate=statistics.median(statistics.median(v) for v in grouped.values()),
                acceptance=statistics.mean(acceptance), acceptance_counts=counts)

def row_output(index, lane):
    """Registered output of packet189 row `index` on `lane`."""
    from common import HERE
    from bracket_config import row
    r = row(index)
    return HERE / 'evidence' / f'device-{r["name"]}-{lane}-p189'


def view_variant(selection):
    return Path(selection['selection']).parent.name


def check_view(output, window, identity, isolation, oracle, index, view, selection, cap, shared):
    """One view of any row: identity, boundary proof, incident, exact requests; returns its row record."""
    dest = output / 'run/views' / f'{index:02d}-{view["choice"]}'
    require(view['index'] == index and view['choice'] == selection['choice'] and view['selection_sha256'] == selection['selection_sha256'],
            'view order/identity differs')
    require(view['output'] == str(dest) and view['passed'] is True and view['started_utc_ns'] < view['finished_utc_ns'], 'failed view')
    boundary = []
    for rank in (0, 1):
        r = read(dest / 'boundary' / f'boundary-rank{rank}.json')
        require(r == view['boundary'][rank] and r['passed'] is True and r['total_reset'] is True and r['cached_tokens'] == 0 and
                r['weight_uploads_after_load'] == 0 and r['selection_sha256'] == selection['selection_sha256'], 'boundary not proven')
        boundary.append((r['arena_descriptors_sha256'], r['weight_descriptors_sha256']))
    incident = read(dest / 'incident64/receipt.json')
    require(view['incident64']['receipt_sha256'] == sha(dest / 'incident64/receipt.json') and
            incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens'] == 0 and
            incident['passed'] is True and incident['exact_oracle'] is True, 'incident64 differs')
    result = summary(view['requests'], view['incident64'], 'tp2')
    result.update(placement=identity['placement'], lane=identity['lane'], conditions=identity['conditions'], timing='token',
                  device_isolation=isolation, bracket_view=index, shared_model_lifetime=shared)
    metrics = checked_requests(result, oracle, cap)
    save(dest / 'summary.json', result)
    save(dest / 'identity.json', dict(identity, view=selection, bracket_view=index))
    proposals = {name: proposal_identity(dest / name) for name in ['incident64', *D.CHECK.PROMPT_IDS]}
    variant = view_variant(selection)
    record = dict(index=index, choice=view['choice'], variant=variant, all_13_exact=True, exact_count=13, draft_proposals=proposals,
                  lane=identity['lane'], boot_id=window['boot_id'], output=str(dest), started_utc_ns=view['started_utc_ns'],
                  finished_utc_ns=view['finished_utc_ns'], **metrics)
    if cap == 128:
        from s189_decision import view_stats
        record['interval_stats'] = (dict(status='synthetic report wiring only', device_evidence=False) if isolation.get('synthetic_cpu_fixture')
                                    else view_stats(dest, list(D.CHECK.PROMPT_IDS), variant))
    return record, boundary


def finish_bracket(output, window, identity, coordination):
    """Packet189 row report (kind smoke | view | bracket); the bracket row 1 also decides (s189_decision, with packet188 row 1 as the pinned fresh V3 reference)."""
    proof = read(output / 'run/bracket-inputs.json')
    views = proof['views'];config = identity['bracket'];kind = config['kind'];index = config['row_index']
    require(proof.get('passed') is True and proof['kind'] == kind and len(views) == len(config['views']), 'incomplete row')
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    isolation = read(output / 'run/device-isolation.json')
    require(isolation.get('passed') is True, 'row isolation failed')
    cap = 64 if kind == 'smoke' else 128
    rows, descriptors = [], None
    for i, view in enumerate(views):
        record, boundary = check_view(output, window, identity, isolation, oracle, i, view, config['views'][i], cap, kind == 'bracket')
        if i:
            require(views[i - 1]['finished_utc_ns'] < view['started_utc_ns'], 'overlapping views')
        if descriptors is None:
            descriptors = boundary
        require(boundary == descriptors, 'view loaded arena differs')
        rows.append(record)
    require(all(r['acceptance_counts'] == rows[0]['acceptance_counts'] for r in rows), 'per-prompt acceptance changed across views')
    require(all(r['draft_proposals'] == rows[0]['draft_proposals'] for r in rows), 'per-prompt draft proposals changed across views')
    variants = [r['variant'] for r in rows]
    result = label(dict(schema='packet189.row.v1', passed=True, kind=kind, row_index=index, variant=identity['lineage'].rsplit('/', 1)[-1],
                        model_lifetimes=1, target_loads=1, draft_loads=1, teardown_count=1, views=rows, all_13_exact=True,
                        draft_proposals_identical=True, class_copies=class_copies(output, identity),
                        measured_wall_seconds=(__import__('time').time_ns() - window['started_utc_ns']) / 1e9))
    from timing_report import summarize
    result['scheduling_costs'] = summarize(output, views)
    if not isolation.get('synthetic_cpu_fixture'):
        require(all(v['status'] == 'measured' for v in result['scheduling_costs']['views']), 'missing real correction trace')
    from analyze import analyze
    analysis = analyze(views, synthetic=isolation.get('synthetic_cpu_fixture', False), variants=variants)
    if kind == 'smoke':
        result['timing_data_proof'] = analysis
        result['smoke_rate_note'] = 'smoke only: 64-token views, no speed verdict'
    else:
        result['rank0_split'] = analysis
    if kind == 'view':
        result['interval_stats'] = rows[0].get('interval_stats')
    if kind == 'bracket':
        v3 = [r['rate'] for r in rows if r['variant'] == 'v3k']
        result['inload_v3_drift_percent'] = 100 * (max(v3) / min(v3) - 1)
        result['k3x_over_inload_v3_min_percent'] = 100 * (min(r['rate'] for r in rows if r['variant'] == 'k3x') / max(v3) - 1)
    result['candidate_qualified'] = False
    result['purpose'] = 'packet189 k3x screen (smoke / one-load V3-k3x bracket; packet188 row 1 is the fresh V3 reference); never a record claim'
    from s189_decision import decide_or_incomplete, smoke_record, bracket_record
    if index == 1:
        try:
            previous = load(row_output(0, identity['lane']))
            result['s189_decision'] = decide_or_incomplete(smoke_record(previous), bracket_record(dict(result, views=rows)))
        except (ValueError, KeyError, OSError) as error:
            result['s189_decision'] = decide_or_incomplete(error)
    else:
        result['s189_decision'] = dict(schema='packet189.s189-decision.v1', screen_winner=False, chain_rule_met=False,
                                       outcome='PENDING: decided by the bracket row 1 (or s189_decision.py over rows 0..1)')
    save(output / 'bracket-summary.json', result)
    return result


def load(output):
    """Read one retained packet189 row, verifying every retained file digest."""
    output = Path(output)
    window = read(output / 'window.json')
    require(window.get('passed') is True and window.get('device_executed') is True and window.get('device_complete') is True and
            window.get('lease_released') is True and not window.get('child_still_running') and not window.get('stop_reasons'),
            'row device phase incomplete')
    require(read(output / 'run/teardown.json').get('drained') is True, 'teardown unproven')
    for leaf, digest in window['files'].items():
        path = (output / leaf).resolve()
        require(path.is_relative_to(output.resolve()) and sha(path) == digest, 'changed row artifact: ' + leaf)
    result = read(output / 'bracket-summary.json')
    identity = read(output / 'identity.json')
    require(result['passed'] is True and result['model_lifetimes'] == 1 and result['kind'] == identity['bracket']['kind'] and
            result['row_index'] == identity['bracket']['row_index'], 'row result failed')
    require(window['identity'] == identity, 'row identity differs')
    from common import HERE
    require(window['wrapper_seal_sha256'] == sha(HERE / 'placement-validation/wrapper-seal.json'), 'wrapper seal changed')
    require(window['oracle_completion_sha256'] == sha(D.ORACLE / 'results/completion.json'), 'oracle changed')
    require(read(output / 'suite-manifest.snapshot.json') == D.oracle_inputs(), 'oracle prompt suite changed')
    oracle = lambda prompt: D.CHECK.token_record(D.ORACLE / 'results' / prompt)
    cap = 64 if result['kind'] == 'smoke' else 128
    for i, row in enumerate(result['views']):
        dest = output / 'run/views' / f'{i:02d}-{row["choice"]}'
        checked = checked_requests(read(dest / 'summary.json'), oracle, cap)
        require(checked['rate'] == row['rate'] and checked['acceptance_counts'] == row['acceptance_counts'], 'changed view metrics')
        proposals = {name: proposal_identity(dest / name) for name in ['incident64', *D.CHECK.PROMPT_IDS]}
        require(proposals == row['draft_proposals'] == result['views'][0]['draft_proposals'], 'draft proposal parity changed')
        incident = read(dest / 'incident64/receipt.json')
        require(incident['tokens'] == oracle(D.CHECK.PROMPT_IDS[0])[:64] and incident['cached_tokens'] == 0, 'changed incident')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser();parser.add_argument('output', type=Path);args = parser.parse_args()
    print(json.dumps(load(args.output), indent=2))
