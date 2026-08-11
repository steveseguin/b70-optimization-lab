#!/usr/bin/env python3
"""LoRA fine-tune of the DFlash drafter on the fleet's serving distribution.

Faithful to the llama.cpp serving glue: features are target layer INPUTS
(hidden_states[k]) at tap layers {1,13,25,37,49}; noise block = raw
embedding of [anchor, mask x (block-1)]; logits via the frozen target head
at block positions 1..block-1; CE against the teacher-forced next tokens.
Context capped at 2048 (drafter attention is SWA-2048 everywhere).
Run in the muse-distill venv. Trains on XPU 0+1 while production is paused
or degraded; checkpoints go to USB.
"""
import glob, json, os, random, sys, time
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoConfig
from safetensors.torch import load_file
from peft import LoraConfig, get_peft_model

FEAT_DIR = "/mnt/usb-models/muse-glimmer-30b-extra/distill-features"
TARGET_DIR = "/mnt/usb-models/muse-glimmer-30b-hf"
DRAFTER_DIR = "/mnt/fast-ai/llm-models/muse-glimmer-dflash-hf"
OUT_DIR = "/mnt/usb-models/muse-glimmer-30b-extra/drafter-lora"
CTX_CAP = 2048
ANCHORS_PER_SAMPLE = 8
EPOCHS = 2
LR = 1e-4
DEV = "xpu:0"

def load_target_embeddings():
    # only tok_embd and output head are needed from the target; load lazily
    # from safetensors index without instantiating the 30B model
    idx = json.load(open(f"{TARGET_DIR}/model.safetensors.index.json"))
    wmap = idx["weight_map"]
    def pull(name):
        shard = wmap[name]
        return load_file(f"{TARGET_DIR}/{shard}")[name]
    embd = pull("model.embed_tokens.weight").to(torch.bfloat16)
    head_name = "lm_head.weight" if "lm_head.weight" in wmap else "model.embed_tokens.weight"
    head = pull(head_name).to(torch.bfloat16)
    return embd, head

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = AutoConfig.from_pretrained(DRAFTER_DIR)
    block = cfg.block_size
    mask_id = cfg.mask_token_id
    print(f"drafter block={block} mask_id={mask_id} taps={cfg.target_layer_ids}", flush=True)

    drafter = AutoModel.from_pretrained(DRAFTER_DIR, dtype=torch.bfloat16).to(DEV)
    lora = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.0,
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
                      modules_to_save=["encoder"])
    drafter = get_peft_model(drafter, lora)
    drafter.print_trainable_parameters()

    embd_w, head_w = load_target_embeddings()
    embd_w = embd_w.to(DEV); head_w = head_w.to(DEV)

    files = sorted(glob.glob(f"{FEAT_DIR}/sample-*.pt"))
    print(f"{len(files)} feature shards", flush=True)
    opt = torch.optim.AdamW([p for p in drafter.parameters() if p.requires_grad], lr=LR)
    rng = random.Random(20260811)
    step = 0
    for ep in range(EPOCHS):
        rng.shuffle(files)
        for fp in files:
            d = torch.load(fp)
            ids = torch.tensor(d["ids"], dtype=torch.long)
            feats = d["features"]  # [5, T, n_embd] bf16
            T = feats.shape[1]
            lo = max(1, d["prompt_len"] - 4)
            if T - lo < block + 2:
                continue
            anchors = rng.sample(range(lo, T - block - 1), min(ANCHORS_PER_SAMPLE, T - block - 1 - lo))
            for t in anchors:
                c0 = max(0, t + 1 - CTX_CAP)
                ctx = feats[:, c0:t+1].permute(1, 0, 2).reshape(t + 1 - c0, -1)  # [n_ctx, 5*n_embd]
                ctx = ctx.unsqueeze(0).to(DEV, torch.bfloat16)
                noise_ids = torch.cat([ids[t:t+1], torch.full((block - 1,), mask_id, dtype=torch.long)])
                noise = F.embedding(noise_ids.to(DEV), embd_w).unsqueeze(0)
                pos = torch.arange(c0, t + 1 + block, device=DEV).unsqueeze(0)
                attn = torch.ones(1, t + 1 - c0 + block, device=DEV, dtype=torch.long)
                out = drafter(noise_embeds=noise, context_hidden_states=ctx,
                              position_ids=pos, attention_mask=attn, use_cache=False)
                h = out.last_hidden_state[:, 1:]                      # [1, block-1, dim]
                logits = h.float() @ head_w.float().T                 # [1, block-1, vocab]
                labels = ids[t+1:t+block].to(DEV)
                loss = F.cross_entropy(logits[0], labels)
                loss.backward()
                opt.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 50 == 0:
                    print(f"ep{ep} step{step} loss {loss.item():.4f}", flush=True)
        drafter.save_pretrained(f"{OUT_DIR}/ep{ep}")
        print(f"saved {OUT_DIR}/ep{ep}", flush=True)
    print("training complete", flush=True)

if __name__ == "__main__":
    main()
