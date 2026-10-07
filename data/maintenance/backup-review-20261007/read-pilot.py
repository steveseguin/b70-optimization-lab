"""One bounded, read-only comparison of known external/internal model bytes."""
from pathlib import Path
import hashlib
import json
import os
import time

out = Path(__file__).parent
internal = Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
external = Path('/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8')
assert os.path.ismount('/mnt/usb-models')
assert os.statvfs(external).f_flag & os.ST_RDONLY
pins = {
    'config.json': '99c11efba4012d0f760f4e4831a8d6cafd845044e21d0aa9e6d9e70a15a90a8d',
    'model.safetensors.index.json': '0419e2c2dfbb925257d7409405433a793cf7ff7d96f3eba882a815ec6d9fe7a6',
}
rows = []
started = time.monotonic()
for name, expected in pins.items():
    for root in (internal, external):
        data = (root / name).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        assert digest == expected, f'pinned hash mismatch: {root / name}'
        rows.append({'path': str(root/name), 'bytes': len(data), 'sha256': digest,
                     'pinned_match': True})
shards = sorted(set(json.loads((internal/'model.safetensors.index.json').read_text())['weight_map'].values()))
assert len(shards) == 131
for name in (shards[0], shards[-1]):
    assert Path(name).name == name
    size = (internal / name).stat().st_size
    assert (external / name).stat().st_size == size
    amount = min(32 * 1024**2, size // 2)
    for offset in (0, size - amount):
        digests = []
        for root in (internal, external):
            with (root/name).open('rb') as stream:
                stream.seek(offset)
                data = stream.read(amount)
                assert len(data) == amount
                digests.append(hashlib.sha256(data).hexdigest())
        assert digests[0] == digests[1], f'range mismatch: {name} at {offset}'
        rows.append({'internal_path': str(internal/name), 'external_path': str(external/name),
                     'offset': offset, 'bytes_per_copy': amount, 'sha256': digests[0],
                     'range_match': True, 'full_shard_verified': False})
result = {'status': 'bounded-read-passed', 'rows': rows,
          'elapsed_seconds': time.monotonic()-started,
          'scope': 'Pinned config/index and 128 MiB selected model ranges only; not full model/drive qualification'}
(out/'read-pilot.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({'status': result['status'], 'elapsed_seconds': result['elapsed_seconds']}))
