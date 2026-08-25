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
    # Transformers versions/tokenizer implementations may return a plain ID
    # list, a one-row nested list/tensor, or a BatchEncoding. ``len`` on a
    # BatchEncoding counts mapping keys, not tokens.
    if hasattr(ids, "get"):
        input_ids = ids.get("input_ids")
        if input_ids is not None:
            ids = input_ids
    shape = getattr(ids, "shape", None)
    if shape is not None:
        return int(shape[-1])
    if ids and isinstance(ids[0], (list, tuple)):
        ids = ids[0]
    return len(ids)


def tokenizer_file_hashes(model: Path) -> dict[str, str]:
    names = (
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "added_tokens.json",
        "chat_template.jinja",
    )
    hashes = {}
    for name in names:
        path = model / name
        if path.is_file():
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if "tokenizer.json" not in hashes or "tokenizer_config.json" not in hashes:
        raise RuntimeError("tokenizer identity files are incomplete")
    return hashes


def make_prompt(tokenizer, target: int, position_name: str, fraction: float) -> tuple[str, int, str]:
    marker = f"NDCTX-{target}-{position_name}-B2DD"
    needle = f" The unique retrieval marker is {marker}. "
    prefix = (
        "Read the archive. Begin your answer with the unique retrieval marker exactly, "
        "then explain in plain prose where it appeared. Do not omit the marker.\n\n"
    )
    suffix = "\n\nAnswer now; begin with the marker and continue for roughly 110 words."

    def prompt_for(repetitions: int) -> str:
        left = int(repetitions * fraction)
        return prefix + FILLER * left + needle + FILLER * (repetitions - left) + suffix

    # Repeated natural-language filler has an effectively linear token cost.
    # Estimate that slope from a small bounded probe instead of exponentially
    # tokenizing candidates far beyond the model context (the old search could
    # briefly construct a 376K-token candidate while targeting 32K).
    base_tokens = token_count(tokenizer, prompt_for(0))
    probe_repetitions = 64
    probe_tokens = token_count(tokenizer, prompt_for(probe_repetitions))
    tokens_per_repeat = (probe_tokens - base_tokens) / probe_repetitions
    if tokens_per_repeat <= 0:
        raise RuntimeError("filler did not increase the prompt token count")

    repetitions = max(1, round((target - base_tokens) / tokens_per_repeat))
    for _ in range(4):
        actual = token_count(tokenizer, prompt_for(repetitions))
        if target - 16 <= actual <= target + 16:
            prompt = prompt_for(repetitions)
            return prompt, actual, marker
        correction = round((target - actual) / tokens_per_repeat)
        if correction == 0:
            correction = 1 if actual < target else -1
        repetitions = max(1, repetitions + correction)

    candidates = []
    for candidate in range(max(1, repetitions - 4), repetitions + 5):
        prompt = prompt_for(candidate)
        candidates.append((abs(target - token_count(tokenizer, prompt)), prompt))
    _, prompt = min(candidates, key=lambda item: item[0])
    actual = token_count(tokenizer, prompt)
    if not target - 16 <= actual <= target + 16:
        raise RuntimeError(f"could not construct {target}-token prompt: got {actual}")
    return prompt, actual, marker


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--model",
        type=Path,
        default=MODEL,
        help=f"tokenizer/model directory (default: {MODEL})",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if not args.model.is_dir():
        raise SystemExit(f"missing model: {args.model}")

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "transformers is required to generate the suite; use the vLLM "
            "environment or another Python environment that provides it"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
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
        "tokenizer_source": {
            "logical_model": "Qwen3.8-27B AutoRound INT4",
            "files_sha256": tokenizer_file_hashes(args.model),
        },
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
