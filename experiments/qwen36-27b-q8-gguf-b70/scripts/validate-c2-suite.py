#!/usr/bin/env python3
"""Validate paired c2 prompt calibration with the pinned Qwen tokenizer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

def load_prompt_builder(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("long_context_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load prompt builder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--tokenizer", required=True)
    parser.add_argument("--prompt-builder", type=Path, required=True)
    parser.add_argument("--ctx-size", type=int, default=32768)
    parser.add_argument("--output-tokens", type=int, default=512)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    try:
        import transformers
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "transformers is required; use the pinned validation Python environment"
        ) from exc

    suite = json.loads(args.suite.read_text())
    make_prompt = load_prompt_builder(args.prompt_builder)
    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer, trust_remote_code=True, local_files_only=True
    )

    rows: list[dict[str, Any]] = []
    passed = True
    for pair in suite.get("pairs", []):
        cases = pair.get("cases", [])
        if len(cases) != 2:
            raise SystemExit(f"band {pair.get('band')} must contain exactly two cases")
        pair_hashes: set[str] = set()
        for case in cases:
            prompt = make_prompt(case)
            encoded = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            token_ids = encoded["input_ids"]
            actual = len(token_ids)
            declared = int(case["calibrated_prompt_tokens"])
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
            pair_hashes.add(prompt_hash)
            row_passed = actual == declared and actual + args.output_tokens <= args.ctx_size
            passed = passed and row_passed
            rows.append(
                {
                    "band": pair["band"],
                    "case_id": case["id"],
                    "declared_prompt_tokens": declared,
                    "actual_prompt_tokens": actual,
                    "output_tokens": args.output_tokens,
                    "total_tokens": actual + args.output_tokens,
                    "ctx_size": args.ctx_size,
                    "prompt_sha256": prompt_hash,
                    "passed": row_passed,
                }
            )
        passed = passed and len(pair_hashes) == 2

    result = {
        "suite": str(args.suite),
        "suite_sha256": hashlib.sha256(args.suite.read_bytes()).hexdigest(),
        "tokenizer": args.tokenizer,
        "tokenizer_resolved": str(Path(args.tokenizer).resolve()),
        "tokenizer_class": tokenizer.__class__.__name__,
        "transformers_version": transformers.__version__,
        "chat_template_sha256": hashlib.sha256(
            str(tokenizer.chat_template).encode()
        ).hexdigest(),
        "prompt_builder": str(args.prompt_builder),
        "prompt_builder_sha256": hashlib.sha256(
            args.prompt_builder.read_bytes()
        ).hexdigest(),
        "ctx_size": args.ctx_size,
        "output_tokens": args.output_tokens,
        "rows": rows,
        "passed": passed and bool(rows),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered)
    print(rendered, end="")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
