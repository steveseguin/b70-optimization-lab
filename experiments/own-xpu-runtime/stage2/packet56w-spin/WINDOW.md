# Coordinator screen command

CPU preparation launches no device window or service. The coordinator owns
the A/B screen and fresh admission. Packet56w uses the screen's packet56
two-card profile and unchanged packet49 oracle: incident check, then all
12 × 128 suite tokens. A screen is diagnostic, never a record submission.

Inside the coordinator's admitted screen user unit, from the repository root,
using its approved library path and actual reviewed past fault boundary:

```bash
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage experiments/own-xpu-runtime/stage2/packet56w-spin \
  --seal experiments/own-xpu-runtime/stage2/packet56w-spin/screen-seal.json \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet56w-a
```

Append `--plan` for the CPU-only seal/oracle/command check, which creates no
window and contacts no device. Use the identical command/affinity for the
control with lineage `experiments/own-xpu-runtime/stage2/packet56-draft-prefix`,
omit `--seal` so it uses packet56's existing seal, and choose a separate output
under the screen's required evidence root, such as
`experiments/own-xpu-runtime/stage2/screen/evidence/packet56-control-for56w-a`.
Never run A and B together.
Do not reuse any output path or retry a fault automatically. The coordinator
may use the newer screen wrapper once its own validation finishes; its identity
will be retained in the screen receipt.

Both arms must use the same CPU placement/priority. This helper-core command
honors the brief's reserved-core exclusion. A GPU-core placement requires the
coordinator's allocation for both arms. Preserve the screen's existing
admission, no-restart and graceful teardown requirements; no service is started
by any preparation command in this packet.

The recorded CPU plan uses `1970-01-01T00:00:00Z` only to satisfy the required
date parser while `--plan` prevents admission/execution. It reviews or waives
no fault. The actual screen must use the coordinator's reviewed boundary.
