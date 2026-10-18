#!/usr/bin/env python3
"""One candidate, one incident prompt, 64 tokens; pinned v4 lifecycle."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import types

HERE = Path(__file__).resolve().parent
P105 = HERE.parent / 'packet105-head-split'
sys.path.insert(0, str(P105))
from screen_jobs import verify, view, WRAPPER
from bootstrap import install

PROMPT = 'incident-retrospective'
CHOICE = 'head-split-compute'
OUTPUT = WRAPPER / 'evidence/p105s-B-head-split-compute-incident64-v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('pinned smoke adaptation anchor changed: ' + old)
    return source.replace(old, new, 1)


def adapted_source(name):
    source = (WRAPPER / name).read_text()
    if name == 'tp2_worker.py':
        source = once(source, "entries = manifest['prompts']", "entries = manifest['prompts'][:1]")
        source = once(source, "'--tokens', '128'", "'--tokens', '64'")
        source = once(source,
            "requests = [('incident64', entries[0], 64)] + [(e['prompt_id'], e, 128) for e in entries]",
            "requests = [('incident64', entries[0], 64)]")
        source = once(source, '            else:\n                rows.append(result)',
                             '            rows.append(result)')
    elif name == 'screen.py':
        source = once(source, "len(proof['requests']) == 12", "len(proof['requests']) == 1")
        source = once(source, 'result = summary(proof[\'requests\'], proof[\'incident64\'], args.profile)',
            "result = smoke_summary(proof['requests'], proof['incident64'], args.output)")
    else:
        raise ValueError('unsupported adapter')
    return source


def verify_adapter():
    pins = json.loads((HERE / 'source-pins.json').read_text())
    for name, sha in pins.items():
        if digest(HERE / name) != sha:
            raise ValueError('smoke source changed: ' + name)
    verify()  # Includes the original dependency pins and shared wrapper seal.
    return pins


def load_adapter(name):
    module = types.ModuleType('p105s_' + Path(name).stem)
    # Preserve the shared wrapper's path-based safety checks and provenance.
    module.__file__ = str(WRAPPER / name)
    exec(compile(adapted_source(name), str(HERE / ('adapted-' + name)), 'exec'), module.__dict__)
    return module


def transfer_receipts(output):
    from common import require
    files, counts = {}, {}
    expected = {'hidden-export': (5120, 'host_dependency_wait_us'),
                'hidden-import': (5120, 'host_us'),
                'best-export': (16, 'host_us'), 'prefix-export': (16, 'host_us')}
    for path in sorted((output / 'run').rglob('p105-transfers.jsonl')):
        files[str(path.relative_to(output))] = digest(path)
        for line in path.read_text().splitlines():
            row = json.loads(line)
            require(row.get('leg') in expected, 'unknown head transfer leg')
            size, field = expected[row['leg']]
            require(row.get('placement') == 'compute' and row.get('bytes') == size,
                    'head transfer placement/size changed')
            require(isinstance(row.get(field), (int, float)) and math.isfinite(row[field])
                    and row[field] >= 0, 'invalid transfer timing')
            if row['leg'] == 'hidden-export':
                require(row.get('prefix_submitted_before_publication') is True,
                        'prefix submission receipt missing')
            counts[row['leg']] = counts.get(row['leg'], 0) + 1
    require(set(counts) == set(expected) and len(set(counts.values())) == 1,
            'missing/unbalanced head transfer receipts')
    return dict(files_sha256=files, leg_counts=counts,
                note='hidden-export includes producer dependency wait; not pure DMA latency')


def smoke_summary(rows, incident, output):
    from common import D, compare_tokens, label, read, require
    require(len(rows) == 1 and rows[0].get('prompt_id') == PROMPT,
            'exactly the registered incident prompt required')
    row = rows[0]
    require(row.get('passed') is True and row.get('exact_oracle') is True,
            'smoke exactness failed')
    compare_tokens(row['tokens'], D.CHECK.token_record(D.ORACLE / 'results' / PROMPT), 64, PROMPT)
    receipt = output / 'run/incident64/receipt.json'
    require(read(receipt) == row and incident.get('passed') is True
            and incident.get('tokens_compared') == 64
            and incident.get('receipt_sha256') == digest(receipt), 'incident receipt differs')
    return label(dict(schema='own-runtime.packet105s.smoke.v1', passed=True,
        request_count=1, requested_max_new=64, prompt_id=PROMPT, choice=CHOICE,
        requests=rows, incident64=incident, transfer_receipts=transfer_receipts(output),
        arithmetic='iq3-p49-split32-v1', kv_dtype='BF16', record_ready=False))


def worker_command(args, identity, manifest):
    from common import require
    require(manifest['prompts'][0]['prompt_id'] == PROMPT, 'incident must be first')
    identity['smoke'] = dict(prompt_id=PROMPT, generated_tokens=64, request_count=1,
                             candidate=CHOICE, adapter_sources=verify_adapter())
    return ['/usr/bin/python3', '-B', str(HERE / 'worker.py'),
            '--identity', str(args.output / 'identity.json'), '--output', str(args.output / 'run'),
            '--seconds', '3600']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', choices=('B',), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--fault-review')
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    verify_adapter()
    if args.output.resolve() != OUTPUT.resolve():
        raise ValueError('private smoke output required; grid outputs forbidden')
    wrapper = load_adapter('screen.py')
    wrapper.command = worker_command
    wrapper.smoke_summary = smoke_summary
    lineage = view(CHOICE)
    cmd = ['--profile', 'tp2', '--lane', args.lane, '--placement', '1', '--timing', 'token',
           '--lineage', str(lineage), '--seal', str(lineage / 'screen-seal.json'),
           '--output', str(args.output)]
    if args.plan:
        cmd += ['--plan']
    else:
        if not args.authorized_device_window or not args.fault_review:
            raise ValueError('coordinator authorization and fault review required')
        cmd += ['--authorized-device-window', '--fault-review', args.fault_review]
    return wrapper.main(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
