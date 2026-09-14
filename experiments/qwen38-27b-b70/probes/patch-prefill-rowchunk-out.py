#!/usr/bin/env python3
"""Candidate only: retain chunk arithmetic and <=32-row decode; opt in with env or the diagnostic cache-directory flag."""
import argparse
import pathlib

ap = argparse.ArgumentParser()
ap.add_argument('--path', default='/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py')
a = ap.parse_args()
p = pathlib.Path(a.path)
s = p.read_text()
old = '''    elif m <= chunk:
        out = torch.nn.functional.linear(x2, weight, bias)
    else:
        out = torch.cat(
'''
new = '''    elif m <= chunk:
        out = torch.nn.functional.linear(x2, weight, bias)
    elif bias is None and x.dtype == torch.float16 and (__import__("os").environ.get("VLLM_XPU_FP16_ROWCHUNK_DIRECT_OUT", "0") == "1" or __import__("os").path.isfile("/root/.cache/vllm/prefill-direct-out.enabled")):
        out = torch.empty((m, weight.shape[0]), dtype=x2.dtype, device=x2.device)
        for i in range(0, m, chunk):
            torch.mm(x2[i:i + chunk], weight.t(), out=out[i:i + chunk])
    else:
        out = torch.cat(
'''
if s.count(old) != 1:
    raise SystemExit('unexpected rowchunk source; refusing patch')
s = s.replace(old, new)
compile(s, str(p), 'exec')
p.write_text(s)
print('Patched opt-in direct-output rowchunk candidate:', p)
