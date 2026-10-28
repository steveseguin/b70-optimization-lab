#!/usr/bin/env python3
"""CPU-only fixture preparation; authenticate sealed inputs, never open a GPU."""
import hashlib
import json
import pathlib
import random
import struct
import subprocess
import sys

def digest(data):
    return hashlib.sha256(data).hexdigest()

def checked(path, record):
    data = path.read_bytes()
    assert len(data) == record['bytes'] and digest(data) == record['sha256'], path
    return data

def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir()  # exclusive output, including all CPU replay outputs
    native = pathlib.Path('/dev/shm/sc117-reference-prefix178-20261028-r1/router-lastrow-extract')
    cpu = pathlib.Path('/dev/shm/sc117-reference-prefix178-cpu-20261028-r1/model')
    saved = pathlib.Path('/dev/shm/sc117-reference-prefix178-20261028-r1/router-layer3-same-input-r1')
    fixture = pathlib.Path(__file__).resolve().parents[2] / 'router-replay/fixture-r2/result.json'
    replay = pathlib.Path('/dev/shm/sc117-router-fixture-cpu-20261028-r2/replay')
    assert digest(replay.read_bytes()) == json.loads(fixture.read_text())['binary_sha256']
    native_receipt = json.loads((native / 'receipt.json').read_text())
    assert native_receipt['full_sealed_source_hash_verified']
    native_files = {row['name']: row for row in native_receipt['members']}
    cpu_receipt = json.loads((cpu / 'receipt.json').read_text())
    assert cpu_receipt['passed'] and cpu_receipt['full_logits_bitwise_equal']
    records, payload = [], bytearray()

    def add(label, data, **metadata):
        assert len(data) == 2048
        records.append(dict(row=len(records), label=label, bytes=2048,
                            sha256=digest(data), **metadata))
        payload.extend(data)

    for layer in range(48):
        source = native / f'blk.{layer}.router.bin'
        raw = checked(source, native_files[source.name])
        target = out / f'native-host-replay-{layer:02d}'
        argv = ['nice', '-n', '19', 'taskset', '-c', '8-15', str(replay), str(source), str(target)]
        with (out / f'native-host-replay-{layer:02d}.log').open('w') as log:
            subprocess.run(argv, check=True, stdout=log, stderr=subprocess.STDOUT)
        add(f'native-host-probability-{layer:02d}', (target / 'native-probs.f32').read_bytes(),
            input_source=str(source), input_sha256=digest(raw), replay_argv=argv)
    for layer in range(48):
        name = f'on/layer-{layer:02d}-probabilities.f32'
        source = cpu / name
        add(f'actual-cpu-probability-{layer:02d}', checked(source, cpu_receipt['files'][name]),
            input_source=str(source))
    for replay_name in ('native-replay', 'cpu-replay'):
        for name in ('native-probs.f32', 'ggml-probs.f32'):
            source = saved / replay_name / name
            add(f'saved-tie-{replay_name}-{name}', source.read_bytes(), input_source=str(source))

    rng = random.Random(0x117B70)
    while len(records) < 512:
        row = len(records)
        kind = (row - 100) % 12
        if kind == 0: values = [1.0] * 512
        elif kind == 1: values = [(-0.0 if i % 2 else 0.0) for i in range(512)]
        elif kind == 2: values = list(range(512))
        elif kind == 3: values = list(reversed(range(512)))
        elif kind == 4: values = [min(i, 511 - i) for i in range(512)]
        elif kind == 5: values = [i % 7 for i in range(512)]
        elif kind == 6: values = [(i // 13) % 5 for i in range(512)]
        elif kind == 7:
            values = [((i + row) % 512) for i in range(512)]
            values = [(k + 256 if k % 2 else k + 1) if k < 256 else 2 * (k - 256) + 2 for k in values]
        elif kind == 8: values = [struct.unpack('<f', struct.pack('<I', 0x3f800000 + rng.randrange(8)))[0] for _ in range(512)]
        elif kind == 9: values = [struct.unpack('<f', struct.pack('<I', rng.randrange(32)))[0] for _ in range(512)]
        elif kind == 10: values = [rng.randrange(16) / 16 for _ in range(512)]
        else: values = [rng.random() for _ in range(512)]
        add(f'synthetic-{kind}-{row}', struct.pack('<512f', *values), synthetic=True)
    (out / 'input.f32').write_bytes(payload)
    receipts = [native / 'receipt.json', cpu / 'receipt.json', fixture, saved / 'result.json']
    manifest = dict(schema='ownrt.reference-sort-device-input.v1', rows=512, columns=512,
                    bytes=len(payload), sha256=digest(payload), gpu_executed=False,
                    actual_native_host_rows=48, actual_cpu_rows=48, saved_tie_rows=4,
                    synthetic_rows=412, seed=0x117B70, rows_detail=records,
                    replay_binary=dict(path=str(replay), sha256=digest(replay.read_bytes())),
                    source_receipts=[dict(path=str(p), sha256=digest(p.read_bytes())) for p in receipts])
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('rows_detail', 'source_receipts')}))

if __name__ == '__main__':
    main()
