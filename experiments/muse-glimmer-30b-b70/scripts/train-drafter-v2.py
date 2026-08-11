#!/usr/bin/env python3
"""Drafter fine-tune v2 with acceptance-predictive validation.

Differences vs v1 (which lost to stock):
- 85/15 train/val split at the SAMPLE level; validation metric is
  block-position-wise top-1 match rate vs the teacher tokens - the direct
  predictor of serving acceptance. The STOCK drafter is scored first and
  becomes the bar; checkpoints are kept only if they beat it on val.
- conservative LR (2e-5) with linear warmup, grad clipping, r=64 LoRA,
  more anchors per sample, up to 4 epochs with early stop on val.
"""
import glob, json, os, random
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoConfig
from safetensors.torch import load_file
from peft import LoraConfig, get_peft_model

FEAT_DIR = "/mnt/usb-models/muse-glimmer-30b-extra/distill-features-v3"
TARGET_DIR = "/mnt/usb-models/muse-glimmer-30b-hf"
DRAFTER_DIR = "/mnt/fast-ai/llm-models/muse-glimmer-dflash-hf"
OUT_DIR = "/mnt/usb-models/muse-glimmer-30b-extra/drafter-lora-v2"
CTX_CAP = 2048
ANCHORS_PER_SAMPLE = 12
VAL_ANCHORS = 6
EPOCHS = 4
LR = 2e-5
WARMUP = 100
DEV = "xpu:0"

def load_target_embeddings():
    idx = json.load(open(f"{TARGET_DIR}/model.safetensors.index.json"))
    wmap = idx["weight_map"]
    def pull(name):
        return load_file(f"{TARGET_DIR}/{wmap[name]}")[name]
    embd = pull("model.language_model.embed_tokens.weight").to(torch.bfloat16)
    head = pull("lm_head.weight" if "lm_head.weight" in wmap else "model.language_model.embed_tokens.weight").to(torch.bfloat16)
    return embd, head

def block_forward(drafter, d, t, block, mask_id, embd_w, head_w):
    ids = torch.tensor(d["ids"], dtype=torch.long)
    feats = d["features"]
    c0 = max(0, t + 1 - CTX_CAP)
    ctx = feats[:, c0:t+1].permute(1, 0, 2).reshape(t + 1 - c0, -1).unsqueeze(0).to(DEV, torch.bfloat16)
    noise_ids = torch.cat([ids[t:t+1], torch.full((block - 1,), mask_id, dtype=torch.long)])
    noise = F.embedding(noise_ids.to(DEV), embd_w).unsqueeze(0)
    pos = torch.arange(c0, t + 1 + block, device=DEV).unsqueeze(0)
    attn = torch.ones(1, t + 1 - c0 + block, device=DEV, dtype=torch.long)
    out = drafter(noise_embeds=noise, context_hidden_states=ctx,
                  position_ids=pos, attention_mask=attn, use_cache=False)
    h = out.last_hidden_state[:, 1:]
    logits = h.float() @ head_w.float().T
    labels = ids[t+1:t+block].to(DEV)
    return logits[0], labels

@torch.no_grad()
def validate(drafter, val_set, block, mask_id, embd_w, head_w, rng):
    drafter.eval()
    match_by_pos = torch.zeros(block - 1)
    n = 0
    for d in val_set:
        T = d["features"].shape[1]
        lo = max(1, d["prompt_len"] - 4)
        if T - lo < block + 2:
            continue
        for t in rng.sample(range(lo, T - block - 1), min(VAL_ANCHORS, T - block - 1 - lo)):
            logits, labels = block_forward(drafter, d, t, block, mask_id, embd_w, head_w)
            match_by_pos += (logits.argmax(-1) == labels).float().cpu()
            n += 1
    drafter.train()
    per_pos = (match_by_pos / max(1, n))
    # expected accepted run length: prod-sum of positionwise match (greedy chain)
    run = 0.0; p = 1.0
    for m in per_pos.tolist():
        p *= m; run += p
    return per_pos, run, n

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = AutoConfig.from_pretrained(DRAFTER_DIR)
    block, mask_id = cfg.block_size, cfg.mask_token_id
    files = sorted(glob.glob(f"{FEAT_DIR}/sample-*.pt"))
    rng = random.Random(20260811)
    rng.shuffle(files)
    n_val = max(6, len(files) * 15 // 100)
    val_files, train_files = files[:n_val], files[n_val:]
    print(f"{len(train_files)} train / {len(val_files)} val shards", flush=True)
    val_set = [torch.load(f) for f in val_files]

    drafter = AutoModel.from_pretrained(DRAFTER_DIR, dtype=torch.bfloat16).to(DEV)
    embd_w, head_w = load_target_embeddings()
    embd_w = embd_w.to(DEV); head_w = head_w.to(DEV)

    vrng = random.Random(7)
    per_pos, run0, n0 = validate(drafter, val_set, block, mask_id, embd_w, head_w, vrng)
    print(f"STOCK baseline: exp_run {run0:.3f}  pos1-5 {[round(x,3) for x in per_pos[:5].tolist()]}  (n={n0})", flush=True)

    lora = LoraConfig(r=64, lora_alpha=128, lora_dropout=0.05,
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
                      modules_to_save=["encoder"])
    drafter = get_peft_model(drafter, lora)
    drafter.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in drafter.parameters() if p.requires_grad], lr=LR)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / WARMUP))

    best_run = run0
    step = 0
    for ep in range(EPOCHS):
        rng.shuffle(train_files)
        for fp in train_files:
            d = torch.load(fp)
            T = d["features"].shape[1]
            lo = max(1, d["prompt_len"] - 4)
            if T - lo < block + 2:
                continue
            for t in rng.sample(range(lo, T - block - 1), min(ANCHORS_PER_SAMPLE, T - block - 1 - lo)):
                logits, labels = block_forward(drafter, d, t, block, mask_id, embd_w, head_w)
                loss = F.cross_entropy(logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_([p for p in drafter.parameters() if p.requires_grad], 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
                step += 1
                if step % 200 == 0:
                    print(f"ep{ep} step{step} loss {loss.item():.4f}", flush=True)
        vrng = random.Random(7)
        per_pos, run, n = validate(drafter, val_set, block, mask_id, embd_w, head_w, vrng)
        print(f"ep{ep} VAL: exp_run {run:.3f} (stock {run0:.3f})  pos1-5 {[round(x,3) for x in per_pos[:5].tolist()]}", flush=True)
        if run > best_run:
            best_run = run
            drafter.save_pretrained(f"{OUT_DIR}/best")
            print(f"ep{ep} new best -> saved", flush=True)
    print(f"training complete; best exp_run {best_run:.3f} vs stock {run0:.3f}; "
          f"{'IMPROVED' if best_run > run0 else 'NO IMPROVEMENT - do not ship'}", flush=True)

if __name__ == "__main__":
    main()
