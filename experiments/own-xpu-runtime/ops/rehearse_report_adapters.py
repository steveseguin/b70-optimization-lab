"""Declarative synthetic report contracts; called inside the report CPU guard."""
import importlib
import json
import re
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


class ContractError(ValueError):
    """Only these fixed messages may be surfaced by the report child."""


def read_contract(path):
    try:
        if path.suffix != '.json' or path.is_symlink() or path.stat().st_size > 65536:
            raise ValueError()
        value = json.loads(path.read_text())
        required = {'schema', 'analyzer', 'fixture_generator', 'samples', 'analysis', 'cases'}
        if not isinstance(value, dict) or set(value) - required - {'data_roots'} or not required <= value.keys():
            raise ValueError()
        if value['schema'] != 'own-runtime.report-contract.v1':
            raise ValueError()
        for key in ('analyzer', 'fixture_generator'):
            if not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z_]\w*:[A-Za-z_]\w*', value[key]):
                raise ValueError()
        for key in ('samples', 'analysis'):
            stream = value[key]
            if set(stream) != {'path', 'format', 'required'} or stream['format'] != ('jsonl' if key == 'samples' else 'json'):
                raise ValueError()
            leaf = Path(stream['path'])
            if leaf.is_absolute() or '..' in leaf.parts or not leaf.name:
                raise ValueError()
            if not isinstance(stream['required'], dict) or not stream['required']:
                raise ValueError()
            if any(t not in ('str', 'int', 'float', 'bool', 'list', 'dict') for t in stream['required'].values()):
                raise ValueError()
        cases = value['cases']
        if not isinstance(cases, list) or not 1 <= len(cases) <= 16:
            raise ValueError()
        names = set()
        for case in cases:
            if set(case) != {'name', 'fixture', 'expected'} or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', case['name']):
                raise ValueError()
            if case['name'] in names or not isinstance(case['fixture'], dict) or not isinstance(case['expected'], dict) or not case['expected']:
                raise ValueError()
            names.add(case['name'])
        roots = value.get('data_roots', [])
        if not isinstance(roots, list) or any(not isinstance(r, str) or not re.fullmatch(r'[A-Za-z_]\w*:[A-Za-z_]\w*', r) for r in roots):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise ContractError('malformed report contract') from None


def local_symbol(packet, spec):
    module_name, name = spec.split(':')
    path = packet / (module_name + '.py')
    if not path.is_file() or path.is_symlink():
        raise ContractError('report contract requires packet-local Python source')
    module = importlib.import_module(module_name)
    if Path(module.__file__).resolve() != path.resolve():
        raise ContractError('report contract module identity differs')
    return module, getattr(module, name)


def validate_stream(value, required):
    types = dict(str=str, int=int, float=float, bool=bool, list=list, dict=dict)
    if not isinstance(value, dict) or any(k not in value or type(value[k]) is not types[t] for k, t in required.items()):
        raise ContractError('report stream differs from declared schema')


def micro_contract_probe(entry, contract, packet, scratch, digest):
    """Execute real report_completed and verify declared analyzer publication."""
    _, analyzer = local_symbol(packet, contract['analyzer'])
    _, generate = local_symbol(packet, contract['fixture_generator'])
    if not callable(analyzer) or not hasattr(analyzer, '__code__') or not callable(generate):
        raise ContractError('report contract entry point is not callable')
    cases = []
    with ExitStack() as stack:
        for spec in contract.get('data_roots', []):
            module, _ = local_symbol(packet, spec)
            stack.enter_context(patch.object(module, spec.split(':')[1], scratch))
        for case in contract['cases']:
            output = scratch / case['name']
            output.mkdir()
            generate(output, case['fixture'])
            samples = output / contract['samples']['path']
            rows = [json.loads(line) for line in samples.read_text().splitlines()]
            if not rows:
                raise ContractError('report sample stream is empty')
            for row in rows:
                validate_stream(row, contract['samples']['required'])
            # Observe the actual analyzer, never substitute its implementation.
            calls = []
            import sys
            def trace(frame, event, arg):
                if event == 'call' and frame.f_code is analyzer.__code__:
                    calls.append(True)
            sys.setprofile(trace)
            try:
                result = entry['report_completed'](output)
            finally:
                sys.setprofile(None)
            published = json.loads((output / contract['analysis']['path']).read_text())
            validate_stream(published, contract['analysis']['required'])
            if not calls or result != published or any(k not in published or type(published[k]) is not type(v) or published[k] != v for k, v in case['expected'].items()):
                raise ContractError('report contract publication or decision differs')
            cases.append(dict(name=case['name'], samples_sha256=digest(samples)))
    return cases


def window_shape(job, packet, kind):
    """Read small packet declarations only; READY is not treated as admission."""
    if kind != 'bracket':
        return {}
    declared = job.get('plan', {}).get('entry_rehearsal', {}).get('window', {})
    if declared:
        value = declared
    else:
        ready = next((p for p in (packet / 'READY-FOR-DEVICE.json', packet.parent / 'READY-FOR-DEVICE.json') if p.is_file()), None)
        value = {}
        if ready is not None:
            if ready.stat().st_size > 65536:
                raise ContractError('window declaration too large')
            value = json.loads(ready.read_text())
    shape = {k: value[k] for k in ('arm_order', 'max_new') if k in value}
    if 'max_new' in shape and (type(shape['max_new']) is not int or not 1 <= shape['max_new'] <= 512):
        raise ContractError('invalid window token cap')
    if 'arm_order' in shape and (not isinstance(shape['arm_order'], list) or not 1 <= len(shape['arm_order']) <= 32 or not all(isinstance(v, str) for v in shape['arm_order'])):
        raise ContractError('invalid window arm order')
    return shape


def onecard_rows(views, rows):
    """Normalize declared views for synthetic data, retaining separate dimensions.

    Historical rows are (label, view). Gate/up screens declare
    (label, capacity, gateup), with their real view_name defining the report
    identity. Unknown shapes refuse rather than dropping an extra dimension.
    """
    normalized = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) not in (2, 3):
            raise ContractError('unsupported one-card view row')
        label, selected = row[:2]
        if (label is not None and not isinstance(label, str)) or not isinstance(selected, str):
            raise ContractError('invalid one-card view identity')
        gateup = None
        view = selected
        if len(row) == 3:
            gateup = row[2]
            if not isinstance(gateup, str) or not callable(getattr(views, 'view_name', None)):
                raise ContractError('one-card multidimensional view requires view_name')
            view = views.view_name(selected, gateup)
            if not isinstance(view, str) or not view:
                raise ContractError('invalid one-card view name')
        normalized.append(dict(label=label, view=view, selection_view=selected,
                               capacity=selected, gateup=gateup))
    return normalized


def publication_split_fixture(output, rows, prompts, cap):
    """Existing split32 stream schema, from packet58aq's synthetic adapter.

    Only invented input data: real split_analyze and all publication tails run.
    """
    for label, arm in rows:
        for prompt in prompts:
            dest = output / 'run' / label / prompt['prompt_id']
            timings = []
            for i in range(cap):
                waits = [dict(kind='compute-or-copy-tail', phase='decode-compute-drain', scope='normal', begin_ns=1000, call_ns=2000, end_ns=2000000)] if arm == 'wait-split' else []
                timings.append(dict(generated_index=i+1, token_id=1, wall_ms=33., wait_ms=21., prepare_ms=.1, enqueue_loop_ms=.2,
                    publication_split=dict(arm=arm, diagnostic_only=True, calls=1, construction_ms=.04, submit_ms=.02,
                        drain_ms=0. if arm == 'drain-only' else .1 if arm == 'no-upload' else .5 if arm == 'no-scatter' else 1.,
                        repair_ms=1., retire_host_ms=.01, waits=waits)))
            (dest / 'timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in timings))
            (dest / 'prefill-timings.jsonl').write_text(''.join(json.dumps(dict(timings[0], generated_index=0))+'\n' for _ in range(prompt['prompt_tokens']-1)))
