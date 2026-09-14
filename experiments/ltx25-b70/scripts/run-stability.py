#!/usr/bin/env python3
"""Bounded sequential LTX stability client; never manages or retries the server.

All raw archives survive until exact comparison permits deletion. Newly selected
references survive until their complete repeat gate passes. Previews are lossy
review copies, never the quality oracle. Only this campaign's registered files
are eligible for pruning; small evidence and deletion receipts remain forever.
"""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
NAME = re.compile(r'[a-z0-9][a-z0-9_-]*\Z')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    # Replacing this campaign's progress file is atomic; original run evidence
    # is created exclusively by the existing request and comparison clients.
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
    temporary.replace(path)


def safe_path(root, relative, *, exists=True):
    """Reject traversal and every symlink component, including root ancestors."""
    root = Path(root).absolute()
    relative = Path(relative)
    require(not relative.is_absolute() and relative.parts and
            all(part not in ('.', '..') for part in relative.parts), 'unsafe relative path')
    target = root / relative
    for ancestor in [*reversed(target.parents), target]:
        if ancestor.is_symlink():
            raise RuntimeError('symlink path refused: ' + str(ancestor))
    if exists:
        require(target.exists(), 'missing evidence: ' + str(target))
    return target


def owned_file(root, campaign, runs, run, relative):
    require(NAME.fullmatch(campaign) and NAME.fullmatch(run), 'unsafe campaign/run name')
    require(run in runs and run.startswith(campaign + '-r'), 'unregistered/protected run')
    relative = Path(relative)
    allowed_tensor = Path('output/validation') / run / 'tensors.safetensors'
    allowed_preview = (relative.parent == Path('output') / run and
                       re.fullmatch(r'preview_[0-9]+_\.mp4', relative.name))
    require(relative == allowed_tensor or allowed_preview, 'protected file or unknown output')
    path = safe_path(root, relative)
    require(path.is_file(), 'not a regular output file')
    return path


def inventory(root, campaign, runs, run, relative):
    path = owned_file(root, campaign, runs, run, relative)
    info = path.stat()
    return {'run': run, 'relative_path': str(relative), 'path': str(path),
            'bytes': info.st_size, 'sha256': sha(path),
            'device': info.st_dev, 'inode': info.st_ino}


def delete_owned(root, campaign, runs, record, *, parity_passed, receipts):
    """Delete one registered, unchanged file after a durable passing gate."""
    require(parity_passed is True, 'no passing parity gate; preserve evidence')
    path = owned_file(root, campaign, runs, record['run'], record['relative_path'])
    info = path.stat()
    require((info.st_dev, info.st_ino, info.st_size) ==
            (record['device'], record['inode'], record['bytes']), 'output changed since inventory')
    require(sha(path) == record['sha256'], 'output hash changed; preserve evidence')
    # Open each directory without following symlinks, preventing path redirection
    # between validation and unlink. unlink itself never follows a final symlink.
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        current = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
        require(stat.S_ISREG(current.st_mode) and
                (current.st_dev, current.st_ino, current.st_size) ==
                (info.st_dev, info.st_ino, info.st_size), 'file replaced before deletion')
        receipt = {**record, 'action': 'delete', 'parity_passed': True,
                   'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        with receipts.open('a') as handle:
            handle.write(json.dumps({**receipt, 'phase': 'intent'}) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.unlink(path.name, dir_fd=descriptor)
        with receipts.open('a') as handle:
            handle.write(json.dumps({**receipt, 'phase': 'completed'}) + '\n')
    finally:
        os.close(descriptor)


def normalized(graph):
    graph = copy.deepcopy(graph)
    graph['364']['inputs']['text'] = '<fixture>'
    for node in ('338', '339'):
        graph[node]['inputs']['noise_seed'] = 0
    graph['414']['inputs']['run_name'] = '<run>'
    graph['75']['inputs']['filename_prefix'] = '<run>/preview'
    return graph


def validate_prereg(spec, graph):
    require(spec['campaign'] == 'stability-01', 'this client is bounded to stability-01')
    require(spec['rounds'] == 3 and len(spec['fixtures']) == 10, 'require exactly 30 requests')
    require(spec['graph'] == 'speed-resident-split-api.json', 'unreviewed graph')
    require((spec['min_output_width'], spec['min_output_height'], spec['frames'], spec['fps']) ==
            (256, 256, 25, 24), 'quality floor changed')
    expected = json.loads((LANE / 'data/speed-resident-split-api.json').read_text())
    require(normalized(graph) == normalized(expected), 'graph differs from frozen selected recipe')
    require(graph['356']['inputs'] == {'width': 128, 'height': 128, 'length': 25, 'batch_size': 1},
            'stage-one geometry changed')
    require(graph['420']['inputs'] == {'placement': 'split'}, 'placement changed')
    require(graph['348']['class_type'] == 'LTXVLatentUpsampler', 'two-stage upsampler absent')
    for node, sigmas in [('404', [1, .99375, .9875, .98125, .975, .909375, .725, .421875, 0]),
                         ('395', [.85, .725, .4219, 0])]:
        require([float(x) for x in graph[node]['inputs']['sigmas'].split(',')] == sigmas,
                'fixed sampling schedule changed')
    for node in ('352', '341'):
        require(graph[node]['inputs']['sampler_name'] == 'euler_ancestral', 'sampler changed')
    for node in ('388', '391'):
        require(graph[node]['inputs']['video_cfg'] == graph[node]['inputs']['audio_cfg'] == 1,
                'CFG changed')
    require(graph['365']['inputs']['frame_rate'] == graph['366']['inputs']['frame_rate'] ==
            graph['370']['inputs']['fps'] == 24, 'frame rate changed')
    ids = [f['id'] for f in spec['fixtures']]
    require(len(set(ids)) == 10 and all(NAME.fullmatch(x) for x in ids), 'invalid fixture IDs')
    for fixture in spec['fixtures']:
        require(isinstance(fixture['prompt'], str) and fixture['prompt'].strip(), 'missing prompt')
        require(type(fixture['seed']) is int and 0 <= fixture['seed'] < 2 ** 64, 'invalid seed')
        if fixture.get('reference'):
            require(NAME.fullmatch(fixture['reference']), 'unsafe reference name')


def identity_binding(root, expected=None):
    identity_path = root / 'speed-server/server-identity.json'
    identity = json.loads(identity_path.read_text())
    require(identity['pid'] == 24848, 'current approved process changed')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == identity['boot_id'], 'boot changed')
    ticks = Path('/proc/24848/stat').read_text().split(') ')[1].split()[19]
    extensions = identity['extension_sha256s']
    require(set(extensions) == {'resident_node.py', 'ltx_layer_shard.py', 'capture_node.py'}, 'extension identity incomplete')
    for name, digest in extensions.items():
        require(sha(LANE / 'scripts' / name) == digest, 'loaded extension source changed: ' + name)
    require(not (root / 'FAULT.json').exists(), 'device fault latch present')
    require(json.loads((root / 'model-verification.json').read_text())['status'] == 'passed', 'model gate failed')
    current = {'server_identity_sha256': sha(identity_path), 'proc_start_ticks': ticks,
               'boot_id': identity['boot_id'], 'pid': identity['pid'],
               'extension_sha256s': extensions,
               'model_verification_sha256': sha(root / 'model-verification.json'),
               'server_args_sha256': sha(root / 'speed-server/server-args.json')}
    if expected is not None:
        require(current == expected, 'server identity changed; halt without restart')
    require(shutil.disk_usage(root).free >= 5 * 1024 ** 3, 'less than 5 GiB free; halt')
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    require(int(memory['MemAvailable'].split()[0]) >= 8 * 1024 ** 2, 'less than 8 GiB available RAM; halt')
    return current


def snapshot(pid):
    base = Path('/proc') / str(pid)
    clients = {}
    for item in (base / 'fdinfo').iterdir():
        try:
            raw = item.read_text()
        except FileNotFoundError:
            continue
        fields = dict(line.split(':', 1) for line in raw.splitlines() if line.startswith('drm-'))
        fields = {key: value.strip() for key, value in fields.items()}
        if 'drm-client-id' not in fields:
            continue
        key = fields.get('drm-pdev', '') + '/' + fields['drm-client-id']
        if key not in clients:
            clients[key] = {'fd': item.name, 'fields': fields, 'raw_fdinfo': raw}
    return {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'process_status': (base / 'status').read_text(),
            'host_meminfo': Path('/proc/meminfo').read_text(), 'drm_clients': clients,
            'accounting': 'deduplicated by PCI device and drm-client-id; shared GTT is not summed'}


def validate_capture(root, run):
    """Independent CPU validation for a first-time selected-recipe fixture."""
    import torch
    from safetensors.torch import load_file
    folder = root / 'output/validation' / run
    meta = json.loads((folder / 'summary.json').read_text())
    require(meta['run_name'] == run and meta['deterministic_enabled'] and
            not meta['deterministic_warn_only'] and meta['sample_rate'] == 48000, 'capture metadata invalid')
    tensors = load_file(str(folder / 'tensors.safetensors'))
    shapes = {'images': [25, 256, 256, 3], 'video_latent': [1, 128, 4, 8, 8],
              'audio_latent': [1, 8, 26, 16], 'waveform': [1, 2, 48480]}
    require(set(tensors) == set(meta['tensors']) == set(shapes), 'capture keys changed')
    for key, value in tensors.items():
        require(value.dtype == torch.float32 and list(value.shape) == shapes[key], 'capture layout changed: ' + key)
        require(torch.isfinite(value).all().item(), 'nonfinite output: ' + key)
        require(hashlib.sha256(value.view(torch.uint8).numpy().tobytes()).hexdigest() ==
                meta['tensors'][key]['sha256'], 'capture hash mismatch: ' + key)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prereg', type=Path, default=LANE / 'data/stability-01-prereg.json')
    args = parser.parse_args()
    spec = json.loads(args.prereg.read_text())
    graph = json.loads((LANE / 'data' / spec['graph']).read_text())
    validate_prereg(spec, graph)
    root = ROOT
    binding = identity_binding(root)
    campaign = spec['campaign']
    runs = {f"{campaign}-r{r:02d}-{f['id']}" for r in range(1, 4) for f in spec['fixtures']}
    for run in runs:
        for relative in [Path('requests') / run, Path('output') / run,
                         Path('output/validation') / run]:
            require(not safe_path(root, relative, exists=False).exists(), 'campaign output already exists')
    for fixture in spec['fixtures']:
        if not fixture.get('reference'):
            continue
        reference = fixture['reference']
        prompt = json.loads(safe_path(root, Path('requests') / reference / 'prompt.json').read_text())
        require(prompt['364']['inputs']['text'] == fixture['prompt'] and
                all(prompt[node]['inputs']['noise_seed'] == fixture['seed'] for node in ('338', '339')),
                'reference prompt/seed mismatch: ' + reference)
        safe_path(root, Path('output/validation') / reference / 'tensors.safetensors')
    output = safe_path(root, campaign, exists=False)
    output.mkdir(exist_ok=False)
    write_json(output / 'preregistration.json', spec)
    write_json(output / 'identity.json', binding)
    write_json(output / 'client-identity.json', {'run-stability.py': sha(Path(__file__)),
               'profile-clip.py': sha(LANE / 'scripts/profile-clip.py'),
               'compare-clip.py': sha(LANE / 'scripts/compare-clip.py'),
               'prereg_sha256': sha(args.prereg), 'graph_sha256': sha(LANE / 'data' / spec['graph'])})
    rows, files, deleted, passed_runs = [], {}, set(), set()
    references = {f['id']: f.get('reference') for f in spec['fixtures']}
    generated_references = set()
    log = root / 'speed-server.log'
    log_identity = (log.stat().st_dev, log.stat().st_ino)
    current_run = None
    try:
        for round_number in range(1, 4):
            for fixture in spec['fixtures']:
                current_run = f"{campaign}-r{round_number:02d}-{fixture['id']}"
                identity_binding(root, binding)
                before = snapshot(binding['pid'])
                offset = log.stat().st_size
                row = {'run': current_run, 'round': round_number, 'fixture': fixture['id'],
                       'reference': references[fixture['id']], 'status': 'running',
                       'before': before, 'log_start': offset}
                rows.append(row)
                write_json(output / 'progress.json', {'status': 'running', 'rows': rows})
                candidate = copy.deepcopy(graph)
                candidate['364']['inputs']['text'] = fixture['prompt']
                for node in ('338', '339'):
                    candidate[node]['inputs']['noise_seed'] = fixture['seed']
                graph_path = output / (current_run + '-graph.json')
                write_json(graph_path, candidate)
                command = [sys.executable, str(LANE / 'scripts/profile-clip.py'), current_run,
                           '--graph', str(graph_path), '--server-run', str(root / 'speed-server'), '--timeout', '600']
                row['command'] = command
                try:
                    with (output / (current_run + '-client.log')).open('x') as transcript:
                        completed = subprocess.run(command, stdout=transcript, stderr=subprocess.STDOUT, timeout=650)
                    require(completed.returncode == 0, 'request failed; no retry')
                finally:
                    row['after'] = snapshot(binding['pid'])
                    info = log.stat()
                    require((info.st_dev, info.st_ino) == log_identity and info.st_size >= offset,
                            'server log replaced or truncated')
                    with log.open('rb') as handle:
                        handle.seek(offset)
                        appended = handle.read(info.st_size - offset)
                    (output / (current_run + '-server.log')).write_bytes(appended)
                    row['log_end'] = info.st_size
                    row['loading_log_lines'] = [line for line in appended.decode(errors='replace').splitlines()
                                               if any(word in line.lower() for word in ('offload', 'loaded ', 'load ', 'requested to load'))]
                identity_binding(root, binding)
                request = root / 'requests' / current_run
                history = json.loads((request / 'history.json').read_text())
                submitted_graph = json.loads((request / 'prompt.json').read_text())
                require(normalized(submitted_graph) == normalized(graph), 'executed graph invariant changed')
                require(history['prompt'][2] == submitted_graph and history['status']['status_str'] == 'success', 'history mismatch')
                submission = json.loads((request / 'submission.json').read_text())
                result = json.loads((request / 'result.json').read_text())
                require(history['prompt'][1] == submission['prompt_id'] == result['prompt_id'], 'request ID mismatch')
                require(not any(m[1].get('nodes') for m in history['status']['messages'] if m[0] == 'execution_cached'), 'cached execution refused')
                actual_identity = json.loads((request / 'identity.json').read_text())
                for key in ('pid', 'boot_id', 'proc_start_ticks', 'extension_sha256s', 'model_verification_sha256', 'server_args_sha256'):
                    require(actual_identity[key] == binding[key], 'request identity differs: ' + key)
                meta = validate_capture(root, current_run)
                write_json(output / (current_run + '-capture.json'), meta)
                row['profile'] = json.loads((request / 'profile.json').read_text())
                row['capture'] = meta
                entries = [inventory(root, campaign, runs, current_run,
                                     Path('output/validation') / current_run / 'tensors.safetensors')]
                previews = history['outputs']['75']['images']
                require(len(previews) == 1, 'unexpected number of preview files')
                for preview in previews:
                    require(preview['type'] == 'output' and preview['subfolder'] == current_run,
                            'unexpected preview destination')
                    entries.append(inventory(root, campaign, runs, current_run,
                                             Path('output') / current_run / preview['filename']))
                files[current_run] = entries
                write_json(output / 'output-inventory.json', files)
                reference = references[fixture['id']]
                if reference:
                    parity = output / (current_run + '-parity.json')
                    compare_command = [sys.executable, str(LANE / 'scripts/compare-clip.py'), reference, current_run,
                                       '--output', str(parity)]
                    with (output / (current_run + '-compare.log')).open('x') as transcript:
                        comparison = subprocess.run(compare_command, stdout=transcript, stderr=subprocess.STDOUT, timeout=120)
                    require(comparison.returncode == 0 and json.loads(parity.read_text())['status'] == 'passed',
                            'exact parity failed; preserve evidence and halt')
                    passed_runs.add(current_run)
                    if reference in generated_references:
                        passed_runs.add(reference)
                    row['status'] = 'passed'
                    row['parity_path'] = str(parity)
                else:
                    references[fixture['id']] = current_run
                    generated_references.add(current_run)
                    row['status'] = 'reference_captured_pending_repeats'
                write_json(output / 'progress.json', {'status': 'running', 'rows': rows})
                # Keep raw newly selected references until the entire gate ends.
                if current_run in passed_runs:
                    record = entries[0]
                    delete_owned(root, campaign, runs, record, parity_passed=True,
                                 receipts=output / 'deletion-receipts.jsonl')
                    deleted.add(record['relative_path'])
                eligible_previews = [record for run in files if run in passed_runs
                                     for record in files[run] if record['relative_path'].endswith('.mp4')
                                     and record['relative_path'] not in deleted]
                for record in eligible_previews[:-3]:
                    delete_owned(root, campaign, runs, record, parity_passed=True,
                                 receipts=output / 'deletion-receipts.jsonl')
                    deleted.add(record['relative_path'])
                print(json.dumps({'run': current_run, 'status': row['status'],
                                  'completed_requests': len(rows),
                                  'preview_ready_seconds': row['profile']['preview_ready_seconds']}), flush=True)
        require(len(rows) == 30 and all(run in passed_runs for run in runs), 'incomplete exact repeat gate')
        identity_binding(root, binding)
        for run in generated_references:
            record = files[run][0]
            delete_owned(root, campaign, runs, record, parity_passed=True,
                         receipts=output / 'deletion-receipts.jsonl')
            deleted.add(record['relative_path'])
        write_json(output / 'progress.json', {'status': 'passed', 'rows': rows,
                   'all_30_requests_completed': True, 'all_10_fixtures_exact_repeats': True,
                   'stability_promotion': 'pending memory drift and passive fault-log review; exact repeats alone do not establish stability',
                   'retained_outputs': [entry for entries in files.values() for entry in entries
                                        if entry['relative_path'] not in deleted],
                   'retention_note': 'Unmatched first-round reference previews were protected until first parity; final retained MP4 count <=3. All capture summaries and file hashes remain.'})
    except BaseException as error:
        if rows and rows[-1]['status'] == 'running':
            rows[-1]['status'] = 'failed'
        write_json(output / 'progress.json', {'status': 'failed', 'failed_run': current_run,
                   'error': repr(error), 'rows': rows,
                   'action': 'halted new requests; server left untouched; failure evidence preserved'})
        raise


if __name__ == '__main__':
    main()
