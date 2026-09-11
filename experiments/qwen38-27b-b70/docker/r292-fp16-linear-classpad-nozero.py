# R292: R291 without the per-call zeroing of pad rows. Within a verified class every real row's bits are
# independent of the other rows' contents (the position test rolls real rows through every slot), so the
# pad rows may hold whatever the previous call left. Saves one kernel per padded call; q1 on R291 still
# read 8-9% below R224 at single user with ~75 padded calls a step. VLLM_XPU_FP16_LINEAR_CLASSPAD_ZERO_PAD=1
# restores the zeroing for A/B use.
import hashlib, pathlib
p = pathlib.Path("/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/utils.py")
s = p.read_text()
old = '''    buf[:m].copy_(x2)
    buf[m:].zero_()
'''
new = '''    buf[:m].copy_(x2)
    if _R292_ZERO_PAD:
        buf[m:].zero_()
'''
assert s.count(old) == 1
s = s.replace(old, new)
old2 = '_R291_BUFS: dict = {}\n'
new2 = '_R291_BUFS: dict = {}\n_R292_ZERO_PAD = int(__import__("os").environ.get("VLLM_XPU_FP16_LINEAR_CLASSPAD_ZERO_PAD", "0"))\n'
assert s.count(old2) == 1
s = s.replace(old2, new2)
p.write_text(s)
print("R292 no-zero pad inserted; utils.py sha256", hashlib.sha256(s.encode()).hexdigest())
