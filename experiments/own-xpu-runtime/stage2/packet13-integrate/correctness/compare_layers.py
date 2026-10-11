"""Exact fixture comparison; missing live-device files are pending, never passes."""
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
import numpy as np


def compare(cpu, other, expected_layers=48):
    rows = []
    for c in sorted(Path(cpu).glob('layer-*.bf16')):
        b = c.read_bytes()
        assert len(b) == 20480
        d = Path(other)/c.name
        row = dict(layer=int(c.stem.split('-')[1]), cpu_sha256=hashlib.sha256(b).hexdigest())
        if not d.exists() or d.stat().st_size != len(b):
            row.update(status='pending-missing-or-incomplete-fixture', exact=None)
        else:
            raw = d.read_bytes()
            x = np.frombuffer(b, dtype='<u2'); y = np.frombuffer(raw, dtype='<u2')
            a = (x.astype('<u4') << 16).view('<f4'); z = (y.astype('<u4') << 16).view('<f4')
            diffs = np.flatnonzero(x != y)
            k = int(diffs[0]) if len(diffs) else None
            maximum = int(np.argmax(np.abs(a-z)))
            row.update(status='compared', exact=b==raw, other_sha256=hashlib.sha256(raw).hexdigest(),
                       unequal_bf16_values=len(diffs), first_index=k,
                       first_values=None if k is None else dict(cpu=float(a[k]),other=float(z[k])),
                       max_abs=float(np.max(np.abs(a-z))), max_abs_index=maximum,
                       max_abs_values=dict(cpu=float(a[maximum]),other=float(z[maximum])),
                       rms_abs=float(np.sqrt(np.mean((a.astype('f8')-z)**2))),
                       other_rms=float(np.sqrt(np.mean(z.astype('f8')**2))))
        rows.append(row)
    compared = [r for r in rows if r['exact'] is not None]
    observed = next((r['layer'] for r in compared if not r['exact']), None)
    by_layer = {r['layer']:r for r in rows}
    contiguous = observed is not None and all(by_layer.get(i, {}).get('exact') is True for i in range(observed))
    complete = set(by_layer)==set(range(expected_layers)) and len(compared)==expected_layers
    return dict(expected_layers=expected_layers, cpu_layers=len(rows), compared_layers=len(compared),
                first_observed_divergent_layer=observed,
                first_divergent_layer=observed if contiguous else None,
                coverage_complete=complete,
                all_layers_match=complete and observed is None, rows=rows)


if __name__ == '__main__':
    result = compare(sys.argv[1], sys.argv[2], int(sys.argv[4]) if len(sys.argv)>4 else 48)
    result.update(cpu_fixture_root=sys.argv[1], other_fixture_root=sys.argv[2],
                  observed_utc=datetime.now(timezone.utc).isoformat())
    Path(sys.argv[3]).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
