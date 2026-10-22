"""One loaded transport, isolated cold views; any failure ends the bracket.

Packet185: every queue row is ONE fresh load with ONE view (kind `view`). The target-head split
is a storage choice (rank 1 loads 202,240 or 248,320 head rows, rank 0 the 46,080-row suffix or
nothing), so the native bracket refuses an in-load head switch; the five views
production/unsplit/production/unsplit/production are five fresh loads (five queue rows).
The single view's reset re-selects the selection the row loaded (no switch).
"""
import time
from pathlib import Path
from common import D, compare_tokens, label, read, require, save, sha

SWITCH_RESET = 13
DOMAINS = {}  # packet185: no in-load switch
def compatible(selections):
    require(bool(selections),'missing selections')
    base=selections[0]
    for view in selections:
        require(set(view)==set(base) and view['draft']==base['draft'],'selection schema/draft changed')
        require(set(view['choices'])==set(base['choices']),'choice keys changed')
        for key,value in view['choices'].items():
            require(value in DOMAINS[key] if key in DOMAINS else value==base['choices'][key],'unsupported selection change')
        require(view['choices']['miss']=='banks-batch','banked bundle8 required')
    return True

def load_config(path):
    from common import HERE
    path = Path(path).resolve()
    require(path.parent == HERE / 'configs', 'registered bracket configuration required')
    config = read(path)
    views = config['views']
    require(config['kind'] == 'view' and len(views) == 1, 'packet185: one fresh-load view per row')
    require(config.get('view_index') in range(5) and views[0]['choice'] == ('control', 'unsplit')[config['view_index'] % 2],
            'packet185 registered order production/unsplit/production/unsplit/production')
    for view in views:
        selection = Path(view['selection'])
        require(selection.parent.parent == HERE / 'lineage', 'selection outside registered lineage')
        require(sha(selection) == view['selection_sha256'], 'view selection changed')
    compatible([read(v['selection']) for v in views])
    selection = read(views[0]['selection'])
    expected_head = 'head-split-compute' if views[0]['choice'] == 'control' else 'production'
    require(views[0].get('max_new') == 128 and selection['choices']['head'] == expected_head and
            selection['choices']['dense_scales'] == 'expanded' and selection['choices']['snapshot_host'] == 'production',
            'packet185 view: 12x128, bundle-8 choices, head split (control) or full head (unsplit)')
    require(Path(views[0]['selection']).parent.name == ('production' if views[0]['choice'] == 'control' else 'unsplit'),
            'view selection lineage differs from its choice')
    return config

def switch_reset(transport, view, destination, suite):
    """Both native acknowledgements precede clearing shared mailboxes/history."""
    require(not any(transport.pending), 'switch with pending commands')
    destination.mkdir(parents=True, exist_ok=False)
    previous = getattr(transport, 'request_output', transport.out)
    proofs = []
    for rank in (0, 1):
        out = destination / ('rank' + str(rank))
        meta = transport.out / ('rank' + str(rank)) / ('bracket-' + str(transport.seq[rank] + 1) + '.txt')
        reset = meta.with_suffix('.reset.txt')
        receipt = destination / ('boundary-rank' + str(rank) + '.json')
        values = [view['selection'], view['selection_sha256'], str(reset), str(receipt), str(out)]
        require(all('\n' not in v for v in values), 'newline in boundary metadata')
        reset.write_text(str(out) + '\n\n')
        meta.write_text('\n'.join(values[:4]) + '\n')
        transport.call(rank, SWITCH_RESET)
        proof = read(receipt)
        require(proof.get('passed') is True and proof.get('total_reset') is True and
                proof.get('cached_tokens') == 0 and proof['selection_sha256'] == view['selection_sha256'] and
                proof.get('allocation_ids_preserved') is True and proof.get('weight_uploads_after_load') == 0,
                'native switch/reset not proven')
        proofs.append(proof)
    retained = suite.retain_request_state(previous)
    save(previous / 'state-retention.json', retained)
    transport.request_output = destination
    transport.mapping[:] = bytes(len(transport.mapping))
    transport.trace = []
    transport.metrics = [dict(busy_ms=0., handover_ms=0., calls=0, gpu_ms=0.) for _ in range(2)]
    transport.last_complete = [0., 0.]
    return proofs

def execute_views(backend, views, entries, output):
    """Backend owns switch/reset/request; orchestration cannot reuse a response."""
    completed, baseline = [], None
    for index, view in enumerate(views):
        backend.check()
        dest = output / 'views' / f'{index:02d}-{view["choice"]}'
        dest.mkdir(parents=True)
        started = time.time_ns()
        proof = backend.switch_reset(view, dest / 'boundary')
        descriptors = [(r['arena_descriptors_sha256'], r['weight_descriptors_sha256']) for r in proof]
        require(len(descriptors) == 2, 'both native owners must acknowledge reset')
        if baseline is None: baseline = descriptors
        require(descriptors == baseline, 'loaded arena identity differs across views')
        rows, incident = [], {}
        for name, entry, count in [('incident64', entries[0], 64)] + [(e['prompt_id'], e, view.get('max_new',128)) for e in entries]:
            backend.check()
            request_dir = dest / name
            backend.reset(request_dir)
            result = backend.request(entry, count)
            expected = D.CHECK.token_record(D.ORACLE / 'results' / entry['prompt_id'])
            compare_tokens(result['tokens'], expected, count, name)
            require(result.get('passed') is True and result.get('cached_tokens') == 0, 'unclean request receipt')
            result.update(prompt_id=entry['prompt_id'], prompt_class=D.METRICS.PROMPT_CLASSES[entry['prompt_id']],
                          repeat=1, exact_oracle=True, prompt_token_sha256=backend.prompt_hash(entry))
            save(request_dir / 'receipt.json', label(result))
            if name == 'incident64':
                from analyze import first_minute_proof
                first_minute_proof(dest, result, started, view['choice'] == 'control')
            if name == 'incident64':
                incident = dict(passed=True, tokens_compared=64, mode='separate-reset-request',
                                receipt_sha256=sha(request_dir / 'receipt.json'))
                save(dest / 'incident64.json', incident)
            else: rows.append(result)
        row = dict(passed=True, index=index, choice=view['choice'], selection_sha256=view['selection_sha256'],
                   started_utc_ns=started, finished_utc_ns=time.time_ns(), requests=rows,
                   incident64=incident, boundary=proof, output=str(dest))
        save(dest / 'report-inputs.json', row)
        completed.append(row)
    return completed
