"""One loaded transport, isolated cold views; any failure ends the bracket."""
import time
from pathlib import Path
from common import D, compare_tokens, label, read, require, save, sha

SWITCH_RESET = 13
DOMAINS = {'restore_table': ('production', 'p121')}

def compatible(selections):
    require(len(selections) >= 2, 'at least two views required')
    base = selections[0]
    for view in selections:
        require(set(view) == set(base), 'selection schema fields differ')
        require(view['schema']=='packet59c.selection.v1', 'unsupported selection schema')
        require(view['schema'] == base['schema'] and set(view['draft']) == set(base['draft']),
                'draft schema differs; reload required')
        for key, value in base['draft'].items():
            require(view['draft'][key] == value, 'draft bytes/layout differ; reload required: ' + key)
        require(set(view['choices']) == set(base['choices']), 'selection keys differ')
        for key, value in base['choices'].items():
            if key in DOMAINS:
                require(view['choices'][key] in DOMAINS[key], 'unsupported switch value: ' + key)
            else:
                require(view['choices'][key] == value, 'load-time/unsupported choice differs: ' + key)
        require(not view['choices']['miss'].startswith('banks'), 'third banks are not qualified')
    return True

def load_config(path):
    from common import HERE
    path = Path(path).resolve()
    require(path.parent == HERE / 'configs', 'registered bracket configuration required')
    config = read(path)
    require(path.name == config['kind'] + '.json' and config['kind'] in ('smoke', 'bracket'), 'unregistered configuration filename')
    views = config['views']
    order = [v['choice'] for v in views]
    require(order == (['control', 'candidate', 'control'] if config['kind'] == 'smoke' else
                     ['control', 'candidate', 'control', 'candidate', 'control']),
            'smoke A/B/A or complete A/B/A/B/A required')
    require(config['kind'] in ('smoke', 'bracket'), 'unknown bracket kind')
    for view in views:
        selection = Path(view['selection'])
        require(selection.parent == HERE / 'lineage', 'selection outside registered lineage')
        require(sha(selection) == view['selection_sha256'], 'view selection changed')
    compatible([read(v['selection']) for v in views])
    require(len({v['selection_sha256'] for v in views[::2]}) == 1 and
            len({v['selection_sha256'] for v in views[1::2]}) == 1,
            'alternating selections must be identical')
    if config['kind'] == 'smoke':
        first, candidate = [read(v['selection']) for v in views[:2]]
        require(first['choices']['restore_table'] == 'production' and candidate['choices']['restore_table'] == 'p121', 'smoke production/reverse required')
        candidate['choices']['restore_table'] = first['choices']['restore_table']
        require(candidate == first, 'smoke changes restore transport only')
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

def execute_views(backend, views, entries, output, tokens=128):
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
        require(tokens in (64,128),'unregistered response cap')
        for name, entry, count in [('incident64', entries[0], 64)] + [(e['prompt_id'], e, tokens) for e in entries]:
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
