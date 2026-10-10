#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Rehash frozen receipts/headers and recompute admission; stdlib CPU only."""
import hashlib
import json
from pathlib import Path
import stat
import struct

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
d = json.loads((HERE/'continuation130-residency.json').read_text())
checks = []
for name, info in d['sources'].items():
    path = Path(name)
    if not path.is_absolute(): path = REPO / path
    assert stat.S_ISREG(path.stat().st_mode), name
    with path.open('rb') as stream:
        if 'header_with_length_sha256' in info:
            prefix = stream.read(8)
            length, = struct.unpack('<Q', prefix)
            assert 0 < length <= 16*1024*1024
            raw = prefix + stream.read(length)
            assert len(raw) == 8+length
            expected = info['header_with_length_sha256']
            assert path.stat().st_size == info['file_bytes']
            kind = 'safetensors-header-only'
        else:
            raw = stream.read()
            expected = info['sha256']
            assert len(raw) == info['bytes'], name
            kind = 'regular-evidence-file'
    assert hashlib.sha256(raw).hexdigest() == expected, name
    checks.append(dict(path=name, kind=kind, passed=True))
gib=2**30
s=d['shortfall']
assert s['transient_bytes'] == 13*gib//2 and s['floor_bytes']==2*gib
assert s['unchanged_screening_bytes']==3*gib//4 and s['near_floor_band_bytes']==gib//2
base=s['transient_bytes']+s['floor_bytes']-s['refusal_free_bytes']
assert base==s['base_deficit_bytes']==661405696
assert base+gib//2==s['deficit_including_near_floor_band_bytes']
assert base+3*gib//4==s['actual_deficit_bytes']==1466712064
assert sum(d['text_layer_bytes'][str(i)] for i in range(24))+sum(d['text_nonlayer_bytes'].values())==d['text_primary_bytes']
assert sum(d['text_layer_bytes'][str(i)] for i in range(24,48))==d['text_secondary_bytes']
for row in d['failure_snapshots']:
    assert row['reserved']-row['allocated']==row['reserved_minus_allocated_bytes']
for i in range(4):
    card='xpu:%d'%i
    assert min(row['free_bytes'][card] for row in d['qualification_snapshots'])==d['qualification_phase_minimum_free_bytes'][card]
for row in d['reclaim_scenarios']:
    free=s['refusal_free_bytes']/gib+row['reclaimed_gib']
    assert row['post_reclaim_free_gib']==free
    assert row['margin_over_transient_and_floor_gib']==free-8.5
    assert row['clears_075_screen']==(free>=9.25)
print(json.dumps(dict(schema='ltx.stream130.residency-verification.v1', passed=True,
    source_checks=checks, source_count=len(checks), header_count=sum(x['kind']=='safetensors-header-only' for x in checks),
    snapshot_count=len(d['qualification_snapshots']), actual_deficit_bytes=s['actual_deficit_bytes'],
    guaranteed_reclaim_bytes=0, numerical_or_device_work=False),indent=2,ensure_ascii=False))
