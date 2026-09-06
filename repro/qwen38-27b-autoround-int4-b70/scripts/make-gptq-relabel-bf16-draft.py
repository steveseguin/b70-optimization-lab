#!/usr/bin/env python3
"""Build the gptq relabel of the AutoRound INT4 checkpoint with a full-precision (BF16) MTP draft layer (R244, 2026-09-05).

Backbone: devan-carlin/Qwen3.8-27B-int4-AutoRound tensors (hard links, minus the INT4 mtp.* tensors, which are dropped
from the shard that holds them). Draft: the 15 BF16 mtp.* tensors of SergiioB/Qwen3.8-27B-GPTQ-Int4-sym-G128-MTP-BF16
(bit-identical to Qwen/Qwen3.8-27B), written to model-mtp-bf16.safetensors. The gptq config excludes mtp.* (`-:mtp.*`),
which makes vLLM's qwen3_5_mtp build the draft module unquantized. The draft only proposes tokens; the target verifies,
so this changes acceptance (speed), never the sampled output.

usage: make-gptq-relabel-bf16-draft.py AUTOROUND_DIR BF16_MTP_DIR DEST_DIR
"""
import json, os, sys
from safetensors import safe_open
from safetensors.torch import save_file

src, mtp_src, dst = (os.path.abspath(a) for a in sys.argv[1:4])
os.makedirs(dst, exist_ok=True)
idx = json.load(open(f"{src}/model.safetensors.index.json"))
wm = idx["weight_map"]
mtp_shards = sorted({f for k, f in wm.items() if k.startswith("mtp.")})
print("AutoRound mtp tensors live in", mtp_shards)
# 1. hard-link every file except configs, the index and the mtp shard(s)
for name in sorted(os.listdir(src)):
    p = os.path.join(src, name)
    if os.path.isdir(p) or name in ("config.json", "quantization_config.json", "model.safetensors.index.json") or name in mtp_shards:
        continue
    d = os.path.join(dst, name)
    if os.path.lexists(d): os.remove(d)
    os.link(p, d)
# 2. rewrite the mtp shard(s) without mtp.* tensors
new_wm = {k: f for k, f in wm.items() if not k.startswith("mtp.")}
for shard in mtp_shards:
    keep = {}
    with safe_open(f"{src}/{shard}", "pt") as f:
        meta = f.metadata()
        for k in f.keys():
            if not k.startswith("mtp."):
                keep[k] = f.get_tensor(k)
    save_file(keep, f"{dst}/{shard}", metadata=meta or {"format": "pt"})
    print(f"rewrote {shard}: kept {len(keep)} tensors")
# 3. BF16 mtp tensors from the community checkpoint
midx = json.load(open(f"{mtp_src}/model.safetensors.index.json"))["weight_map"]
mtp_keys = sorted(k for k in midx if k.startswith("mtp."))
by_file = {}
for k in mtp_keys: by_file.setdefault(midx[k], []).append(k)
mtp = {}
for f, ks in by_file.items():
    with safe_open(f"{mtp_src}/{f}", "pt") as h:
        for k in ks:
            t = h.get_tensor(k); mtp[k] = t
print("BF16 mtp tensors:", len(mtp), {k: (str(v.dtype), tuple(v.shape)) for k, v in list(mtp.items())[:3]})
assert all(v.dtype.is_floating_point for v in mtp.values()), "draft tensors must be floating point"
save_file(mtp, f"{dst}/model-mtp-bf16.safetensors", metadata={"format": "pt"})
for k in mtp: new_wm[k] = "model-mtp-bf16.safetensors"
idx["weight_map"] = new_wm
json.dump(idx, open(f"{dst}/model.safetensors.index.json", "w"), indent=2)
# 4. configs: plain gptq with the fp16 layers and the whole mtp module excluded
q = json.load(open(f"{src}/quantization_config.json"))
dyn = {f"-:{k}": {} for k, v in q["extra_config"].items() if v.get("bits") == 16 and "mtp" not in k}
dyn["-:mtp.*"] = {}
newq = {"quant_method": "gptq", "bits": 4, "group_size": 128, "sym": True, "desc_act": False, "lm_head": False, "dynamic": dyn,
        "relabel_note": "R244: AutoRound INT4 backbone (devan-carlin bce40cac, hard-linked; INT4 mtp.* tensors dropped) with the BF16 mtp.* draft tensors of SergiioB/Qwen3.8-27B-GPTQ-Int4-sym-G128-MTP-BF16 (bit-identical to Qwen/Qwen3.8-27B) in model-mtp-bf16.safetensors; plain gptq config; '-:mtp.*' makes vLLM build the draft unquantized."}
c = json.load(open(f"{src}/config.json")); c["quantization_config"] = newq
json.dump(c, open(f"{dst}/config.json", "w"), indent=2); json.dump(newq, open(f"{dst}/quantization_config.json", "w"), indent=2)
print("done:", dst, "| dynamic exclusions:", len(dyn))
