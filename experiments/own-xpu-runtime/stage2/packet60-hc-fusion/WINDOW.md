# Coordinator screen: packet60

Three target HC kernels per side are the accepted coordinator decision.
No device window ran during preparation. The target oracle, target weights,
full target head, BF16 state, draft/controller and topology remain packet56.

Seal after the lean CPU gates (never overwrite an existing seal):

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/screen/seal.py \
  --profile tp2 --lineage experiments/own-xpu-runtime/stage2/packet60-hc-fusion \
  --build-receipt experiments/own-xpu-runtime/stage2/packet60-hc-fusion/build-device-receipt.json \
  --fixture experiments/own-xpu-runtime/stage2/packet60-hc-fusion/integrated-fixture/receipt.json \
  --binary experiments/own-xpu-runtime/stage2/packet60-hc-fusion/build/device/own-rt-iq3 \
  --dispatch experiments/own-xpu-runtime/stage2/packet60-hc-fusion/dispatch-speed6.json \
  --output experiments/own-xpu-runtime/stage2/packet60-hc-fusion/screen-seal.json
```

CPU-only admission check; it reads seals/metadata and executes no device code.
The epoch timestamp is a parser placeholder for this plan only, not a claimed
journal review. The device command below requires the real reviewed boundary:

```bash
nice -n 19 taskset -c 8-15,24-31 python3 -B \
  experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage experiments/own-xpu-runtime/stage2/packet60-hc-fusion \
  --seal experiments/own-xpu-runtime/stage2/packet60-hc-fusion/screen-seal.json \
  --faults-reviewed-through 1970-01-01T00:00:00Z \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet60-a --plan
```

Exact candidate device command, inside the coordinator's admitted `screen-*`
systemd user unit with the settings in [the screen guide](../screen/README.md).
`REVIEWED_THROUGH` is the coordinator's real past journal review boundary for
this boot; it is not filled automatically. Use a fresh output directory.

```bash
nice -n 19 taskset -c 8-15,24-31 env -i \
  PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  python3 -B experiments/own-xpu-runtime/stage2/screen/screen.py \
  --profile tp2 --lineage experiments/own-xpu-runtime/stage2/packet60-hc-fusion \
  --seal experiments/own-xpu-runtime/stage2/packet60-hc-fusion/screen-seal.json \
  --authorized-device-window --faults-reviewed-through "$REVIEWED_THROUGH" \
  --output experiments/own-xpu-runtime/stage2/screen/evidence/packet60-a
```

The coordinator runs the matched packet56 A/B. This preparation does not run
it, start services, acquire devices, load weights, change host settings or
claim speed. A diagnostic screen never substitutes for a full qualification
chain or a submission attestation.
