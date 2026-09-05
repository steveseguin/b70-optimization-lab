#!/usr/bin/env python3
"""Build the plain-GPTQ relabel of devan-carlin/Qwen3.8-27B-int4-AutoRound (R212, 2026-09-04).

The tensors are unchanged (hard links to the verified source copy; symlinks are invisible inside the serving
container). Only config.json and quantization_config.json are rewritten so vLLM selects AutoGPTQConfig ->
XPUwNa16LinearKernel (_xpu_C.int4_gemm_w4a16) instead of INC/ARK woqgemm. The fp16 layers of the AutoRound
extra_config become gptq `dynamic` exclusions; the mtp.fc exclusion is spelled `mt[p]\\.fc` because vLLM's
qwen3_5_mtp nulls the draft quant config whenever an exclusion key contains "mtp" (the draft layers are INT4).

usage: make-gptq-relabel.py SOURCE_DIR DEST_DIR [--manifest MANIFEST_JSON]
"""
import argparse, json, os, subprocess, sys

NOTE = ("R212: identical safetensors to devan-carlin/Qwen3.8-27B-int4-AutoRound bce40cac (hard-linked); config relabelled "
        "from auto-round/auto_round:auto_gptq packing to plain gptq so vLLM routes to XPUwNa16LinearKernel "
        "(_xpu_C.int4_gemm_w4a16) instead of INC/ARK woqgemm. fp16 layers carried over as gptq dynamic exclusions. "
        "The mtp.fc exclusion is spelled 'mt[p]\\.fc' so vLLM's qwen3_5_mtp does not null the draft quant config "
        "(the AutoRound draft layers are INT4).")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("dest"); ap.add_argument("--manifest")
    a = ap.parse_args()
    src, dst = os.path.abspath(a.source), os.path.abspath(a.dest)
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        if name in ("config.json", "quantization_config.json"):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            continue
        if os.path.exists(d) or os.path.islink(d):
            if os.path.islink(d) or not os.path.samefile(s, d):
                os.remove(d)
            else:
                continue
        os.link(s, d)
    q = json.load(open(os.path.join(src, "quantization_config.json")))
    assert q.get("quant_method") == "auto-round" and q.get("bits") == 4 and q.get("group_size") == 128 and q.get("sym") is True
    dyn = {}
    for k, v in q["extra_config"].items():
        if v.get("bits") == 16:
            dyn["-:" + k.replace("mtp\\.fc", "mt[p]\\.fc")] = {}
    newq = {"quant_method": "gptq", "bits": 4, "group_size": 128, "sym": True, "desc_act": False, "lm_head": False,
            "dynamic": dyn, "relabel_note": NOTE}
    c = json.load(open(os.path.join(src, "config.json")))
    c["quantization_config"] = newq
    json.dump(c, open(os.path.join(dst, "config.json"), "w"), indent=2)
    json.dump(newq, open(os.path.join(dst, "quantization_config.json"), "w"), indent=2)
    print(f"relabel written to {dst}: {len(dyn)} dynamic exclusions")
    if a.manifest:
        here = os.path.dirname(os.path.abspath(__file__))
        r = subprocess.run([sys.executable, os.path.join(here, "verify-model-direct.py"), a.manifest, dst])
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
