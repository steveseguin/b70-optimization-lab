#!/usr/bin/env python3
"""Placement table for the DSpark draft GGUF (dflash), in the format of profiles/dsv41-iq2xxs/placement.tsv.

Each tensor name gets the prefix "dsp." so the draft's weights can share one weight table with the target
(own41::load_weights): shard name comp kind offset size layer mask rank dims... with offset = the tensor's
absolute file offset (the draft's shard line in the shards list has data start 0).

  ~/.venvs/vllm-xpu/bin/python -I tools/mk_dspark_placement.py \
      /mnt/fast-ai/llm-models/DeepSeek-V4.1-Flash-1017-GGUF/dspark-DeepSeek-V4.1-Flash-1017-Q8_0.gguf \
      profiles/dspark-q8/placement.tsv
"""
import os
import sys

import gguf


def main() -> int:
    path, out = sys.argv[1], sys.argv[2]
    r = gguf.GGUFReader(path)
    shard = os.path.basename(path)
    lines = []
    for t in r.tensors:
        dims = [int(d) for d in t.shape]  # ne0 first (columns), as the target's table
        name = "dsp." + t.name
        layer = int(t.name.split(".")[1]) if t.name.startswith("blk.") else -1
        lines.append(
            f"{shard} {name} draft {int(t.tensor_type)} {int(t.data_offset)} {int(t.n_bytes)} {layer} 0 {len(dims)} "
            + " ".join(str(d) for d in dims)
        )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(lines)} tensors -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
