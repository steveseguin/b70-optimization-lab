#!/usr/bin/env python3
"""Screen identical 32-row FP16 GEMMs with direct output slices; no server changes."""
import argparse
import json
import pathlib
import statistics
import time

import torch


def baseline(x, w, chunk=32):
    return torch.cat([torch.nn.functional.linear(x[i:i + chunk], w)
                      for i in range(0, len(x), chunk)], dim=0)


def direct_out(x, w, chunk=32):
    out = torch.empty((len(x), len(w)), device=x.device, dtype=x.dtype)
    for i in range(0, len(x), chunk):
        torch.mm(x[i:i + chunk], w.t(), out=out[i:i + chunk])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--rows', default='33,128,512,1024')
    ap.add_argument('--repeats', type=int, default=8)
    ap.add_argument('--shapes-json', help='JSON list of {label,n,k}; defaults to verified 4B/9B config shapes')
    a = ap.parse_args()
    path = pathlib.Path(a.out)
    if path.exists():
        raise SystemExit('refusing to overwrite output')
    shapes = json.loads(pathlib.Path(a.shapes_json).read_text()) if a.shapes_json else [
        {'label': '4b-tp1-lm_head', 'n': 248320, 'k': 2560},
        {'label': '4b-tp1-mtp_fc', 'n': 2560, 'k': 5120},
        {'label': '4b-tp1-gdn_out', 'n': 2560, 'k': 4096},
        {'label': '9b-tp1-lm_head', 'n': 248320, 'k': 4096},
        {'label': '9b-tp1-mtp_fc', 'n': 4096, 'k': 8192},
        {'label': '9b-tp1-gdn_out', 'n': 4096, 'k': 4096},
        {'label': '27b-tp2-lm_head', 'n': 124160, 'k': 5120},
        {'label': '27b-tp2-mtp_fc', 'n': 2560, 'k': 10240},
        {'label': '27b-tp2-gdn_out', 'n': 5120, 'k': 3072},
    ]
    torch.manual_seed(308)
    result = {'schema': 'rowchunk-direct-output-screen-v1', 'torch': torch.__version__,
              'device': torch.xpu.get_device_name(0), 'dtype': 'float16',
              'chunk': 32, 'rows': [], 'passed': True,
              'scope': 'operator screening only; no server lossless or decode claim'}
    with torch.inference_mode():
        for shape in shapes:
            n, k = shape['n'], shape['k']
            w = torch.randn((n, k), device='xpu', dtype=torch.float16) * 0.02
            for m in map(int, a.rows.split(',')):
                for pattern in ('mixed', 'zero'):
                    x = torch.randn((m, k), device='xpu', dtype=torch.float16)
                    if pattern == 'zero':
                        x.zero_()
                    else:
                        x[::3].mul_(0.01)
                        x[1::3].mul_(4)
                    expected = baseline(x, w)
                    actual = direct_out(x, w)
                    # Integer views reject signed-zero differences as well.
                    differences = int((expected.view(torch.int16) != actual.view(torch.int16)).sum().item())
                    del actual
                    repeat_differences = {}
                    for name, fn in [('baseline', baseline), ('direct_out', direct_out)]:
                        repeated = fn(x, w)
                        repeat_differences[name] = int((expected.view(torch.int16) != repeated.view(torch.int16)).sum().item())
                        del repeated
                    del expected
                    row = dict(shape, m=m, pattern=pattern, bit_differences=differences,
                               repeat_bit_differences=repeat_differences)
                    if differences or any(repeat_differences.values()):
                        result['passed'] = False
                    else:
                        samples = {'baseline': [], 'direct_out': []}
                        for iteration in range(a.repeats + 2):
                            order = [('baseline', baseline), ('direct_out', direct_out)]
                            if iteration % 2:
                                order.reverse()
                            for name, fn in order:
                                torch.xpu.synchronize()
                                start = time.perf_counter()
                                y = fn(x, w)
                                torch.xpu.synchronize()
                                duration = (time.perf_counter() - start) * 1000
                                del y
                                if iteration >= 2:
                                    samples[name].append(duration)
                        row['samples_ms'] = samples
                        row['median_ms'] = {name: statistics.median(values) for name, values in samples.items()}
                        row['speedup'] = row['median_ms']['baseline'] / row['median_ms']['direct_out']
                    result['rows'].append(row)
                    path.write_text(json.dumps(result, indent=2) + '\n')
                    print(json.dumps(row), flush=True)
                    del x
            del w
    raise SystemExit(0 if result['passed'] else 3)


if __name__ == '__main__':
    main()
