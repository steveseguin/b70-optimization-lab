# R211: pad the row count of the ARK W4A16 GEMM in the nondeterministic band. R210 census on real AutoRound layers:
# run-to-run bit-identical at M<=16 and at M=512/1024, nondeterministic at M in [32,256] (3 of 4 shapes), and padding
# 60->512 rows is deterministic and row-consistent with a true M=512 call. Decode rows (M<=16) are never padded.
import hashlib
p = "/opt/venv/lib/python3.12/site-packages/vllm/model_executor/layers/quantization/inc/schemes/inc_ark_ops.py"
s = open(p).read()
old = "    ark = get_ark_state()[2]\n    assert ark is not None\n"
new = old + """    m = x.reshape(-1, x.shape[-1]).shape[0]
    pad_to = 0
    if _R211_PAD and 16 < m < 512:
        pad_to = 512
    elif _R211_PAD and 512 < m < 1024:
        pad_to = 1024
    elif _R211_PAD and m > 1024 and m % 512:
        pad_to = ((m + 511) // 512) * 512
    if pad_to:
        x2 = x.reshape(-1, x.shape[-1])
        xp = torch.zeros(pad_to, x2.shape[1], dtype=x2.dtype, device=x2.device)
        xp[:m].copy_(x2)
        out = ark.woqgemm_linear(xp, qweight, bias, out_features, in_features, group_size, compute_type, weight_type, scale_type, asym)
        return out[:m].reshape(x.shape[:-1] + (out_features,))
"""
assert s.count(old) == 1, "anchor"
s = s.replace(old, new)
assert "import torch" in s
s = s.replace("import torch\n", "import torch\nimport os as _r211_os\n_R211_PAD = _r211_os.environ.get(\"VLLM_XPU_ARK_PREFILL_PAD\", \"1\") == \"1\"\n", 1)
assert "_R211_PAD" in s
open(p, "w").write(s)
print("R211 ARK prefill-band padding inserted (VLLM_XPU_ARK_PREFILL_PAD, default 1); sha256", hashlib.sha256(s.encode()).hexdigest())
