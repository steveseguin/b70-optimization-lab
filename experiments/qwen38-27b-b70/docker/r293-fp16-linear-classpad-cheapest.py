# R293: R292 + a cost-aware canonical class for small weights. q1 (R291) still read 8-9% below R224 at
# single user. Per call the pad costs a copy plus a GEMM at the class's first member instead of at M; for
# the 2560x4096 out-projection the most populous eligible class starts at 97 rows, so every single-row
# call ran as 97 rows (0.055 ms against 0.015 plain), ~24 times a step. For a weight below
# VLLM_XPU_FP16_LINEAR_CLASSPAD_BIG_BYTES (default 256 MiB) the canonical class is now the eligible class
# with the SMALLEST first member (33 here), since padding cost dominates at low M and the piece cost at
# high M is small for small N. Large weights (the vocabulary projection) keep the most populous class,
# where one extra piece costs a full weight read.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py")
s = p.read_text()
old = '''    if cands:
        canonical = max(cands, key=lambda c: (len(members[c]), -c))
'''
new = '''    if cands:
        big = weight.numel() * weight.element_size() >= _R293_BIG_BYTES
        if big:
            canonical = max(cands, key=lambda c: (len(members[c]), -c))
        else:
            canonical = min(cands, key=lambda c: (members[c][0], -len(members[c])))
'''
assert s.count(old) == 1
s = s.replace(old, new)
old2 = '_R291_BUFS: dict = {}\n'
new2 = '_R291_BUFS: dict = {}\n_R293_BIG_BYTES = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_CLASSPAD_BIG_BYTES", str(256 << 20)))\n'
assert s.count(old2) == 1
s = s.replace(old2, new2)
p.write_text(s)
print("R293 cheapest-class rule inserted; utils.py sha256", hashlib.sha256(s.encode()).hexdigest())
