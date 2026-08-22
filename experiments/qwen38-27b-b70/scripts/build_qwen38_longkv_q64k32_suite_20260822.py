#!/usr/bin/env python3
"""Deterministically build the 25-row long-KV validation suite (20260822).

Constructs three tiers (8/8/9 rows) from the frozen 25-prompt
qwen36-27b-int4-independent-validation-20260815-v1 suite, targeting
chat-templated prompt lengths near 1250/1550/1850 tokens so the strict
100-event metric window sits at KV ~1300/1600/1900 — the region where the
Q64xK32 chunk-native FA saving was operator-qualified (~75 us/call at
KV1300). The row count stays 25 because the sealed TP2 gate checker pins
exactly 25 prompts; keeping it means the sealed contract is untouched.
No randomness is used anywhere; rerunning this script on the same inputs
reproduces the identical suite bytes.

Each row is a legitimate synthesis task over real suite prompts presented as
background documents. Row prefixes are unique from the first token so no two
rows share a prefix (prefix caching is disabled in the lane and cached_tokens
is gated to zero regardless; this is defense in depth).

The suite is written with a per-row frozen prompt-token band; the campaign
gate requires the server-reported prompt_tokens to land inside the band.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_SUITE = Path(
    "/mnt/usb-models/bench-results/qwen38-27b-autoround-int4-b70/"
    "qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820/validation-suite.json"
)
SOURCE_SUITE_SHA256 = (
    "292dea6aaf60f53067fb63c9bc5aba15bd1c6e71c2601693e6750239edf9fa0c"
)
MODEL_DIR = Path("/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan")

TIER_TARGETS = (1250, 1550, 1850)
BAND_HALF_WIDTH = 75
TIER_SIZES = (8, 8, 9)
FILLER_SENTENCE = (
    "This paragraph is deterministic length-normalization text for the "
    "long-context evaluation harness and adds no task content. "
)
TASK_INSTRUCTION = (
    "Task: using only the numbered background documents above, write one "
    "prioritized action plan of at most twelve bullet points that addresses "
    "the most critical work items across all documents together. Cite the "
    "relevant document numbers inline in each bullet."
)
SUITE_ID = "qwen38-longkv-q64k32-20260822-v1"
METRIC = "99 inter-token intervals between generated events 1 and 100 after TTFT"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--tier-targets",
        default=",".join(str(t) for t in TIER_TARGETS),
        help="comma-separated chat-templated token targets, one per tier",
    )
    parser.add_argument(
        "--band-half-width", type=int, default=BAND_HALF_WIDTH
    )
    parser.add_argument("--suite-id", default=SUITE_ID)
    args = parser.parse_args()
    tier_targets = tuple(int(t) for t in args.tier_targets.split(","))
    if len(tier_targets) != len(TIER_SIZES):
        raise SystemExit("need exactly one target per tier")
    band_half_width = args.band_half_width

    actual = sha256_file(SOURCE_SUITE)
    if actual != SOURCE_SUITE_SHA256:
        raise SystemExit(
            f"source suite SHA mismatch: {actual} != {SOURCE_SUITE_SHA256}"
        )
    source = json.loads(SOURCE_SUITE.read_text(encoding="utf-8"))
    base_prompts = source["prompts"]
    if len(base_prompts) != 25:
        raise SystemExit("expected exactly 25 source prompts")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))

    def templated_len(text: str) -> int:
        rendered = tokenizer.apply_chat_template(
            [{"role": "user", "content": text}],
            add_generation_prompt=True,
            enable_thinking=False,
            tokenize=False,
        )
        return len(tokenizer(rendered, add_special_tokens=False).input_ids)

    filler_unit = templated_len(FILLER_SENTENCE * 2) - templated_len(
        FILLER_SENTENCE
    )
    if filler_unit <= 0:
        raise SystemExit("filler sentence has nonpositive marginal length")

    tier_of_row = [
        tier for tier, size in enumerate(TIER_SIZES) for _ in range(size)
    ]
    row_in_tier: list[int] = []
    for size in TIER_SIZES:
        row_in_tier.extend(range(size))
    rows = []
    for j in range(sum(TIER_SIZES)):
        tier = tier_of_row[j]
        target = tier_targets[tier]
        lo, hi = target - band_half_width, target + band_half_width
        row_id = f"longkv--tier{tier + 1}-row{row_in_tier[j] + 1}"

        header = (
            f"Long-context evaluation row {row_id}. The numbered background "
            "documents below precede a single synthesis task.\n\n"
        )
        docs: list[str] = []
        doc_source_ids: list[str] = []
        cursor = (j * 2 + 1) % len(base_prompts)
        body = header
        # Append whole documents while comfortably below target, leaving
        # headroom for the task instruction and filler fine-tuning.
        while True:
            entry = base_prompts[cursor]
            candidate_doc = (
                f"Document {len(docs) + 1} "
                f"(source id {entry['id']}):\n{entry['prompt']}\n\n"
            )
            trial = body + candidate_doc + TASK_INSTRUCTION
            if templated_len(trial) > target - 60:
                break
            docs.append(candidate_doc)
            doc_source_ids.append(entry["id"])
            body += candidate_doc
            cursor = (cursor + 3) % len(base_prompts)
        if not docs:
            raise SystemExit(f"row {row_id}: no document fit under target")

        # Deterministic filler to close the remaining gap into the band.
        current = templated_len(body + TASK_INSTRUCTION)
        deficit = target - current
        k = max(0, deficit // filler_unit)
        prompt_text = body + FILLER_SENTENCE * k + TASK_INSTRUCTION
        measured = templated_len(prompt_text)
        while measured < lo:
            k += 1
            prompt_text = body + FILLER_SENTENCE * k + TASK_INSTRUCTION
            measured = templated_len(prompt_text)
        while measured > hi and k > 0:
            k -= 1
            prompt_text = body + FILLER_SENTENCE * k + TASK_INSTRUCTION
            measured = templated_len(prompt_text)
        if not (lo <= measured <= hi):
            raise SystemExit(
                f"row {row_id}: measured {measured} outside band [{lo},{hi}]"
            )
        rows.append(
            {
                "group": f"longkv-tier{tier + 1}",
                "id": row_id,
                "original_id": row_id,
                "prompt": prompt_text,
                "builder_measured_prompt_tokens": measured,
                "prompt_token_band": [lo, hi],
                "document_source_ids": doc_source_ids,
                "filler_repeats": k,
            }
        )
        print(
            f"{row_id}: docs={len(docs)} filler={k} "
            f"templated_tokens={measured} band=[{lo},{hi}]"
        )

    suite = {
        "description": (
            "Deterministic 25-row long-KV synthesis suite (tiers 8/8/9) "
            "built from the frozen 25-prompt validation suite; three tiers "
            "place the strict 100-event metric window at KV ~1300/1600/1900. "
            "Built for the Q64xK32 long-KV endpoint campaign with ignore_eos "
            "benchmark requests (bench-only), which makes the 100-event "
            "window structurally present on every row."
        ),
        "metric": METRIC,
        "prompts": rows,
        "source_suites": [
            {
                "group": "qwen38-postrecovery-marginfree-mtp5-25-spec-b-20260820",
                "path": str(SOURCE_SUITE),
                "sha256": SOURCE_SUITE_SHA256,
            }
        ],
        "suite_id": args.suite_id,
        "version": 1,
        "tokenizer_identity": {
            "model_dir": str(MODEL_DIR),
            "tokenizer_json_sha256": sha256_file(MODEL_DIR / "tokenizer.json"),
            "chat_template_kwargs": {"enable_thinking": False},
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(suite, indent=1, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}")
    print(f"suite sha256 {hashlib.sha256(text.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
