#!/usr/bin/env python3
"""Build TP1 serving-input retrieval probes; does not run a model.

These 2K--32,000-input prompts are supporting serving evidence. They are not
exact measurements of the website's numeric ``active_context_tokens`` axis.
In particular, 32,000 input plus 128 requested output is not the exact 32,768
active-context cell, and this suite has no active-context-zero row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from transformers import AutoTokenizer


MODEL = Path("/mnt/usb-models/llm-models/qwen3.8-27b-int4-autoround-devan")
TARGETS = (2048, 4096, 8192, 16384, 24576, 32000)
POSITIONS = (("early", 0.25), ("middle", 0.50), ("late", 0.75))
FILLER = (
    "Archive note: the observatory recorded calm weather, routine maintenance, "
    "and an unchanged calibration schedule for the following shift. "
)


def token_count(tokenizer, prompt: str) -> int:
    messages = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, enable_thinking=False
    )
    return len(ids)


def make_prompt(tokenizer, target: int, position_name: str, fraction: float) -> tuple[str, int, str]:
    marker = f"NDCTX-{target}-{position_name}-B2DD"
    needle = f" The unique retrieval marker is {marker}. "
    prefix = (
        "Read the archive. Begin your answer with the unique retrieval marker exactly, "
        "then explain in plain prose where it appeared. Do not omit the marker.\n\n"
    )
    suffix = "\n\nAnswer now; begin with the marker and continue for roughly 110 words."

    low, high = 1, 1
    while token_count(tokenizer, prefix + FILLER * high + needle + suffix) < target:
        high *= 2
    while low < high:
        mid = (low + high) // 2
        left = int(mid * fraction)
        prompt = prefix + FILLER * left + needle + FILLER * (mid - left) + suffix
        if token_count(tokenizer, prompt) < target:
            low = mid + 1
        else:
            high = mid

    candidates = []
    for repetitions in range(max(1, low - 3), low + 2):
        left = int(repetitions * fraction)
        prompt = prefix + FILLER * left + needle + FILLER * (repetitions - left) + suffix
        candidates.append((abs(target - token_count(tokenizer, prompt)), prompt))
    _, prompt = min(candidates, key=lambda item: item[0])
    actual = token_count(tokenizer, prompt)
    if not target - 16 <= actual <= target + 16:
        raise RuntimeError(f"could not construct {target}-token prompt: got {actual}")
    return prompt, actual, marker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if not MODEL.is_dir():
        raise SystemExit(f"missing model: {MODEL}")

    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    prompts = []
    for target in TARGETS:
        for position_name, fraction in POSITIONS:
            prompt, actual, marker = make_prompt(tokenizer, target, position_name, fraction)
            prompts.append(
                {
                    "group": f"context-{target}",
                    "id": f"context-{target}-{position_name}",
                    "original_id": f"context-{target}-{position_name}",
                    "prompt": prompt,
                    "requested_prompt_tokens": target,
                    "actual_prompt_tokens": actual,
                    "expected_prefix": marker,
                    "needle_position": position_name,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                }
            )

    payload = {
        "suite_id": "qwen38-b2dd-tp1-context-sentinels-v1",
        "version": 1,
        "description": "Three unique retrieval markers at each TP1 serving-input target; supporting evidence only, not exact active_context_tokens cells.",
        "metric": "decode_tok_s_1_100_after_ttft",
        "fixed_output_tokens": 128,
        "evidence_semantics": {
            "kind": "serving-input-probe",
            "fills_exact_active_context_axis": False,
            "active_context_zero_present": False,
            "input_32000_fills_active_context_32768": False,
        },
        "source_suites": [],
        "prompts": prompts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "prompts": len(prompts)}, sort_keys=True))


if __name__ == "__main__":
    main()
