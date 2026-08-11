#!/usr/bin/env python3
"""Teacher-forced feature extraction for DFlash drafter fine-tuning.

Reads harvest-v2-tokens.jsonl (exact prompt+generated token ids from the
serving fleet), runs the BF16 target with output_hidden_states, and saves
per-sample training shards: features at the drafter's tap layers
{1,13,25,37,49} (layer INPUTS, i.e. hidden_states[k]) as bf16, plus the
token stream. Run inside the muse-distill venv on 2 XPUs.
"""
import json, os, sys, glob
import torch
from transformers import AutoModelForImageTextToText, AutoConfig

TARGET_DIR = "/mnt/usb-models/muse-glimmer-30b-hf"
HARVEST = "/mnt/fast-ai/bench-results/muse-glimmer-30b/distill/harvest-v2-tokens.jsonl"
OUT_DIR = "/mnt/usb-models/muse-glimmer-30b-extra/distill-features"
TAP_LAYERS = [1, 13, 25, 37, 49]  # llama.cpp layer-input == hf hidden_states[k]
MAX_SEQ = 1024

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = AutoConfig.from_pretrained(TARGET_DIR)
    print("target:", cfg.model_type, flush=True)
    model = AutoModelForImageTextToText.from_pretrained(
        TARGET_DIR, dtype=torch.bfloat16, device_map="balanced",
        max_memory={0: "28GiB", 1: "28GiB"})
    model.eval()
    done = {os.path.basename(p) for p in glob.glob(f"{OUT_DIR}/*.pt")}
    rows = [json.loads(l) for l in open(HARVEST)]
    print(f"{len(rows)} harvest rows, {len(done)} already extracted", flush=True)
    for idx, row in enumerate(rows):
        name = f"sample-{idx:04d}.pt"
        if name in done:
            continue
        ids = (row["prompt_tokens"] + row["gen_tokens"])[:MAX_SEQ]
        input_ids = torch.tensor([ids], dtype=torch.long)
        with torch.no_grad():
            out = model(input_ids.to(model.device), output_hidden_states=True, use_cache=False)
        feats = torch.stack([out.hidden_states[k][0].to(torch.bfloat16).cpu() for k in TAP_LAYERS])  # [5, T, n_embd]
        torch.save({"prompt_len": len(row["prompt_tokens"]), "ids": ids,
                    "tap_layers": TAP_LAYERS, "features": feats}, f"{OUT_DIR}/{name}")
        if idx % 10 == 0:
            print(f"extracted {idx}/{len(rows)}", flush=True)
    print("extraction complete", flush=True)

if __name__ == "__main__":
    main()
