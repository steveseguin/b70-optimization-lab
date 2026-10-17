"""CPU-only ELF section comparison; no device binary is loaded."""
from pathlib import Path
import subprocess
import re
import hashlib
import json

p = Path(__file__).resolve().parents[1]
rows = []
images = []
for directory in (p.with_name('packet61-spin-hcfusion'), p):
    f = directory / 'build/device/own-rt-iq3'
    text = subprocess.check_output(['readelf', '-SW', str(f)], text=True)
    m = re.search(r'__CLANG_OFFLOAD_BUNDLE__sycl-spir64\s+PROGBITS\s+[0-9a-f]+\s+([0-9a-f]+)\s+([0-9a-f]+)', text)
    assert m
    offset, size = (int(x, 16) for x in m.groups())
    with f.open('rb') as stream:
        stream.seek(offset)
        raw = stream.read(size)
    images.append(raw)
    rows.append(dict(binary=str(f), binary_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                     section='__CLANG_OFFLOAD_BUNDLE__sycl-spir64', offset=offset,
                     bytes=size, sha256=hashlib.sha256(raw).hexdigest()))
result = dict(passed=images[0] == images[1], device_executed=False,
              byte_identical_kernel_bundle=images[0] == images[1], rows=rows)
(p / 'evidence/kernel-bundle-identity.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
assert result['passed']
