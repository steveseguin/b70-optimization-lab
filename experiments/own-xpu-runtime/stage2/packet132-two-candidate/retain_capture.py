#!/usr/bin/env python3
"""Retain completed CPU captures; never remove originals or copy model weights.

Run only after build/capture/completion.json exists:
  nice -n 19 taskset -c 8-15,24-31 python3 -B retain_capture.py </dev/null
Use --check to regenerate expected archive bytes and verify retained/original
bytes without writing. Existing outputs are never overwritten.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import tarfile

P = Path(__file__).resolve().parent
SOURCE = P / 'build/capture'
DEST = P / 'evidence/capture'
MIB = 1024 * 1024


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def same_stream(left, right):
    while True:
        a, b = left.read(65536), right.read(65536)
        require(a == b, 'archive/copy bytes differ from original')
        if not a:
            return


def record(path):
    require(path.is_file() and not path.is_symlink(), f'not a plain source file: {path}')
    return dict(source=str(path.relative_to(SOURCE)), bytes=path.stat().st_size,
                sha256=digest(path))


def archive(paths, output_name):
    """Deterministic gzip/tar; each original is byte-compared after compression."""
    members = [record(path) for path in sorted(paths)]
    require(members, f'empty archive: {output_name}')
    require(sum(m['bytes'] for m in members) < 32 * MIB, 'archive exceeds bounded in-memory budget')
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, filename='', mode='wb', mtime=0, compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped, mode='w|', format=tarfile.USTAR_FORMAT) as tar:
            for member in members:
                info = tarfile.TarInfo(member['source'])
                info.size = member['bytes']
                info.mode, info.mtime = 0o644, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                with (SOURCE / member['source']).open('rb') as original:
                    tar.addfile(info, original)
    raw = buffer.getvalue()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        require(tar.getnames() == [m['source'] for m in members], 'archive member order differs')
        for member in members:
            with tar.extractfile(member['source']) as stored, (SOURCE / member['source']).open('rb') as original:
                same_stream(stored, original)
            require(digest(SOURCE / member['source']) == member['sha256'], 'source changed during archive')
    return raw, dict(retained=output_name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                     members=members, every_member_byte_compared=True,
                     restore_base='build/capture',
                     restore_command=f'tar -xzf evidence/capture/{output_name} -C build/capture')


def prepare():
    require((SOURCE / 'completion.json').is_file(), 'capture is incomplete; no retention writes allowed')
    from analyze import validate_capture, validate_rows
    rows = json.loads((SOURCE / 'rows.json').read_text())
    validate_rows(rows)
    validation = validate_capture(SOURCE / 'rows.json', rows)
    completion = json.loads((SOURCE / 'completion.json').read_text())
    inputs = json.loads((SOURCE / 'inputs.json').read_text())
    original_selection = json.loads((P.parent/'packet114-draft-prefix/calibration/selection.json').read_text())
    tokenizer = P.parents[3]/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet2-cpu-oracle/tokenizer.py'
    require(digest(tokenizer) == original_selection['tokenizer_sha256'],
            'tokenizer differs from packet114 independent-corpus identity')
    names = ['inputs.json', 'rows.json', 'rows.jsonl', 'completion.json', 'build-receipt.json']
    for phase in ('prepare', 'build-oracle', 'build-matmul'):
        names += [phase + '.log', phase + '.receipt.json']
    resource_rows = []
    for index in range(5):
        prefix = f'doc-{index}/'
        names += [prefix + name for name in (
            'input/input.json', 'input/tokens.txt', 'input/plan.tsv', 'input/identity.tsv',
            'target/result.json', 'target/positions.jsonl', 'target/tokens.jsonl',
            'draft-receipt.json', 'draft-rows.jsonl',
            'target.log', 'target.receipt.json', 'draft.log', 'draft.receipt.json')]
        # Native oracle versions do not all emit a separate teardown receipt.
        # Retain it when present and explicitly record absence below.
        teardown = SOURCE / prefix / 'target/teardown.json'
        if teardown.is_file():
            names.append(prefix + 'target/teardown.json')
        target = json.loads((SOURCE / prefix / 'target/result.json').read_text())
        draft = json.loads((SOURCE / prefix / 'draft-receipt.json').read_text())
        require((SOURCE / prefix / 'draft-receipt.json').stat().st_size < MIB,
                'draft receipt >=1 MiB: stop before writes; analyzer needs plain receipt; owner task coordinator must decide retention')
        for phase in ('target', 'draft'):
            receipt = json.loads((SOURCE / prefix / (phase + '.receipt.json')).read_text())
            require(receipt['returncode'] == 0 and 'exception' not in receipt,
                    f'failed capture stage: {prefix}{phase}')
            resource_rows.append(dict(source=prefix + phase + '.receipt.json',
                parent_child_peak_rss_bytes=receipt['sampled_parent_child_peak_rss_bytes'],
                wall_seconds=receipt['wall_seconds']))
        resource_rows.append(dict(source=prefix + 'target/result.json', max_rss_kib=target['max_rss_kib']))
        resource_rows.append(dict(source=prefix + 'draft-receipt.json', max_rss_kib=draft['max_rss_kib']))
        draft_rows = [json.loads(line) for line in (SOURCE / prefix / 'draft-rows.jsonl').read_text().splitlines()]
        require(draft_rows == [r for r in rows if r['source_index'] == index + 1], 'per-document rows differ')
        for row in draft_rows:
            require(digest(SOURCE/prefix/f"target/capture-streams/streams-{row['position']}.bf16") == row['stream_sha256'],
                    'draft row is not bound to its retained target stream')
        require(json.loads((SOURCE / prefix / 'input/input.json').read_text()) == inputs['sources'][index],
                'per-document input provenance differs')

    copies = [record(SOURCE / name) for name in sorted(names)]
    for phase in ('prepare', 'build-oracle', 'build-matmul'):
        receipt = json.loads((SOURCE / (phase + '.receipt.json')).read_text())
        require(receipt['returncode'] == 0 and 'exception' not in receipt, f'failed stage: {phase}')
        resource_rows.append(dict(source=phase + '.receipt.json',
            parent_child_peak_rss_bytes=receipt['sampled_parent_child_peak_rss_bytes'],
            wall_seconds=receipt['wall_seconds']))
    require(max(r.get('parent_child_peak_rss_bytes', 0) for r in resource_rows) < 8_000_000_000,
            'recorded parent-child memory exceeds requested 8 GB')

    archives, archive_records = {}, []
    for index in range(5):
        streams = sorted((SOURCE / f'doc-{index}/target/capture-streams').glob('streams-*.bf16'))
        source = inputs['sources'][index]
        target = json.loads((SOURCE / f'doc-{index}/target/result.json').read_text())
        count = len(source['tokens']) + len(target['tokens']) - 1
        require({p.name for p in streams} == {f'streams-{i}.bf16' for i in range(count)},
                f'incomplete target stream capture for doc-{index}')
        require(all(p.stat().st_size == 4 * 2560 * 2 for p in streams), 'invalid target stream size')
        name = f'doc-{index}-target-streams.tar.gz'
        archives[name], metadata = archive(streams, name)
        archive_records.append(metadata)
    code = sorted((SOURCE / 'build/src').iterdir())
    require(all(p.suffix in ('.cpp', '.hpp') for p in code), 'unexpected private build source file')
    name = 'private-oracle-sources.tar.gz'
    archives[name], metadata = archive(code, name)
    archive_records.append(metadata)

    scripts = {name: digest(P / name) for name in
               ('capture.py', 'analyze.py', 'audit_capture.py', 'retain_capture.py', 'PLAN.md')}
    manifest = dict(schema='lab.packet132.capture-retention.v1', complete=True,
        source_root='build/capture', retained_root='evidence/capture', originals_deleted=False,
        binaries_or_model_weights_retained=False, capture_validation=validation,
        capture_completion_sha256=digest(SOURCE / 'completion.json'),
        copied_files=[dict(row, retained=row['source']) for row in copies], archives=archive_records,
        source_script_sha256=scripts, observed_resources=resource_rows,
        tokenizer_sha256=digest(tokenizer), tokenizer_matches_packet114=True,
        maximum_observed_parent_child_rss_bytes=max(r.get('parent_child_peak_rss_bytes', 0) for r in resource_rows),
        maximum_reported_process_rss_kib=max(r.get('max_rss_kib', 0) for r in resource_rows),
        whole_capture_seconds=completion['wall_seconds'],
        teardown_receipts={f'doc-{i}':(SOURCE / f'doc-{i}/target/teardown.json').is_file() for i in range(5)},
        retention_reason='Small independent-text target streams preserve every captured state byte needed to repeat draft analysis; archives are storage only and every member was byte-compared and hashed.',
        reproduction=dict(capture='nice -n 19 taskset -c 8-15,24-31 ionice -c 3 python3 -B capture.py NEW_PRIVATE_DIRECTORY </dev/null',
            audit='nice -n 19 taskset -c 8-15,24-31 python3 -B audit_capture.py --check </dev/null',
            analysis='nice -n 19 taskset -c 8-15,24-31 python3 -B analyze.py --rows evidence/capture/rows.json --check </dev/null',
            retention='nice -n 19 taskset -c 8-15,24-31 python3 -B retain_capture.py --check </dev/null',
            restore='From this packet directory, restore each archive using its restore_command; copy retained JSON/log files back to the same paths under build/capture. Original files are never removed by this tool.'))
    return copies, archives, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    require(sys.flags.optimize == 0, 'assertions must remain enabled for capture validation')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'CPU affinity required')
    resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
    copies, archives, manifest = prepare()
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    outputs = [DEST / row['source'] for row in copies] + [DEST / n for n in archives] + [DEST / 'retention-manifest.json']
    if not args.check:
        require(not any(path.exists() for path in outputs), 'retained outputs already exist; use --check, never overwrite')
        for row in copies:
            source, out = SOURCE / row['source'], DEST / row['source']
            require(digest(source) == row['sha256'], f'source changed before copy: {source}')
            out.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as original, out.open('xb') as copied:
                shutil.copyfileobj(original, copied, 65536)
        for name, raw in archives.items():
            with (DEST / name).open('xb') as out:
                out.write(raw)
        with (DEST / 'retention-manifest.json').open('xb') as out:
            out.write(manifest_raw)
    for row in copies:
        source, out = SOURCE / row['source'], DEST / row['source']
        require(digest(source) == row['sha256'] == digest(out), f'copied hash differs: {source}')
        with source.open('rb') as original, out.open('rb') as copied:
            same_stream(original, copied)
    for name, raw in archives.items():
        require((DEST / name).read_bytes() == raw, f'deterministic archive differs: {name}')
    require((DEST / 'retention-manifest.json').read_bytes() == manifest_raw, 'retention manifest differs')
    print(json.dumps(dict(passed=True, checked=args.check, copied_files=len(copies),
                          archives=len(archives), originals_deleted=False)))


if __name__ == '__main__':
    main()
