# R276: make the R228 grouped GDN speculative branch capturable. It computed the token boundaries of each sequence group with
# `spec_query_start_loc[...].to("cpu").tolist()`, a device->host sync that XPU graph capture rejects ("wait method cannot be
# used for an event associated with a command graph"), so no verify batch above the group size (16 sequences = 80 tokens at
# depth 4) could ever be captured and c32/c64 ran the eager grouped path (R274/R275). In a speculative decode step every spec
# row has exactly num_speculative_tokens + 1 query tokens (padded drafter batch), so the boundaries are arithmetic:
# t = s * (k + 1). Use that whenever the host-side token count confirms uniform rows; keep the synchronous path otherwise.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/_xpu_ops.py"
s = open(p).read()
old = '''            sp_qs_cpu = spec_query_start_loc[: num_spec_decodes + 1].to("cpu", non_blocking=False).tolist()
'''
new = '''            _n_spec_tok = int(getattr(attn_metadata, "num_spec_decode_tokens", 0) or 0)
            _q = _n_spec_tok // num_spec_decodes if num_spec_decodes else 0
            if _q > 0 and _q * num_spec_decodes == _n_spec_tok and n_sp == _n_spec_tok:
                # R276: uniform spec rows (k+1 tokens each): arithmetic boundaries, no device sync, graph-capturable
                sp_qs_cpu = [i * _q for i in range(num_spec_decodes + 1)]
            else:
                sp_qs_cpu = spec_query_start_loc[: num_spec_decodes + 1].to("cpu", non_blocking=False).tolist()
'''
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
open(p, "w").write(s)
print("R276 sync-free GDN spec grouping inserted; _xpu_ops.py sha256", hashlib.sha256(s.encode()).hexdigest())
