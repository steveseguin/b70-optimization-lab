#!/usr/bin/env python3
"""Build simple EAGLE-1 training samples from vLLM hidden-state dump shards.

The vLLM dump stores one record per sampled token:

  hidden_states[row]       = target hidden state for the current token
  current_token_ids[row]   = token id that produced that hidden state
  positions[row]           = absolute model position for the current token
  sampled_token_ids[row]   = target greedy next token

EAGLE's original trainer expects per-sequence .pt files with:

  hidden_state: [T, hidden]
  input_ids:    [T]
  positions:    [T]
  loss_mask:    [T]

It then trains hidden_state[t] + input_ids[t + 1] -> hidden_state[t + 1].
This script stitches dumped rows by request id and splits on broken token
continuity, because a valid next row should have
current_token_id == previous sampled_token_id.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import torch


def torch_load(path: str) -> dict[str, Any]:
    try:
        return torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:
        return torch.load(path, map_location="cpu")


@dataclass
class SequenceBuffer:
    hidden: list[torch.Tensor] = field(default_factory=list)
    aux_hidden: list[torch.Tensor] = field(default_factory=list)
    input_ids: list[int] = field(default_factory=list)
    positions: list[int] = field(default_factory=list)
    sampled_next_ids: list[int] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    segments: int = 0

    def append(
        self,
        *,
        hidden_row: torch.Tensor,
        aux_hidden_row: torch.Tensor | None = None,
        current_token_id: int,
        position: int,
        sampled_token_id: int,
        source_file: str,
    ) -> None:
        self.hidden.append(hidden_row.detach().cpu().contiguous())
        if aux_hidden_row is not None:
            self.aux_hidden.append(aux_hidden_row.detach().cpu().contiguous())
        self.input_ids.append(int(current_token_id))
        self.positions.append(int(position))
        self.sampled_next_ids.append(int(sampled_token_id))
        self.source_files.append(source_file)

    def clear(self) -> None:
        self.hidden.clear()
        self.aux_hidden.clear()
        self.input_ids.clear()
        self.positions.clear()
        self.sampled_next_ids.clear()
        self.source_files.clear()
        self.segments += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help=(
            "Collector summary JSON from collect-qwen36-eagle-hidden-corpus.py. "
            "May repeat; request metadata is copied into saved samples."
        ),
    )
    parser.add_argument("--min-len", type=int, default=8)
    parser.add_argument("--max-len", type=int, default=2048)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--glob", default="step-*.pt")
    parser.add_argument("--hidden-dtype", default="native",
                        choices=("native", "float32", "float16", "bfloat16"))
    parser.add_argument(
        "--allow-missing-current-token-ids",
        action="store_true",
        help=(
            "Allow async no-spec dump shards where current_token_ids are -1. "
            "Continuity is reconstructed from per-request sampled_next IDs."
        ),
    )
    parser.add_argument(
        "--reconstruct-positions-from-num-tokens",
        action="store_true",
        help=(
            "When positions are missing, use num_tokens_no_spec - 2. In vLLM "
            "async no-spec dumps, num_tokens_no_spec has already advanced by "
            "the sampled token, so -2 recovers the current hidden row position."
        ),
    )
    return parser.parse_args()


def load_request_metadata(paths: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            compact = {
                "source_metadata_path": path,
                "index": record.get("index"),
                "offset": record.get("offset"),
                "suite_index": record.get("suite_index"),
                "prompt_id": record.get("prompt_id"),
                "family": record.get("family"),
                "prompt_sha256": record.get("prompt_sha256"),
                "text_sha256": record.get("text_sha256"),
                "output_tokens_actual": record.get("output_tokens_actual"),
                "metadata": record.get("metadata"),
            }
            for key in (
                "request_id",
                "response_x_request_id",
                "response_id",
            ):
                value = record.get(key)
                if isinstance(value, str) and value:
                    out[value] = compact
    return out


def lookup_request_metadata(
    req_id: str,
    request_metadata: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    exact = request_metadata.get(req_id)
    if exact is not None:
        return exact
    # vLLM may append a short unique suffix to the response/request id used in
    # hidden-state dump rows, e.g. collector response_id
    # "chatcmpl-qwen27-eagle-v2-000000-ops-runbook" can appear in dumps as
    # "chatcmpl-qwen27-eagle-v2-000000-ops-runbook-9b850c71".
    for key, metadata in request_metadata.items():
        if key and req_id.startswith(f"{key}-"):
            return metadata
    return {}


def cast_hidden(hidden: torch.Tensor, dtype_name: str) -> torch.Tensor:
    if dtype_name == "native":
        return hidden
    if dtype_name == "float32":
        return hidden.to(torch.float32)
    if dtype_name == "float16":
        return hidden.to(torch.float16)
    if dtype_name == "bfloat16":
        return hidden.to(torch.bfloat16)
    raise ValueError(dtype_name)


def save_buffer(
    *,
    req_id: str,
    buffer: SequenceBuffer,
    out_dir: str,
    sample_index: int,
    min_len: int,
    max_len: int,
    hidden_dtype: str,
    request_metadata: dict[str, dict[str, Any]],
) -> bool:
    if len(buffer.hidden) < min_len:
        return False
    hidden = torch.stack(buffer.hidden[:max_len], dim=0)
    hidden = cast_hidden(hidden, hidden_dtype)
    aux_hidden = None
    if len(buffer.aux_hidden) == len(buffer.hidden):
        aux_hidden = torch.stack(buffer.aux_hidden[:max_len], dim=0)
        aux_hidden = cast_hidden(aux_hidden, hidden_dtype)
    input_ids = torch.tensor(buffer.input_ids[:max_len], dtype=torch.long)
    positions = torch.tensor(buffer.positions[:max_len], dtype=torch.long)
    loss_mask = torch.ones(input_ids.shape[0], dtype=torch.long)
    sampled_next_ids = torch.tensor(
        buffer.sampled_next_ids[:max_len], dtype=torch.long
    )
    safe_req = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in req_id)
    path = os.path.join(out_dir, f"sample-{sample_index:06d}-{safe_req}.pt")
    metadata = lookup_request_metadata(req_id, request_metadata)
    payload = {
        "format": (
            "qwen36_eagle_sequence_v2"
            if aux_hidden is not None
            else "qwen36_eagle_sequence_v1"
        ),
        "req_id": req_id,
        "request_metadata": metadata,
        "prompt_id": metadata.get("prompt_id"),
        "family": metadata.get("family"),
        "prompt_sha256": metadata.get("prompt_sha256"),
        "hidden_state": hidden,
        "input_ids": input_ids,
        "positions": positions,
        "loss_mask": loss_mask,
        "sampled_next_token_ids": sampled_next_ids,
        "source_files": list(buffer.source_files[:max_len]),
    }
    if aux_hidden is not None:
        payload["aux_hidden_states"] = aux_hidden
    torch.save(payload, path)
    return True


def main() -> int:
    args = parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(args.dump_dir, args.glob)))
    request_metadata = load_request_metadata(args.metadata)

    buffers: dict[str, SequenceBuffer] = defaultdict(SequenceBuffer)
    sample_count = 0
    total_rows = 0
    usable_rows = 0
    invalid_current_token_rows = 0
    continuity_matches = 0
    continuity_breaks = 0
    position_matches = 0
    position_breaks = 0
    missing_position_rows = 0
    reconstructed_current_token_rows = 0
    reconstructed_position_rows = 0
    skipped_bad_files: list[str] = []
    samples_with_metadata = 0
    aux_rows_available = 0
    aux_rows_saved = 0
    aux_bad_files = 0

    def maybe_save(req_id: str) -> None:
        nonlocal sample_count, samples_with_metadata
        if args.max_samples and sample_count >= args.max_samples:
            return
        buffer = buffers[req_id]
        if save_buffer(
            req_id=req_id,
            buffer=buffer,
            out_dir=args.out_dir,
            sample_index=sample_count,
            min_len=args.min_len,
            max_len=args.max_len,
            hidden_dtype=args.hidden_dtype,
            request_metadata=request_metadata,
        ):
            if lookup_request_metadata(req_id, request_metadata):
                samples_with_metadata += 1
            sample_count += 1

    for path in paths:
        if args.max_samples and sample_count >= args.max_samples:
            break
        try:
            shard = torch_load(path)
            if shard.get("format") != "qwen36_eagle_hidden_step_v1":
                skipped_bad_files.append(path)
                continue
            hidden = shard["hidden_states"]
            aux_hidden_rows = None
            raw_aux_hidden = shard.get("aux_hidden_states")
            if isinstance(raw_aux_hidden, list) and raw_aux_hidden:
                if all(torch.is_tensor(t) for t in raw_aux_hidden):
                    try:
                        # Dump format stores one tensor per aux layer,
                        # [rows, hidden]. Dataset format keeps rows first:
                        # [rows, aux_layers, hidden].
                        aux_hidden_rows = torch.stack(raw_aux_hidden, dim=1)
                    except Exception:
                        aux_bad_files += 1
                        aux_hidden_rows = None
            elif torch.is_tensor(raw_aux_hidden):
                aux_hidden_rows = raw_aux_hidden
            req_ids = shard["req_ids"]
            current_ids = shard["current_token_ids"]
            positions = shard.get("positions")
            sampled_ids = shard["sampled_token_ids"]
            num_tokens_no_spec = shard.get("num_tokens_no_spec")
        except Exception:
            skipped_bad_files.append(path)
            continue

        rows = min(len(req_ids), len(current_ids), len(sampled_ids), hidden.shape[0])
        if aux_hidden_rows is not None:
            rows = min(rows, int(aux_hidden_rows.shape[0]))
            aux_rows_available += rows
        total_rows += rows
        for row in range(rows):
            req_id = str(req_ids[row])
            current_token_id = int(current_ids[row])
            sampled_token_id = int(sampled_ids[row])
            if positions is None:
                position = -1
                missing_position_rows += 1
            else:
                position = int(positions[row])
            if (
                position < 0
                and args.reconstruct_positions_from_num_tokens
                and num_tokens_no_spec is not None
                and row < len(num_tokens_no_spec)
            ):
                try:
                    candidate_position = int(num_tokens_no_spec[row]) - 2
                    if candidate_position >= 0:
                        position = candidate_position
                        reconstructed_position_rows += 1
                except Exception:
                    pass
            if current_token_id < 0:
                if not args.allow_missing_current_token_ids:
                    invalid_current_token_rows += 1
                    continue
                buffer = buffers[req_id]
                if buffer.sampled_next_ids:
                    current_token_id = buffer.sampled_next_ids[-1]
                else:
                    # The trainer consumes sampled_next_token_ids for draft
                    # inputs; input_ids are retained for audit/continuity only.
                    current_token_id = sampled_token_id
                reconstructed_current_token_rows += 1

            buffer = buffers[req_id]
            if buffer.sampled_next_ids:
                expected = buffer.sampled_next_ids[-1]
                if current_token_id == expected:
                    continuity_matches += 1
                else:
                    continuity_breaks += 1
                    maybe_save(req_id)
                    buffer.clear()
                if position >= 0 and buffer.positions:
                    if position == buffer.positions[-1] + 1:
                        position_matches += 1
                    else:
                        position_breaks += 1

            buffer.append(
                hidden_row=hidden[row],
                aux_hidden_row=(
                    aux_hidden_rows[row] if aux_hidden_rows is not None else None
                ),
                current_token_id=current_token_id,
                position=position,
                sampled_token_id=sampled_token_id,
                source_file=os.path.basename(path),
            )
            usable_rows += 1
            if aux_hidden_rows is not None:
                aux_rows_saved += 1

    if not (args.max_samples and sample_count >= args.max_samples):
        for req_id in list(buffers):
            if args.max_samples and sample_count >= args.max_samples:
                break
            maybe_save(req_id)

    summary = {
        "dump_dir": args.dump_dir,
        "out_dir": args.out_dir,
        "input_files": len(paths),
        "skipped_bad_files": skipped_bad_files[:20],
        "skipped_bad_file_count": len(skipped_bad_files),
        "total_rows": total_rows,
        "usable_rows": usable_rows,
        "invalid_current_token_rows": invalid_current_token_rows,
        "reconstructed_current_token_rows": reconstructed_current_token_rows,
        "continuity_matches": continuity_matches,
        "continuity_breaks": continuity_breaks,
        "position_matches": position_matches,
        "position_breaks": position_breaks,
        "missing_position_rows": missing_position_rows,
        "reconstructed_position_rows": reconstructed_position_rows,
        "samples_saved": sample_count,
        "min_len": args.min_len,
        "max_len": args.max_len,
        "hidden_dtype": args.hidden_dtype,
        "allow_missing_current_token_ids": args.allow_missing_current_token_ids,
        "reconstruct_positions_from_num_tokens": (
            args.reconstruct_positions_from_num_tokens
        ),
        "metadata_files": args.metadata,
        "metadata_request_keys": len(request_metadata),
        "samples_with_metadata": samples_with_metadata,
        "aux_rows_available": aux_rows_available,
        "aux_rows_saved": aux_rows_saved,
        "aux_bad_files": aux_bad_files,
    }
    summary_path = args.summary or os.path.join(args.out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if sample_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
