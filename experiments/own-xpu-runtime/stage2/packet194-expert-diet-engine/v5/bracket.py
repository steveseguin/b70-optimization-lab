"""One loaded transport, isolated cold views; any failure ends the bracket.

Packet189 rows (v5/bracket_config.py ROWS): kind `smoke` (one k3x view, 12 x 64) and kind `bracket` (one load of the k3
storage, views V3/k3x/V3/k3x/V3, 12 x 128 each). In the bracket only the boundary set (rank0 <-> rank0-k3), the two
trims (kernel_io, rank0_prepare) and the export path (boundary_export) switch in-load; storage (rank0_layers 0-26,
head) is identical, which the native bracket_select enforces as well. Kind `view` (a fresh single view) stays
supported by the loader but no packet189 row registers it: packet188 row 1 is the fresh V3 reference.
"""
import time
from pathlib import Path
from common import D, compare_tokens, label, read, require, save, sha

SWITCH_RESET = 13
DOMAINS = {'boundary': ('rank0', 'rank0-k3'), 'kernel_io': ('copy', 'kernel'), 'rank0_prepare': ('sync', 'async'), 'boundary_export': ('copy', 'kernel'),
           'expert_gateup': ('production', 'diet'),  # packet194: in-load gate/up kernel switch (k3 storage)
}  # packet189 V3 <-> k3x only
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

def variant_of(selection_path):
    """v3 (packet187 record selection), v3k (k3 storage run as V3), k3x-record (packet189's 19-key k3x), k3x (20 keys, expert_gateup production: the control) or k3x-diet (the candidate)."""
    return Path(selection_path).parent.name


def load_config(path):
    from common import HERE
    from bracket_config import ROWS
    path = Path(path).resolve()
    require(path.parent == HERE / 'configs', 'registered bracket configuration required')
    config = read(path)
    views = config['views']
    index = config.get('row_index')
    require(index in range(len(ROWS)) and ROWS[index]['config'] == path.name and ROWS[index]['kind'] == config['kind'],
            'packet189 registered row configuration required')
    for view in views:
        selection = Path(view['selection'])
        require(selection.parent.parent == HERE / 'lineage', 'selection outside registered lineage')
        require(sha(selection) == view['selection_sha256'], 'view selection changed')
    compatible([read(v['selection']) for v in views])
    choices = [read(v['selection'])['choices'] for v in views]
    expected = {'v3': ('control', '0-25', 'rank0', None, None, None, None),
                'v3k': ('control', '0-26', 'rank0', 'copy', 'sync', 'copy', None),
                'k3x-record': ('control', '0-26', 'rank0-k3', 'kernel', 'async', 'copy', None),
                'k3x': ('control', '0-26', 'rank0-k3', 'kernel', 'async', 'copy', 'production'),
                'k3x-diet': ('candidate', '0-26', 'rank0-k3', 'kernel', 'async', 'copy', 'diet')}
    for view, c in zip(views, choices):
        variant = variant_of(view['selection'])
        choice, layers, boundary, io, prepare, export, gateup = expected[variant]
        require(view['choice'] == choice and c['head'] == 'production' and c.get('rank0_layers') == layers and c.get('boundary') == boundary and
                c.get('kernel_io') == io and c.get('rank0_prepare') == prepare and c.get('boundary_export') == export and c.get('expert_gateup') == gateup and
                c['experts'] == 'exp-halfcache+down-tile16' and c['snapshot_host'] == 'static' and c['dense_scales'] == 'expanded',
                'packet194 view selection differs from its registered variant: ' + variant)
    order = [variant_of(v['selection']) for v in views]
    if config['kind'] == 'smoke':
        require(order == ['k3x-diet'] and views[0].get('max_new') == 64, 'packet194 smoke: one k3x-diet view, 12 x 64')
    elif config['kind'] == 'view':
        require(order == ['v3'] and views[0].get('max_new') == 128, 'packet189 control: one fresh-load V3 view (record selection), 12 x 128')
    else:
        require(config['kind'] == 'bracket' and order == ['k3x', 'k3x-diet', 'k3x', 'k3x-diet', 'k3x'] and all(v.get('max_new') == 128 for v in views),
                'packet194 bracket: k3x/k3x-diet/k3x/k3x-diet/k3x, 12 x 128 each')
        require(len({v['selection_sha256'] for v in views[::2]}) == 1 and len({v['selection_sha256'] for v in views[1::2]}) == 1,
                'alternating selections must be identical')
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
                first_minute_proof(dest, result, started, variant_of(view['selection']))
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
