#!/usr/bin/env bash
# One-command post-chain session: v2 drafter A/B + L0 batching A/B + honest scoreboard.
# Run after lane-c-v2-chain completes (production restored by the chain).
set -u
D=/mnt/fast-ai/bench-results/muse-glimmer-30b/distill
V=/mnt/usb-models/muse-venvs/muse-distill/bin/python
echo "=== chain verdict ==="; tail -4 $D/train-v2.log
if rg -q 'IMPROVED' $D/train-v2.log; then
  echo "=== merging + converting v2 drafter ==="
  $V - <<'PY'
import torch
from transformers import AutoModel
from peft import PeftModel
base = AutoModel.from_pretrained("/mnt/fast-ai/llm-models/muse-glimmer-dflash-hf", dtype=torch.bfloat16)
m = PeftModel.from_pretrained(base, "/mnt/usb-models/muse-glimmer-30b-extra/drafter-lora-v2/best").merge_and_unload()
out="/mnt/usb-models/muse-glimmer-dflash-tuned-v2-hf"
m.save_pretrained(out)
import shutil, os
for f in os.listdir("/mnt/fast-ai/llm-models/muse-glimmer-dflash-hf"):
    if f.endswith(".json") and not os.path.exists(f"{out}/{f}"):
        shutil.copy("/mnt/fast-ai/llm-models/muse-glimmer-dflash-hf/"+f, out)
print("merged")
PY
  source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
  /home/steve/.venvs/deepseek-v4-xpu/bin/python convert_hf_to_gguf.py /mnt/usb-models/muse-glimmer-dflash-tuned-v2-hf \
    --outfile /mnt/usb-models/muse-glimmer-30b-extra/dflash-bf16-tuned-v2.gguf \
    --outtype bf16 --target-model-dir /mnt/fast-ai/llm-models/muse-glimmer-target-meta | tail -1
  echo "A/B (pause production, N4, stock vs v2, then L0 batching ladder):"
  echo "  sudo systemctl stop muse-glimmer-frontdoor.service muse-glimmer-bf16-fleet.service"
  echo "  then run servers/l0-batch-ab.sh and the stock-vs-v2 bench, then restart fleet"
else
  echo "v2 did NOT beat stock on validation - do not merge; scale corpus/objective for v3."
  echo "Still run servers/l0-batch-ab.sh in the next GPU window (independent lever)."
fi
