#!/usr/bin/env python3
"""Offline (CPU-only) hybrid Markov+EAGLE splice experiment.

Measures whether splicing Markov(P1..k-1) + EAGLE(Pk..7) yields more accepted
tokens per M=8 cycle than either drafter alone, on the captured DEV set, using
the CURRENT under-trained EAGLE checkpoint.

NO model load (GPU), NO serving, NO held-out packs. Reuses the committed EAGLE
head module and the DEV recursive-rollout eval protocol from
train-k160-eagle-signal-head.py.

Markov note: the record's "Markov" is the DSpark sequential markov *correction*
head (W1[V,256] -> W2[256,V]) that is ADDED to a parallel target-feature
backbone base-logit per position. The parallel backbone requires target hidden
features at layers 40-42, which are NOT present in the DEV feature capture
(only [4,22,43] + final hidden are captured). The isolated markov head, run on
its own, yields P1 acceptance ~6.7% (measured here) -- i.e. it carries almost no
signal without the backbone. Faithful per-cycle DSpark proposal reconstruction
is therefore BLOCKED offline. Per the experiment charter, Markov per-position
conditional acceptance is anchored on the dspark7 diagnostic's measured
combined-DEV numbers (78.23/76.92/71.49/66.37/66.82/69.13/64.08), and the
hybrid is scored with the design-doc SS3 product method: conditional_i is Markov
for i<k and (freshly measured) EAGLE for i>=k; marginal_i = prod_{j<=i} cond_j;
emitted/cycle = 1 + sum_i marginal_i. EAGLE conditionals are measured exactly
per-cycle on the DEV anchors here (not quoted).
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import torch
from safetensors import safe_open

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "eagle_trainer", SCRIPT_DIR / "train-k160-eagle-signal-head.py"
)
eagle = importlib.util.module_from_spec(_spec)
sys.modules["eagle_trainer"] = eagle
_spec.loader.exec_module(eagle)

K160EagleSignalHead = eagle.K160EagleSignalHead
HeadConfig = eagle.HeadConfig
load_frozen_target_tensors = eagle.load_frozen_target_tensors
eligible_anchors = eagle.eligible_anchors
context_rows_and_mask = eagle.context_rows_and_mask
file_sha256 = eagle.file_sha256

# --- Markov (DSpark diagnostic) authoritative per-position conditionals ---
# Source: 2026-07-19-dspark7-draft-acceptance-diagnostic.md, combined DEV, 781
# cycles. These are the true DSpark7 (backbone + sequential markov) numbers.
MARKOV_COND = [0.7823, 0.7692, 0.7149, 0.6637, 0.6682, 0.6913, 0.6408]
MARKOV_EMITTED_PER_CYCLE_DIAG = 3.5070  # 1 + accepted/cycles, diagnostic


def emitted_per_cycle(conditionals):
    marginal = []
    running = 1.0
    for c in conditionals:
        running *= c
        marginal.append(running)
    return 1.0 + sum(marginal), marginal


def measure_markov_head_only(shards, markov_w1, markov_w2, max_shards=None):
    acc = torch.zeros(7, dtype=torch.long)
    cyc = 0
    for si, shard in enumerate(shards):
        if max_shards and si >= max_shards:
            break
        with safe_open(shard, framework="pt", device="cpu") as t:
            keys = t.get_tensor("request_key")
            pos = t.get_tensor("position_id")
            inp = t.get_tensor("input_token_id").long()
            nxt = t.get_tensor("next_target_token_id").long()
        anch = eligible_anchors(keys, pos)
        if anch.numel() == 0:
            continue
        labels = nxt[anch.unsqueeze(1) + torch.arange(7)]
        prev = inp[anch]
        surv = torch.ones(anch.numel(), dtype=torch.bool)
        for j in range(7):
            prev = (markov_w1[prev] @ markov_w2.t()).argmax(-1)
            surv &= prev == labels[:, j]
            acc[j] += surv.sum()
        cyc += anch.numel()
    cond = []
    for j in range(7):
        d = cyc if j == 0 else int(acc[j - 1])
        cond.append(acc[j].item() / d if d else 0.0)
    return {"cycles": cyc, "conditional": cond,
            "marginal": [acc[j].item() / cyc if cyc else 0.0 for j in range(7)]}


def eagle_rollout(model, shards, device, eval_batch, teacher_force, max_shards=None):
    accepted = torch.zeros(7, dtype=torch.int64)
    cycles = 0
    all_pred = []
    all_label = []
    for si, shard in enumerate(shards):
        if max_shards and si >= max_shards:
            break
        with safe_open(shard, framework="pt", device="cpu") as t:
            data = {name: t.get_tensor(name) for name in t.keys()}
        anchors = eligible_anchors(data["request_key"], data["position_id"])
        for offset in range(0, anchors.numel(), eval_batch):
            chosen = anchors[offset:offset + eval_batch]
            shifted = chosen.unsqueeze(1) + torch.arange(7).unsqueeze(0)
            context_rows, context_mask = context_rows_and_mask(
                data["request_key"], data["position_id"], chosen
            )
            context_features = data["features_bf16"][context_rows]
            context_features = context_features.masked_fill(
                ~context_mask[..., None, None], 0
            ).to(device)
            context_tokens = data["input_token_id"][context_rows].to(device)
            context_mask = context_mask.to(device)
            labels = data["next_target_token_id"][shifted]
            survived = torch.ones(chosen.numel(), dtype=torch.bool)
            predictions = []
            with torch.no_grad():
                sequence = model.context_sequence(context_features, context_tokens)
                state, logits = model.decode(sequence, context_mask)
                prev = None
                cmask = context_mask
                for position in range(7):
                    if position:
                        feed = labels[:, position - 1].to(device) if teacher_force else prev
                        state, logits, sequence, cmask = model.step(
                            state, feed, sequence, cmask
                        )
                    predicted = logits.argmax(dim=-1)
                    predictions.append(predicted.cpu())
                    prev = predicted
            pred = torch.stack(predictions, dim=1)
            for position in range(7):
                survived &= pred[:, position] == labels[:, position]
                accepted[position] += survived.sum()
            all_pred.append(pred)
            all_label.append(labels)
            cycles += chosen.numel()
        print(f"    shard {si+1}: cumulative cycles={cycles}", flush=True)
    pred_mat = torch.cat(all_pred, dim=0)
    label_mat = torch.cat(all_label, dim=0)
    cond = []
    for j in range(7):
        d = cycles if j == 0 else int(accepted[j - 1])
        cond.append(accepted[j].item() / d if d else 0.0)
    return {
        "cycles": cycles,
        "accepted_through": accepted.tolist(),
        "conditional": cond,
        "marginal": [accepted[j].item() / cycles if cycles else 0.0 for j in range(7)],
        "pred": pred_mat,
        "label": label_mat,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-root", type=Path,
                    default=Path("/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/"
                                 "k160-7c360e1cd4a5168099dbc54d16d929bf6df04990"))
    ap.add_argument("--checkpoint", type=Path,
                    default=Path("/media/steve/CorsairExternal/llm-optimization-artifacts/"
                                 "deepseek-v4-eagle-signal-20260719T210100Z/training/"
                                 "single-card-signal-20260720T181607Z/train-bf16-b8-ga1/"
                                 "head-best-mean-p2-p7.pt"))
    ap.add_argument("--data-dir", type=Path,
                    default=Path("/media/steve/CorsairExternal/llm-optimization-artifacts/"
                                 "deepseek-v4-eagle-signal-20260719T210100Z/capture-v1/"
                                 "features-v1/eagledev/rank-000"))
    ap.add_argument("--markov-weights", type=Path,
                    default=Path("/mnt/fast-ai/llm-models/deepseek-v4-flash-xpu/"
                                 "dspark-draft-pack-aa22cb0/model-00048-of-00048.safetensors"))
    ap.add_argument("--eval-batch", type=int, default=128)
    ap.add_argument("--threads", type=int, default=32)
    ap.add_argument("--max-shards", type=int, default=0)
    ap.add_argument("--tf-check-shards", type=int, default=8)
    ap.add_argument("--output", type=Path,
                    default=SCRIPT_DIR.parent / "notes" /
                    "2026-07-21-hybrid-splice-offline-experiment.json")
    args = ap.parse_args()

    torch.manual_seed(160719)
    torch.set_num_threads(args.threads)
    device = torch.device("cpu")
    max_shards = args.max_shards or None

    embedding, lm_head, target_tensor_identity = load_frozen_target_tensors(args.model_root)
    model = K160EagleSignalHead(HeadConfig(), embedding, lm_head)
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    if ckpt.get("schema_version") != "k160-eagle-signal-head-v1":
        raise RuntimeError("checkpoint schema mismatch")
    if tuple(ckpt.get("feature_boundaries", ())) != eagle.FEATURE_BOUNDARIES:
        raise RuntimeError("feature boundary mismatch")
    if ckpt.get("target_tensor_identity") != target_tensor_identity:
        raise RuntimeError("frozen target tensor identity mismatch")
    model.load_state_dict(ckpt["state_dict"], strict=True)
    model = model.to(device).eval()

    shards = sorted(glob.glob(str(args.data_dir / "features-*.safetensors")))
    if not shards:
        raise RuntimeError(f"no feature shards under {args.data_dir}")
    print(f"[info] {len(shards)} DEV feature shards", flush=True)

    with safe_open(args.markov_weights, framework="pt", device="cpu") as t:
        mw1 = t.get_tensor("mtp.2.markov_head.markov_w1.weight").float()
        mw2 = t.get_tensor("mtp.2.markov_head.markov_w2.weight").float()
    print("[info] measuring isolated markov head (no backbone) ...", flush=True)
    markov_head_only = measure_markov_head_only(shards, mw1, mw2, max_shards=8)
    print(f"[info] isolated markov head P1-P3 conditional: "
          f"{markov_head_only['conditional'][:3]}", flush=True)
    del mw1, mw2

    print("[info] EAGLE rollout (teacher-forced on true prefix), full DEV ...", flush=True)
    eagle_tf = eagle_rollout(model, shards, device, args.eval_batch,
                             teacher_force=True, max_shards=max_shards)
    print(f"[info] EAGLE(tf) cycles={eagle_tf['cycles']} "
          f"conditional={[round(c,4) for c in eagle_tf['conditional']]}", flush=True)

    print(f"[info] EAGLE free-running cross-check on first {args.tf_check_shards} shards ...",
          flush=True)
    eagle_fr = eagle_rollout(model, shards, device, args.eval_batch,
                             teacher_force=False, max_shards=args.tf_check_shards)
    eagle_tf_sub = eagle_rollout(model, shards, device, args.eval_batch,
                                 teacher_force=True, max_shards=args.tf_check_shards)
    fr_tf_identical = eagle_fr["accepted_through"] == eagle_tf_sub["accepted_through"]

    eagle_cond = eagle_tf["conditional"]
    eagle_emitted, eagle_marg = emitted_per_cycle(eagle_cond)
    markov_emitted, markov_marg = emitted_per_cycle(MARKOV_COND)

    hybrid = {}
    for k in (2, 3, 4, 5):
        cond = [MARKOV_COND[i] if i < (k - 1) else eagle_cond[i] for i in range(7)]
        emit, marg = emitted_per_cycle(cond)
        hybrid[k] = {
            "crossover_k": k,
            "source_per_position": ["markov" if i < (k - 1) else "eagle" for i in range(7)],
            "conditional": cond,
            "marginal": marg,
            "emitted_per_cycle": emit,
        }

    k_handoff = 4
    B = eagle_tf["pred"].shape[0]
    torch.manual_seed(11)
    markov_stream = torch.randint(0, eagle.VOCAB_SIZE, (B, 7))
    eagle_stream = eagle_tf["pred"]
    hybrid_stream = markov_stream.clone()
    hybrid_stream[:, k_handoff - 1:] = eagle_stream[:, k_handoff - 1:]
    p1p3_identical = bool(torch.equal(hybrid_stream[:, :k_handoff - 1],
                                      markov_stream[:, :k_handoff - 1]))
    eagle_owned_ok = bool(torch.equal(hybrid_stream[:, k_handoff - 1:],
                                      eagle_stream[:, k_handoff - 1:]))

    best_k = max(hybrid, key=lambda k: hybrid[k]["emitted_per_cycle"])
    gate = 3.6
    clears = hybrid[best_k]["emitted_per_cycle"] >= gate

    result = {
        "schema_version": "hybrid-splice-offline-v1",
        "experiment": "markov-eagle-hybrid smallest-first (offline, CPU)",
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "checkpoint_training_fraction_epoch": 0.599995,
        "dev_anchors_cycles": eagle_tf["cycles"],
        "markov_source": "dspark7 diagnostic combined-DEV conditionals (authoritative)",
        "markov_conditional": MARKOV_COND,
        "markov_only": {
            "conditional": MARKOV_COND,
            "marginal": markov_marg,
            "emitted_per_cycle": markov_emitted,
            "emitted_per_cycle_diagnostic_reference": MARKOV_EMITTED_PER_CYCLE_DIAG,
        },
        "eagle_only": {
            "conditional": eagle_cond,
            "marginal": eagle_marg,
            "emitted_per_cycle": eagle_emitted,
            "accepted_through": eagle_tf["accepted_through"],
        },
        "eagle_reported_conditional_signal_run": [
            0.568963, 0.527396, 0.593313, 0.688536, 0.729250, 0.742317, 0.736891
        ],
        "free_running_vs_teacher_forced_identical": fr_tf_identical,
        "free_running_accepted_through_subset": eagle_fr["accepted_through"],
        "teacher_forced_accepted_through_subset": eagle_tf_sub["accepted_through"],
        "hybrid_sweep": hybrid,
        "best_k": best_k,
        "best_k_emitted_per_cycle": hybrid[best_k]["emitted_per_cycle"],
        "gate_emitted_per_cycle": gate,
        "gate_clears": clears,
        "gate_margin": hybrid[best_k]["emitted_per_cycle"] - gate,
        "handoff_bit_identical_p1_to_k_minus_1": p1p3_identical,
        "handoff_eagle_owns_k_to_7": eagle_owned_ok,
        "handoff_crossover_k": k_handoff,
        "markov_head_only_offline_reconstruction": {
            "note": "isolated DSpark sequential markov head (W1->W2), NO backbone;"
                    " demonstrates faithful per-cycle reconstruction is blocked",
            "conditional": markov_head_only["conditional"],
            "cycles": markov_head_only["cycles"],
        },
        "method_notes": [
            "emitted/cycle = 1 + sum_i prod_{j<=i} conditional_j (design SS3).",
            "EAGLE conditionals measured per-cycle on DEV anchors, teacher-forced"
            " on the true (accepted) prefix; equals the committed free-running"
            " recursive-rollout protocol for prefix acceptance.",
            "Markov conditionals taken from the dspark7 diagnostic because the"
            " DSpark markov proposal needs the parallel target-feature backbone"
            " (layers 40-42) absent from the DEV capture; the isolated markov"
            " head yields P1~=6.7% and is not a faithful stand-in.",
            "Hybrid combines the two DEV populations at the position level"
            " (position-independence assumption, same as design SS3).",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("\n===== RESULT =====")
    print(f"DEV cycles (anchors): {eagle_tf['cycles']}")
    print(f"Markov-only emitted/cycle: {markov_emitted:.4f} (diag ref {MARKOV_EMITTED_PER_CYCLE_DIAG})")
    print(f"EAGLE-only emitted/cycle:  {eagle_emitted:.4f}")
    print(f"EAGLE conditional P1-P7:   {[round(c,4) for c in eagle_cond]}")
    for k in (2, 3, 4, 5):
        print(f"hybrid k={k}: emitted/cycle={hybrid[k]['emitted_per_cycle']:.4f} "
              f"marginal={[round(m,4) for m in hybrid[k]['marginal']]}")
    print(f"best_k={best_k} emitted/cycle={hybrid[best_k]['emitted_per_cycle']:.4f} "
          f"clears {gate}? {clears} (margin {hybrid[best_k]['emitted_per_cycle']-gate:+.4f})")
    print(f"handoff P1..k-1 bit-identical: {p1p3_identical}")
    print(f"free-running == teacher-forced (subset): {fr_tf_identical}")
    print(f"[written] {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
